"""Unit tests for Worker Lambda handler."""

import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

_this_dir = Path(__file__).resolve().parent
_shared_layer = str(_this_dir.parent / "shared_layer" / "python")

# Ensure venv pydantic is loaded first (Lambda layer has Linux-only binary)
import pydantic  # noqa: F401 - force venv pydantic into sys.modules first

sys.path.insert(0, str(_this_dir))
sys.path.insert(0, _shared_layer)

os.environ.setdefault("JOBS_TABLE", "test-jobs-table")
os.environ.setdefault("REPORTS_TABLE", "test-reports-table")
os.environ.setdefault("SETTINGS_TABLE", "test-settings-table")
os.environ.setdefault("VIDEO_BUCKET", "test-video-bucket")
os.environ.setdefault("BEDROCK_REGION", "us-east-1")
os.environ.setdefault("ACCOUNT_ID", "123456789012")


def _make_event(job_id="job-123", user_id="user-abc", s3_key="uploads/test.mp4", region="global"):
    return {"job_id": job_id, "user_id": user_id, "s3_key": s3_key, "region": region}


def _reset_worker_globals():
    import worker
    worker._s3_client = None
    worker._dynamodb_resource = None


# ---- _map_error_message tests (no heavy imports needed) ----

class TestMapErrorMessage:
    """Test _map_error_message maps exceptions to correct user-friendly messages."""

    def test_s3_no_such_key(self):
        from botocore.exceptions import ClientError
        from worker import _map_error_message
        err = ClientError({"Error": {"Code": "NoSuchKey", "Message": "Not found"}}, "GetObject")
        assert _map_error_message(err) == "Failed to download video file"

    def test_s3_access_denied(self):
        from botocore.exceptions import ClientError
        from worker import _map_error_message
        err = ClientError({"Error": {"Code": "AccessDenied", "Message": "Denied"}}, "GetObject")
        assert _map_error_message(err) == "Failed to download video file"

    def test_unprocessable_video(self):
        from botocore.exceptions import ClientError
        from worker import _map_error_message
        err = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Unprocessable video"}},
            "InvokeModel",
        )
        assert _map_error_message(err) == "Video format not supported. Please use H.264/H.265 codec."

    def test_throttling(self):
        from botocore.exceptions import ClientError
        from worker import _map_error_message
        err = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "InvokeModel",
        )
        assert _map_error_message(err) == "Analysis service temporarily unavailable. Please try again."

    def test_service_unavailable(self):
        from botocore.exceptions import ClientError
        from worker import _map_error_message
        err = ClientError(
            {"Error": {"Code": "ServiceUnavailableException", "Message": "Unavailable"}},
            "InvokeModel",
        )
        assert _map_error_message(err) == "Analysis service temporarily unavailable. Please try again."

    def test_twelvelabs_api_key_not_configured(self):
        from worker import _map_error_message
        err = ValueError("TwelveLabs API key not configured. Please set it in Settings.")
        assert _map_error_message(err) == "TwelveLabs API key not configured. Please set it in Settings."

    def test_timeout_error(self):
        from worker import _map_error_message
        err = TimeoutError("TwelveLabs indexing timed out")
        assert _map_error_message(err) == "Video analysis timed out. Please try again with a shorter video."

    def test_unexpected_error(self):
        from worker import _map_error_message
        err = RuntimeError("Something weird happened")
        assert _map_error_message(err) == "An unexpected error occurred during analysis."


# ---- Handler integration tests (mock heavy dependencies) ----

