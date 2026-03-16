"""Property-based test for Worker Lambda - state transition correctness.

Feature: async-analysis, Property 3: Worker 상태 전이 정확성

Validates: Requirements 2.1, 2.2, 2.4
"""

import json
import os
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch, call

_this_dir = Path(__file__).resolve().parent
_shared_layer = str(_this_dir.parent / "shared_layer" / "python")

# Remove shared_layer from sys.path if present (avoids pydantic_core binary conflict)
sys.path = [p for p in sys.path if "shared_layer" not in p]

# Pre-import pydantic from venv BEFORE adding shared_layer to sys.path
# This prevents shared_layer's incompatible pydantic_core binary from loading
import pydantic  # noqa: F401
import pydantic_core  # noqa: F401

# Now insert shared_layer at front so shared_layer/core (with twelvelabs_client)
# takes priority over root-level core/ (which lacks it)
sys.path.insert(0, _shared_layer)
sys.path.insert(0, str(_this_dir))

os.environ.setdefault("JOBS_TABLE", "test-jobs-table")
os.environ.setdefault("REPORTS_TABLE", "test-reports-table")
os.environ.setdefault("SETTINGS_TABLE", "test-settings-table")
os.environ.setdefault("VIDEO_BUCKET", "test-video-bucket")
os.environ.setdefault("BEDROCK_REGION", "us-east-1")
os.environ.setdefault("ACCOUNT_ID", "123456789012")

from hypothesis import given, settings
from hypothesis import strategies as st

from shared.schemas import CampaignRelevanceResult
from shared.constants import RelevanceLabel

# --- Strategies ---

job_id_strategy = st.uuids().map(str)

user_id_strategy = st.text(
    min_size=1, max_size=100,
    alphabet=st.characters(categories=("L", "N"), exclude_characters="\x00"),
)

s3_key_strategy = st.text(
    min_size=1, max_size=100,
    alphabet=st.characters(categories=("L", "N"), exclude_characters="\x00"),
).map(lambda s: f"uploads/{s}.mp4")

region_strategy = st.sampled_from(["global", "north_america", "western_europe", "east_asia"])

# Exception strategies for failure path
exception_strategy = st.sampled_from([
    RuntimeError("Unexpected boom"),
    ValueError("Some validation error"),
    ConnectionError("Network failure"),
    OSError("File system error"),
    TypeError("Type mismatch"),
])


def _reset_worker_globals():
    import worker
    worker._s3_client = None
    worker._dynamodb_resource = None


def _make_event(job_id: str, user_id: str, s3_key: str, region: str) -> dict:
    return {"job_id": job_id, "user_id": user_id, "s3_key": s3_key, "region": region}


def _build_success_mocks():
    """Build mock return values for a successful analysis pipeline."""
    relevance = CampaignRelevanceResult(
        score=0.9, label=RelevanceLabel.ON_BRIEF,
        reasoning="Good match", search_evidence=[],
    )
    analysis_result = (relevance, [], "Test description", {})
    decision_result = {
        "decision": "APPROVE",
        "decision_reasoning": "All clear",
        "compliance": {"status": "PASS"},
        "product": {"status": "CLEAR"},
        "disclosure": {"status": "PRESENT"},
    }
    return analysis_result, decision_result


# --- Property 3 Test: Success Path ---


