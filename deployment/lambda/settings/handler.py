"""Settings Lambda handler - user preferences (backend, API keys)."""

import json
import logging
import os

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,PUT,OPTIONS",
}

ALLOWED_BACKENDS = {"bedrock", "twelvelabs"}

_table = None


def _get_table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(os.environ["SETTINGS_TABLE"])
    return _table


def _resp(code: int, body: dict) -> dict:
    return {"statusCode": code, "headers": CORS_HEADERS, "body": json.dumps(body)}


def handler(event, context):
    """GET /settings → read, PUT /settings → upsert."""
    try:
        user_id = event["requestContext"]["authorizer"]["claims"]["sub"]
        method = event["httpMethod"]

        if method == "GET":
            result = _get_table().get_item(Key={"user_id": user_id})
            item = result.get("Item", {})
            return _resp(200, {
                "backend": item.get("backend", "bedrock"),
                "twelvelabsApiKey": item.get("twelvelabs_api_key", ""),
                "bedrockRegion": item.get("bedrock_region", "us-east-1"),
            })

        if method == "PUT":
            body = json.loads(event.get("body", "{}") or "{}")
            backend = body.get("backend", "bedrock")
            if backend not in ALLOWED_BACKENDS:
                return _resp(400, {"error": f"Invalid backend: {backend}"})

            item = {
                "user_id": user_id,
                "backend": backend,
                "bedrock_region": body.get("bedrockRegion", "us-east-1"),
            }
            api_key = body.get("twelvelabsApiKey", "")
            if api_key:
                item["twelvelabs_api_key"] = api_key

            _get_table().put_item(Item=item)
            logger.info("Settings saved for user %s, backend=%s", user_id, backend)
            return _resp(200, {"message": "Settings saved"})

        return _resp(405, {"error": "Method not allowed"})
    except Exception as e:
        logger.exception("Settings error")
        return _resp(500, {"error": "Internal server error"})
