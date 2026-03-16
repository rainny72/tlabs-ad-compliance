"""Analysis Lambda handler - video compliance analysis via Bedrock or TwelveLabs."""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from core.bedrock_client import get_bedrock_analyzer
from core.bedrock_analyzer import analyze_video_bedrock
from core.twelvelabs_client import analyze_video_twelvelabs
from core.decision import make_split_decision
from core.description_audit import audit_description
from shared.constants import Region
from shared.schemas import ComplianceReport

logger = logging.getLogger()
logger.setLevel(logging.INFO)

VALID_REGIONS = {r.value for r in Region}

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}

_s3_client = None
_dynamodb_resource = None


class ValidationError(Exception):
    """Raised when request input validation fails."""


def _get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def _get_dynamodb_table():
    global _dynamodb_resource
    if _dynamodb_resource is None:
        _dynamodb_resource = boto3.resource("dynamodb")
    return _dynamodb_resource.Table(os.environ["REPORTS_TABLE"])


def _get_user_settings(user_id: str) -> dict:
    """Read user settings from DynamoDB settings table."""
    table_name = os.environ.get("SETTINGS_TABLE")
    if not table_name:
        return {"backend": "bedrock"}
    try:
        global _dynamodb_resource
        if _dynamodb_resource is None:
            _dynamodb_resource = boto3.resource("dynamodb")
        table = _dynamodb_resource.Table(table_name)
        result = table.get_item(Key={"user_id": user_id})
        return result.get("Item", {"backend": "bedrock"})
    except Exception as e:
        logger.warning("Failed to read settings for %s: %s", user_id, e)
        return {"backend": "bedrock"}


def _build_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body, default=str),
    }


def _validate_request(body: dict) -> tuple[str, str]:
    """Validate and extract s3Key and region from request body."""
    s3_key = body.get("s3Key", "")
    if not s3_key or not isinstance(s3_key, str):
        raise ValidationError("s3Key is required")
    if not s3_key.startswith("uploads/"):
        raise ValidationError("s3Key must start with 'uploads/'")

    region = body.get("region", "global")
    if region not in VALID_REGIONS:
        raise ValidationError(
            f"Invalid region '{region}'. Allowed: {', '.join(sorted(VALID_REGIONS))}"
        )
    return s3_key, region


def _download_video(s3_key: str) -> Path:
    """Download video from S3 to /tmp/ and return the local path."""
    bucket = os.environ["VIDEO_BUCKET"]
    filename = s3_key.split("/")[-1]
    local_path = Path(f"/tmp/{filename}")
    logger.info("Downloading s3://%s/%s to %s", bucket, s3_key, local_path)
    _get_s3_client().download_file(bucket, s3_key, str(local_path))
    return local_path


def _cleanup(*paths: Path) -> None:
    """Remove temporary files."""
    for p in paths:
        try:
            if p and p.exists():
                p.unlink()
                logger.info("Cleaned up temp file: %s", p)
        except OSError as e:
            logger.warning("Failed to clean up %s: %s", p, e)


def _strip_thumbnail_stream(video_path: Path) -> Path:
    """Remove mjpeg thumbnail streams that cause Bedrock 'Unprocessable video'.

    Returns path to cleaned video, or original path if ffmpeg unavailable
    or video has no extra streams.
    """
    import subprocess

    ffmpeg = "/opt/bin/ffmpeg"
    if not Path(ffmpeg).exists():
        logger.info("ffmpeg not found at %s, skipping preprocessing", ffmpeg)
        return video_path

    clean_path = video_path.with_suffix(".clean.mp4")
    cmd = [
        ffmpeg, "-i", str(video_path),
        "-map", "0:v:0", "-map", "0:a:0?",
        "-c", "copy", "-y", str(clean_path),
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=30, check=True)
        logger.info("Preprocessed video: %s -> %s", video_path, clean_path)
        return clean_path
    except Exception as e:
        logger.warning("ffmpeg preprocessing failed: %s, using original", e)
        return video_path


