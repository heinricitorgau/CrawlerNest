from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecommendationConfig:
    recommendation_method_version: str = "rule_rec_v1"
    ranking_weight: float = 0.75
    ielts_fit_weight: float = 0.20
    completeness_weight: float = 0.10
    v2_ranking_weight: float = 0.45
    v2_ielts_fit_weight: float = 0.20
    v2_confidence_weight: float = 0.20
    v2_risk_alignment_weight: float = 0.15
    v3_ranking_weight: float = 0.50
    v3_ielts_fit_weight: float = 0.20
    v3_confidence_weight: float = 0.20
    v3_country_match_weight: float = 0.10
    v3_ranking_min_weight: float = 0.40
    confidence_weight: float = 0.20
    risk_alignment_weight: float = 0.15
    ranking_rank_cap: int = 500
    ranking_top10_floor: float = 90.0
    ranking_top50_floor: float = 55.0
    ranking_tail_decay: float = 0.01
    ielts_optimal_band: float = 0.5
    ielts_saturation_gap: float = 1.0
    ielts_saturation_score: float = 94.0
    allow_missing_ielts_requirement: bool = False
    completeness_requires_ielts: bool = False
    max_limit: int = 50
    reach_ratio_upper: float = 0.8
    target_ratio_upper: float = 1.2
    conservative_reach_adjustment: float = -0.1
    conservative_target_adjustment: float = -0.1
    aggressive_reach_adjustment: float = 0.1
    aggressive_target_adjustment: float = 0.15
    low_confidence_threshold: float = 60.0
    very_low_confidence_threshold: float = 45.0
    missing_source_penalty: float = 12.0
    source_agreement_weight: float = 0.35
    completeness_confidence_weight: float = 0.65
    conservative_safety_boost: float = 8.0
    conservative_target_boost: float = 2.0
    conservative_reach_penalty: float = -10.0
    balanced_reach_boost: float = 2.0
    balanced_target_boost: float = 4.0
    balanced_safety_boost: float = 1.0
    aggressive_reach_boost: float = 9.0
    aggressive_target_boost: float = 3.0
    aggressive_safety_penalty: float = -6.0


def default_recommendation_config() -> RecommendationConfig:
    return RecommendationConfig(
        recommendation_method_version="rule_rec_v2",
        ranking_weight=0.75,
        ielts_fit_weight=0.20,
        completeness_weight=0.05,
        v2_ranking_weight=0.45,
        v2_ielts_fit_weight=0.20,
        v2_confidence_weight=0.20,
        v2_risk_alignment_weight=0.15,
        v3_ranking_weight=0.50,
        v3_ielts_fit_weight=0.20,
        v3_confidence_weight=0.20,
        v3_country_match_weight=0.10,
        v3_ranking_min_weight=0.40,
        confidence_weight=0.20,
        risk_alignment_weight=0.15,
        ranking_rank_cap=500,
        ranking_top10_floor=90.0,
        ranking_top50_floor=55.0,
        ranking_tail_decay=0.01,
        ielts_optimal_band=0.5,
        ielts_saturation_gap=1.0,
        ielts_saturation_score=94.0,
        allow_missing_ielts_requirement=False,
        completeness_requires_ielts=False,
        max_limit=50,
        reach_ratio_upper=0.8,
        target_ratio_upper=1.2,
        conservative_reach_adjustment=-0.1,
        conservative_target_adjustment=-0.1,
        aggressive_reach_adjustment=0.1,
        aggressive_target_adjustment=0.15,
        low_confidence_threshold=60.0,
        very_low_confidence_threshold=45.0,
        missing_source_penalty=12.0,
        source_agreement_weight=0.35,
        completeness_confidence_weight=0.65,
        conservative_safety_boost=8.0,
        conservative_target_boost=2.0,
        conservative_reach_penalty=-10.0,
        balanced_reach_boost=2.0,
        balanced_target_boost=4.0,
        balanced_safety_boost=1.0,
        aggressive_reach_boost=9.0,
        aggressive_target_boost=3.0,
        aggressive_safety_penalty=-6.0,
    )
