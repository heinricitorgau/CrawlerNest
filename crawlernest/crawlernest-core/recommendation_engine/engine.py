from __future__ import annotations

import math
from dataclasses import asdict
from typing import Iterable, Optional

from .config import RecommendationConfig, default_recommendation_config
from .types import (
    GroupedRecommendationResult,
    RecommendationCandidate,
    RecommendationQuery,
    RecommendationResult,
    RecommendationScoreBreakdown,
)

SOURCE_ORDER = ("QS", "THE", "ARWU")
CATEGORY_ORDER = ("reach", "target", "safety")
RISK_PROFILES = {"conservative", "balanced", "aggressive"}
PREFERENCE_WEIGHT_KEYS = ("ranking", "ielts", "confidence", "country_match")


class RuleBasedRecommender:
    def __init__(self, config: Optional[RecommendationConfig] = None):
        self.config = config or default_recommendation_config()

    def recommend(
        self,
        candidates: Iterable[RecommendationCandidate],
        query: RecommendationQuery,
    ) -> list[RecommendationResult]:
        rows = list(candidates)
        if not rows:
            return []

        filtered: list[RecommendationCandidate] = []
        for row in rows:
            if self._passes_hard_constraints(row, query):
                filtered.append(row)

        scored: list[RecommendationResult] = []
        for row in filtered:
            breakdown = self._score_candidate_v1(row, query)
            if breakdown is None:
                continue
            explanation = self._build_explanation_v1(row, query, breakdown)
            scored.append(
                RecommendationResult(
                    canonical_university_id=row.canonical_university_id,
                    university_name=row.university_name,
                    country=row.country,
                    aggregated_rank=row.aggregated_rank,
                    ielts_min=row.ielts_min,
                    matching_score=self._composite_from_breakdown(breakdown),
                    category=None,
                    preference_alignment=None,
                    explanation=explanation,
                    score_breakdown=breakdown,
                    aggregation_method_version=row.aggregation_method_version,
                )
            )

        scored.sort(
            key=lambda r: (
                -r.matching_score,
                r.aggregated_rank if r.aggregated_rank is not None else 10**9,
                r.canonical_university_id,
            )
        )
        limit = max(1, min(int(query.limit or 10), self.config.max_limit))
        return scored[:limit]

    def recommend_grouped(
        self,
        candidates: Iterable[RecommendationCandidate],
        query: RecommendationQuery,
    ) -> GroupedRecommendationResult:
        if query.target_rank is None or int(query.target_rank) <= 0:
            raise ValueError("target_rank is required for recommendation v2.")

        rows = list(candidates)
        if not rows:
            return GroupedRecommendationResult(metadata=self._metadata(query, {}, 0))

        filtered: list[RecommendationCandidate] = []
        for row in rows:
            if self._passes_v2_filters(row, query):
                filtered.append(row)

        grouped: dict[str, list[RecommendationResult]] = {category: [] for category in CATEGORY_ORDER}
        for row in filtered:
            breakdown = self._score_candidate_v2(row, query)
            if breakdown is None or breakdown.category is None:
                continue
            explanation = self._build_explanation_v2(row, query, breakdown)
            grouped[breakdown.category].append(
                RecommendationResult(
                    canonical_university_id=row.canonical_university_id,
                    university_name=row.university_name,
                    country=row.country,
                    aggregated_rank=row.aggregated_rank,
                    ielts_min=row.ielts_min,
                    matching_score=self._composite_from_breakdown(breakdown),
                    category=breakdown.category,
                    preference_alignment=breakdown.preference_alignment,
                    explanation=explanation,
                    score_breakdown=breakdown,
                    aggregation_method_version=row.aggregation_method_version,
                )
            )

        for category in CATEGORY_ORDER:
            grouped[category].sort(
                key=lambda result: (
                    -result.matching_score,
                    result.aggregated_rank if result.aggregated_rank is not None else 10**9,
                    result.canonical_university_id,
                )
            )
            grouped[category] = grouped[category][: max(1, min(int(query.limit or 10), self.config.max_limit))]

        counts = {category: len(grouped[category]) for category in CATEGORY_ORDER}
        return GroupedRecommendationResult(
            reach=grouped["reach"],
            target=grouped["target"],
            safety=grouped["safety"],
            metadata=self._metadata(query, counts, len(filtered)),
        )

    def recommend_grouped_v3(
        self,
        candidates: Iterable[RecommendationCandidate],
        query: RecommendationQuery,
    ) -> GroupedRecommendationResult:
        if query.target_rank is None or int(query.target_rank) <= 0:
            raise ValueError("target_rank is required for recommendation v3.")

        rows = list(candidates)
        if not rows:
            return GroupedRecommendationResult(metadata=self._metadata_v3(query, {}, 0))

        filtered: list[RecommendationCandidate] = []
        for row in rows:
            if self._passes_v3_filters(row):
                filtered.append(row)

        grouped: dict[str, list[RecommendationResult]] = {category: [] for category in CATEGORY_ORDER}
        for row in filtered:
            breakdown = self._score_candidate_v3(row, query)
            if breakdown is None or breakdown.category is None:
                continue
            explanation = self._build_explanation_v3(row, query, breakdown)
            grouped[breakdown.category].append(
                RecommendationResult(
                    canonical_university_id=row.canonical_university_id,
                    university_name=row.university_name,
                    country=row.country,
                    aggregated_rank=row.aggregated_rank,
                    ielts_min=row.ielts_min,
                    matching_score=self._composite_from_breakdown_v3(breakdown),
                    category=breakdown.category,
                    preference_alignment=breakdown.preference_alignment,
                    explanation=explanation,
                    score_breakdown=breakdown,
                    aggregation_method_version=row.aggregation_method_version,
                )
            )

        for category in CATEGORY_ORDER:
            grouped[category].sort(
                key=lambda result: (
                    -result.matching_score,
                    result.aggregated_rank if result.aggregated_rank is not None else 10**9,
                    result.canonical_university_id,
                )
            )
            grouped[category] = grouped[category][: max(1, min(int(query.limit or 10), self.config.max_limit))]

        counts = {category: len(grouped[category]) for category in CATEGORY_ORDER}
        return GroupedRecommendationResult(
            reach=grouped["reach"],
            target=grouped["target"],
            safety=grouped["safety"],
            metadata=self._metadata_v3(query, counts, len(filtered)),
        )

    def _metadata(
        self,
        query: RecommendationQuery,
        counts: dict[str, int],
        candidate_count: int,
    ) -> dict[str, object]:
        return {
            "target_rank": query.target_rank,
            "risk_profile": self._normalize_risk_profile(query.risk_profile),
            "country": query.country,
            "ielts_score": query.ielts_score,
            "candidate_count": candidate_count,
            "counts": counts,
            "thresholds": {
                "balanced": {
                    "reach_upper": self.config.reach_ratio_upper,
                    "target_upper": self.config.target_ratio_upper,
                },
                "conservative": {
                    "reach_upper": self.config.reach_ratio_upper + self.config.conservative_reach_adjustment,
                    "target_upper": self.config.target_ratio_upper + self.config.conservative_target_adjustment,
                },
                "aggressive": {
                    "reach_upper": self.config.reach_ratio_upper + self.config.aggressive_reach_adjustment,
                    "target_upper": self.config.target_ratio_upper + self.config.aggressive_target_adjustment,
                },
            },
        }

    def _metadata_v3(
        self,
        query: RecommendationQuery,
        counts: dict[str, int],
        candidate_count: int,
    ) -> dict[str, object]:
        metadata = self._metadata(query, counts, candidate_count)
        metadata["version"] = "v3"
        metadata["preference_weights"] = self._resolve_preference_weights(query)
        metadata["country_preference_mode"] = "soft_preference" if query.country else "none"
        return metadata

    def _passes_hard_constraints(self, row: RecommendationCandidate, query: RecommendationQuery) -> bool:
        if query.country:
            if (row.country or "").strip().lower() != query.country.strip().lower():
                return False

        effective_rank, _ = self._choose_effective_rank(row, query)
        if query.target_rank is not None:
            if effective_rank is None or effective_rank > int(query.target_rank):
                return False

        if query.ielts_score is not None:
            if row.ielts_min is None:
                return bool(self.config.allow_missing_ielts_requirement)
            if float(query.ielts_score) + 1e-9 < float(row.ielts_min):
                return False

        return True

    def _passes_v2_filters(self, row: RecommendationCandidate, query: RecommendationQuery) -> bool:
        if query.country and (row.country or "").strip().lower() != query.country.strip().lower():
            return False
        effective_rank, _ = self._choose_effective_rank(row, query)
        return effective_rank is not None

    def _passes_v3_filters(self, row: RecommendationCandidate) -> bool:
        return row.aggregated_rank is not None or any(rank is not None for rank in row.source_ranks.values())

    def _score_candidate_v1(
        self,
        row: RecommendationCandidate,
        query: RecommendationQuery,
    ) -> Optional[RecommendationScoreBreakdown]:
        effective_rank, effective_rank_source = self._choose_effective_rank(row, query)
        ranking_score = self._ranking_score(effective_rank, query)
        ielts_fit_score = self._ielts_fit_score(row.ielts_min, query.ielts_score)
        completeness_score = self._completeness_score(row)

        component_weights = {
            "ranking": max(0.0, float(self.config.ranking_weight)),
            "ielts_fit": max(0.0, float(self.config.ielts_fit_weight)),
            "completeness": max(0.0, float(self.config.completeness_weight)),
        }

        available_scores = {
            "ranking": ranking_score,
            "ielts_fit": ielts_fit_score,
            "completeness": completeness_score,
        }
        used_weights = {
            name: weight
            for name, weight in component_weights.items()
            if weight > 0 and available_scores[name] is not None
        }
        if not used_weights:
            return None

        contributions = self._component_contributions(used_weights, available_scores)
        rules_passed: list[str] = []
        if query.country:
            rules_passed.append(f"country={query.country}")
        if query.target_rank is not None and effective_rank is not None:
            rules_passed.append(f"rank<={query.target_rank} via {effective_rank_source} ({effective_rank})")
        if query.ielts_score is not None and row.ielts_min is not None:
            rules_passed.append(f"IELTS {query.ielts_score} >= required {row.ielts_min}")
        elif query.ielts_score is None:
            rules_passed.append("IELTS filter not applied")

        return RecommendationScoreBreakdown(
            ranking_score=round(ranking_score, 4) if ranking_score is not None else None,
            ielts_fit_score=round(ielts_fit_score, 4) if ielts_fit_score is not None else None,
            completeness_score=round(completeness_score, 4) if completeness_score is not None else None,
            weights_used=used_weights,
            contributions=contributions,
            effective_rank_used=effective_rank,
            effective_rank_source=effective_rank_source,
            rules_passed=rules_passed,
        )

    def _score_candidate_v2(
        self,
        row: RecommendationCandidate,
        query: RecommendationQuery,
    ) -> Optional[RecommendationScoreBreakdown]:
        effective_rank, effective_rank_source = self._choose_effective_rank(row, query)
        if effective_rank is None:
            return None

        ranking_score = self._ranking_score(effective_rank, query)
        ielts_fit_score = self._ielts_fit_score_v2(row.ielts_min, query.ielts_score)
        completeness_score = self._completeness_score(row)
        confidence_score = self._confidence_score(row, query)
        category, category_reason = self._classify_category(row, query, confidence_score, effective_rank)
        risk_alignment_score = self._risk_alignment_score(category, query.risk_profile)
        ielts_margin = self._ielts_margin(row.ielts_min, query.ielts_score)
        confidence_label = self._confidence_label(confidence_score)

        available_scores = {
            "ranking": ranking_score,
            "ielts_fit": ielts_fit_score,
            "confidence": confidence_score,
            "risk_alignment": risk_alignment_score,
        }
        weights = {
            "ranking": max(0.0, float(self.config.v2_ranking_weight)),
            "ielts_fit": max(0.0, float(self.config.v2_ielts_fit_weight)),
            "confidence": max(0.0, float(self.config.v2_confidence_weight)),
            "risk_alignment": max(0.0, float(self.config.v2_risk_alignment_weight)),
        }
        used_weights = {
            name: weight
            for name, weight in weights.items()
            if weight > 0 and available_scores[name] is not None
        }
        if not used_weights:
            return None

        contributions = self._component_contributions(used_weights, available_scores)
        rules_passed = [
            f"category={category}",
            f"risk_profile={self._normalize_risk_profile(query.risk_profile)}",
            f"confidence={confidence_label}",
        ]
        if row.country:
            rules_passed.append(f"country={row.country}")
        if ielts_margin is not None:
            rules_passed.append(f"ielts_margin={round(ielts_margin, 2)}")
        elif query.ielts_score is None:
            rules_passed.append("IELTS not provided")
        else:
            rules_passed.append("IELTS requirement missing")

        return RecommendationScoreBreakdown(
            ranking_score=round(ranking_score, 4) if ranking_score is not None else None,
            ielts_fit_score=round(ielts_fit_score, 4) if ielts_fit_score is not None else None,
            completeness_score=round(completeness_score, 4) if completeness_score is not None else None,
            confidence_score=round(confidence_score, 4) if confidence_score is not None else None,
            risk_alignment_score=round(risk_alignment_score, 4) if risk_alignment_score is not None else None,
            weights_used=used_weights,
            contributions=contributions,
            effective_rank_used=effective_rank,
            effective_rank_source=effective_rank_source,
            category=category,
            category_reason=category_reason,
            ielts_margin=round(ielts_margin, 4) if ielts_margin is not None else None,
            confidence_label=confidence_label,
            rules_passed=rules_passed,
        )

    def _score_candidate_v3(
        self,
        row: RecommendationCandidate,
        query: RecommendationQuery,
    ) -> Optional[RecommendationScoreBreakdown]:
        effective_rank, effective_rank_source = self._choose_effective_rank(row, query)
        if effective_rank is None:
            return None

        ranking_score = self._ranking_score(effective_rank, query)
        ielts_fit_score = self._ielts_fit_score_v2(row.ielts_min, query.ielts_score)
        completeness_score = self._completeness_score(row)
        confidence_score = self._confidence_score(row, query)
        category, category_reason = self._classify_category(row, query, confidence_score, effective_rank)
        ielts_margin = self._ielts_margin(row.ielts_min, query.ielts_score)
        confidence_label = self._confidence_label(confidence_score)
        country_match_score = self._country_match_score(row.country, query.country)
        weights_used = self._resolve_preference_weights(query)
        available_scores = {
            "ranking": ranking_score,
            "ielts": ielts_fit_score,
            "confidence": confidence_score,
            "country_match": country_match_score,
        }
        contributions = self._component_contributions(weights_used, available_scores)
        base_score = self._weighted_score(weights_used, available_scores)
        risk_adjustment = self._risk_adjustment(category, query.risk_profile)
        final_score = max(0.0, min(100.0, base_score + risk_adjustment))
        preference_alignment = self._preference_alignment(country_match_score, risk_adjustment, query.country)

        rules_passed = [
            "version=v3",
            f"category={category}",
            f"risk_profile={self._normalize_risk_profile(query.risk_profile)}",
            f"preference_alignment={preference_alignment}",
        ]
        if query.country:
            rules_passed.append(f"country_preference={query.country}")
        if ielts_margin is not None:
            rules_passed.append(f"ielts_margin={round(ielts_margin, 2)}")
        elif query.ielts_score is None:
            rules_passed.append("IELTS not provided")
        else:
            rules_passed.append("IELTS requirement missing")

        return RecommendationScoreBreakdown(
            ranking_score=round(ranking_score, 4) if ranking_score is not None else None,
            ielts_fit_score=round(ielts_fit_score, 4) if ielts_fit_score is not None else None,
            completeness_score=round(completeness_score, 4) if completeness_score is not None else None,
            confidence_score=round(confidence_score, 4) if confidence_score is not None else None,
            weights_used=weights_used,
            contributions=contributions,
            effective_rank_used=effective_rank,
            effective_rank_source=effective_rank_source,
            category=category,
            category_reason=category_reason,
            ielts_margin=round(ielts_margin, 4) if ielts_margin is not None else None,
            confidence_label=confidence_label,
            country_match_score=round(country_match_score, 4) if country_match_score is not None else None,
            preference_alignment=preference_alignment,
            base_score=round(base_score, 4),
            risk_adjustment=round(risk_adjustment, 4),
            rules_passed=rules_passed,
        )

    def _composite_from_breakdown(self, breakdown: RecommendationScoreBreakdown) -> float:
        score_map = {
            "ranking": breakdown.ranking_score,
            "ielts_fit": breakdown.ielts_fit_score,
            "completeness": breakdown.completeness_score,
            "confidence": breakdown.confidence_score,
            "risk_alignment": breakdown.risk_alignment_score,
        }
        weighted_sum = 0.0
        weight_sum = 0.0
        for key, weight in breakdown.weights_used.items():
            score = score_map.get(key)
            if score is None or weight <= 0:
                continue
            weighted_sum += weight * score
            weight_sum += weight
        if weight_sum <= 0:
            return 0.0
        return round(weighted_sum / weight_sum, 4)

    def _composite_from_breakdown_v3(self, breakdown: RecommendationScoreBreakdown) -> float:
        if breakdown.base_score is None:
            return 0.0
        return round(max(0.0, min(100.0, breakdown.base_score + (breakdown.risk_adjustment or 0.0))), 4)

    def _component_contributions(
        self,
        used_weights: dict[str, float],
        available_scores: dict[str, Optional[float]],
    ) -> dict[str, float]:
        weight_sum = sum(used_weights.values()) or 1.0
        contributions: dict[str, float] = {}
        for key, weight in used_weights.items():
            score = available_scores.get(key)
            if score is None:
                continue
            contributions[key] = round((weight / weight_sum) * score, 4)
        return contributions

    def _weighted_score(
        self,
        used_weights: dict[str, float],
        available_scores: dict[str, Optional[float]],
    ) -> float:
        weighted_sum = 0.0
        weight_sum = 0.0
        for key, weight in used_weights.items():
            score = available_scores.get(key)
            if score is None or weight <= 0:
                continue
            weighted_sum += weight * score
            weight_sum += weight
        if weight_sum <= 0:
            return 0.0
        return weighted_sum / weight_sum

    def _choose_effective_rank(
        self,
        row: RecommendationCandidate,
        query: RecommendationQuery,
    ) -> tuple[Optional[int], str]:
        preferred = (query.preferred_ranking_source or "").strip().upper()
        if preferred:
            rank = row.source_ranks.get(preferred)
            if rank is not None:
                return int(rank), preferred
        if row.aggregated_rank is not None:
            return int(row.aggregated_rank), "AGGREGATED"
        return None, preferred or "AGGREGATED"

    def _ranking_score(self, rank_value: Optional[int], query: RecommendationQuery) -> Optional[float]:
        if rank_value is None or rank_value <= 0:
            return None
        rank = int(rank_value)
        if query.target_rank:
            ratio = rank / max(1.0, float(query.target_rank))
            ratio_score = max(0.0, min(100.0, 125.0 - 50.0 * ratio))
        else:
            ratio_score = None
        if rank <= 10:
            global_score = 100.0 - 10.0 * math.log10(rank)
        elif rank <= 50:
            mid_progress = math.log(rank / 10.0) / math.log(5.0)
            global_score = self.config.ranking_top10_floor - (
                self.config.ranking_top10_floor - self.config.ranking_top50_floor
            ) * mid_progress
        else:
            cap = max(int(self.config.ranking_rank_cap), int(query.target_rank or 0), rank)
            global_score = self.config.ranking_top50_floor * math.exp(-float(self.config.ranking_tail_decay) * (rank - 50))
            if rank >= cap:
                global_score = min(global_score, 1.0)
        if ratio_score is None:
            return round(max(0.0, min(100.0, global_score)), 4)
        return round(max(0.0, min(100.0, (0.6 * ratio_score) + (0.4 * global_score))), 4)

    def _ielts_fit_score(self, requirement: Optional[float], user_ielts: Optional[float]) -> Optional[float]:
        if user_ielts is None or requirement is None:
            return None
        if user_ielts + 1e-9 < requirement:
            return None
        gap = max(0.0, float(user_ielts) - float(requirement))
        optimal_band = max(0.0, float(self.config.ielts_optimal_band))
        saturation_gap = max(optimal_band + 1e-9, float(self.config.ielts_saturation_gap))
        saturation_score = max(0.0, min(100.0, float(self.config.ielts_saturation_score)))
        if gap <= optimal_band:
            return 100.0
        if gap <= saturation_gap:
            progress = (gap - optimal_band) / max(1e-9, saturation_gap - optimal_band)
            return round(100.0 - (100.0 - saturation_score) * progress, 4)
        return saturation_score

    def _ielts_fit_score_v2(self, requirement: Optional[float], user_ielts: Optional[float]) -> Optional[float]:
        if user_ielts is None:
            return 55.0
        if requirement is None:
            return 60.0
        if user_ielts + 1e-9 < requirement:
            deficit = float(requirement) - float(user_ielts)
            return round(max(10.0, 55.0 - 35.0 * deficit), 4)
        return self._ielts_fit_score(requirement, user_ielts)

    def _completeness_score(self, row: RecommendationCandidate) -> Optional[float]:
        if self.config.completeness_requires_ielts and row.ielts_min is None:
            return None
        score = 0.0
        if row.aggregated_rank is not None:
            score += 40.0
        if row.ielts_min is not None:
            score += 30.0
        score += 30.0 * max(0.0, min(1.0, float(row.coverage_ratio or 0.0)))
        return min(100.0, score)

    def _confidence_score(self, row: RecommendationCandidate, query: RecommendationQuery) -> float:
        completeness = self._completeness_score(row) or 0.0
        source_ranks = [int(row.source_ranks[source]) for source in SOURCE_ORDER if row.source_ranks.get(source) is not None]
        if not source_ranks:
            agreement = 45.0
        elif len(source_ranks) == 1:
            agreement = 68.0
        else:
            spread = max(source_ranks) - min(source_ranks)
            denominator = max(max(source_ranks), int(query.target_rank or max(source_ranks)), 1)
            spread_ratio = spread / denominator
            agreement = max(45.0, 100.0 - (spread_ratio * 100.0) - (self.config.missing_source_penalty * (len(SOURCE_ORDER) - len(source_ranks))))
        confidence = (
            (self.config.completeness_confidence_weight * completeness)
            + (self.config.source_agreement_weight * agreement)
        )
        if query.ielts_score is not None and row.ielts_min is None:
            confidence -= 8.0
        return round(max(0.0, min(100.0, confidence)), 4)

    def _classify_category(
        self,
        row: RecommendationCandidate,
        query: RecommendationQuery,
        confidence_score: float,
        effective_rank: int,
    ) -> tuple[str, str]:
        target_rank = max(1.0, float(query.target_rank or 1))
        ratio = effective_rank / target_rank
        reach_upper, target_upper = self._category_thresholds(query.risk_profile)
        category = "target"
        if ratio < reach_upper:
            category = "reach"
        elif ratio > target_upper:
            category = "safety"

        if query.ielts_score is not None and row.ielts_min is not None and float(query.ielts_score) + 1e-9 < float(row.ielts_min):
            category = self._shift_riskier(category)
        if confidence_score < self.config.very_low_confidence_threshold:
            category = self._shift_riskier(category)
        elif confidence_score < self.config.low_confidence_threshold and category == "safety":
            category = "target"

        if category == "reach":
            reason = (
                f"Classified as Reach: rank #{effective_rank} is materially stronger than your target "
                f"#{int(target_rank)}, so it is an ambitious option."
            )
        elif category == "safety":
            reason = (
                f"Classified as Safety: rank #{effective_rank} is below your target threshold #{int(target_rank)}, "
                f"so it is a lower-risk option."
            )
        else:
            reason = (
                f"Classified as Target: rank #{effective_rank} sits close to your target #{int(target_rank)}, "
                f"so it is a balanced option."
            )

        if query.ielts_score is not None and row.ielts_min is not None:
            margin = round(float(query.ielts_score) - float(row.ielts_min), 2)
            if margin < 0:
                reason += f" IELTS is short by {abs(margin):.2f}, which makes the category more aggressive."
            else:
                reason += f" IELTS margin is {margin:.2f}, which supports the application profile."
        elif query.ielts_score is not None and row.ielts_min is None:
            reason += " IELTS requirement is missing, so confidence is reduced."
        if confidence_score < self.config.low_confidence_threshold:
            reason += f" Confidence is only {confidence_score:.1f}/100 due to incomplete or inconsistent data."
        return category, reason

    def _risk_alignment_score(self, category: str, risk_profile: Optional[str]) -> float:
        profile = self._normalize_risk_profile(risk_profile)
        matrix = {
            "conservative": {"reach": 55.0, "target": 82.0, "safety": 100.0},
            "balanced": {"reach": 72.0, "target": 100.0, "safety": 86.0},
            "aggressive": {"reach": 100.0, "target": 88.0, "safety": 70.0},
        }
        return matrix[profile][category]

    def _risk_adjustment(self, category: str, risk_profile: Optional[str]) -> float:
        profile = self._normalize_risk_profile(risk_profile)
        matrix = {
            "conservative": {
                "reach": self.config.conservative_reach_penalty,
                "target": self.config.conservative_target_boost,
                "safety": self.config.conservative_safety_boost,
            },
            "balanced": {
                "reach": self.config.balanced_reach_boost,
                "target": self.config.balanced_target_boost,
                "safety": self.config.balanced_safety_boost,
            },
            "aggressive": {
                "reach": self.config.aggressive_reach_boost,
                "target": self.config.aggressive_target_boost,
                "safety": self.config.aggressive_safety_penalty,
            },
        }
        return float(matrix[profile][category])

    def _category_thresholds(self, risk_profile: Optional[str]) -> tuple[float, float]:
        profile = self._normalize_risk_profile(risk_profile)
        if profile == "conservative":
            return (
                max(0.2, self.config.reach_ratio_upper + self.config.conservative_reach_adjustment),
                max(0.6, self.config.target_ratio_upper + self.config.conservative_target_adjustment),
            )
        if profile == "aggressive":
            return (
                self.config.reach_ratio_upper + self.config.aggressive_reach_adjustment,
                self.config.target_ratio_upper + self.config.aggressive_target_adjustment,
            )
        return self.config.reach_ratio_upper, self.config.target_ratio_upper

    def _shift_riskier(self, category: str) -> str:
        if category == "safety":
            return "target"
        return "reach"

    def _ielts_margin(self, requirement: Optional[float], user_ielts: Optional[float]) -> Optional[float]:
        if requirement is None or user_ielts is None:
            return None
        return float(user_ielts) - float(requirement)

    def _confidence_label(self, confidence_score: float) -> str:
        if confidence_score >= 80:
            return "high"
        if confidence_score >= 60:
            return "medium"
        return "low"

    def _normalize_risk_profile(self, value: Optional[str]) -> str:
        cleaned = (value or "balanced").strip().lower()
        return cleaned if cleaned in RISK_PROFILES else "balanced"

    def _resolve_preference_weights(self, query: RecommendationQuery) -> dict[str, float]:
        merged = {
            "ranking": max(0.0, float(self.config.v3_ranking_weight)),
            "ielts": max(0.0, float(self.config.v3_ielts_fit_weight)),
            "confidence": max(0.0, float(self.config.v3_confidence_weight)),
            "country_match": max(0.0, float(self.config.v3_country_match_weight)),
        }
        for key, value in (query.preference_weights or {}).items():
            if key not in merged:
                continue
            try:
                merged[key] = max(0.0, float(value))
            except (TypeError, ValueError):
                continue

        total = sum(merged.values())
        if total <= 0:
            merged = {
                "ranking": 0.5,
                "ielts": 0.2,
                "confidence": 0.2,
                "country_match": 0.1,
            }
            total = 1.0
        normalized = {key: value / total for key, value in merged.items()}

        min_ranking = max(0.0, min(1.0, float(self.config.v3_ranking_min_weight)))
        max_other = max(normalized[key] for key in normalized if key != "ranking")
        target_ranking = max(normalized["ranking"], min_ranking, max_other + 0.01)
        target_ranking = min(0.85, target_ranking)
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

    def _country_match_score(self, candidate_country: Optional[str], preferred_country: Optional[str]) -> Optional[float]:
        if not preferred_country:
            return 55.0
        if not candidate_country:
            return 40.0
        if candidate_country.strip().lower() == preferred_country.strip().lower():
            return 100.0
        return 25.0

    def _preference_alignment(
        self,
        country_match_score: Optional[float],
        risk_adjustment: float,
        preferred_country: Optional[str],
    ) -> str:
        signals: list[float] = [60.0 + risk_adjustment]
        if preferred_country:
            signals.append(country_match_score or 0.0)
        average = sum(signals) / len(signals)
        if average >= 78:
            return "strong"
        if average >= 55:
            return "moderate"
        return "low"

    def _build_explanation_v1(
        self,
        row: RecommendationCandidate,
        query: RecommendationQuery,
        breakdown: RecommendationScoreBreakdown,
    ) -> str:
        parts: list[str] = []
        if breakdown.effective_rank_used is not None:
            rank_label = "aggregated rank" if breakdown.effective_rank_source == "AGGREGATED" else f"{breakdown.effective_rank_source} rank"
            parts.append(f"{rank_label} #{breakdown.effective_rank_used}")
        if query.ielts_score is not None and row.ielts_min is not None:
            parts.append(f"IELTS requirement {row.ielts_min} matches profile {query.ielts_score}")
        if row.country:
            parts.append(f"country match: {row.country}")
        parts.append(
            "score breakdown: "
            f"ranking={_fmt_score(breakdown.ranking_score)} "
            f"(contribution={_fmt_score(breakdown.contributions.get('ranking'))}), "
            f"ielts_fit={_fmt_score(breakdown.ielts_fit_score)} "
            f"(contribution={_fmt_score(breakdown.contributions.get('ielts_fit'))}), "
            f"completeness={_fmt_score(breakdown.completeness_score)} "
            f"(contribution={_fmt_score(breakdown.contributions.get('completeness'))}), "
            f"final={self._composite_from_breakdown(breakdown):.2f}"
        )
        return "; ".join(parts)

    def _build_explanation_v2(
        self,
        row: RecommendationCandidate,
        query: RecommendationQuery,
        breakdown: RecommendationScoreBreakdown,
    ) -> str:
        parts = [breakdown.category_reason or "Category not available."]
        recommendation_bits: list[str] = []
        if breakdown.ranking_score is not None:
            recommendation_bits.append(f"ranking score is {breakdown.ranking_score:.2f}")
        recommendation_bits.append(f"confidence is {breakdown.confidence_label}")
        if query.ielts_score is not None and row.ielts_min is not None:
            margin = (breakdown.ielts_margin or 0.0)
            if margin >= 0:
                recommendation_bits.append(f"IELTS requirement {row.ielts_min} is covered by a {margin:.2f} margin")
            else:
                recommendation_bits.append(f"IELTS is short by {abs(margin):.2f}")
        elif query.ielts_score is not None and row.ielts_min is None:
            recommendation_bits.append("IELTS requirement is missing")
        recommendation_bits.append(
            f"overall fit score is {self._composite_from_breakdown(breakdown):.2f}"
        )
        parts.append("Recommended because " + ", ".join(recommendation_bits) + ".")
        return " ".join(parts)

    def _build_explanation_v3(
        self,
        row: RecommendationCandidate,
        query: RecommendationQuery,
        breakdown: RecommendationScoreBreakdown,
    ) -> str:
        parts = [breakdown.category_reason or "Category not available."]
        base_bits: list[str] = []
        if breakdown.ranking_score is not None:
            base_bits.append(f"ranking contributes {breakdown.ranking_score:.2f}")
        if breakdown.ielts_fit_score is not None:
            base_bits.append(f"IELTS fit contributes {breakdown.ielts_fit_score:.2f}")
        if breakdown.confidence_score is not None:
            base_bits.append(f"confidence contributes {breakdown.confidence_score:.2f}")
        parts.append(
            "Base score "
            + ", ".join(base_bits)
            + f", producing {self._fmt_optional(breakdown.base_score)} before scenario adjustment."
        )

        preference_bits: list[str] = []
        if query.country:
            preference_bits.append(
                f"country match is {self._fmt_optional(breakdown.country_match_score)} for preference {query.country}"
            )
        preference_bits.append(f"preference alignment is {breakdown.preference_alignment}")
        preference_bits.append(f"weights used {breakdown.weights_used}")
        parts.append("Preference impact: " + ", ".join(preference_bits) + ".")

        profile = self._normalize_risk_profile(query.risk_profile)
        adjustment = breakdown.risk_adjustment or 0.0
        direction = "boosted" if adjustment >= 0 else "reduced"
        parts.append(
            f"Risk adjustment: {direction} by {abs(adjustment):.2f} due to the {profile} profile favoring "
            f"{breakdown.category} options. Final score is {self._composite_from_breakdown_v3(breakdown):.2f}."
        )
        return " ".join(parts)

    def _fmt_optional(self, value: Optional[float]) -> str:
        if value is None:
            return "n/a"
        return f"{value:.2f}"


