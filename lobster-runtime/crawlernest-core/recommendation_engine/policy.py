from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .config import RecommendationConfig

RISK_PROFILES = {"conservative", "balanced", "aggressive"}
COUNTRY_POLICY_MODES = {"hard_filter", "soft_preference"}
PREFERENCE_WEIGHT_KEYS = ("ranking", "ielts", "confidence", "country_match")


@dataclass(frozen=True)
class CategoryDecision:
    category: str
    reason: str


def normalize_risk_profile(value: Optional[str]) -> str:
    cleaned = (value or "balanced").strip().lower()
    return cleaned if cleaned in RISK_PROFILES else "balanced"


def normalize_country_policy(value: Optional[str], default: str = "hard_filter") -> str:
    cleaned = (value or default).strip().lower()
    return cleaned if cleaned in COUNTRY_POLICY_MODES else default


def resolve_preference_weights(config: RecommendationConfig, raw_weights: dict[str, float]) -> dict[str, float]:
    merged = {
        "ranking": max(0.0, float(config.v3_ranking_weight)),
        "ielts": max(0.0, float(config.v3_ielts_fit_weight)),
        "confidence": max(0.0, float(config.v3_confidence_weight)),
        "country_match": max(0.0, float(config.v3_country_match_weight)),
    }
    for key, value in (raw_weights or {}).items():
        if key not in merged:
            continue
        try:
            merged[key] = max(0.0, float(value))
        except (TypeError, ValueError):
            continue

    total = sum(merged.values())
    if total <= 0:
        merged = {"ranking": 0.5, "ielts": 0.2, "confidence": 0.2, "country_match": 0.1}
        total = 1.0
    normalized = {key: value / total for key, value in merged.items()}

    min_ranking = max(0.0, min(1.0, float(config.v3_ranking_min_weight)))
    max_other = max(normalized[key] for key in normalized if key != "ranking")
    target_ranking = min(0.85, max(normalized["ranking"], min_ranking, max_other + 0.01))
    if target_ranking > normalized["ranking"]:
        other_total = sum(normalized[key] for key in normalized if key != "ranking")
        normalized["ranking"] = target_ranking
        remaining = max(0.0, 1.0 - target_ranking)
        for key in normalized:
            if key == "ranking":
                continue
            share = 0.0 if other_total <= 0 else normalized[key] / other_total
            normalized[key] = remaining * share
    return {key: round(normalized[key], 4) for key in PREFERENCE_WEIGHT_KEYS}


def category_thresholds(config: RecommendationConfig, risk_profile: Optional[str]) -> tuple[float, float]:
    profile = normalize_risk_profile(risk_profile)
    if profile == "conservative":
        return (
            max(0.2, config.reach_ratio_upper + config.conservative_reach_adjustment),
            max(0.6, config.target_ratio_upper + config.conservative_target_adjustment),
        )
    if profile == "aggressive":
        return (
            config.reach_ratio_upper + config.aggressive_reach_adjustment,
            config.target_ratio_upper + config.aggressive_target_adjustment,
        )
    return config.reach_ratio_upper, config.target_ratio_upper


def shift_riskier(category: str) -> str:
    if category == "safety":
        return "target"
    return "reach"


def classify_category(
    *,
    effective_rank: int,
    target_rank: int,
    risk_profile: Optional[str],
    confidence_score: float,
    low_confidence_threshold: float,
    very_low_confidence_threshold: float,
    ielts_margin: Optional[float],
    ielts_shortfall_risk_shift_threshold: float,
    thresholds: tuple[float, float],
) -> CategoryDecision:
    ratio = effective_rank / max(1.0, float(target_rank))
    reach_upper, target_upper = thresholds
    category = "target"
    if ratio < reach_upper:
        category = "reach"
    elif ratio > target_upper:
        category = "safety"

    if ielts_margin is not None and ielts_margin <= -abs(ielts_shortfall_risk_shift_threshold):
        category = shift_riskier(category)

    if category == "reach":
        reason = f"Reach: rank #{effective_rank} is clearly above your target level of #{target_rank}."
    elif category == "safety":
        reason = f"Safety: rank #{effective_rank} is comfortably below your target level of #{target_rank}."
    else:
        reason = f"Target: rank #{effective_rank} is close to your target level of #{target_rank}."

    if ielts_margin is not None:
        if ielts_margin <= -abs(ielts_shortfall_risk_shift_threshold):
            reason += f" IELTS is short by {abs(ielts_margin):.2f}, which makes it riskier."
        elif ielts_margin < 0:
            reason += f" IELTS is slightly short by {abs(ielts_margin):.2f}."
        else:
            reason += f" IELTS margin is {ielts_margin:.2f}."
    if confidence_score < low_confidence_threshold:
        reason += f" Confidence is only {confidence_score:.2f}/100."
    return CategoryDecision(category=category, reason=reason)


def country_match_score(candidate_country: Optional[str], preferred_country: Optional[str]) -> float:
    if not preferred_country:
        return 55.0
    if not candidate_country:
        return 25.0
    if candidate_country.strip().lower() == preferred_country.strip().lower():
        return 100.0
    return 10.0


def preference_alignment(country_match: float, risk_adjustment: float, preferred_country: Optional[str]) -> str:
    signals: list[float] = [60.0 + risk_adjustment]
    if preferred_country:
        signals.append(country_match)
    average = sum(signals) / len(signals)
    if average >= 78:
        return "strong"
    if average >= 55:
        return "moderate"
    return "low"


def risk_adjustment(config: RecommendationConfig, category: str, risk_profile: Optional[str]) -> float:
    profile = normalize_risk_profile(risk_profile)
    matrix = {
        "conservative": {
            "reach": config.conservative_reach_penalty,
            "target": config.conservative_target_boost,
            "safety": config.conservative_safety_boost,
        },
        "balanced": {
            "reach": config.balanced_reach_boost,
            "target": config.balanced_target_boost,
            "safety": config.balanced_safety_boost,
        },
        "aggressive": {
            "reach": config.aggressive_reach_boost,
            "target": config.aggressive_target_boost,
            "safety": config.aggressive_safety_penalty,
        },
    }
    return float(matrix[profile][category])


def weighted_score(weights: dict[str, float], scores: dict[str, Optional[float]]) -> float:
    weighted_sum = 0.0
    weight_sum = 0.0
    for key, weight in weights.items():
        score = scores.get(key)
        if score is None or weight <= 0:
            continue
        weighted_sum += weight * score
        weight_sum += weight
    if weight_sum <= 0:
        return 0.0
    return weighted_sum / weight_sum