@given(
    job_id=job_id_strategy,
    user_id=user_id_strategy,
    s3_key=s3_key_strategy,
    region=region_strategy,
)
@settings(max_examples=100, deadline=None)
def test_worker_success_transitions_processing_then_completed(
    job_id: str, user_id: str, s3_key: str, region: str,
):
    """Property 3 (Success): For any job, Worker starts by setting status to
    PROCESSING, and on success sets COMPLETED with result field.

    Feature: async-analysis, Property 3: Worker 상태 전이 정확성

    **Validates: Requirements 2.1, 2.2, 2.4**
    """
    _reset_worker_globals()
    from worker import handler

    analysis_result, decision_result = _build_success_mocks()

    mock_update = MagicMock()
    mock_settings = MagicMock(return_value={"backend": "bedrock"})
    mock_download = MagicMock(return_value=Path("/tmp/test.mp4"))
    mock_strip = MagicMock(return_value=Path("/tmp/test.mp4"))
    mock_get_analyzer = MagicMock(return_value=MagicMock())
    mock_analyze = MagicMock(return_value=analysis_result)
    mock_audit = MagicMock(return_value=[])
    mock_decision = MagicMock(return_value=decision_result)
    mock_save_report = MagicMock()
    mock_cleanup = MagicMock()

    with patch("worker._update_job_status", mock_update), \
         patch("worker._get_user_settings", mock_settings), \
         patch("worker._download_video", mock_download), \
         patch("worker._strip_thumbnail_stream", mock_strip), \
         patch("worker.get_bedrock_analyzer", mock_get_analyzer), \
         patch("worker.analyze_video_bedrock", mock_analyze), \
         patch("worker.audit_description", mock_audit), \
         patch("worker.make_split_decision", mock_decision), \
         patch("worker._save_report", mock_save_report), \
         patch("worker._cleanup", mock_cleanup):

        event = _make_event(job_id, user_id, s3_key, region)
        handler(event, None)

    # _update_job_status must be called at least twice
    calls = mock_update.call_args_list
    assert len(calls) >= 2, (
        f"Expected at least 2 _update_job_status calls, got {len(calls)}"
    )

    # First call: PROCESSING
    assert calls[0][0] == (job_id, "PROCESSING"), (
        f"First call should be (job_id, 'PROCESSING'), got {calls[0][0]}"
    )

    # Second call: COMPLETED with result field
    assert calls[1][0] == (job_id, "COMPLETED"), (
        f"Second call should be (job_id, 'COMPLETED'), got {calls[1][0]}"
    )
    assert "result" in calls[1][1], (
        f"COMPLETED call should include 'result' kwarg, got kwargs: {calls[1][1]}"
    )


# --- Property 3 Test: Failure Path ---


@given(
    job_id=job_id_strategy,
    user_id=user_id_strategy,
    s3_key=s3_key_strategy,
    region=region_strategy,
    exc=exception_strategy,
)
@settings(max_examples=100, deadline=None)
def test_worker_failure_transitions_processing_then_failed(
    job_id: str, user_id: str, s3_key: str, region: str, exc: Exception,
):
    """Property 3 (Failure): For any job, Worker starts by setting status to
    PROCESSING, and on exception sets FAILED with error field.

    Feature: async-analysis, Property 3: Worker 상태 전이 정확성

    **Validates: Requirements 2.1, 2.2, 2.4**
    """
    _reset_worker_globals()
    from worker import handler

    mock_update = MagicMock()
    mock_settings = MagicMock(return_value={"backend": "bedrock"})
    mock_download = MagicMock(return_value=Path("/tmp/test.mp4"))
    mock_strip = MagicMock(return_value=Path("/tmp/test.mp4"))
    # get_bedrock_analyzer raises the exception to trigger failure path
    mock_get_analyzer = MagicMock(side_effect=exc)
    mock_cleanup = MagicMock()

    with patch("worker._update_job_status", mock_update), \
         patch("worker._get_user_settings", mock_settings), \
         patch("worker._download_video", mock_download), \
         patch("worker._strip_thumbnail_stream", mock_strip), \
         patch("worker.get_bedrock_analyzer", mock_get_analyzer), \
         patch("worker._cleanup", mock_cleanup):

        event = _make_event(job_id, user_id, s3_key, region)
        handler(event, None)

    # _update_job_status must be called at least twice
    calls = mock_update.call_args_list
    assert len(calls) >= 2, (
        f"Expected at least 2 _update_job_status calls, got {len(calls)}"
    )

    # First call: PROCESSING
    assert calls[0][0] == (job_id, "PROCESSING"), (
        f"First call should be (job_id, 'PROCESSING'), got {calls[0][0]}"
    )

    # Second call: FAILED with error field
    assert calls[1][0] == (job_id, "FAILED"), (
        f"Second call should be (job_id, 'FAILED'), got {calls[1][0]}"
    )
    assert "error" in calls[1][1], (
        f"FAILED call should include 'error' kwarg, got kwargs: {calls[1][1]}"
    )
    # error should be a non-empty string
    error_val = calls[1][1]["error"]
    assert isinstance(error_val, str) and len(error_val) > 0, (
        f"error should be a non-empty string, got: {error_val!r}"
    )