def _save_report(user_id: str, report: ComplianceReport) -> None:
    """Save ComplianceReport to DynamoDB."""
    table = _get_dynamodb_table()
    item = json.loads(report.model_dump_json(), parse_float=Decimal)
    item["user_id"] = user_id
    item["analyzed_at"] = report.analyzed_at.isoformat()
    table.put_item(Item=item)
    logger.info("Saved report %s for user %s", report.video_id, user_id)


def handler(event, context):
    """Lambda handler for video compliance analysis."""
    local_path = None
    try:
        # 1. Extract user_id from JWT
        user_id = event["requestContext"]["authorizer"]["claims"]["sub"]
        logger.info("Analysis request from user: %s", user_id)

        # 2. Parse and validate request body
        body = json.loads(event.get("body", "{}") or "{}")
        s3_key, region = _validate_request(body)

        # 3. Download video from S3 to /tmp/
        local_path = _download_video(s3_key)

        # 4. Read user settings to determine backend
        settings = _get_user_settings(user_id)
        backend = settings.get("backend", "bedrock")
        logger.info("Using backend: %s", backend)

        # 5. Analyze video via selected backend
        if backend == "twelvelabs":
            api_key = settings.get("twelvelabs_api_key", "")
            if not api_key:
                return _build_response(400, {"error": "TwelveLabs API key not configured. Please set it in Settings."})
            relevance, violations, description, raw_response = analyze_video_twelvelabs(
                api_key, local_path, region=region
            )
        else:
            # Strip mjpeg thumbnail streams that cause Bedrock errors
            clean_path = _strip_thumbnail_stream(local_path)
            bedrock_region = os.environ.get("BEDROCK_REGION", "us-east-1")
            analyzer = get_bedrock_analyzer(region=bedrock_region)
            relevance, violations, description, raw_response = analyze_video_bedrock(
                analyzer, clean_path, region=region
            )

        # 6. Post-process: scan description for missed violations
        violations = audit_description(description, violations)

        # 7. 3-axis evaluation via core/decision
        region_enum = Region(region)
        decision_result = make_split_decision(
            relevance=relevance,
            violations=violations,
            region=region_enum,
            description=description,
        )

        # 8. Build ComplianceReport
        report_id = str(uuid.uuid4())
        analyzed_at = datetime.now(timezone.utc)
        video_file = s3_key.split("/")[-1]

        report = ComplianceReport(
            video_id=report_id,
            video_file=video_file,
            region=region_enum,
            description=description,
            campaign_relevance=relevance,
            policy_violations=violations,
            decision=decision_result["decision"],
            decision_reasoning=decision_result["decision_reasoning"],
            compliance=decision_result["compliance"],
            product=decision_result["product"],
            disclosure=decision_result["disclosure"],
            analyzed_at=analyzed_at,
        )

        # 9. Save to DynamoDB
        _save_report(user_id, report)

        # 10. Return result
        result = json.loads(report.model_dump_json())
        result["reportId"] = report_id
        logger.info("Analysis complete: report=%s, decision=%s", report_id, report.decision.value)
        return _build_response(200, result)

    except ValidationError as e:
        logger.warning("Validation error: %s", e)
        return _build_response(400, {"error": str(e)})
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = str(e)
        logger.error("AWS ClientError: %s", e)
        if error_code == "ValidationException" and "Unprocessable video" in error_message:
            return _build_response(400, {
                "error": "Video format not supported. Please use H.264/H.265 codec, MP4 container, and ensure duration is under 30 minutes."
            })
        if error_code in ("ThrottlingException", "ServiceUnavailableException"):
            return _build_response(503, {"error": "Service temporarily unavailable"})
        return _build_response(500, {"error": "Internal server error"})
    except Exception as e:
        logger.exception("Unexpected error during analysis")
        return _build_response(500, {"error": "Internal server error"})
    finally:
        if local_path:
            clean_path_var = local_path.with_suffix(".clean.mp4")
            _cleanup(local_path, clean_path_var)
