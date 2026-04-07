from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RecommendationConfig:
    config_version: str = "decision_config_v1"
    scoring_version: str = "hybrid_scoring_v3"
    decision_policy_version: str = "decision_policy_v2"
    explanation_version: str = "explanation_templates_v2"
    recommendation_method_version: str = "rule_rec_v1"
    country_match_policy: str = "hard_filter"
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
    reach_ratio_upper: float = 0.7
    target_ratio_upper: float = 1.35
    elite_pool_target_rank_cap: int = 200
    elite_pool_rank_ceiling_ratio: float = 0.5
    elite_pool_min_size: int = 4
    conservative_reach_adjustment: float = -0.1
    conservative_target_adjustment: float = -0.15
    aggressive_reach_adjustment: float = 0.12
    aggressive_target_adjustment: float = 0.2
    ielts_shortfall_risk_shift_threshold: float = 0.25
    low_confidence_threshold: float = 60.0
    very_low_confidence_threshold: float = 45.0
    missing_source_penalty: float = 12.0
    source_agreement_weight: float = 0.35
    completeness_confidence_weight: float = 0.65
    conservative_safety_boost: float = 1.5
    conservative_target_boost: float = 0.75
    conservative_reach_penalty: float = -2.0
    balanced_reach_boost: float = 0.5
    balanced_target_boost: float = 1.0
    balanced_safety_boost: float = 0.5
    aggressive_reach_boost: float = 2.0
    aggressive_target_boost: float = 0.75
    aggressive_safety_penalty: float = -1.0


