"""Dispatcher Lambda handler - async analysis job creation and status polling."""

import json
import logging
import os
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from shared.constants import Region

logger = logging.getLogger()
logger.setLevel(logging.INFO)

VALID_REGIONS = {r.value for r in Region}

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "POST,GET,OPTIONS",
}

_dynamodb_resource = None
_lambda_client = None


class ValidationError(Exception):
    """Raised when request input validation fails."""


def _get_dynamodb_resource():
    global _dynamodb_resource
    if _dynamodb_resource is None:
        _dynamodb_resource = boto3.resource("dynamodb")
    return _dynamodb_resource


def _get_jobs_table():
    return _get_dynamodb_resource().Table(os.environ["JOBS_TABLE"])


def _get_lambda_client():
    global _lambda_client
    if _lambda_client is None:
        _lambda_client = boto3.client("lambda")
    return _lambda_client


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


def _extract_user_id(event: dict) -> str:
    """Extract user_id from JWT claims in the API Gateway event."""
    return event["requestContext"]["authorizer"]["claims"]["sub"]


def handle_post(event: dict) -> dict:
    """Handle POST /analyze - create async analysis job."""
    try:
        # 1. Extract user_id from JWT
        user_id = _extract_user_id(event)
        logger.info("Analysis request from user: %s", user_id)

        # 2. Parse and validate request body
        body = json.loads(event.get("body", "{}") or "{}")
        s3_key, region = _validate_request(body)

        # 3. Generate job_id (UUID v4)
        job_id = str(uuid.uuid4())

        # 4. Save PENDING record to Jobs table
        now = datetime.now(timezone.utc)
        created_at = now.isoformat()
        ttl = int(now.timestamp()) + 86400

        jobs_table = _get_jobs_table()
        try:
            jobs_table.put_item(Item={
                "job_id": job_id,
                "user_id": user_id,
                "s3_key": s3_key,
                "region": region,
                "status": "PENDING",
                "created_at": created_at,
                "updated_at": created_at,
                "ttl": ttl,
            })
        except ClientError as e:
            logger.error("Failed to save job to Jobs table: %s", e)
            return _build_response(500, {"error": "Internal server error"})

        # 5. Invoke Worker Lambda asynchronously
        worker_function = os.environ["WORKER_FUNCTION_NAME"]
        payload = {
            "job_id": job_id,
            "user_id": user_id,
            "s3_key": s3_key,
            "region": region,
        }
        try:
            _get_lambda_client().invoke(
                FunctionName=worker_function,
                InvocationType="Event",
                Payload=json.dumps(payload),
            )
        except ClientError as e:
            logger.error("Failed to invoke Worker Lambda: %s", e)
            # Update job status to FAILED
            try:
                jobs_table.update_item(
                    Key={"job_id": job_id},
                    UpdateExpression="SET #s = :s, updated_at = :u",
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={
                        ":s": "FAILED",
                        ":u": datetime.now(timezone.utc).isoformat(),
                    },
                )
            except ClientError:
                logger.exception("Failed to update job status to FAILED")
            return _build_response(500, {"error": "Internal server error"})

        # 6. Return HTTP 202 with jobId
        logger.info("Job created: %s for user %s", job_id, user_id)
        return _build_response(202, {"jobId": job_id, "status": "PENDING"})

    except ValidationError as e:
        logger.warning("Validation error: %s", e)
        return _build_response(400, {"error": str(e)})
    except Exception as e:
        logger.exception("Unexpected error in handle_post")
        return _build_response(500, {"error": "Internal server error"})


def handle_get(event: dict) -> dict:
    """Handle GET /analyze/{jobId} - query job status."""
    try:
        # 1. Extract user_id from JWT
        user_id = _extract_user_id(event)

        # 2. Extract jobId from path parameters
        path_params = event.get("pathParameters") or {}
        job_id = path_params.get("jobId", "")
        if not job_id:
            return _build_response(400, {"error": "jobId is required"})

        # 3. GetItem from Jobs table
        jobs_table = _get_jobs_table()
        try:
            response = jobs_table.get_item(Key={"job_id": job_id})
        except ClientError as e:
            logger.error("Failed to query Jobs table: %s", e)
            return _build_response(500, {"error": "Internal server error"})

        item = response.get("Item")

        # 4. Record not found → 404
        if not item:
            return _build_response(404, {"error": "Job not found"})

        # 5. user_id mismatch → 404 (prevent information leakage)
        if item.get("user_id") != user_id:
            return _build_response(404, {"error": "Job not found"})

        # 6. Build response based on status
        status = item.get("status", "PENDING")
        result = {"jobId": job_id, "status": status}

        if status == "COMPLETED" and "result" in item:
            result["result"] = item["result"]
        elif status == "FAILED" and "error" in item:
            result["error"] = item["error"]

        return _build_response(200, result)

    except Exception as e:
        logger.exception("Unexpected error in handle_get")
        return _build_response(500, {"error": "Internal server error"})


def handler(event, context):
    """Lambda entry point - routes to POST or GET handler."""
    http_method = event.get("httpMethod", "")

    if http_method == "POST":
        return handle_post(event)
    if http_method == "GET":
        return handle_get(event)

    return _build_response(405, {"error": "Method not allowed"})
