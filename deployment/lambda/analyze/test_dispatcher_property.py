"""Property-based test for Dispatcher POST /analyze - Job creation completeness.

Feature: async-analysis, Property 1: 유효한 요청에 대한 Job 생성 완전성

Validates: Requirements 1.1, 1.4
"""

import json
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

_this_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_this_dir))
sys.path.insert(0, str(_this_dir.parent / "shared_layer" / "python"))

os.environ.setdefault("JOBS_TABLE", "test-jobs-table")
os.environ.setdefault("WORKER_FUNCTION_NAME", "test-worker-fn")
os.environ.setdefault("VIDEO_BUCKET", "test-video-bucket")

from hypothesis import given, settings
from hypothesis import strategies as st

from dispatcher import handle_post

# --- Strategies ---

# Valid s3Key: "uploads/" followed by arbitrary non-empty text
valid_s3key_strategy = st.text(
    min_size=1, max_size=200,
    alphabet=st.characters(categories=("L", "N", "P"), exclude_characters="\x00"),
).map(lambda s: f"uploads/{s}")

# Valid region: one of the four allowed values
valid_region_strategy = st.sampled_from(["global", "north_america", "western_europe", "east_asia"])

# User ID: non-empty string
user_id_strategy = st.text(
    min_size=1, max_size=100,
    alphabet=st.characters(categories=("L", "N"), exclude_characters="\x00"),
)


def _make_event(s3_key: str, region: str, user_id: str) -> dict:
    return {
        "httpMethod": "POST",
        "requestContext": {"authorizer": {"claims": {"sub": user_id}}},
        "body": json.dumps({"s3Key": s3_key, "region": region}),
    }


# --- Property Test ---


@given(
    s3_key=valid_s3key_strategy,
    region=valid_region_strategy,
    user_id=user_id_strategy,
)
@settings(max_examples=100)
def test_valid_request_creates_job_and_returns_202(s3_key: str, region: str, user_id: str):
    """Property 1: For any valid s3Key (starts with "uploads/") and valid region,
    Dispatcher generates UUID v4 jobId, saves record to Jobs table with all
    required fields (user_id, job_id, s3_key, region, status=PENDING, created_at),
    and returns HTTP 202.

    Feature: async-analysis, Property 1: 유효한 요청에 대한 Job 생성 완전성

    **Validates: Requirements 1.1, 1.4**
    """
    import dispatcher
    dispatcher._dynamodb_resource = None
    dispatcher._lambda_client = None

    mock_table = MagicMock()
    mock_lambda = MagicMock()

    with patch("dispatcher._get_jobs_table", return_value=mock_table), \
         patch("dispatcher._get_lambda_client", return_value=mock_lambda):

        event = _make_event(s3_key, region, user_id)
        response = handle_post(event)

    # 1. HTTP 202 response
    assert response["statusCode"] == 202, f"Expected 202, got {response['statusCode']}"

    body = json.loads(response["body"])

    # 2. jobId is present and is valid UUID v4
    assert "jobId" in body, f"Response missing 'jobId': {body}"
    job_id = body["jobId"]
    parsed_uuid = uuid.UUID(job_id, version=4)
    assert str(parsed_uuid) == job_id, f"jobId is not valid UUID v4: {job_id}"

    # 3. status is PENDING in response
    assert body.get("status") == "PENDING", f"Expected status PENDING, got {body.get('status')}"

    # 4. put_item was called exactly once
    mock_table.put_item.assert_called_once()

    # 5. Verify all required fields in the saved record
    call_kwargs = mock_table.put_item.call_args
    item = call_kwargs[1]["Item"] if "Item" in (call_kwargs[1] or {}) else call_kwargs[0][0]

    assert item["job_id"] == job_id, f"Saved job_id mismatch: {item['job_id']} != {job_id}"
    assert item["user_id"] == user_id, f"Saved user_id mismatch: {item['user_id']} != {user_id}"
    assert item["s3_key"] == s3_key, f"Saved s3_key mismatch: {item['s3_key']} != {s3_key}"
    assert item["region"] == region, f"Saved region mismatch: {item['region']} != {region}"
    assert item["status"] == "PENDING", f"Saved status should be PENDING, got {item['status']}"
    assert "created_at" in item, "Saved record missing 'created_at'"
    assert isinstance(item["created_at"], str), "created_at should be a string (ISO 8601)"

    # 6. Worker Lambda was invoked asynchronously
    mock_lambda.invoke.assert_called_once()
    invoke_kwargs = mock_lambda.invoke.call_args[1]
    assert invoke_kwargs["InvocationType"] == "Event"


