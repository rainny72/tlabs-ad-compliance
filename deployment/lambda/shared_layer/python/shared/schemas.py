"""Shared data schemas used across all sub-projects."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from shared.constants import (
    Decision,
    Modality,
    PolicyCategory,
    Region,
    RelevanceLabel,
    Severity,
)


# --- Ground Truth schemas (Sub-Project 1 output / Sub-Project 3 input) ---


class RegionalDecision(BaseModel):
    global_decision: Decision = Field(alias="global")
    north_america: Decision
    western_europe: Decision
    east_asia: Decision

    model_config = {"populate_by_name": True}


class RegionalSeverity(BaseModel):
    north_america: Severity = Severity.NONE
    western_europe: Severity = Severity.NONE
    east_asia: Severity = Severity.NONE


class ExpectedViolation(BaseModel):
    category: PolicyCategory
    expected_severity: RegionalSeverity
    timestamp_range: list[float] = Field(description="[start_sec, end_sec]")
    modality: Modality
    description: str


class ExpectedRelevance(BaseModel):
    label: RelevanceLabel
    score_range: list[float] = Field(description="[min, max]")


class GroundTruthItem(BaseModel):
    video_file: str
    scenario_id: str
    tier: str
    scenario_name: str
    language: str
    expected_decision: RegionalDecision
    expected_relevance: ExpectedRelevance
    expected_violations: list[ExpectedViolation] = []
    description: str


class GroundTruthDataset(BaseModel):
    videos: list[GroundTruthItem]


# --- Demo system output schemas (Sub-Project 2 output / Sub-Project 3 input) ---


class SearchEvidence(BaseModel):
    query: str
    top_score: float
    matched_segments: int


class ViolationEvidence(BaseModel):
    description: str
    timestamp_start: float
    timestamp_end: float
    modality: Modality
    evidence: str
    evidence_original: Optional[str] = None
    search_confidence: Optional[str] = None
    transcription: Optional[str] = None


class PolicyViolationResult(BaseModel):
    category: PolicyCategory
    severity: Severity
    violations: list[ViolationEvidence] = []


class CampaignRelevanceResult(BaseModel):
    score: float
    label: RelevanceLabel
    product_visible: Optional[bool] = None
    reasoning: str
    search_evidence: list[SearchEvidence] = []


class ComplianceReport(BaseModel):
    video_id: str
    video_file: str
    region: Region
    description: str
    campaign_relevance: CampaignRelevanceResult
    policy_violations: list[PolicyViolationResult] = []
    # Campaign decision
    decision: Decision = Decision.APPROVE
    decision_reasoning: str = ""
    # Three evaluation axes (stored for UI detail display)
    compliance: dict = {}
    product: dict = {}
    disclosure: dict = {}
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


# --- Verification schemas (Sub-Project 3 output) ---


class CategoryMetrics(BaseModel):
    precision: float
    recall: float
    f1: float
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0


class ConfusionMatrix(BaseModel):
    labels: list[str] = ["APPROVE", "REVIEW", "BLOCK"]
    matrix: list[list[int]]


class ErrorCase(BaseModel):
    video_file: str
    scenario_id: str
    region: str
    expected_decision: str
    actual_decision: str
    error_type: str
    details: str


class EvaluationSummary(BaseModel):
    total_videos: int
    total_evaluations: int
    global_accuracy: float
    per_region_accuracy: dict[str, float]
    per_category_metrics: dict[str, CategoryMetrics]
    confusion_matrices: dict[str, ConfusionMatrix]
    error_cases: list[ErrorCase] = []
    recommendations: list[str] = []