class TestHandlerSuccess:
    """Test worker handler success path: PROCESSING -> analysis -> COMPLETED + Reports save."""

    @patch("worker._cleanup")
    @patch("worker._save_report")
    @patch("worker.make_split_decision")
    @patch("worker.audit_description")
    @patch("worker.analyze_video_bedrock")
    @patch("worker.get_bedrock_analyzer")
    @patch("worker._strip_thumbnail_stream")
    @patch("worker._download_video")
    @patch("worker._get_user_settings")
    @patch("worker._update_job_status")
    def test_success_bedrock_sets_completed(
        self, mock_update, mock_settings, mock_download, mock_strip,
        mock_get_analyzer, mock_analyze, mock_audit, mock_decision,
        mock_save_report, mock_cleanup,
    ):
        _reset_worker_globals()
        from worker import handler
        from shared.schemas import CampaignRelevanceResult
        from shared.constants import RelevanceLabel

        mock_settings.return_value = {"backend": "bedrock"}
        mock_download.return_value = Path("/tmp/test.mp4")
        mock_strip.return_value = Path("/tmp/test.mp4")
        mock_get_analyzer.return_value = MagicMock()

        relevance = CampaignRelevanceResult(
            score=0.9, label=RelevanceLabel.ON_BRIEF,
            reasoning="Good match", search_evidence=[],
        )
        mock_analyze.return_value = (relevance, [], "Test description", {})
        mock_audit.return_value = []
        mock_decision.return_value = {
            "decision": "APPROVE",
            "decision_reasoning": "All clear",
            "compliance": {"status": "PASS"},
            "product": {"status": "CLEAR"},
            "disclosure": {"status": "PRESENT"},
        }

        handler(_make_event(), None)

        # Verify PROCESSING was set first, then COMPLETED
        calls = mock_update.call_args_list
        assert calls[0][0] == ("job-123", "PROCESSING")
        assert calls[1][0] == ("job-123", "COMPLETED")
        assert "result" in calls[1][1]

        # Verify report was saved to Reports table
        mock_save_report.assert_called_once()


class TestHandlerFailure:
    """Test worker handler failure path: sets FAILED + error message."""

    @patch("worker._cleanup")
    @patch("worker._download_video")
    @patch("worker._get_user_settings")
    @patch("worker._update_job_status")
    def test_s3_download_failure_sets_failed(
        self, mock_update, mock_settings, mock_download, mock_cleanup,
    ):
        _reset_worker_globals()
        from worker import handler
        from botocore.exceptions import ClientError

        mock_settings.return_value = {"backend": "bedrock"}
        mock_download.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}, "GetObject"
        )

        handler(_make_event(), None)

        calls = mock_update.call_args_list
        assert calls[0][0] == ("job-123", "PROCESSING")
        assert calls[1][0] == ("job-123", "FAILED")
        assert calls[1][1]["error"] == "Failed to download video file"

    @patch("worker._cleanup")
    @patch("worker._download_video")
    @patch("worker._get_user_settings")
    @patch("worker._update_job_status")
    def test_twelvelabs_no_api_key_sets_failed(
        self, mock_update, mock_settings, mock_download, mock_cleanup,
    ):
        _reset_worker_globals()
        from worker import handler

        mock_settings.return_value = {"backend": "twelvelabs", "twelvelabs_api_key": ""}
        mock_download.return_value = Path("/tmp/test.mp4")

        handler(_make_event(), None)

        calls = mock_update.call_args_list
        assert calls[0][0] == ("job-123", "PROCESSING")
        assert calls[1][0] == ("job-123", "FAILED")
        assert calls[1][1]["error"] == "TwelveLabs API key not configured. Please set it in Settings."

    @patch("worker._cleanup")
    @patch("worker.get_bedrock_analyzer")
    @patch("worker._strip_thumbnail_stream")
    @patch("worker._download_video")
    @patch("worker._get_user_settings")
    @patch("worker._update_job_status")
    def test_unexpected_error_sets_failed(
        self, mock_update, mock_settings, mock_download, mock_strip,
        mock_get_analyzer, mock_cleanup,
    ):
        _reset_worker_globals()
        from worker import handler

        mock_settings.return_value = {"backend": "bedrock"}
        mock_download.return_value = Path("/tmp/test.mp4")
        mock_strip.return_value = Path("/tmp/test.mp4")
        mock_get_analyzer.side_effect = RuntimeError("Unexpected boom")

        handler(_make_event(), None)

        calls = mock_update.call_args_list
        assert calls[0][0] == ("job-123", "PROCESSING")
        assert calls[1][0] == ("job-123", "FAILED")
        assert calls[1][1]["error"] == "An unexpected error occurred during analysis."
