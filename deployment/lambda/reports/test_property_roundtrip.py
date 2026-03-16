"""Property-based test for report save/retrieve roundtrip via DynamoDB.

Feature: amplify-serverless-migration, Property 7: 리포트 저장/조회 라운드트립

Validates: Requirements 6.2, 6.4
"""

import json
import os
import sys
from decimal import Decimal

# Add shared_layer to path so shared modules are importable
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared_layer", "python"))

from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key
from hypothesis import given, settings
from hypothesis import strategies as st
from moto import mock_aws

from shared.constants import (
    Decision,
    Modality,
    PolicyCategory,
    Region,
    RelevanceLabel,
    Severity,
)
from shared.schemas import (
    CampaignRelevanceResult,
    ComplianceReport,
    PolicyViolationResult,
    SearchEvidence,
    ViolationEvidence,
)

# --- Strategies (reused from test_property_serialization.py) ---

# Use Decimal-safe floats: avoid subnormal/extreme precision values that cause DynamoDB underflow
score_strategy = st.decimals(min_value=0, max_value=1, places=6).map(float)
timestamp_strategy = st.decimals(min_value=0, max_value=3600, places=3).map(float)
short_text_strategy = st.text(min_size=1, max_size=50, alphabet=st.characters(categories=("L", "N", "Z")))
reasoning_strategy = st.text(min_size=0, max_size=200, alphabet=st.characters(categories=("L", "N", "Z", "P")))

region_strategy = st.sampled_from(list(Region))
decision_strategy = st.sampled_from(list(Decision))
severity_strategy = st.sampled_from(list(Severity))
policy_category_strategy = st.sampled_from(list(PolicyCategory))
relevance_label_strategy = st.sampled_from(list(RelevanceLabel))
modality_strategy = st.sampled_from(list(Modality))

aware_datetime_strategy = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
    timezones=st.just(timezone.utc),
)

search_evidence_strategy = st.builds(
    SearchEvidence,
    query=short_text_strategy,
    top_score=score_strategy,
    matched_segments=st.integers(min_value=0, max_value=100),
)

violation_evidence_strategy = st.builds(
    ViolationEvidence,
    description=short_text_strategy,
    timestamp_start=timestamp_strategy,
    timestamp_end=timestamp_strategy,
    modality=modality_strategy,
    evidence=short_text_strategy,
    evidence_original=st.one_of(st.none(), short_text_strategy),
    search_confidence=st.one_of(st.none(), st.sampled_from(["high", "medium", "low"])),
    transcription=st.one_of(st.none(), short_text_strategy),
)

policy_violation_strategy = st.builds(
    PolicyViolationResult,
    category=policy_category_strategy,
    severity=severity_strategy,
    violations=st.lists(violation_evidence_strategy, min_size=0, max_size=3),
)

campaign_relevance_strategy = st.builds(
    CampaignRelevanceResult,
    score=score_strategy,
    label=relevance_label_strategy,
    product_visible=st.one_of(st.none(), st.booleans()),
    reasoning=reasoning_strategy,
    search_evidence=st.lists(search_evidence_strategy, min_size=0, max_size=3),
)

status_dict_strategy = st.fixed_dictionaries({
    "status": st.sampled_from(["PASS", "REVIEW", "BLOCK", "PRESENT", "MISSING", "ON_BRIEF", "OFF_BRIEF"]),
    "reasoning": reasoning_strategy,
})

compliance_report_strategy = st.builds(
    ComplianceReport,
    video_id=st.uuids().map(str),
    video_file=st.builds(
        lambda base, ext: f"{base}.{ext}",
        st.text(min_size=1, max_size=20, alphabet=st.characters(categories=("L", "N"))),
        st.sampled_from(["mp4", "mov", "avi", "mkv"]),
    ),
    region=region_strategy,
    description=reasoning_strategy,
    campaign_relevance=campaign_relevance_strategy,
    policy_violations=st.lists(policy_violation_strategy, min_size=0, max_size=5),
    decision=decision_strategy,
    decision_reasoning=reasoning_strategy,
    compliance=status_dict_strategy,
    product=status_dict_strategy,
    disclosure=status_dict_strategy,
    analyzed_at=aware_datetime_strategy,
)

TABLE_NAME = "test-compliance-reports"


def _convert_floats_to_decimal(obj):
    """Recursively convert float values to Decimal for DynamoDB compatibility."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _convert_floats_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_floats_to_decimal(v) for v in obj]
    return obj


def _create_table(dynamodb):
    """Create the DynamoDB table matching the production schema."""
    dynamodb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {"AttributeName": "user_id", "KeyType": "HASH"},
            {"AttributeName": "analyzed_at", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "analyzed_at", "AttributeType": "S"},
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    return dynamodb.Table(TABLE_NAME)


def _save_report(table, user_id: str, report: ComplianceReport):
    """Replicate the save pattern from analyze handler (with Decimal conversion)."""
    item = json.loads(report.model_dump_json())
    item["user_id"] = user_id
    item["analyzed_at"] = report.analyzed_at.isoformat()
    item = _convert_floats_to_decimal(item)
    table.put_item(Item=item)


def _get_report(table, user_id: str, report_id: str):
    """Replicate the retrieve pattern from reports handler."""
    response = table.query(
        KeyConditionExpression=Key("user_id").eq(user_id),
        ScanIndexForward=False,
    )
    items = response.get("Items", [])
    for item in items:
        if item.get("video_id") == report_id:
            return item
    return None


def _run_single_roundtrip(report: ComplianceReport, user_id: str):
    """Execute a single save-then-retrieve roundtrip in an isolated mock AWS env."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = _create_table(dynamodb)

        # Save
        _save_report(table, user_id, report)

        # Retrieve
        retrieved = _get_report(table, user_id, report.video_id)

        # Verify retrieval succeeded
        assert retrieved is not None, f"Report {report.video_id} not found for user {user_id}"

        # Verify key fields match
        assert retrieved["video_id"] == report.video_id
        assert retrieved["video_file"] == report.video_file
        assert retrieved["decision"] == report.decision.value
        assert retrieved["region"] == report.region.value
        assert retrieved["analyzed_at"] == report.analyzed_at.isoformat()
        assert retrieved["description"] == report.description


@given(
    report=compliance_report_strategy,
    user_id=st.uuids().map(str),
)
@settings(max_examples=100, deadline=None)
def test_report_save_retrieve_roundtrip(report: ComplianceReport, user_id: str):
    """Property 7: For any valid ComplianceReport, saving to DynamoDB and
    retrieving by report_id (video_id) must return the same key data fields.

    Feature: amplify-serverless-migration, Property 7: 리포트 저장/조회 라운드트립

    **Validates: Requirements 6.2, 6.4**
    """
    _run_single_roundtrip(report, user_id)
