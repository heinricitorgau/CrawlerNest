from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class RecommendationQuery:
    country: Optional[str] = None
    ielts_score: Optional[float] = None
    target_rank: Optional[int] = None
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
    effective_rank_used: Optional[int]
    effective_rank_source: str
    rules_passed: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RecommendationResult:
    canonical_university_id: int
    university_name: str
    country: Optional[str]
    aggregated_rank: Optional[int]
    ielts_min: Optional[float]
    matching_score: float
    explanation: str
    score_breakdown: RecommendationScoreBreakdown
    aggregation_method_version: Optional[str] = None
