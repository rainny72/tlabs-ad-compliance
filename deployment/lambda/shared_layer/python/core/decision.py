"""Decision engine: APPROVE / REVIEW / BLOCK for ad campaign compliance.

Three evaluation axes feed into a single campaign decision:
  1. Compliance  — content policy violations (hate, drugs, profanity, etc.)
  2. Product     — campaign relevance (on-brief / off-brief)
  3. Disclosure  — ad labeling (#ad, #sponsored, etc.)

Final decision rules:
  BLOCK  — clear compliance violation (HIGH / CRITICAL severity)
  REVIEW — compliance violation uncertain (LOW / MEDIUM severity)
         — product not properly advertised (off-brief, borderline, not visible)
         — ad disclosure missing
  APPROVE — no compliance issues + on-brief + disclosure present
"""

from __future__ import annotations

from shared.constants import (
    Decision,
    PolicyCategory,
    RelevanceLabel,
    Region,
    Severity,
    SEVERITY_PRIORITY,
)
from shared.schemas import CampaignRelevanceResult, PolicyViolationResult
from shared.regional_policies import REGIONAL_POLICIES
from shared.regional_policies.base import (
    get_regional_severity, get_strictest_severity, RegionalPolicy,
)


# ---------------------------------------------------------------------------
# Axis 1: Compliance (content policy violations, excludes disclosure)
# ---------------------------------------------------------------------------

def _match_sub_rule(
    category: PolicyCategory,
    evidence_text: str,
    policy: RegionalPolicy,
) -> str | None:
    """Match violation evidence text against regional sub-rule keywords."""
    entry = policy.policies.get(category)
    if not entry:
        return None
    text_lower = evidence_text.lower()
    best_match = None
    best_priority = -1
    for sr in entry.sub_rules:
        if any(kw.lower() in text_lower for kw in sr.keywords):
            priority = SEVERITY_PRIORITY.get(sr.severity, 0)
            if priority > best_priority:
                best_match = sr.name
                best_priority = priority
    return best_match


def _evaluate_compliance(
    violations: list[PolicyViolationResult],
    region: Region,
) -> dict:
    worst_severity = Severity.NONE
    summaries = []

    for v in violations:
        if v.severity == Severity.NONE or v.category == PolicyCategory.DISCLOSURE:
            continue

        effective_severity = v.severity
        if region == Region.GLOBAL:
            matched_sub_rule = None
            for policy in REGIONAL_POLICIES.values():
                for ev in v.violations:
                    combined_text = f"{ev.description} {ev.evidence}"
                    match = _match_sub_rule(v.category, combined_text, policy)
                    if match:
                        matched_sub_rule = match
                        break
            strictest_sev = get_strictest_severity(v.category, matched_sub_rule, REGIONAL_POLICIES)
            if SEVERITY_PRIORITY[strictest_sev] > SEVERITY_PRIORITY[effective_severity]:
                effective_severity = strictest_sev
        elif region.value in REGIONAL_POLICIES:
            policy = REGIONAL_POLICIES[region.value]
            matched_sub_rule = None
            for ev in v.violations:
                combined_text = f"{ev.description} {ev.evidence}"
                matched_sub_rule = _match_sub_rule(v.category, combined_text, policy)
                if matched_sub_rule:
                    break
            regional_sev = get_regional_severity(v.category, matched_sub_rule, policy)
            if SEVERITY_PRIORITY[regional_sev] > SEVERITY_PRIORITY[effective_severity]:
                effective_severity = regional_sev

        if SEVERITY_PRIORITY[effective_severity] > SEVERITY_PRIORITY[worst_severity]:
            worst_severity = effective_severity

        for ev in v.violations:
            t_start = f"{int(ev.timestamp_start // 60):02d}:{int(ev.timestamp_start % 60):02d}"
            t_end = f"{int(ev.timestamp_end // 60):02d}:{int(ev.timestamp_end % 60):02d}"
            summaries.append(
                f"{v.category.value} ({effective_severity.value}) "
                f"at {t_start}-{t_end}: {ev.description}"
            )

    if worst_severity == Severity.NONE:
        return {"status": "PASS", "severity": worst_severity, "reasoning": "No policy violations detected.", "details": summaries}
    elif worst_severity in (Severity.HIGH, Severity.CRITICAL):
        return {"status": "BLOCK", "severity": worst_severity, "reasoning": f"Clear policy violation ({worst_severity.value}): " + "; ".join(summaries), "details": summaries}
    else:
        return {"status": "REVIEW", "severity": worst_severity, "reasoning": f"Possible policy concern ({worst_severity.value}): " + "; ".join(summaries), "details": summaries}


# ---------------------------------------------------------------------------
# Axis 2: Product relevance (on-brief / off-brief)
# ---------------------------------------------------------------------------