# --- Property 2: 유효하지 않은 입력 거부 ---

# Invalid s3Key strategies
# Strategy: empty string OR text that does NOT start with "uploads/"
_non_uploads_prefix = st.text(
    min_size=1, max_size=200,
    alphabet=st.characters(categories=("L", "N", "P"), exclude_characters="\x00"),
).filter(lambda s: not s.startswith("uploads/"))

invalid_s3key_strategy = st.one_of(
    st.just(""),           # empty string
    _non_uploads_prefix,   # non-empty but doesn't start with "uploads/"
)

# Invalid region: text that is NOT in the allowed list
ALLOWED_REGIONS = {"global", "north_america", "western_europe", "east_asia"}

invalid_region_strategy = st.text(
    min_size=1, max_size=50,
    alphabet=st.characters(categories=("L", "N"), exclude_characters="\x00"),
).filter(lambda r: r not in ALLOWED_REGIONS)


@given(
    s3_key=invalid_s3key_strategy,
    region=valid_region_strategy,
    user_id=user_id_strategy,
)
@settings(max_examples=100)
def test_invalid_s3key_returns_400_no_record(s3_key: str, region: str, user_id: str):
    """Property 2 (Strategy 1): For any s3Key that is empty or doesn't start
    with "uploads/", Dispatcher returns HTTP 400 and does NOT create a record
    in Jobs table.

    Feature: async-analysis, Property 2: 유효하지 않은 입력 거부

    **Validates: Requirements 1.2, 1.3**
    """
    import dispatcher
    dispatcher._dynamodb_resource = None
    dispatcher._lambda_client = None

    mock_table = MagicMock()
    mock_lambda = MagicMock()

    with patch("dispatcher._get_jobs_table", return_value=mock_table), \
         patch("dispatcher._get_lambda_client", return_value=mock_lambda):

        event = _make_event(s3_key, region, user_id)
        response = handle_post(event)

    # 1. HTTP 400 response
    assert response["statusCode"] == 400, (
        f"Expected 400 for invalid s3Key={s3_key!r}, got {response['statusCode']}"
    )

    # 2. put_item NOT called (no record created)
    mock_table.put_item.assert_not_called()

    # 3. Worker Lambda NOT invoked
    mock_lambda.invoke.assert_not_called()


@given(
    s3_key=valid_s3key_strategy,
    region=invalid_region_strategy,
    user_id=user_id_strategy,
)
@settings(max_examples=100)
def test_invalid_region_returns_400_no_record(s3_key: str, region: str, user_id: str):
    """Property 2 (Strategy 2): For any region not in the allowed list
    (global, north_america, western_europe, east_asia), Dispatcher returns
    HTTP 400 and does NOT create a record in Jobs table.

    Feature: async-analysis, Property 2: 유효하지 않은 입력 거부

    **Validates: Requirements 1.2, 1.3**
    """
    import dispatcher
    dispatcher._dynamodb_resource = None
    dispatcher._lambda_client = None

    mock_table = MagicMock()
    mock_lambda = MagicMock()

    with patch("dispatcher._get_jobs_table", return_value=mock_table), \
         patch("dispatcher._get_lambda_client", return_value=mock_lambda):

        event = _make_event(s3_key, region, user_id)
        response = handle_post(event)

    # 1. HTTP 400 response
    assert response["statusCode"] == 400, (
        f"Expected 400 for invalid region={region!r}, got {response['statusCode']}"
    )

    # 2. put_item NOT called (no record created)
    mock_table.put_item.assert_not_called()

    # 3. Worker Lambda NOT invoked
    mock_lambda.invoke.assert_not_called()


# --- Property 9: TTL 값 정확성 ---