# --- Property 4 Test: Worker 성공 시 이중 저장 ---


@given(
    job_id=job_id_strategy,
    user_id=user_id_strategy,
    s3_key=s3_key_strategy,
    region=region_strategy,
)
@settings(max_examples=100, deadline=None)
def test_worker_success_saves_to_both_jobs_and_reports(
    job_id: str, user_id: str, s3_key: str, region: str,
):
    """Property 4: For any successfully completed analysis job, Worker saves
    the ComplianceReport data to both Jobs table (result field) and Reports table.

    Feature: async-analysis, Property 4: Worker 성공 시 이중 저장

    **Validates: Requirements 2.2, 2.3**
    """
    _reset_worker_globals()
    from worker import handler

    analysis_result, decision_result = _build_success_mocks()

    mock_update = MagicMock()
    mock_settings = MagicMock(return_value={"backend": "bedrock"})
    mock_download = MagicMock(return_value=Path("/tmp/test.mp4"))
    mock_strip = MagicMock(return_value=Path("/tmp/test.mp4"))
    mock_get_analyzer = MagicMock(return_value=MagicMock())
    mock_analyze = MagicMock(return_value=analysis_result)
    mock_audit = MagicMock(return_value=[])
    mock_decision = MagicMock(return_value=decision_result)
    mock_save_report = MagicMock()
    mock_cleanup = MagicMock()

    with patch("worker._update_job_status", mock_update), \
         patch("worker._get_user_settings", mock_settings), \
         patch("worker._download_video", mock_download), \
         patch("worker._strip_thumbnail_stream", mock_strip), \
         patch("worker.get_bedrock_analyzer", mock_get_analyzer), \
         patch("worker.analyze_video_bedrock", mock_analyze), \
         patch("worker.audit_description", mock_audit), \
         patch("worker.make_split_decision", mock_decision), \
         patch("worker._save_report", mock_save_report), \
         patch("worker._cleanup", mock_cleanup):

        event = _make_event(job_id, user_id, s3_key, region)
        handler(event, None)

    # 1. _save_report must be called exactly once (Reports table save)
    assert mock_save_report.call_count == 1, (
        f"Expected _save_report called exactly once, got {mock_save_report.call_count}"
    )

    # 2. _update_job_status must be called with COMPLETED and result (Jobs table save)
    update_calls = mock_update.call_args_list
    completed_calls = [c for c in update_calls if len(c[0]) >= 2 and c[0][1] == "COMPLETED"]
    assert len(completed_calls) == 1, (
        f"Expected exactly 1 COMPLETED update call, got {len(completed_calls)}"
    )
    completed_call = completed_calls[0]
    assert "result" in completed_call[1], (
        f"COMPLETED call must include 'result' kwarg, got kwargs: {completed_call[1]}"
    )

    # 3. Both saves reference the same report data
    # _save_report receives (user_id, report) where report is a ComplianceReport
    saved_report = mock_save_report.call_args[0][1]
    jobs_result = completed_call[1]["result"]

    # The report's video_id should appear as reportId in the jobs result
    assert jobs_result.get("reportId") == saved_report.video_id, (
        f"reportId mismatch: jobs={jobs_result.get('reportId')}, "
        f"report={saved_report.video_id}"
    )

    # The decision stored in jobs result should match the report's decision
    assert jobs_result.get("decision") == saved_report.decision.value, (
        f"decision mismatch: jobs={jobs_result.get('decision')}, "
        f"report={saved_report.decision.value}"
    )

    # The description should match
    assert jobs_result.get("description") == saved_report.description, (
        f"description mismatch: jobs={jobs_result.get('description')!r}, "
        f"report={saved_report.description!r}"
    )


