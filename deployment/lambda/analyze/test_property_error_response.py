"""Property-based test for Lambda error response format.

Feature: amplify-serverless-migration, Property 6: Lambda 에러 응답 형식

Validates: Requirements 4.7
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

# Add handler directory and shared_layer to path
_this_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_this_dir))
sys.path.insert(0, str(_this_dir.parent / "shared_layer" / "python"))

from botocore.exceptions import ClientError
from hypothesis import given, settings
from hypothesis import strategies as st

from handler import ValidationError, handler

# --- Environment setup ---

os.environ.setdefault("VIDEO_BUCKET", "test-video-bucket")
os.environ.setdefault("REPORTS_TABLE", "test-reports-table")
os.environ.setdefault("BEDROCK_REGION", "us-east-1")


# --- Helpers ---

def _make_valid_event(user_id: str = "test-user-123") -> dict:
    """Build a minimal valid API Gateway event with JWT and s3Key."""
    return {
        "requestContext": {"authorizer": {"claims": {"sub": user_id}}},
        "body": json.dumps({"s3Key": "uploads/test-user-123/12345_video.mp4", "region": "global"}),
    }


# --- Strategies ---

error_message_strategy = st.text(
    min_size=0, max_size=100, alphabet=st.characters(categories=("L", "N", "Z", "P"))
)

# ClientError codes that map to 503
throttle_codes = st.sampled_from(["ThrottlingException", "ServiceUnavailableException"])

# ClientError codes that map to 500 (non-throttle AWS errors)
other_client_error_codes = st.sampled_from([
    "AccessDenied",
    "NoSuchKey",
    "InternalError",
    "InvalidParameterValue",
    "ResourceNotFoundException",
    "ExpiredTokenException",
])

# Generic exception types (all map to 500)
generic_exception_strategy = st.one_of(
    error_message_strategy.map(lambda m: RuntimeError(m)),
    error_message_strategy.map(lambda m: TypeError(m)),
    error_message_strategy.map(lambda m: ValueError(m)),
    error_message_strategy.map(lambda m: KeyError(m)),
    error_message_strategy.map(lambda m: IOError(m)),
    error_message_strategy.map(lambda m: OSError(m)),
    error_message_strategy.map(lambda m: MemoryError()),
    error_message_strategy.map(lambda m: AttributeError(m)),
)


def _make_client_error(code: str, message: str) -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": message}},
        "TestOperation",
    )


# --- Property Test ---


@given(message=error_message_strategy)
@settings(max_examples=100)
def test_validation_error_returns_400_with_json_error(message: str):
    """Property 6 (ValidationError path): For any ValidationError message,
    the handler returns HTTP 400 with a JSON body containing an 'error' key
    and CORS headers.

    Feature: amplify-serverless-migration, Property 6: Lambda 에러 응답 형식

    **Validates: Requirements 4.7**
    """
    with patch("handler._download_video", side_effect=ValidationError(message)):
        event = _make_valid_event()
        response = handler(event, None)

    assert response["statusCode"] == 400, f"Expected 400, got {response['statusCode']}"
    body = json.loads(response["body"])
    assert "error" in body, f"Response body missing 'error' key: {body}"
    assert response["headers"]["Access-Control-Allow-Origin"] == "*"
    assert response["headers"]["Access-Control-Allow-Methods"] == "POST,OPTIONS"


@given(code=throttle_codes, message=error_message_strategy)
@settings(max_examples=100)
def test_throttle_client_error_returns_503_with_json_error(code: str, message: str):
    """Property 6 (ClientError throttle path): For any ThrottlingException or
    ServiceUnavailableException, the handler returns HTTP 503 with a JSON body
    containing an 'error' key and CORS headers.

    Feature: amplify-serverless-migration, Property 6: Lambda 에러 응답 형식

    **Validates: Requirements 4.7**
    """
    exc = _make_client_error(code, message)
    with patch("handler._download_video", side_effect=exc):
        event = _make_valid_event()
        response = handler(event, None)

    assert response["statusCode"] == 503, f"Expected 503, got {response['statusCode']}"
    body = json.loads(response["body"])
    assert "error" in body, f"Response body missing 'error' key: {body}"
    assert response["headers"]["Access-Control-Allow-Origin"] == "*"


@given(code=other_client_error_codes, message=error_message_strategy)
@settings(max_examples=100)
def test_other_client_error_returns_500_with_json_error(code: str, message: str):
    """Property 6 (ClientError non-throttle path): For any non-throttle
    ClientError, the handler returns HTTP 500 with a JSON body containing
    an 'error' key and CORS headers.

    Feature: amplify-serverless-migration, Property 6: Lambda 에러 응답 형식

    **Validates: Requirements 4.7**
    """
    exc = _make_client_error(code, message)
    with patch("handler._download_video", side_effect=exc):
        event = _make_valid_event()
        response = handler(event, None)

    assert response["statusCode"] == 500, f"Expected 500, got {response['statusCode']}"
    body = json.loads(response["body"])
    assert "error" in body, f"Response body missing 'error' key: {body}"
    assert response["headers"]["Access-Control-Allow-Origin"] == "*"


@given(exc=generic_exception_strategy)
@settings(max_examples=100)
def test_generic_exception_returns_500_with_json_error(exc: Exception):
    """Property 6 (generic Exception path): For any unexpected exception type
    and message, the handler returns HTTP 500 with a JSON body containing
    an 'error' key and CORS headers.

    Feature: amplify-serverless-migration, Property 6: Lambda 에러 응답 형식

    **Validates: Requirements 4.7**
    """
    with patch("handler._download_video", side_effect=exc):
        event = _make_valid_event()
        response = handler(event, None)

    assert response["statusCode"] == 500, f"Expected 500, got {response['statusCode']}"
    body = json.loads(response["body"])
    assert "error" in body, f"Response body missing 'error' key: {body}"
    assert response["headers"]["Access-Control-Allow-Origin"] == "*"
    assert response["headers"]["Access-Control-Allow-Methods"] == "POST,OPTIONS"