@given(
    s3_key=valid_s3key_strategy,
    region=valid_region_strategy,
    user_id=user_id_strategy,
)
@settings(max_examples=100)
def test_ttl_equals_created_at_plus_86400(s3_key: str, region: str, user_id: str):
    """Property 9: For any record created in Jobs table, the ttl field value
    must be created_at's Unix epoch + 86400 (24 hours).

    Feature: async-analysis, Property 9: TTL 값 정확성

    **Validates: Requirements 5.5**
    """
    import dispatcher
    from datetime import datetime, timezone

    dispatcher._dynamodb_resource = None
    dispatcher._lambda_client = None

    mock_table = MagicMock()
    mock_lambda = MagicMock()

    with patch("dispatcher._get_jobs_table", return_value=mock_table), \
         patch("dispatcher._get_lambda_client", return_value=mock_lambda):

        event = _make_event(s3_key, region, user_id)
        response = handle_post(event)

    # Precondition: request must succeed
    assert response["statusCode"] == 202, f"Expected 202, got {response['statusCode']}"

    # Extract the Item saved to DynamoDB
    mock_table.put_item.assert_called_once()
    call_kwargs = mock_table.put_item.call_args
    item = call_kwargs[1]["Item"] if "Item" in (call_kwargs[1] or {}) else call_kwargs[0][0]

    # Parse created_at ISO 8601 to Unix epoch
    created_at_str = item["created_at"]
    created_at_dt = datetime.fromisoformat(created_at_str)
    created_at_epoch = int(created_at_dt.timestamp())

    # Verify ttl == created_at epoch + 86400
    expected_ttl = created_at_epoch + 86400
    actual_ttl = item["ttl"]

    assert actual_ttl == expected_ttl, (
        f"TTL mismatch: expected {expected_ttl} (created_at epoch {created_at_epoch} + 86400), "
        f"got {actual_ttl}"
    )


# --- Property 6: 상태별 응답 형식 정확성 ---

from dispatcher import handle_get

# Strategy: random UUID string for job_id
job_id_strategy = st.uuids().map(str)

# Strategy: status from the four valid states
status_strategy = st.sampled_from(["PENDING", "PROCESSING", "COMPLETED", "FAILED"])

# Strategy: result dict with arbitrary string keys/values (for COMPLETED)
result_strategy = st.dictionaries(
    keys=st.text(min_size=1, max_size=20, alphabet=st.characters(categories=("L",))),
    values=st.text(min_size=1, max_size=50),
    min_size=1,
    max_size=5,
)

# Strategy: error message string (for FAILED)
error_strategy = st.text(min_size=1, max_size=200, alphabet=st.characters(categories=("L", "N", "P", "Z")))


def _make_get_event(job_id: str, user_id: str) -> dict:
    return {
        "httpMethod": "GET",
        "requestContext": {"authorizer": {"claims": {"sub": user_id}}},
        "pathParameters": {"jobId": job_id},
    }


@given(
    job_id=job_id_strategy,
    user_id=user_id_strategy,
    status=status_strategy,
    result_data=result_strategy,
    error_msg=error_strategy,
)
@settings(max_examples=100)
def test_get_response_fields_match_status(
    job_id: str, user_id: str, status: str, result_data: dict, error_msg: str
):
    """Property 6: For any Jobs table record, GET /analyze/{jobId} response:
    - PENDING or PROCESSING -> response contains only jobId and status (no result, no error)
    - COMPLETED -> response contains jobId, status, and result
    - FAILED -> response contains jobId, status, and error

    Feature: async-analysis, Property 6: 상태별 응답 형식 정확성

    **Validates: Requirements 3.2, 3.3, 3.4**
    """
    import dispatcher
    dispatcher._dynamodb_resource = None

    # Build the Jobs table record based on status
    item = {
        "job_id": job_id,
        "user_id": user_id,
        "status": status,
        "s3_key": "uploads/test.mp4",
        "region": "global",
        "created_at": "2025-01-01T00:00:00+00:00",
    }
    if status == "COMPLETED":
        item["result"] = result_data
    if status == "FAILED":
        item["error"] = error_msg

    mock_table = MagicMock()
    mock_table.get_item.return_value = {"Item": item}

    with patch("dispatcher._get_jobs_table", return_value=mock_table):
        event = _make_get_event(job_id, user_id)
        response = handle_get(event)

    # All statuses should return HTTP 200
    assert response["statusCode"] == 200, f"Expected 200, got {response['statusCode']}"

    body = json.loads(response["body"])

    # jobId and status always present
    assert body["jobId"] == job_id, f"jobId mismatch: {body['jobId']} != {job_id}"
    assert body["status"] == status, f"status mismatch: {body['status']} != {status}"

    if status in ("PENDING", "PROCESSING"):
        # No result or error fields
        assert "result" not in body, f"PENDING/PROCESSING should not have 'result', got: {body}"
        assert "error" not in body, f"PENDING/PROCESSING should not have 'error', got: {body}"
    elif status == "COMPLETED":
        # Must have result
        assert "result" in body, f"COMPLETED should have 'result', got: {body}"
        assert body["result"] == result_data, f"result mismatch"
    elif status == "FAILED":
        # Must have error
        assert "error" in body, f"FAILED should have 'error', got: {body}"
        assert body["error"] == error_msg, f"error mismatch"


