"""Reports Lambda handler - list and retrieve compliance reports from DynamoDB."""

import json
import logging
import os

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
}

_dynamodb_resource = None


def _get_dynamodb_table():
    """Lazy-initialize DynamoDB table resource."""
    global _dynamodb_resource
    if _dynamodb_resource is None:
        _dynamodb_resource = boto3.resource("dynamodb")
    return _dynamodb_resource.Table(os.environ["REPORTS_TABLE"])


def _build_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body, default=str),
    }


def _get_user_id(event: dict) -> str:
    """Extract user_id from JWT claims."""
    return event["requestContext"]["authorizer"]["claims"]["sub"]


def _list_reports(user_id: str) -> dict:
    """Query all reports for a user, newest first."""
    table = _get_dynamodb_table()
    response = table.query(
        KeyConditionExpression=Key("user_id").eq(user_id),
        ScanIndexForward=False,
    )
    items = response.get("Items", [])
    reports = []
    for item in items:
        reports.append({
            "reportId": item.get("video_id", ""),
            "videoFile": item.get("video_file", ""),
            "decision": item.get("decision", ""),
            "region": item.get("region", ""),
            "analyzedAt": item.get("analyzed_at", ""),
        })
    return {"reports": reports}


def _get_report(user_id: str, report_id: str) -> dict:
    """Find a specific report by report_id for the given user."""
    table = _get_dynamodb_table()
    response = table.query(
        KeyConditionExpression=Key("user_id").eq(user_id),
        ScanIndexForward=False,
    )
    items = response.get("Items", [])
    for item in items:
        if item.get("video_id") == report_id:
            return item
    return None


def handler(event, context):
    """Lambda handler for report listing and retrieval."""
    try:
        user_id = _get_user_id(event)
        path_params = event.get("pathParameters") or {}
        report_id = path_params.get("id")

        if report_id:
            # GET /reports/{id}
            logger.info("Get report %s for user %s", report_id, user_id)
            report = _get_report(user_id, report_id)
            if report is None:
                return _build_response(404, {"error": "Report not found"})
            return _build_response(200, report)
        else:
            # GET /reports
            logger.info("List reports for user %s", user_id)
            result = _list_reports(user_id)
            return _build_response(200, result)

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        logger.error("AWS ClientError: %s", e)
        if error_code in ("ThrottlingException", "ServiceUnavailableException"):
            return _build_response(503, {"error": "Service temporarily unavailable"})
        return _build_response(500, {"error": "Internal server error"})
    except Exception as e:
        logger.exception("Unexpected error in reports handler")
        return _build_response(500, {"error": "Internal server error"})
