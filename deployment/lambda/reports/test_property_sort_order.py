"""Property-based test for report list sort order via DynamoDB.

Feature: amplify-serverless-migration, Property 8: 리포트 목록 정렬 순서

Validates: Requirements 6.3
"""

import json
import os
import sys
from decimal import Decimal
from unittest.mock import patch

# Add shared_layer and reports dir to path so modules are importable
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared_layer", "python"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timezone

import boto3
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

# --- Strategies (reused from test_property_roundtrip.py) ---

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


# Use unique datetimes for analyzed_at to ensure distinct sort keys
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
    violations=st.lists(violation_evidence_strategy, min_size=0, max_size=2),
)

campaign_relevance_strategy = st.builds(
    CampaignRelevanceResult,
    score=score_strategy,
    label=relevance_label_strategy,
    product_visible=st.one_of(st.none(), st.booleans()),
    reasoning=reasoning_strategy,
    search_evidence=st.lists(search_evidence_strategy, min_size=0, max_size=2),
)

status_dict_strategy = st.fixed_dictionaries({
    "status": st.sampled_from(["PASS", "REVIEW", "BLOCK", "PRESENT", "MISSING", "ON_BRIEF", "OFF_BRIEF"]),
    "reasoning": reasoning_strategy,
})


def _compliance_report_with_timestamp(analyzed_at):
    """Build a ComplianceReport strategy with a fixed analyzed_at."""
    return st.builds(
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
        policy_violations=st.lists(policy_violation_strategy, min_size=0, max_size=3),
        decision=decision_strategy,
        decision_reasoning=reasoning_strategy,
        compliance=status_dict_strategy,
        product=status_dict_strategy,
        disclosure=status_dict_strategy,
        analyzed_at=st.just(analyzed_at),
    )


# Strategy: generate a list of 2-10 unique datetimes, then build reports for each
unique_datetimes_strategy = st.lists(
    aware_datetime_strategy,
    min_size=2,
    max_size=10,
    unique_by=lambda dt: dt.isoformat(),
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


@given(
    timestamps=unique_datetimes_strategy,
    user_id=st.uuids().map(str),
    data=st.data(),
)
@settings(max_examples=100, deadline=None)
def test_report_list_sort_order(timestamps, user_id, data):
    """Property 8: For any set of reports with unique analyzed_at timestamps,
    listing reports must return them sorted by analyzedAt in descending order
    (newest first).

    Feature: amplify-serverless-migration, Property 8: 리포트 목록 정렬 순서

    **Validates: Requirements 6.3**
    """
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = _create_table(dynamodb)

        # Generate and save a report for each unique timestamp
        for ts in timestamps:
            report = data.draw(_compliance_report_with_timestamp(ts))
            _save_report(table, user_id, report)

        # Set env var and patch the handler's dynamodb resource to use moto table
        os.environ["REPORTS_TABLE"] = TABLE_NAME
        import handler as reports_handler
        reports_handler._dynamodb_resource = dynamodb

        try:
            result = reports_handler._list_reports(user_id)
        finally:
            reports_handler._dynamodb_resource = None

        reports = result["reports"]

        # Verify count matches
        assert len(reports) == len(timestamps), (
            f"Expected {len(timestamps)} reports, got {len(reports)}"
        )

        # Verify descending order: for all consecutive pairs, analyzedAt[i] >= analyzedAt[i+1]
        for i in range(len(reports) - 1):
            current_at = reports[i]["analyzedAt"]
            next_at = reports[i + 1]["analyzedAt"]
            assert current_at >= next_at, (
                f"Reports not in descending order at index {i}: "
                f"{current_at} should be >= {next_at}"
            )
