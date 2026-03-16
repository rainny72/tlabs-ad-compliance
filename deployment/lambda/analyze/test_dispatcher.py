"""Unit tests for the Dispatcher Lambda handler - POST /analyze."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

# Add shared_layer to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared_layer" / "python"))

from dispatcher import (
    ValidationError,
    _build_response,
    _validate_request,
    handle_get,
    handle_post,
    handler,
)


@pytest.fixture(autouse=True)
def _env_vars(monkeypatch):
    monkeypatch.setenv("JOBS_TABLE", "test-jobs-table")
    monkeypatch.setenv("WORKER_FUNCTION_NAME", "test-worker-fn")
    monkeypatch.setenv("VIDEO_BUCKET", "test-video-bucket")


@pytest.fixture(autouse=True)
def _reset_globals():
    """Reset module-level cached clients between tests."""
    import dispatcher
    dispatcher._dynamodb_resource = None
    dispatcher._lambda_client = None
    yield
    dispatcher._dynamodb_resource = None
    dispatcher._lambda_client = None


def _make_event(body: dict, user_id: str = "user-123", method: str = "POST") -> dict:
    return {
        "httpMethod": method,
        "requestContext": {"authorizer": {"claims": {"sub": user_id}}},
        "body": json.dumps(body),
    }


def _make_get_event(job_id: str, user_id: str = "user-123") -> dict:
    return {
        "httpMethod": "GET",
        "requestContext": {"authorizer": {"claims": {"sub": user_id}}},
        "pathParameters": {"jobId": job_id},
    }


class TestBuildResponse:
    def test_includes_cors_headers(self):
        resp = _build_response(200, {"ok": True})
        assert resp["statusCode"] == 200
        assert resp["headers"]["Access-Control-Allow-Origin"] == "*"
        assert json.loads(resp["body"]) == {"ok": True}

    def test_status_code_preserved(self):
        resp = _build_response(202, {"jobId": "abc"})
        assert resp["statusCode"] == 202


class TestValidateRequest:
    def test_valid_request(self):
        s3_key, region = _validate_request({"s3Key": "uploads/u1/v.mp4", "region": "global"})
        assert s3_key == "uploads/u1/v.mp4"
        assert region == "global"

    def test_missing_s3key(self):
        with pytest.raises(ValidationError, match="s3Key is required"):
            _validate_request({"region": "global"})

    def test_empty_s3key(self):
        with pytest.raises(ValidationError, match="s3Key is required"):
            _validate_request({"s3Key": "", "region": "global"})

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


class TestHandlePost:
    @patch("dispatcher._get_lambda_client")
    @patch("dispatcher._get_jobs_table")
    def test_successful_job_creation(self, mock_get_table, mock_get_lambda):
        mock_table = MagicMock()
        mock_get_table.return_value = mock_table
        mock_lambda = MagicMock()
        mock_get_lambda.return_value = mock_lambda

        event = _make_event({"s3Key": "uploads/u1/video.mp4", "region": "global"})
        resp = handle_post(event)

        assert resp["statusCode"] == 202
        body = json.loads(resp["body"])
        assert "jobId" in body
        assert body["status"] == "PENDING"
        mock_table.put_item.assert_called_once()
        mock_lambda.invoke.assert_called_once()

        # Verify put_item fields
        put_item_args = mock_table.put_item.call_args
        item = put_item_args[1]["Item"] if "Item" in put_item_args[1] else put_item_args[0][0]
        assert item["user_id"] == "user-123"
        assert item["s3_key"] == "uploads/u1/video.mp4"
        assert item["region"] == "global"
        assert item["status"] == "PENDING"
        assert "created_at" in item
        assert "ttl" in item
        assert isinstance(item["ttl"], int)


    @patch("dispatcher._get_lambda_client")
    @patch("dispatcher._get_jobs_table")
    def test_worker_invoke_payload(self, mock_get_table, mock_get_lambda):
        mock_table = MagicMock()
        mock_get_table.return_value = mock_table
        mock_lambda = MagicMock()
        mock_get_lambda.return_value = mock_lambda

        event = _make_event({"s3Key": "uploads/u1/video.mp4", "region": "east_asia"}, user_id="test-user")
        resp = handle_post(event)

        assert resp["statusCode"] == 202
        invoke_args = mock_lambda.invoke.call_args
        assert invoke_args[1]["FunctionName"] == "test-worker-fn"
        assert invoke_args[1]["InvocationType"] == "Event"
        payload = json.loads(invoke_args[1]["Payload"])
        assert payload["user_id"] == "test-user"
        assert payload["s3_key"] == "uploads/u1/video.mp4"
        assert payload["region"] == "east_asia"
        assert "job_id" in payload

    def test_validation_error_returns_400(self):
        event = _make_event({"region": "global"})  # missing s3Key
        resp = handle_post(event)
        assert resp["statusCode"] == 400
        body = json.loads(resp["body"])
        assert "error" in body

    @patch("dispatcher._get_jobs_table")
    def test_jobs_table_error_returns_500(self, mock_get_table):
        mock_table = MagicMock()
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "DDB error"}}, "PutItem"
        )
        mock_get_table.return_value = mock_table

        event = _make_event({"s3Key": "uploads/u/f.mp4", "region": "global"})
        resp = handle_post(event)
        assert resp["statusCode"] == 500

    @patch("dispatcher._get_lambda_client")
    @patch("dispatcher._get_jobs_table")
    def test_worker_invoke_failure_updates_status_to_failed(self, mock_get_table, mock_get_lambda):
        mock_table = MagicMock()
        mock_get_table.return_value = mock_table
        mock_lambda = MagicMock()
        mock_lambda.invoke.side_effect = ClientError(
            {"Error": {"Code": "ServiceException", "Message": "Lambda error"}}, "Invoke"
        )
        mock_get_lambda.return_value = mock_lambda

        event = _make_event({"s3Key": "uploads/u/f.mp4", "region": "global"})
        resp = handle_post(event)

        assert resp["statusCode"] == 500
        # Verify status was updated to FAILED
        mock_table.update_item.assert_called_once()
        update_args = mock_table.update_item.call_args
        assert update_args[1]["ExpressionAttributeValues"][":s"] == "FAILED"


class TestHandler:
    @patch("dispatcher.handle_post")
    def test_routes_post_to_handle_post(self, mock_handle_post):
        mock_handle_post.return_value = _build_response(202, {"jobId": "abc"})
        event = _make_event({"s3Key": "uploads/u/f.mp4"}, method="POST")
        resp = handler(event, None)
        assert resp["statusCode"] == 202
        mock_handle_post.assert_called_once()

    @patch("dispatcher.handle_get")
    def test_routes_get_to_handle_get(self, mock_handle_get):
        mock_handle_get.return_value = _build_response(200, {"jobId": "abc", "status": "PENDING"})
        event = _make_get_event("abc")
        resp = handler(event, None)
        assert resp["statusCode"] == 200
        mock_handle_get.assert_called_once()

    def test_unsupported_method_returns_405(self):
        event = _make_event({}, method="DELETE")
        resp = handler(event, None)
        assert resp["statusCode"] == 405

    def test_missing_jwt_returns_500(self):
        event = {"httpMethod": "POST", "requestContext": {}, "body": json.dumps({"s3Key": "uploads/u/f.mp4"})}
        resp = handler(event, None)
        assert resp["statusCode"] == 500


class TestHandleGet:
    @patch("dispatcher._get_jobs_table")
    def test_returns_pending_status(self, mock_get_table):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {"job_id": "job-1", "user_id": "user-123", "status": "PENDING"}
        }
        mock_get_table.return_value = mock_table

        event = _make_get_event("job-1")
        resp = handle_get(event)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["jobId"] == "job-1"
        assert body["status"] == "PENDING"
        assert "result" not in body
        assert "error" not in body

    @patch("dispatcher._get_jobs_table")
    def test_returns_processing_status(self, mock_get_table):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {"job_id": "job-1", "user_id": "user-123", "status": "PROCESSING"}
        }
        mock_get_table.return_value = mock_table

        event = _make_get_event("job-1")
        resp = handle_get(event)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["status"] == "PROCESSING"
        assert "result" not in body
        assert "error" not in body

    @patch("dispatcher._get_jobs_table")
    def test_returns_completed_with_result(self, mock_get_table):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "job_id": "job-1",
                "user_id": "user-123",
                "status": "COMPLETED",
                "result": {"decision": "APPROVE", "description": "Clean ad"},
            }
        }
        mock_get_table.return_value = mock_table

        event = _make_get_event("job-1")
        resp = handle_get(event)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["status"] == "COMPLETED"
        assert body["result"]["decision"] == "APPROVE"
        assert "error" not in body

    @patch("dispatcher._get_jobs_table")
    def test_returns_failed_with_error(self, mock_get_table):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {
                "job_id": "job-1",
                "user_id": "user-123",
                "status": "FAILED",
                "error": "Video format not supported.",
            }
        }
        mock_get_table.return_value = mock_table

        event = _make_get_event("job-1")
        resp = handle_get(event)

        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["status"] == "FAILED"
        assert body["error"] == "Video format not supported."
        assert "result" not in body

    @patch("dispatcher._get_jobs_table")
    def test_returns_404_when_job_not_found(self, mock_get_table):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}  # No Item
        mock_get_table.return_value = mock_table

        event = _make_get_event("nonexistent-job")
        resp = handle_get(event)

        assert resp["statusCode"] == 404
        body = json.loads(resp["body"])
        assert body["error"] == "Job not found"

    @patch("dispatcher._get_jobs_table")
    def test_returns_404_when_user_id_mismatch(self, mock_get_table):
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {"job_id": "job-1", "user_id": "other-user", "status": "COMPLETED"}
        }
        mock_get_table.return_value = mock_table

        event = _make_get_event("job-1", user_id="user-123")
        resp = handle_get(event)

        assert resp["statusCode"] == 404
        body = json.loads(resp["body"])
        assert body["error"] == "Job not found"

    @patch("dispatcher._get_jobs_table")
    def test_returns_500_on_dynamodb_error(self, mock_get_table):
        mock_table = MagicMock()
        mock_table.get_item.side_effect = ClientError(
            {"Error": {"Code": "InternalError", "Message": "DDB error"}}, "GetItem"
        )
        mock_get_table.return_value = mock_table

        event = _make_get_event("job-1")
        resp = handle_get(event)

        assert resp["statusCode"] == 500
