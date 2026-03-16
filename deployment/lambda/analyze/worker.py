"""Worker Lambda handler - async video compliance analysis.

Invoked asynchronously by Dispatcher Lambda. Performs the actual video
analysis (Bedrock or TwelveLabs) and writes results to Jobs + Reports tables.
"""

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

_s3_client = None
_dynamodb_resource = None


def _get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def _get_dynamodb_resource():
    global _dynamodb_resource
    if _dynamodb_resource is None:
        _dynamodb_resource = boto3.resource("dynamodb")
    return _dynamodb_resource


def _get_jobs_table():
    return _get_dynamodb_resource().Table(os.environ["JOBS_TABLE"])


def _get_reports_table():
    return _get_dynamodb_resource().Table(os.environ["REPORTS_TABLE"])


def _get_user_settings(user_id: str) -> dict:
    """Read user settings from DynamoDB Settings table."""
    table_name = os.environ.get("SETTINGS_TABLE")
    if not table_name:
        return {"backend": "bedrock"}
    try:
        table = _get_dynamodb_resource().Table(table_name)
        result = table.get_item(Key={"user_id": user_id})
        return result.get("Item", {"backend": "bedrock"})
    except Exception as e:
        logger.warning("Failed to read settings for %s: %s", user_id, e)
        return {"backend": "bedrock"}


def _update_job_status(job_id: str, status: str, **extra_fields) -> None:
    """Update Jobs table record status and optional extra fields."""
    jobs_table = _get_jobs_table()
    update_expr = "SET #s = :s, updated_at = :u"
    attr_names = {"#s": "status"}
    attr_values = {
        ":s": status,
        ":u": datetime.now(timezone.utc).isoformat(),
    }
    for key, value in extra_fields.items():
        alias = f"#f_{key}"
        update_expr += f", {alias} = :{key}"
        attr_names[alias] = key
        attr_values[f":{key}"] = value

    jobs_table.update_item(
        Key={"job_id": job_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=attr_names,
        ExpressionAttributeValues=attr_values,
    )


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
    """Remove mjpeg thumbnail streams that cause Bedrock 'Unprocessable video'."""
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
    """Save ComplianceReport to Reports DynamoDB table."""
    table = _get_reports_table()
    item = json.loads(report.model_dump_json(), parse_float=Decimal)
    item["user_id"] = user_id
    item["analyzed_at"] = report.analyzed_at.isoformat()
    table.put_item(Item=item)
    logger.info("Saved report %s for user %s", report.video_id, user_id)


def _map_error_message(exc: Exception) -> str:
    """Map exceptions to user-friendly error messages per design doc."""
    msg = str(exc)

    # S3 download failure
    if isinstance(exc, ClientError):
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code in ("NoSuchKey", "NoSuchBucket", "AccessDenied"):
            return "Failed to download video file"
        if error_code == "ValidationException" and "Unprocessable video" in msg:
            return "Video format not supported. Please use H.264/H.265 codec."
        if error_code in ("ThrottlingException", "ServiceUnavailableException"):
            return "Analysis service temporarily unavailable. Please try again."

    # TwelveLabs API key not configured
    if "TwelveLabs API key not configured" in msg:
        return "TwelveLabs API key not configured. Please set it in Settings."

    # TwelveLabs indexing timeout
    if isinstance(exc, TimeoutError):
        return "Video analysis timed out. Please try again with a shorter video."

    # Bedrock service unavailable
    if "ServiceUnavailableException" in msg or "ThrottlingException" in msg:
        return "Analysis service temporarily unavailable. Please try again."

    return "An unexpected error occurred during analysis."


def handler(event, context):
    """Worker Lambda entry point.

    event payload: {job_id, user_id, s3_key, region}

    1. Jobs table status -> PROCESSING
    2. Settings table -> backend setting
    3. S3 download -> preprocess -> Bedrock/TwelveLabs analysis
    4. description_audit post-processing
    5. make_split_decision 3-axis evaluation
    6. ComplianceReport -> Reports table
    7. Jobs table status -> COMPLETED + result
    On error: Jobs table status -> FAILED + error message
    """
    job_id = event["job_id"]
    user_id = event["user_id"]
    s3_key = event["s3_key"]
    region = event["region"]
    local_path = None

    logger.info("Worker started: job=%s user=%s s3_key=%s region=%s",
                job_id, user_id, s3_key, region)

    try:
        # 1. Update status to PROCESSING
        _update_job_status(job_id, "PROCESSING")

        # 2. Read user settings for backend selection
        settings = _get_user_settings(user_id)
        backend = settings.get("backend", "bedrock")
        logger.info("Using backend: %s", backend)

        # 3. Download video from S3
        try:
            local_path = _download_video(s3_key)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("NoSuchKey", "NoSuchBucket", "AccessDenied"):
                raise
            raise

        # 4. Analyze video via selected backend
        if backend == "twelvelabs":
            api_key = settings.get("twelvelabs_api_key", "")
            if not api_key:
                raise ValueError(
                    "TwelveLabs API key not configured. Please set it in Settings."
                )
            relevance, violations, description, raw_response = (
                analyze_video_twelvelabs(api_key, local_path, region=region)
            )
        else:
            clean_path = _strip_thumbnail_stream(local_path)
            bedrock_region = os.environ.get("BEDROCK_REGION", "us-east-1")
            analyzer = get_bedrock_analyzer(region=bedrock_region)
            relevance, violations, description, raw_response = (
                analyze_video_bedrock(analyzer, clean_path, region=region)
            )

        # 5. Post-process: scan description for missed violations
        violations = audit_description(description, violations)

        # 6. 3-axis evaluation
        region_enum = Region(region)
        decision_result = make_split_decision(
            relevance=relevance,
            violations=violations,
            region=region_enum,
            description=description,
        )

        # 7. Build ComplianceReport
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

        # 8. Save to Reports table
        _save_report(user_id, report)

        # 9. Update Jobs table -> COMPLETED with result
        result_data = json.loads(report.model_dump_json())
        result_data["reportId"] = report_id
        # Convert floats to Decimal for DynamoDB
        result_for_dynamo = json.loads(
            json.dumps(result_data), parse_float=Decimal
        )

        _update_job_status(job_id, "COMPLETED", result=result_for_dynamo)
        logger.info("Worker completed: job=%s report=%s decision=%s",
                     job_id, report_id, report.decision.value)

    except Exception as exc:
        error_msg = _map_error_message(exc)
        logger.exception("Worker failed: job=%s error=%s", job_id, error_msg)
        try:
            _update_job_status(job_id, "FAILED", error=error_msg)
        except Exception:
            logger.exception("Failed to update job status to FAILED: job=%s", job_id)

    finally:
        if local_path:
            clean_path_var = local_path.with_suffix(".clean.mp4")
            _cleanup(local_path, clean_path_var)
