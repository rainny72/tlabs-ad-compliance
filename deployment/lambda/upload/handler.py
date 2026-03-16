"""Upload Lambda handler - generates S3 presigned URLs for video uploads."""

import json
import logging
import os
import time

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ALLOWED_EXTENSIONS = {"mp4", "mov", "avi", "mkv"}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "POST,OPTIONS",
}

def _get_s3_client():
    """Lazy-initialize S3 client with regional endpoint for proper CORS support."""
    global _s3_client
    if _s3_client is None:
        region = os.environ.get("AWS_REGION", "ap-northeast-2")
        _s3_client = boto3.client(
            "s3",
            region_name=region,
            config=BotoConfig(s3={"addressing_style": "virtual"}, signature_version="s3v4"),
        )
    return _s3_client


_s3_client = None


class ValidationError(Exception):
    """Raised when request input validation fails."""


def _build_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body),
    }


def validate_filename(filename: str) -> None:
    """Validate that the filename has an allowed extension."""
    if not filename or not isinstance(filename, str):
        raise ValidationError("filename is required")
    dot_index = filename.rfind(".")
    if dot_index == -1 or dot_index == len(filename) - 1:
        raise ValidationError(
            f"Invalid file extension. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    ext = filename[dot_index + 1 :].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"Invalid file extension '.{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )


def validate_file_size(file_size: int) -> None:
    """Validate that the file size is within the allowed limit."""
    if not isinstance(file_size, (int, float)) or file_size <= 0:
        raise ValidationError("fileSize must be a positive number")
    if file_size > MAX_FILE_SIZE:
        raise ValidationError(
            f"File size {file_size} bytes exceeds maximum allowed size of {MAX_FILE_SIZE} bytes (25MB)"
        )


def generate_s3_key(user_id: str, filename: str) -> str:
    """Generate S3 object key in the format uploads/{user_id}/{timestamp}_{filename}."""
    timestamp = int(time.time())
    return f"uploads/{user_id}/{timestamp}_{filename}"


def handler(event, context):
    """Lambda handler for generating S3 presigned upload URLs."""
    try:
        # Extract user_id from JWT claims
        user_id = event["requestContext"]["authorizer"]["claims"]["sub"]

        # Parse request body
        body = json.loads(event.get("body", "{}") or "{}")
        filename = body.get("filename", "")
        content_type = body.get("contentType", "application/octet-stream")
        file_size = body.get("fileSize", 0)

        # Validate inputs
        validate_filename(filename)
        if file_size:
            validate_file_size(file_size)

        # Generate S3 key and presigned URL
        bucket_name = os.environ["VIDEO_BUCKET"]
        s3_key = generate_s3_key(user_id, filename)

        upload_url = _get_s3_client().generate_presigned_url(
            "put_object",
            Params={
                "Bucket": bucket_name,
                "Key": s3_key,
                "ContentType": content_type,
            },
            ExpiresIn=900,
            HttpMethod="PUT",
        )

        logger.info("Generated presigned URL for user=%s, key=%s", user_id, s3_key)
        return _build_response(200, {"uploadUrl": upload_url, "s3Key": s3_key})

    except ValidationError as e:
        logger.warning("Validation error: %s", e)
        return _build_response(400, {"error": str(e)})
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        logger.error("AWS error: %s", e)
        if error_code in ("ThrottlingException", "ServiceUnavailableException"):
            return _build_response(503, {"error": "Service temporarily unavailable"})
        return _build_response(500, {"error": "Internal server error"})
    except Exception as e:
        logger.exception("Unexpected error")
        return _build_response(500, {"error": "Internal server error"})