def _evaluate_product(
    relevance: CampaignRelevanceResult,
) -> dict:
    score = relevance.score
    label = relevance.label
    product_visible = relevance.product_visible

    if label == RelevanceLabel.OFF_BRIEF:
        return {
            "status": "OFF_BRIEF",
            "reasoning": f"OFF-BRIEF (score: {score:.2f}). {relevance.reasoning} Video does not appear related to the advertised product.",
        }

    if product_visible is False:
        return {
            "status": "NOT_VISIBLE",
            "reasoning": f"Product not visually present (score: {score:.2f}, label: {label.value}). {relevance.reasoning} Add clear product visuals or branding.",
        }

    if label == RelevanceLabel.BORDERLINE:
        return {
            "status": "BORDERLINE",
            "reasoning": f"BORDERLINE relevance (score: {score:.2f}). {relevance.reasoning} Consider adding clearer product visuals or descriptions.",
        }

    return {
        "status": "ON_BRIEF",
        "reasoning": f"Product clearly identified (score: {score:.2f}). {relevance.reasoning}",
    }


# ---------------------------------------------------------------------------
# Axis 3: Disclosure (ad labeling)
# ---------------------------------------------------------------------------

def _evaluate_disclosure(
    violations: list[PolicyViolationResult],
    description: str = "",
) -> dict:
    # First check if description mentions disclosure IS present
    if description:
        desc_lower = description.lower()
        _positive_keywords = [
            "#ad", "#광고", "#pr", "#sponsored", "#advertisement",
            "paid partnership", "유료광고", "협찬", "광고 포함",
            "広告", "プロモーション", "广告", "推广",
            "ad disclosure", "disclosure present", "disclosure visible",
            "labeled as ad", "marked as ad", "identified as ad",
        ]
        if any(kw in desc_lower for kw in _positive_keywords):
            return {
                "status": "PRESENT",
                "reasoning": "Ad disclosure detected in video content.",
            }

    issues = []

    for v in violations:
        if v.category == PolicyCategory.DISCLOSURE and v.severity != Severity.NONE:
            if v.violations:
                for ev in v.violations:
                    issues.append(ev.description)
            else:
                issues.append("Ad disclosure violation detected.")

    if not issues and description:
        desc_lower = description.lower()
        _keywords = [
            "no disclosure", "lacks disclosure", "missing disclosure",
            "no #ad", "missing #ad", "lacks any disclosure",
            "no ad label", "no advertisement label",
            "undisclosed", "without disclosure", "without any disclosure",
        ]
        if any(kw in desc_lower for kw in _keywords):
            issues.append("Video description indicates missing ad disclosure.")

    if issues:
        return {
            "status": "MISSING",
            "reasoning": "Ad disclosure missing: " + "; ".join(issues) + " Add '#ad', '#sponsored', or equivalent label.",
        }

    return {
        "status": "PRESENT",
        "reasoning": "Ad disclosure is present or not required.",
    }


# ---------------------------------------------------------------------------
# Final campaign decision
# ---------------------------------------------------------------------------

def make_split_decision(
    relevance: CampaignRelevanceResult,
    violations: list[PolicyViolationResult],
    region: Region = Region.GLOBAL,
    description: str = "",
) -> dict:
    """Evaluate all three axes and produce a single APPROVE/REVIEW/BLOCK decision."""
    compliance = _evaluate_compliance(violations, region)
    product = _evaluate_product(relevance)
    disclosure = _evaluate_disclosure(violations, description)

    # --- Decision logic ---
    review_reasons = []

    # Compliance: clear violation -> BLOCK
    if compliance["status"] == "BLOCK":
        decision = Decision.BLOCK
        decision_reasoning = f"BLOCK: {compliance['reasoning']}"
        if product["status"] != "ON_BRIEF":
            decision_reasoning += f" Additionally, product is {product['status'].lower()}."
        if disclosure["status"] == "MISSING":
            decision_reasoning += f" {disclosure['reasoning']}"
        return _build_result(decision, decision_reasoning, compliance, product, disclosure)

    # Compliance: uncertain -> REVIEW
    if compliance["status"] == "REVIEW":
        review_reasons.append(f"Compliance concern: {compliance['reasoning']}")

    # Product: not on-brief -> REVIEW
    if product["status"] != "ON_BRIEF":
        review_reasons.append(f"Product: {product['reasoning']}")

    # Disclosure: missing -> REVIEW
    if disclosure["status"] == "MISSING":
        review_reasons.append(f"Disclosure: {disclosure['reasoning']}")

    if review_reasons:
        decision = Decision.REVIEW
        decision_reasoning = "REVIEW: " + " | ".join(review_reasons)
    else:
        decision = Decision.APPROVE
        decision_reasoning = "APPROVE: No compliance violations, product on-brief, disclosure present."

    return _build_result(decision, decision_reasoning, compliance, product, disclosure)


def _build_result(
    decision: Decision,
    decision_reasoning: str,
    compliance: dict,
    product: dict,
    disclosure: dict,
) -> dict:
    return {
        "decision": decision,
        "decision_reasoning": decision_reasoning,
        "compliance": compliance,
        "product": product,
        "disclosure": disclosure,
    }


def make_decision(
    relevance: CampaignRelevanceResult,
    violations: list[PolicyViolationResult],
    region: Region = Region.GLOBAL,
    description: str = "",
) -> tuple[Decision, str]:
    """Legacy interface returning (Decision, reasoning) tuple."""
    result = make_split_decision(relevance, violations, region, description)
    return result["decision"], result["decision_reasoning"]
