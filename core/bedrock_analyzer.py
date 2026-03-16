"""Combined analyzer using Amazon Bedrock (TwelveLabs Pegasus 1.2).

Uses a single Bedrock InvokeModel call per video — no TwelveLabs API quota consumed.
Video is sent as base64 directly to Bedrock (no indexing required).
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from shared.constants import (
    Modality, PolicyCategory, RelevanceLabel, Severity,
    RELEVANCE_THRESHOLD,
)
from shared.schemas import (
    CampaignRelevanceResult,
    PolicyViolationResult,
    ViolationEvidence,
)
from prompts.prompt_templates import COMBINED_JSON_SCHEMA, get_regional_prompt
from core.bedrock_client import BedrockAnalyzer


CATEGORY_MAP = {
    "hate_harassment": PolicyCategory.HATE_HARASSMENT,
    "profanity_explicit": PolicyCategory.PROFANITY_EXPLICIT,
    "drugs_illegal": PolicyCategory.DRUGS_ILLEGAL,
    "unsafe_misleading_usage": PolicyCategory.UNSAFE_MISLEADING_USAGE,
    "medical_cosmetic_claims": PolicyCategory.MEDICAL_COSMETIC_CLAIMS,
    "disclosure": PolicyCategory.DISCLOSURE,
}


def _parse_modality(raw: str) -> Modality:
    raw = raw.lower().strip()
    if raw in ("visual", "video", "image"):
        return Modality.VISUAL
    elif raw in ("speech", "audio", "voice"):
        return Modality.SPEECH
    elif raw in ("text_on_screen", "text", "on-screen text", "on_screen_text"):
        return Modality.TEXT_ON_SCREEN
    return Modality.VISUAL


def _parse_severity(raw: str) -> Severity:
    raw = raw.lower().strip()
    for s in Severity:
        if s.value == raw:
            return s
    return Severity.NONE


def analyze_video_bedrock(
    analyzer: BedrockAnalyzer, video_path: Path, region: str = "global",
    s3_uri: str | None = None, bucket_owner: str | None = None,
) -> tuple[CampaignRelevanceResult, list[PolicyViolationResult], str]:
    """Run a single Bedrock analyze call that returns relevance, violations, and description."""

    prompt = get_regional_prompt(region)
    logger.info("Region: %s | Prompt length: %d chars", region, len(prompt))
    data = analyzer.analyze_json(
        video_path=video_path,
        prompt=prompt,
        json_schema=COMBINED_JSON_SCHEMA,
        s3_uri=s3_uri,
        bucket_owner=bucket_owner,
    )

    # Log raw model response for debugging
    import json as _json
    logger.info("Raw model response:\n%s", _json.dumps(data, indent=2, ensure_ascii=False))

    # Parse relevance
    rel_data = data.get("relevance", {})
    score = rel_data.get("relevance_score", 0.0)
    is_on_brief = rel_data.get("is_on_brief", False)
    product_visible = rel_data.get("product_visible", None)
    reasoning = rel_data.get("reasoning", "Analysis unavailable")

    if score >= RELEVANCE_THRESHOLD and is_on_brief:
        label = RelevanceLabel.ON_BRIEF
    elif score < 0.3:
        label = RelevanceLabel.OFF_BRIEF
    else:
        label = RelevanceLabel.BORDERLINE

    relevance = CampaignRelevanceResult(
        score=score,
        label=label,
        product_visible=product_visible,
        reasoning=reasoning,
        search_evidence=[],
    )

    # Parse description
    description = data.get("description", "Description unavailable.")

    # Parse policy violations
    violations = []
    policy_data = data.get("policy_violations", {})
    for category_key, category_enum in CATEGORY_MAP.items():
        cat_data = policy_data.get(category_key, {})
        has_violation = cat_data.get("has_violation", False)
        severity = _parse_severity(cat_data.get("severity", "none"))
        violation_items = []

        if has_violation:
            for v in cat_data.get("violations", []):
                violation_items.append(
                    ViolationEvidence(
                        description=v.get("description", ""),
                        timestamp_start=float(v.get("timestamp_start", 0)),
                        timestamp_end=float(v.get("timestamp_end", 0)),
                        modality=_parse_modality(v.get("modality", "visual")),
                        evidence=v.get("evidence", ""),
                        evidence_original=v.get("evidence_original"),
                    )
                )

        violations.append(
            PolicyViolationResult(
                category=category_enum,
                severity=severity,
                violations=violation_items,
            )
        )

    return relevance, violations, description, data
