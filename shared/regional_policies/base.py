"""Base regional policy interface and helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

from shared.constants import PolicyCategory, Region, Severity, SEVERITY_PRIORITY


@dataclass
class SubCategoryRule:
    """A fine-grained rule within a policy category."""
    name: str
    description: str
    severity: Severity
    keywords: list[str] = field(default_factory=list)


@dataclass
class RegionalPolicyEntry:
    """Policy entry for a single category in a specific region."""
    category: PolicyCategory
    default_severity: Severity
    sub_rules: list[SubCategoryRule] = field(default_factory=list)
    notes: str = ""


@dataclass
class RegionalPolicy:
    """Full policy set for a region."""
    region: Region
    display_name: str
    regulatory_bodies: list[str]
    policies: dict[PolicyCategory, RegionalPolicyEntry]


def get_regional_severity(
    category: PolicyCategory,
    sub_rule_name: str | None,
    policy: RegionalPolicy,
) -> Severity:
    """Get severity for a category (optionally sub-rule) under a regional policy."""
    entry = policy.policies.get(category)
    if entry is None:
        return Severity.NONE
    if sub_rule_name:
        for sr in entry.sub_rules:
            if sr.name == sub_rule_name:
                return sr.severity
    return entry.default_severity


def get_strictest_severity(
    category: PolicyCategory,
    sub_rule_name: str | None,
    policies: dict[str, RegionalPolicy],
) -> Severity:
    """Return the highest severity across all regions for a given violation."""
    worst = Severity.NONE
    for policy in policies.values():
        s = get_regional_severity(category, sub_rule_name, policy)
        if SEVERITY_PRIORITY[s] > SEVERITY_PRIORITY[worst]:
            worst = s
    return worst
