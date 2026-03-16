"""Policy categories, severity levels, and region constants."""

from enum import Enum


class Region(str, Enum):
    GLOBAL = "global"
    NORTH_AMERICA = "north_america"
    WESTERN_EUROPE = "western_europe"
    EAST_ASIA = "east_asia"


class Severity(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Decision(str, Enum):
    """Legacy combined decision (kept for backward compatibility)."""
    APPROVE = "APPROVE"
    REVIEW = "REVIEW"
    BLOCK = "BLOCK"


class ComplianceDecision(str, Enum):
    """Policy compliance result — violation-only assessment."""
    PASS = "PASS"
    BLOCK = "BLOCK"


class ProductAssessment(str, Enum):
    """Product/campaign relevance assessment."""
    CLEAR = "CLEAR"
    SUPPLEMENT_NEEDED = "SUPPLEMENT_NEEDED"
    OFF_BRIEF = "OFF_BRIEF"


class PolicyCategory(str, Enum):
    HATE_HARASSMENT = "hate_harassment"
    PROFANITY_EXPLICIT = "profanity_explicit"
    DRUGS_ILLEGAL = "drugs_illegal"
    UNSAFE_MISLEADING_USAGE = "unsafe_misleading_usage"
    MEDICAL_COSMETIC_CLAIMS = "medical_cosmetic_claims"
    DISCLOSURE = "disclosure"


class RelevanceLabel(str, Enum):
    ON_BRIEF = "ON_BRIEF"
    OFF_BRIEF = "OFF_BRIEF"
    BORDERLINE = "BORDERLINE"


class Modality(str, Enum):
    VISUAL = "visual"
    SPEECH = "speech"
    TEXT_ON_SCREEN = "text_on_screen"


SEVERITY_PRIORITY = {
    Severity.CRITICAL: 4,
    Severity.HIGH: 3,
    Severity.MEDIUM: 2,
    Severity.LOW: 1,
    Severity.NONE: 0,
}

RELEVANCE_THRESHOLD = 0.5
RELEVANCE_BORDERLINE_LOW = 0.4
RELEVANCE_BORDERLINE_HIGH = 0.6