def default_recommendation_config() -> RecommendationConfig:
    defaults = RecommendationConfig(
        config_version="decision_config_v1",
        scoring_version="hybrid_scoring_v3",
        decision_policy_version="decision_policy_v2",
        explanation_version="explanation_templates_v2",
        recommendation_method_version="rule_rec_v3",
        country_match_policy="hard_filter",
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
        reach_ratio_upper=0.7,
        target_ratio_upper=1.35,
        elite_pool_target_rank_cap=200,
        elite_pool_rank_ceiling_ratio=0.5,
        elite_pool_min_size=4,
        conservative_reach_adjustment=-0.1,
        conservative_target_adjustment=-0.15,
        aggressive_reach_adjustment=0.12,
        aggressive_target_adjustment=0.2,
        ielts_shortfall_risk_shift_threshold=0.25,
        low_confidence_threshold=60.0,
        very_low_confidence_threshold=45.0,
        missing_source_penalty=12.0,
        source_agreement_weight=0.35,
        completeness_confidence_weight=0.65,
        conservative_safety_boost=1.5,
        conservative_target_boost=0.75,
        conservative_reach_penalty=-2.0,
        balanced_reach_boost=0.5,
        balanced_target_boost=1.0,
        balanced_safety_boost=0.5,
        aggressive_reach_boost=2.0,
        aggressive_target_boost=0.75,
        aggressive_safety_penalty=-1.0,
    )
    return RecommendationConfig(
        config_version=os.getenv("CRAWLERNEST_REC_CONFIG_VERSION", defaults.config_version),
        scoring_version=os.getenv("CRAWLERNEST_REC_SCORING_VERSION", defaults.scoring_version),
        decision_policy_version=os.getenv("CRAWLERNEST_REC_POLICY_VERSION", defaults.decision_policy_version),
        explanation_version=os.getenv("CRAWLERNEST_REC_EXPLANATION_VERSION", defaults.explanation_version),
        recommendation_method_version=os.getenv("CRAWLERNEST_REC_METHOD_VERSION", defaults.recommendation_method_version),
        country_match_policy=os.getenv("CRAWLERNEST_REC_COUNTRY_POLICY", defaults.country_match_policy).strip().lower() or defaults.country_match_policy,
        ranking_weight=_env_float("CRAWLERNEST_REC_RANKING_WEIGHT", defaults.ranking_weight),
        ielts_fit_weight=_env_float("CRAWLERNEST_REC_IELTS_FIT_WEIGHT", defaults.ielts_fit_weight),
        completeness_weight=_env_float("CRAWLERNEST_REC_COMPLETENESS_WEIGHT", defaults.completeness_weight),
        v2_ranking_weight=_env_float("CRAWLERNEST_REC_V2_RANKING_WEIGHT", defaults.v2_ranking_weight),
        v2_ielts_fit_weight=_env_float("CRAWLERNEST_REC_V2_IELTS_WEIGHT", defaults.v2_ielts_fit_weight),
        v2_confidence_weight=_env_float("CRAWLERNEST_REC_V2_CONFIDENCE_WEIGHT", defaults.v2_confidence_weight),
        v2_risk_alignment_weight=_env_float("CRAWLERNEST_REC_V2_RISK_WEIGHT", defaults.v2_risk_alignment_weight),
        v3_ranking_weight=_env_float("CRAWLERNEST_REC_V3_RANKING_WEIGHT", defaults.v3_ranking_weight),
        v3_ielts_fit_weight=_env_float("CRAWLERNEST_REC_V3_IELTS_WEIGHT", defaults.v3_ielts_fit_weight),
        v3_confidence_weight=_env_float("CRAWLERNEST_REC_V3_CONFIDENCE_WEIGHT", defaults.v3_confidence_weight),
        v3_country_match_weight=_env_float("CRAWLERNEST_REC_V3_COUNTRY_WEIGHT", defaults.v3_country_match_weight),
        v3_ranking_min_weight=_env_float("CRAWLERNEST_REC_V3_RANKING_MIN_WEIGHT", defaults.v3_ranking_min_weight),
        confidence_weight=_env_float("CRAWLERNEST_REC_CONFIDENCE_WEIGHT", defaults.confidence_weight),
        risk_alignment_weight=_env_float("CRAWLERNEST_REC_RISK_ALIGNMENT_WEIGHT", defaults.risk_alignment_weight),
        ranking_rank_cap=_env_int("CRAWLERNEST_REC_RANK_CAP", defaults.ranking_rank_cap),
        ranking_top10_floor=_env_float("CRAWLERNEST_REC_TOP10_FLOOR", defaults.ranking_top10_floor),
        ranking_top50_floor=_env_float("CRAWLERNEST_REC_TOP50_FLOOR", defaults.ranking_top50_floor),
        ranking_tail_decay=_env_float("CRAWLERNEST_REC_TAIL_DECAY", defaults.ranking_tail_decay),
        ielts_optimal_band=_env_float("CRAWLERNEST_REC_IELTS_OPTIMAL_BAND", defaults.ielts_optimal_band),
        ielts_saturation_gap=_env_float("CRAWLERNEST_REC_IELTS_SATURATION_GAP", defaults.ielts_saturation_gap),
        ielts_saturation_score=_env_float("CRAWLERNEST_REC_IELTS_SATURATION_SCORE", defaults.ielts_saturation_score),
        allow_missing_ielts_requirement=_env_bool("CRAWLERNEST_REC_ALLOW_MISSING_IELTS", defaults.allow_missing_ielts_requirement),
        completeness_requires_ielts=_env_bool("CRAWLERNEST_REC_COMPLETENESS_REQUIRES_IELTS", defaults.completeness_requires_ielts),
        max_limit=_env_int("CRAWLERNEST_REC_MAX_LIMIT", defaults.max_limit),
        reach_ratio_upper=_env_float("CRAWLERNEST_REC_REACH_UPPER", defaults.reach_ratio_upper),
        target_ratio_upper=_env_float("CRAWLERNEST_REC_TARGET_UPPER", defaults.target_ratio_upper),
        elite_pool_target_rank_cap=_env_int("CRAWLERNEST_REC_ELITE_POOL_TARGET_RANK_CAP", defaults.elite_pool_target_rank_cap),
        elite_pool_rank_ceiling_ratio=_env_float("CRAWLERNEST_REC_ELITE_POOL_RANK_CEILING_RATIO", defaults.elite_pool_rank_ceiling_ratio),
        elite_pool_min_size=_env_int("CRAWLERNEST_REC_ELITE_POOL_MIN_SIZE", defaults.elite_pool_min_size),
        conservative_reach_adjustment=_env_float("CRAWLERNEST_REC_CONSERVATIVE_REACH_ADJUSTMENT", defaults.conservative_reach_adjustment),
        conservative_target_adjustment=_env_float("CRAWLERNEST_REC_CONSERVATIVE_TARGET_ADJUSTMENT", defaults.conservative_target_adjustment),
        aggressive_reach_adjustment=_env_float("CRAWLERNEST_REC_AGGRESSIVE_REACH_ADJUSTMENT", defaults.aggressive_reach_adjustment),
        aggressive_target_adjustment=_env_float("CRAWLERNEST_REC_AGGRESSIVE_TARGET_ADJUSTMENT", defaults.aggressive_target_adjustment),
        ielts_shortfall_risk_shift_threshold=_env_float("CRAWLERNEST_REC_IELTS_SHORTFALL_RISK_SHIFT", defaults.ielts_shortfall_risk_shift_threshold),
        low_confidence_threshold=_env_float("CRAWLERNEST_REC_LOW_CONFIDENCE_THRESHOLD", defaults.low_confidence_threshold),
        very_low_confidence_threshold=_env_float("CRAWLERNEST_REC_VERY_LOW_CONFIDENCE_THRESHOLD", defaults.very_low_confidence_threshold),
        missing_source_penalty=_env_float("CRAWLERNEST_REC_MISSING_SOURCE_PENALTY", defaults.missing_source_penalty),
        source_agreement_weight=_env_float("CRAWLERNEST_REC_SOURCE_AGREEMENT_WEIGHT", defaults.source_agreement_weight),
        completeness_confidence_weight=_env_float("CRAWLERNEST_REC_COMPLETENESS_CONFIDENCE_WEIGHT", defaults.completeness_confidence_weight),
        conservative_safety_boost=_env_float("CRAWLERNEST_REC_CONSERVATIVE_SAFETY_BOOST", defaults.conservative_safety_boost),
        conservative_target_boost=_env_float("CRAWLERNEST_REC_CONSERVATIVE_TARGET_BOOST", defaults.conservative_target_boost),
        conservative_reach_penalty=_env_float("CRAWLERNEST_REC_CONSERVATIVE_REACH_PENALTY", defaults.conservative_reach_penalty),
        balanced_reach_boost=_env_float("CRAWLERNEST_REC_BALANCED_REACH_BOOST", defaults.balanced_reach_boost),
        balanced_target_boost=_env_float("CRAWLERNEST_REC_BALANCED_TARGET_BOOST", defaults.balanced_target_boost),
        balanced_safety_boost=_env_float("CRAWLERNEST_REC_BALANCED_SAFETY_BOOST", defaults.balanced_safety_boost),
        aggressive_reach_boost=_env_float("CRAWLERNEST_REC_AGGRESSIVE_REACH_BOOST", defaults.aggressive_reach_boost),
        aggressive_target_boost=_env_float("CRAWLERNEST_REC_AGGRESSIVE_TARGET_BOOST", defaults.aggressive_target_boost),
        aggressive_safety_penalty=_env_float("CRAWLERNEST_REC_AGGRESSIVE_SAFETY_PENALTY", defaults.aggressive_safety_penalty),
    )


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
