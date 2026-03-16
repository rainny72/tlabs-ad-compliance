"""Property-based test for ComplianceReport serialization roundtrip.

Feature: amplify-serverless-migration, Property 5: ComplianceReport 직렬화 라운드트립

Validates: Requirements 4.3
"""

import os
import sys

# Add shared_layer to path so shared modules are importable
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared_layer", "python"))

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

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

# --- Strategies ---

# Basic value strategies
score_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
timestamp_strategy = st.floats(min_value=0.0, max_value=3600.0, allow_nan=False, allow_infinity=False)
short_text_strategy = st.text(min_size=1, max_size=50, alphabet=st.characters(categories=("L", "N", "Z")))
reasoning_strategy = st.text(min_size=0, max_size=200, alphabet=st.characters(categories=("L", "N", "Z", "P")))

# Enum strategies
region_strategy = st.sampled_from(list(Region))
decision_strategy = st.sampled_from(list(Decision))
severity_strategy = st.sampled_from(list(Severity))
policy_category_strategy = st.sampled_from(list(PolicyCategory))
relevance_label_strategy = st.sampled_from(list(RelevanceLabel))
modality_strategy = st.sampled_from(list(Modality))

# Datetime strategy: aware datetimes with UTC timezone for JSON roundtrip consistency
aware_datetime_strategy = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
    timezones=st.just(timezone.utc),
)

# SearchEvidence strategy
search_evidence_strategy = st.builds(
    SearchEvidence,
    query=short_text_strategy,
    top_score=score_strategy,
    matched_segments=st.integers(min_value=0, max_value=100),
)

# ViolationEvidence strategy
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

# PolicyViolationResult strategy
policy_violation_strategy = st.builds(
    PolicyViolationResult,
    category=policy_category_strategy,
    severity=severity_strategy,
    violations=st.lists(violation_evidence_strategy, min_size=0, max_size=3),
)

# CampaignRelevanceResult strategy
campaign_relevance_strategy = st.builds(
    CampaignRelevanceResult,
    score=score_strategy,
    label=relevance_label_strategy,
    product_visible=st.one_of(st.none(), st.booleans()),
    reasoning=reasoning_strategy,
    search_evidence=st.lists(search_evidence_strategy, min_size=0, max_size=3),
)

# Simple dict strategies for compliance/product/disclosure fields
status_dict_strategy = st.fixed_dictionaries({
    "status": st.sampled_from(["PASS", "REVIEW", "BLOCK", "PRESENT", "MISSING", "ON_BRIEF", "OFF_BRIEF"]),
    "reasoning": reasoning_strategy,
})

# ComplianceReport strategy
compliance_report_strategy = st.builds(
    ComplianceReport,
    video_id=st.uuids().map(str),
    video_file=st.builds(lambda base, ext: f"{base}.{ext}",
                         st.text(min_size=1, max_size=20, alphabet=st.characters(categories=("L", "N"))),
                         st.sampled_from(["mp4", "mov", "avi", "mkv"])),
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


@given(report=compliance_report_strategy)
@settings(max_examples=100)
def test_compliance_report_serialization_roundtrip(report: ComplianceReport):
    """Property 5: For any valid ComplianceReport object, serializing to JSON
    with model_dump_json() and deserializing with model_validate_json() must
    produce an object equal to the original.

    Feature: amplify-serverless-migration, Property 5: ComplianceReport 직렬화 라운드트립

    **Validates: Requirements 4.3**
    """
    json_str = report.model_dump_json()
    restored = ComplianceReport.model_validate_json(json_str)
    assert restored == report, (
        f"Roundtrip mismatch:\nOriginal: {report}\nRestored: {restored}"
    )