# --- Property 5 Test: Backend 선택 정확성 ---

backend_strategy = st.sampled_from(["bedrock", "twelvelabs"])


@given(
    job_id=job_id_strategy,
    user_id=user_id_strategy,
    s3_key=s3_key_strategy,
    region=region_strategy,
    backend_choice=backend_strategy,
)
@settings(max_examples=100, deadline=None)
def test_worker_calls_correct_backend_based_on_settings(
    job_id: str, user_id: str, s3_key: str, region: str, backend_choice: str,
):
    """Property 5: For any user_id and their Settings table backend setting
    (bedrock or twelvelabs), Worker calls the correct analysis function.

    Feature: async-analysis, Property 5: Backend 선택 정확성

    **Validates: Requirements 2.6**
    """
    _reset_worker_globals()
    from worker import handler

    analysis_result, decision_result = _build_success_mocks()

    # Build settings based on backend choice
    if backend_choice == "twelvelabs":
        user_settings = {"backend": "twelvelabs", "twelvelabs_api_key": "test-key"}
    else:
        user_settings = {"backend": "bedrock"}

    mock_update = MagicMock()
    mock_settings = MagicMock(return_value=user_settings)
    mock_download = MagicMock(return_value=Path("/tmp/test.mp4"))
    mock_strip = MagicMock(return_value=Path("/tmp/test.mp4"))
    mock_get_analyzer = MagicMock(return_value=MagicMock())
    mock_analyze_bedrock = MagicMock(return_value=analysis_result)
    mock_analyze_twelvelabs = MagicMock(return_value=analysis_result)
    mock_audit = MagicMock(return_value=[])
    mock_decision = MagicMock(return_value=decision_result)
    mock_save_report = MagicMock()
    mock_cleanup = MagicMock()

    with patch("worker._update_job_status", mock_update), \
         patch("worker._get_user_settings", mock_settings), \
         patch("worker._download_video", mock_download), \
         patch("worker._strip_thumbnail_stream", mock_strip), \
         patch("worker.get_bedrock_analyzer", mock_get_analyzer), \
         patch("worker.analyze_video_bedrock", mock_analyze_bedrock), \
         patch("worker.analyze_video_twelvelabs", mock_analyze_twelvelabs), \
         patch("worker.audit_description", mock_audit), \
         patch("worker.make_split_decision", mock_decision), \
         patch("worker._save_report", mock_save_report), \
         patch("worker._cleanup", mock_cleanup):

        event = _make_event(job_id, user_id, s3_key, region)
        handler(event, None)

    if backend_choice == "bedrock":
        assert mock_analyze_bedrock.call_count == 1, (
            f"Expected analyze_video_bedrock called once for backend='bedrock', "
            f"got {mock_analyze_bedrock.call_count}"
        )
        assert mock_analyze_twelvelabs.call_count == 0, (
            f"Expected analyze_video_twelvelabs NOT called for backend='bedrock', "
            f"got {mock_analyze_twelvelabs.call_count}"
        )
    else:
        assert mock_analyze_twelvelabs.call_count == 1, (
            f"Expected analyze_video_twelvelabs called once for backend='twelvelabs', "
            f"got {mock_analyze_twelvelabs.call_count}"
        )
        assert mock_analyze_bedrock.call_count == 0, (
            f"Expected analyze_video_bedrock NOT called for backend='twelvelabs', "
            f"got {mock_analyze_bedrock.call_count}"
        )
