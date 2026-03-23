from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecommendationConfig:
    recommendation_method_version: str = "rule_rec_v1"
    ranking_weight: float = 0.55
    ielts_fit_weight: float = 0.35
    completeness_weight: float = 0.10
    ranking_rank_cap: int = 500
    ielts_gap_tolerance: float = 2.0
    allow_missing_ielts_requirement: bool = False
    completeness_requires_ielts: bool = False
    max_limit: int = 50


def default_recommendation_config() -> RecommendationConfig:
    return RecommendationConfig(
        recommendation_method_version="rule_rec_v1",
        ranking_weight=0.55,
        ielts_fit_weight=0.35,
        completeness_weight=0.10,
        ranking_rank_cap=500,
        ielts_gap_tolerance=2.0,
        allow_missing_ielts_requirement=False,
        completeness_requires_ielts=False,
        max_limit=50,
    )