def recommend_universities(
    candidates: list[RecommendationCandidate],
    query: RecommendationQuery,
    config: Optional[RecommendationConfig] = None,
) -> list[RecommendationResult]:
    return RuleBasedRecommender(config=config).recommend(candidates, query)


def recommend_universities_v2(
    candidates: list[RecommendationCandidate],
    query: RecommendationQuery,
    config: Optional[RecommendationConfig] = None,
) -> GroupedRecommendationResult:
    return RuleBasedRecommender(config=config).recommend_grouped(candidates, query)


def recommend_universities_v3(
    candidates: list[RecommendationCandidate],
    query: RecommendationQuery,
    config: Optional[RecommendationConfig] = None,
) -> GroupedRecommendationResult:
    return RuleBasedRecommender(config=config).recommend_grouped_v3(candidates, query)


def grouped_recommendations_to_dict(result: GroupedRecommendationResult) -> dict[str, object]:
    return {
        "reach": [_result_to_dict(row) for row in result.reach],
        "target": [_result_to_dict(row) for row in result.target],
        "safety": [_result_to_dict(row) for row in result.safety],
        "metadata": result.metadata,
    }


def _result_to_dict(row: RecommendationResult) -> dict[str, object]:
    return {
        "canonical_university_id": row.canonical_university_id,
        "university_name": row.university_name,
        "country": row.country,
        "aggregated_rank": row.aggregated_rank,
        "ielts_requirement": row.ielts_min,
        "score": row.matching_score,
        "category": row.category,
        "preference_alignment": row.preference_alignment,
        "explanation": row.explanation,
        "score_breakdown": asdict(row.score_breakdown),
        "aggregation_method_version": row.aggregation_method_version,
    }


def _fmt_score(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"
