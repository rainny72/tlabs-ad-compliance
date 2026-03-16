"""Unit tests for Reports Lambda handler."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("REPORTS_TABLE", "test-reports-table")

from botocore.exceptions import ClientError

from handler import (
    _build_response,
    _get_user_id,
    handler,
)


def _make_event(user_id="test-user", path_params=None):
    return {
        "requestContext": {"authorizer": {"claims": {"sub": user_id}}},
        "pathParameters": path_params,
    }


SAMPLE_ITEMS = [
    {
        "user_id": "test-user",
        "analyzed_at": "2024-01-03T00:00:00Z",
        "video_id": "report-3",
        "video_file": "c.mp4",
        "decision": "BLOCK",
        "region": "global",
    },
    {
        "user_id": "test-user",
        "analyzed_at": "2024-01-02T00:00:00Z",
        "video_id": "report-2",
        "video_file": "b.mp4",
        "decision": "REVIEW",
        "region": "north_america",
    },
    {
        "user_id": "test-user",
        "analyzed_at": "2024-01-01T00:00:00Z",
        "video_id": "report-1",
        "video_file": "a.mp4",
        "decision": "APPROVE",
        "region": "global",
    },
]


class TestBuildResponse:
    def test_includes_cors_headers(self):
        resp = _build_response(200, {"ok": True})
        assert "Access-Control-Allow-Origin" in resp["headers"]

    def test_json_body(self):
        resp = _build_response(200, {"key": "value"})
        assert json.loads(resp["body"]) == {"key": "value"}


class TestGetUserId:
    def test_extracts_sub(self):
        event = _make_event("user-abc")
        assert _get_user_id(event) == "user-abc"


class TestListReports:
    @patch("handler._get_dynamodb_table")
    def test_returns_reports_list(self, mock_table_fn):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": SAMPLE_ITEMS}
        mock_table_fn.return_value = mock_table

        event = _make_event("test-user")
        resp = handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert "reports" in body
        assert len(body["reports"]) == 3
        assert body["reports"][0]["reportId"] == "report-3"

    @patch("handler._get_dynamodb_table")
    def test_empty_reports(self, mock_table_fn):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": []}
        mock_table_fn.return_value = mock_table

        event = _make_event("test-user")
        resp = handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["reports"] == []


class TestGetReport:
    @patch("handler._get_dynamodb_table")
    def test_returns_single_report(self, mock_table_fn):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": SAMPLE_ITEMS}
        mock_table_fn.return_value = mock_table

        event = _make_event("test-user", {"id": "report-2"})
        resp = handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["video_id"] == "report-2"
        assert body["video_file"] == "b.mp4"

    @patch("handler._get_dynamodb_table")
    def test_not_found_returns_404(self, mock_table_fn):
        mock_table = MagicMock()
        mock_table.query.return_value = {"Items": SAMPLE_ITEMS}
        mock_table_fn.return_value = mock_table

        event = _make_event("test-user", {"id": "nonexistent"})
        resp = handler(event, None)
        assert resp["statusCode"] == 404
        assert "not found" in json.loads(resp["body"])["error"].lower()


class TestErrorHandling:
    @patch("handler._get_dynamodb_table")
    def test_throttling_returns_503(self, mock_table_fn):
        mock_table = MagicMock()
        mock_table.query.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "throttled"}},
            "Query",
        )
        mock_table_fn.return_value = mock_table

        event = _make_event("test-user")
        resp = handler(event, None)
        assert resp["statusCode"] == 503

    @patch("handler._get_dynamodb_table")
    def test_client_error_returns_500(self, mock_table_fn):
        mock_table = MagicMock()
        mock_table.query.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "err"}},
            "Query",
        )
        mock_table_fn.return_value = mock_table

        event = _make_event("test-user")
        resp = handler(event, None)
        assert resp["statusCode"] == 500

    def test_missing_auth_returns_500(self):
        event = {"requestContext": {}, "pathParameters": None}
        resp = handler(event, None)
        assert resp["statusCode"] == 500

    @patch("handler._get_dynamodb_table")
    def test_unexpected_error_returns_500(self, mock_table_fn):
        mock_table_fn.side_effect = RuntimeError("boom")

        event = _make_event("test-user")
        resp = handler(event, None)
        assert resp["statusCode"] == 500
