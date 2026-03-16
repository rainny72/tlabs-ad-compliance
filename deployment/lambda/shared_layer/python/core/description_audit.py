"""Post-processing: detect violations from video description text.

When the model transcribes audio but fails to flag violations,
this module scans the description for known violation keywords
and patches the violations list accordingly.
"""

from __future__ import annotations

import logging
import re

from shared.constants import Modality, PolicyCategory, Severity
from shared.schemas import PolicyViolationResult, ViolationEvidence

logger = logging.getLogger(__name__)

# keyword -> (category, severity, description_en)
_DRUG_KEYWORDS = [
    (r"\bcannabis\b", "Cannabis/marijuana reference in ad content"),
    (r"\bmarijuana\b", "Marijuana reference in ad content"),
    (r"\bweed\b", "Drug slang (weed) reference in ad content"),
    (r"\bcbd\b", "CBD product reference in ad content"),
    (r"\bcocaine\b", "Cocaine reference in ad content"),
    (r"\bheroin\b", "Heroin reference in ad content"),
    (r"\bdrug[s]?\b", "Drug reference in ad content"),
    (r"\bmdma\b", "MDMA reference in ad content"),
    (r"\blsd\b", "LSD reference in ad content"),
    (r"\bopium\b", "Opium reference in ad content"),
    (r"\bmeth\b", "Methamphetamine reference in ad content"),
    (r"\b大麻\b", "Cannabis reference (Japanese/Chinese)"),
    (r"\b마약\b", "Drug reference (Korean)"),
    (r"\b대마\b", "Cannabis reference (Korean)"),
]

_UNSAFE_KEYWORDS = [
    (r"rub\s+it\s+in\s+hard", "Aggressive product application instruction"),
    (r"feel\s+that\s+tingle", "Encouraging skin irritation as positive sign"),
    (r"see\s+the\s+redness", "Skin redness presented as normal/positive"),
    (r"broken\s+skin", "Product use on broken skin"),
    (r"near\s+(your\s+)?eyes", "Product applied near eyes unsafely"),
    (r"miracle\s+whiten", "Unsafe whitening product claim"),
    (r"bleach", "Bleaching reference in cosmetics context"),
    (r"diy\s+(cosmetic|skincare|cream|serum)", "DIY cosmetics without safety warning"),
]

_HATE_KEYWORDS = [
    (r"yeux\s+brid[eé]s", "Racial stereotyping of East Asian eye features (French)"),
    (r"cr[eè]mes?\s+asiatiques?\s+sont?\s+nulles?", "Derogatory generalization about Asian products"),
    (r"pas\s+jaune\s+et\s+terne", "Skin tone superiority claim (not yellow and dull)"),
    (r"peau\s+grasse", "Negative racial skin stereotype"),
    (r"\bslant[- ]?eye", "Racial slur targeting East Asian features"),
    (r"\byellow\s+skin\b", "Racial skin tone derogation"),
]


def _scan(text: str, patterns: list[tuple[str, str]]) -> list[str]:
    """Return list of matched descriptions."""
    hits = []
    lower = text.lower()
    for pattern, desc in patterns:
        if re.search(pattern, lower):
            hits.append(desc)
    return hits


def audit_description(
    description: str,
    violations: list[PolicyViolationResult],
) -> list[PolicyViolationResult]:
    """Scan description for missed violations and patch the list."""
    if not description:
        return violations

    patched = False

    # Build lookup of existing categories
    cat_map = {v.category: v for v in violations}

    # --- drugs_illegal ---
    drug_hits = _scan(description, _DRUG_KEYWORDS)
    existing_drug = cat_map.get(PolicyCategory.DRUGS_ILLEGAL)
    if drug_hits and (not existing_drug or existing_drug.severity == Severity.NONE):
        ev = ViolationEvidence(
            description="; ".join(drug_hits),
            timestamp_start=0.0, timestamp_end=0.0,
            modality=Modality.SPEECH,
            evidence=drug_hits[0],
        )
        new_v = PolicyViolationResult(
            category=PolicyCategory.DRUGS_ILLEGAL,
            severity=Severity.HIGH,
            violations=[ev],
        )
        if existing_drug:
            idx = violations.index(existing_drug)
            violations[idx] = new_v
        else:
            violations.append(new_v)
        patched = True
        logger.info("Description audit: added drugs_illegal from keywords")

    # --- unsafe_misleading_usage ---
    unsafe_hits = _scan(description, _UNSAFE_KEYWORDS)
    existing_unsafe = cat_map.get(PolicyCategory.UNSAFE_MISLEADING_USAGE)
    if unsafe_hits and (not existing_unsafe or existing_unsafe.severity == Severity.NONE):
        ev = ViolationEvidence(
            description="; ".join(unsafe_hits),
            timestamp_start=0.0, timestamp_end=0.0,
            modality=Modality.SPEECH,
            evidence=unsafe_hits[0],
        )
        new_v = PolicyViolationResult(
            category=PolicyCategory.UNSAFE_MISLEADING_USAGE,
            severity=Severity.HIGH,
            violations=[ev],
        )
        if existing_unsafe:
            idx = violations.index(existing_unsafe)
            violations[idx] = new_v
        else:
            violations.append(new_v)
        patched = True
        logger.info("Description audit: added unsafe_misleading_usage from keywords")

    # --- hate_harassment ---
    hate_hits = _scan(description, _HATE_KEYWORDS)
    existing_hate = cat_map.get(PolicyCategory.HATE_HARASSMENT)
    if hate_hits and (not existing_hate or existing_hate.severity == Severity.NONE):
        ev = ViolationEvidence(
            description="; ".join(hate_hits),
            timestamp_start=0.0, timestamp_end=0.0,
            modality=Modality.SPEECH,
            evidence=hate_hits[0],
        )
        new_v = PolicyViolationResult(
            category=PolicyCategory.HATE_HARASSMENT,
            severity=Severity.CRITICAL,
            violations=[ev],
        )
        if existing_hate:
            idx = violations.index(existing_hate)
            violations[idx] = new_v
        else:
            violations.append(new_v)
        patched = True
        logger.info("Description audit: added hate_harassment from keywords")

    if not patched:
        logger.info("Description audit: no additional violations found")

    return violations
