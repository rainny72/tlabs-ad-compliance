"""Unit tests for Upload Lambda handler."""

import json
import os
from unittest.mock import patch

import pytest

os.environ.setdefault("VIDEO_BUCKET", "test-video-bucket")

from botocore.exceptions import ClientError

from handler import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE,
    ValidationError,
    generate_s3_key,
    handler,
    validate_file_size,
    validate_filename,
)


# --- validate_filename tests ---

class TestValidateFilename:
    @pytest.mark.parametrize("ext", sorted(ALLOWED_EXTENSIONS))
    def test_allowed_extensions(self, ext):
        validate_filename(f"video.{ext}")

    @pytest.mark.parametrize("ext", sorted(ALLOWED_EXTENSIONS))
    def test_allowed_extensions_uppercase(self, ext):
        validate_filename(f"video.{ext.upper()}")

    def test_rejects_invalid_extension(self):
        with pytest.raises(ValidationError, match="Invalid file extension"):
            validate_filename("video.exe")

    def test_rejects_no_extension(self):
        with pytest.raises(ValidationError, match="Invalid file extension"):
            validate_filename("video")

    def test_rejects_empty_filename(self):
        with pytest.raises(ValidationError, match="filename is required"):
            validate_filename("")

    def test_rejects_none(self):
        with pytest.raises(ValidationError, match="filename is required"):
            validate_filename(None)


    def test_rejects_trailing_dot(self):
        with pytest.raises(ValidationError, match="Invalid file extension"):
            validate_filename("video.")


# --- validate_file_size tests ---

class TestValidateFileSize:
    def test_valid_size(self):
        validate_file_size(1024)

    def test_exact_max_size(self):
        validate_file_size(MAX_FILE_SIZE)

    def test_rejects_over_max(self):
        with pytest.raises(ValidationError, match="exceeds maximum"):
            validate_file_size(MAX_FILE_SIZE + 1)

    def test_rejects_zero(self):
        with pytest.raises(ValidationError, match="positive number"):
            validate_file_size(0)

    def test_rejects_negative(self):
        with pytest.raises(ValidationError, match="positive number"):
            validate_file_size(-100)


# --- generate_s3_key tests ---

class TestGenerateS3Key:
    def test_key_format(self):
        key = generate_s3_key("user-123", "video.mp4")
        assert key.startswith("uploads/user-123/")
        assert key.endswith("_video.mp4")

    def test_contains_timestamp(self):
        key = generate_s3_key("uid", "f.mp4")
        parts = key.split("/")
        assert len(parts) == 3
        ts_part = parts[2].split("_")[0]
        assert ts_part.isdigit()


# --- handler integration tests ---

def _make_event(body: dict, user_id: str = "test-user-id") -> dict:
    return {
        "requestContext": {"authorizer": {"claims": {"sub": user_id}}},
        "body": json.dumps(body),
    }


class TestHandler:
    @patch.dict(os.environ, {"VIDEO_BUCKET": "test-bucket"})
    @patch("handler._get_s3_client")
    def test_success(self, mock_get_s3):
        mock_s3 = mock_get_s3.return_value
        mock_s3.generate_presigned_url.return_value = "https://s3.example.com/presigned"
        event = _make_event({"filename": "clip.mp4", "contentType": "video/mp4"})
        resp = handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert "uploadUrl" in body
        assert "s3Key" in body
        assert body["s3Key"].startswith("uploads/test-user-id/")

    def test_invalid_extension_returns_400(self):
        event = _make_event({"filename": "doc.pdf"})
        resp = handler(event, None)
        assert resp["statusCode"] == 400

    def test_missing_filename_returns_400(self):
        event = _make_event({})
        resp = handler(event, None)
        assert resp["statusCode"] == 400

    def test_missing_auth_returns_500(self):
        event = {"requestContext": {}, "body": "{}"}
        resp = handler(event, None)
        assert resp["statusCode"] == 500

    def test_cors_headers_present(self):
        event = _make_event({"filename": "doc.pdf"})
        resp = handler(event, None)
        assert "Access-Control-Allow-Origin" in resp["headers"]

    @patch.dict(os.environ, {"VIDEO_BUCKET": "test-bucket"})
    @patch("handler._get_s3_client")
    def test_file_size_validation(self, mock_get_s3):
        event = _make_event({"filename": "v.mp4", "fileSize": MAX_FILE_SIZE + 1})
        resp = handler(event, None)
        assert resp["statusCode"] == 400
        assert "exceeds" in json.loads(resp["body"])["error"]

    @patch.dict(os.environ, {"VIDEO_BUCKET": "test-bucket"})
    @patch("handler._get_s3_client")
    def test_aws_throttling_returns_503(self, mock_get_s3):
        mock_s3 = mock_get_s3.return_value
        mock_s3.generate_presigned_url.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "throttled"}},
            "GeneratePresignedUrl",
        )
        event = _make_event({"filename": "v.mp4"})
        resp = handler(event, None)
        assert resp["statusCode"] == 503
