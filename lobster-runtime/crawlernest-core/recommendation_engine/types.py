from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class RecommendationQuery:
    country: Optional[str] = None
    country_policy: Optional[str] = None
    ielts_score: Optional[float] = None
    target_rank: Optional[int] = None
    risk_profile: Optional[str] = None
    preference_weights: dict[str, float] = field(default_factory=dict)
    preferred_ranking_source: Optional[str] = None
    limit: int = 10
    ranking_year: Optional[int] = None


@dataclass(frozen=True)
class RecommendationCandidate:
    canonical_university_id: int
    university_name: str
    country: Optional[str]
    ranking_year: Optional[int]
    aggregated_rank: Optional[int]
    aggregated_score: Optional[float]
    coverage_ratio: float = 0.0
    ielts_min: Optional[float] = None
    source_ranks: dict[str, Optional[int]] = field(default_factory=dict)
    source_scores: dict[str, Optional[float]] = field(default_factory=dict)
    aggregation_method_version: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecommendationScoreBreakdown:
    ranking_score: Optional[float]
    ielts_fit_score: Optional[float]
    completeness_score: Optional[float]
    weights_used: dict[str, float]
    contributions: dict[str, float]
    effective_rank_used: Optional[int]
    effective_rank_source: str
    confidence_score: Optional[float] = None
    risk_alignment_score: Optional[float] = None
    category: Optional[str] = None
    category_reason: Optional[str] = None
    ielts_margin: Optional[float] = None
    confidence_label: Optional[str] = None
    country_match_score: Optional[float] = None
    preference_alignment: Optional[str] = None
    base_score: Optional[float] = None
    risk_adjustment: Optional[float] = None
    recommendation_confidence: Optional[float] = None
    confidence_reason: Optional[str] = None
    scoring_version: Optional[str] = None
    decision_policy_version: Optional[str] = None
    explanation_version: Optional[str] = None
    filter_reasons: list[str] = field(default_factory=list)
    rules_passed: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RecommendationResult:
    canonical_university_id: int
    university_name: str
    country: Optional[str]
    aggregated_rank: Optional[int]
    ielts_min: Optional[float]
    matching_score: float
    category: Optional[str]
    preference_alignment: Optional[str]
    recommendation_confidence: Optional[float]
    confidence_reason: Optional[str]
    scoring_version: Optional[str]
    decision_policy_version: Optional[str]
    explanation_version: Optional[str]
    explanation: str
    score_breakdown: RecommendationScoreBreakdown
    aggregation_method_version: Optional[str] = None


@dataclass(frozen=True)
class GroupedRecommendationResult:
    reach: list[RecommendationResult] = field(default_factory=list)
    target: list[RecommendationResult] = field(default_factory=list)
    safety: list[RecommendationResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