# --- Property 7: 접근 불가능한 Job에 대한 404 반환 ---

# Strategy: owner_id that is always different from requester user_id
def _different_user_ids():
    """Generate two distinct user_id strings (requester vs owner)."""
    return st.tuples(
        user_id_strategy,
        user_id_strategy,
    ).filter(lambda pair: pair[0] != pair[1])


@given(
    job_id=job_id_strategy,
    user_id=user_id_strategy,
)
@settings(max_examples=100)
def test_nonexistent_job_returns_404(job_id: str, user_id: str):
    """Property 7 (Strategy 1): For any non-existent jobId, GET /analyze/{jobId}
    returns HTTP 404 with "Job not found" error message.

    Feature: async-analysis, Property 7: 접근 불가능한 Job에 대한 404 반환

    **Validates: Requirements 3.5, 3.6**
    """
    import dispatcher
    dispatcher._dynamodb_resource = None

    mock_table = MagicMock()
    # Simulate non-existent job: get_item returns empty response (no Item key)
    mock_table.get_item.return_value = {}

    with patch("dispatcher._get_jobs_table", return_value=mock_table):
        event = _make_get_event(job_id, user_id)
        response = handle_get(event)

    # 1. HTTP 404 response
    assert response["statusCode"] == 404, (
        f"Expected 404 for non-existent job_id={job_id!r}, got {response['statusCode']}"
    )

    # 2. Error message is "Job not found"
    body = json.loads(response["body"])
    assert body.get("error") == "Job not found", (
        f"Expected error 'Job not found', got {body.get('error')!r}"
    )


@given(
    job_id=job_id_strategy,
    user_ids=_different_user_ids(),
    status=status_strategy,
)
@settings(max_examples=100)
def test_user_id_mismatch_returns_404(job_id: str, user_ids: tuple, status: str):
    """Property 7 (Strategy 2): For any jobId where the record's user_id doesn't
    match the authenticated user, GET /analyze/{jobId} returns HTTP 404 with
    "Job not found" error message (prevents information leakage).

    Feature: async-analysis, Property 7: 접근 불가능한 Job에 대한 404 반환

    **Validates: Requirements 3.5, 3.6**
    """
    requester_id, owner_id = user_ids

    import dispatcher
    dispatcher._dynamodb_resource = None

    # Build a record owned by a different user
    item = {
        "job_id": job_id,
        "user_id": owner_id,  # different from requester
        "status": status,
        "s3_key": "uploads/test.mp4",
        "region": "global",
        "created_at": "2025-01-01T00:00:00+00:00",
    }

    mock_table = MagicMock()
    mock_table.get_item.return_value = {"Item": item}

    with patch("dispatcher._get_jobs_table", return_value=mock_table):
        # Requester has a different user_id than the record owner
        event = _make_get_event(job_id, requester_id)
        response = handle_get(event)

    # 1. HTTP 404 response
    assert response["statusCode"] == 404, (
        f"Expected 404 for user_id mismatch (requester={requester_id!r}, "
        f"owner={owner_id!r}), got {response['statusCode']}"
    )

    # 2. Error message is "Job not found" (no information leakage)
    body = json.loads(response["body"])
    assert body.get("error") == "Job not found", (
        f"Expected error 'Job not found', got {body.get('error')!r}"
    )
