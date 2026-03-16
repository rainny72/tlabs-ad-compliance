"""Unit tests for the Analysis Lambda handler."""

import json
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add shared_layer to path so core/shared/prompts are importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared_layer" / "python"))

from handler import (
    ValidationError,
    _build_response,
    _cleanup,
    _validate_request,
    handler,
)


# --- Fixtures ---

@pytest.fixture(autouse=True)
def _env_vars(monkeypatch):
    monkeypatch.setenv("VIDEO_BUCKET", "test-video-bucket")
    monkeypatch.setenv("REPORTS_TABLE", "test-reports-table")
    monkeypatch.setenv("BEDROCK_REGION", "us-east-1")


def _make_event(body: dict, user_id: str = "user-123") -> dict:
    return {
        "requestContext": {"authorizer": {"claims": {"sub": user_id}}},
        "body": json.dumps(body),
    }


# --- _build_response tests ---

class TestBuildResponse:
    def test_includes_cors_headers(self):
        resp = _build_response(200, {"ok": True})
        assert resp["statusCode"] == 200
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"
        assert json.loads(resp["body"]) == {"ok": True}

    def test_error_response(self):
        resp = _build_response(400, {"error": "bad"})
        assert resp["statusCode"] == 400
        assert json.loads(resp["body"])["error"] == "bad"


# --- _validate_request tests ---

class TestValidateRequest:
    def test_valid_request(self):
        s3_key, region = _validate_request({"s3Key": "uploads/u1/123_v.mp4", "region": "global"})
        assert s3_key == "uploads/u1/123_v.mp4"
        assert region == "global"

    def test_missing_s3key(self):
        with pytest.raises(ValidationError, match="s3Key is required"):
            _validate_request({"region": "global"})

    def test_invalid_s3key_prefix(self):
        with pytest.raises(ValidationError, match="must start with"):
            _validate_request({"s3Key": "other/path.mp4"})

    def test_invalid_region(self):
        with pytest.raises(ValidationError, match="Invalid region"):
            _validate_request({"s3Key": "uploads/u/f.mp4", "region": "mars"})

    def test_default_region(self):
        _, region = _validate_request({"s3Key": "uploads/u/f.mp4"})
        assert region == "global"

    def test_all_valid_regions(self):
        for r in ("global", "north_america", "western_europe", "east_asia"):
            _, region = _validate_request({"s3Key": "uploads/u/f.mp4", "region": r})
            assert region == r


# --- _cleanup tests ---

class TestCleanup:
    def test_removes_existing_file(self, tmp_path):
        f = tmp_path / "video.mp4"
        f.write_text("data")
        _cleanup(f)
        assert not f.exists()

    def test_no_error_on_missing_file(self, tmp_path):
        f = tmp_path / "nonexistent.mp4"
        _cleanup(f)  # should not raise


# --- handler integration tests ---

class TestHandler:
    def test_validation_error_returns_400(self):
        event = _make_event({"region": "global"})  # missing s3Key
        resp = handler(event, None)
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert "error" in body

    def test_missing_jwt_returns_500(self):
        event = {"requestContext": {}, "body": json.dumps({"s3Key": "uploads/u/f.mp4"})}
        resp = handler(event, None)
        assert resp["statusCode"] == 500

    @patch("handler._get_dynamodb_table")
    @patch("handler.make_split_decision")
    @patch("handler.analyze_video_bedrock")
    @patch("handler.get_bedrock_analyzer")
    @patch("handler._download_video")
    def test_successful_analysis(
        self, mock_download, mock_get_analyzer, mock_analyze, mock_decision, mock_table
    ):
        from shared.constants import Decision, RelevanceLabel, Severity, PolicyCategory
        from shared.schemas import CampaignRelevanceResult, PolicyViolationResult

        tmp_file = Path("/tmp/test_video.mp4")
        mock_download.return_value = tmp_file

        mock_analyzer = MagicMock()
        mock_get_analyzer.return_value = mock_analyzer

        relevance = CampaignRelevanceResult(
            score=0.9, label=RelevanceLabel.ON_BRIEF,
            product_visible=True, reasoning="Product visible", search_evidence=[],
        )
        violations = []
        mock_analyze.return_value = (relevance, violations, "Test description", {})

        mock_decision.return_value = {
            "decision": Decision.APPROVE,
            "decision_reasoning": "All clear",
            "compliance": {"status": "PASS", "severity": "none", "reasoning": "No issues", "details": []},
            "product": {"status": "ON_BRIEF", "reasoning": "Product visible"},
            "disclosure": {"status": "PRESENT", "reasoning": "Disclosure present"},
        }

        mock_dynamo = MagicMock()
        mock_table.return_value = mock_dynamo

        event = _make_event({"s3Key": "uploads/user-123/123_video.mp4", "region": "global"})

        with patch("handler._cleanup"):
            resp = handler(event, None)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["decision"] == "APPROVE"
        assert "reportId" in body
        mock_dynamo.put_item.assert_called_once()

    @patch("handler._download_video")
    def test_client_error_throttling_returns_503(self, mock_download):
        from botocore.exceptions import ClientError

        mock_download.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "GetObject",
        )
        event = _make_event({"s3Key": "uploads/u/f.mp4", "region": "global"})
        resp = handler(event, None)
        assert resp["statusCode"] == 503

    @patch("handler._download_video")
    def test_client_error_other_returns_500(self, mock_download):
        from botocore.exceptions import ClientError

        mock_download.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Denied"}},
            "GetObject",
        )
        event = _make_event({"s3Key": "uploads/u/f.mp4", "region": "global"})
        resp = handler(event, None)
        assert resp["statusCode"] == 500

    @patch("handler._download_video")
    def test_unexpected_error_returns_500(self, mock_download):
        mock_download.side_effect = RuntimeError("boom")
        event = _make_event({"s3Key": "uploads/u/f.mp4", "region": "global"})
        resp = handler(event, None)
        assert resp["statusCode"] == 500
        body = json.loads(resp["body"])
        assert body["error"] == "Internal server error"
