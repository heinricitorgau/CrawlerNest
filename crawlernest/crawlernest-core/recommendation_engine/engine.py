from __future__ import annotations

import logging
import math
from dataclasses import asdict
from typing import Iterable, Optional

from .config import RecommendationConfig, default_recommendation_config
from .confidence import build_confidence_assessment
from .explanations import build_no_results_reason, build_v3_explanation
from .policy import (
    category_thresholds,
    classify_category,
    country_match_score,
    normalize_country_policy,
    normalize_risk_profile,
    preference_alignment,
    resolve_preference_weights,
    risk_adjustment,
    weighted_score,
)
from .types import (
    GroupedRecommendationResult,
    RecommendationCandidate,
    RecommendationQuery,
    RecommendationResult,
    RecommendationScoreBreakdown,
)

SOURCE_ORDER = ("QS", "THE", "ARWU")
CATEGORY_ORDER = ("reach", "target", "safety")
LOGGER = logging.getLogger(__name__)

CONCERN_DEFINITIONS: dict[str, dict[str, object]] = {
    "early_deadline": {"label": "Early deadline", "priority_level": 1},
    "high_urgency_deadline": {"label": "High urgency deadline", "priority_level": 1},
    "medium_urgency_deadline": {"label": "Medium urgency deadline", "priority_level": 2},
    "ielts_well_below": {"label": "IELTS well below requirement", "priority_level": 0},
    "ielts_slightly_below": {"label": "IELTS slightly below requirement", "priority_level": 0},
    "ielts_meets_requirement": {"label": "IELTS just meets requirement", "priority_level": 2},
    "ielts_comfortably_above": {"label": "IELTS comfortably above requirement", "priority_level": 3},
    "toefl_well_below": {"label": "TOEFL well below requirement", "priority_level": 0},
    "toefl_slightly_below": {"label": "TOEFL slightly below requirement", "priority_level": 0},
    "toefl_meets_requirement": {"label": "TOEFL just meets requirement", "priority_level": 2},
    "toefl_comfortably_above": {"label": "TOEFL comfortably above requirement", "priority_level": 3},
    "gpa_well_below": {"label": "GPA well below requirement", "priority_level": 0},
    "gpa_slightly_below": {"label": "GPA slightly below requirement", "priority_level": 0},
    "gpa_meets_requirement": {"label": "GPA just meets requirement", "priority_level": 2},
    "gpa_comfortably_above": {"label": "GPA comfortably above requirement", "priority_level": 3},
    "duolingo_well_below": {"label": "Duolingo well below requirement", "priority_level": 0},
    "duolingo_slightly_below": {"label": "Duolingo slightly below requirement", "priority_level": 0},
    "duolingo_meets_requirement": {"label": "Duolingo just meets requirement", "priority_level": 2},
    "duolingo_comfortably_above": {"label": "Duolingo comfortably above requirement", "priority_level": 3},
}

try:
    from crawlernest_admission_crawler.deadline_interpretation import interpret_deadline_decision
except ImportError:  # pragma: no cover - optional integration path
    interpret_deadline_decision = None  # type: ignore[assignment]


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
                    gpa_min=row.gpa_min,
                    ielts_min=row.ielts_min,
                    toefl_min=row.toefl_min,
                    duolingo_min=row.duolingo_min,
                    matching_score=self._composite_from_breakdown(breakdown),
                    category=None,
                    preference_alignment=None,
                    recommendation_confidence=None,
                    confidence_reason=None,
                    scoring_version=self.config.scoring_version,
                    decision_policy_version=self.config.decision_policy_version,
                    explanation_version=self.config.explanation_version,
                    explanation=explanation,
                    score_breakdown=breakdown,
                    aggregation_method_version=row.aggregation_method_version,
                    metadata={
                        **dict(row.metadata or {}),
                        "user_ielts": query.ielts_score,
                        "user_toefl": query.toefl_score,
                        "user_gpa": query.gpa_score,
                        "user_duolingo": query.duolingo_score,
                    },
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
                    gpa_min=row.gpa_min,
                    ielts_min=row.ielts_min,
                    toefl_min=row.toefl_min,
                    duolingo_min=row.duolingo_min,
                    matching_score=self._composite_from_breakdown(breakdown),
                    category=breakdown.category,
                    preference_alignment=breakdown.preference_alignment,
                    recommendation_confidence=breakdown.recommendation_confidence,
                    confidence_reason=breakdown.confidence_reason,
                    scoring_version=breakdown.scoring_version,
                    decision_policy_version=breakdown.decision_policy_version,
                    explanation_version=breakdown.explanation_version,
                    explanation=explanation,
                    score_breakdown=breakdown,
                    aggregation_method_version=row.aggregation_method_version,
                    metadata={
                        **dict(row.metadata or {}),
                        "user_ielts": query.ielts_score,
                        "user_toefl": query.toefl_score,
                        "user_gpa": query.gpa_score,
                        "user_duolingo": query.duolingo_score,
                    },
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
            if self._passes_v3_filters(row, query):
                filtered.append(row)

        pool_context = self._build_pool_context(filtered, query)
        grouped: dict[str, list[RecommendationResult]] = {category: [] for category in CATEGORY_ORDER}
        for row in filtered:
            breakdown = self._score_candidate_v3(row, query, pool_context.get(row.canonical_university_id))
            if breakdown is None or breakdown.category is None:
                continue
            explanation = self._build_explanation_v3(row, query, breakdown)
            grouped[breakdown.category].append(
                RecommendationResult(
                    canonical_university_id=row.canonical_university_id,
                    university_name=row.university_name,
                    country=row.country,
                    aggregated_rank=row.aggregated_rank,
                    gpa_min=row.gpa_min,
                    ielts_min=row.ielts_min,
                    toefl_min=row.toefl_min,
                    duolingo_min=row.duolingo_min,
                    matching_score=self._composite_from_breakdown_v3(breakdown),
                    category=breakdown.category,
                    preference_alignment=breakdown.preference_alignment,
                    recommendation_confidence=breakdown.recommendation_confidence,
                    confidence_reason=breakdown.confidence_reason,
                    scoring_version=breakdown.scoring_version,
                    decision_policy_version=breakdown.decision_policy_version,
                    explanation_version=breakdown.explanation_version,
                    explanation=explanation,
                    score_breakdown=breakdown,
                    aggregation_method_version=row.aggregation_method_version,
                    metadata={
                        **dict(row.metadata or {}),
                        "user_ielts": query.ielts_score,
                        "user_toefl": query.toefl_score,
                        "user_gpa": query.gpa_score,
                        "user_duolingo": query.duolingo_score,
                    },
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
        self._log_v3_summary(query, len(rows), len(filtered), grouped)
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
        metadata["config_version"] = self.config.config_version
        metadata["scoring_version"] = self.config.scoring_version
        metadata["decision_policy_version"] = self.config.decision_policy_version
        metadata["explanation_version"] = self.config.explanation_version
        metadata["preference_weights"] = self._resolve_preference_weights(query)
        country_policy = self._country_policy(query) if query.country else "none"
        metadata["country_policy"] = country_policy
        metadata["country_preference_mode"] = country_policy
        if not any(counts.values()):
            metadata["no_results_reason"] = build_no_results_reason(candidate_count, query.target_rank)
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

    def _passes_v3_filters(self, row: RecommendationCandidate, query: RecommendationQuery) -> bool:
        if self._country_policy(query) == "hard_filter" and query.country:
            if (row.country or "").strip().lower() != query.country.strip().lower():
                return False
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
            scoring_version=self.config.scoring_version,
            decision_policy_version=self.config.decision_policy_version,
            explanation_version=self.config.explanation_version,
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
            recommendation_confidence=round(confidence_score, 4) if confidence_score is not None else None,
            confidence_reason=f"Confidence is {confidence_label} based on ranking-source agreement and data completeness.",
            scoring_version=self.config.scoring_version,
            decision_policy_version=self.config.decision_policy_version,
            explanation_version=self.config.explanation_version,
            rules_passed=rules_passed,
        )

    def _score_candidate_v3(
        self,
        row: RecommendationCandidate,
        query: RecommendationQuery,
        pool_context: Optional[dict[str, object]] = None,
    ) -> Optional[RecommendationScoreBreakdown]:
        effective_rank, effective_rank_source = self._choose_effective_rank(row, query)
        if effective_rank is None:
            return None

        ranking_score = self._ranking_score(effective_rank, query)
        ielts_fit_score = self._ielts_fit_score_v2(row.ielts_min, query.ielts_score)
        completeness_score = self._completeness_score(row) or 0.0
        ielts_margin = self._ielts_margin(row.ielts_min, query.ielts_score)
        confidence_assessment = self._confidence_assessment(row, query, completeness_score)
        confidence_score = confidence_assessment.score
        confidence_label = confidence_assessment.label
        category_decision = classify_category(
            effective_rank=effective_rank,
            target_rank=int(query.target_rank or 1),
            risk_profile=query.risk_profile,
            confidence_score=confidence_score,
            low_confidence_threshold=self.config.low_confidence_threshold,
            very_low_confidence_threshold=self.config.very_low_confidence_threshold,
            ielts_margin=ielts_margin,
            ielts_shortfall_risk_shift_threshold=self.config.ielts_shortfall_risk_shift_threshold,
            thresholds=category_thresholds(self.config, query.risk_profile),
        )
        category = category_decision.category
        category_reason = category_decision.reason
        if pool_context and pool_context.get("elite_pool"):
            category, category_reason = self._elite_pool_category(
                row=row,
                query=query,
                effective_rank=effective_rank,
                ielts_margin=ielts_margin,
                pool_context=pool_context,
            )
        country_preference_score = country_match_score(row.country, query.country)
        weights_used = self._resolve_preference_weights(query)
        available_scores = {
            "ranking": ranking_score,
            "ielts": ielts_fit_score,
            "confidence": confidence_score,
            "country_match": country_preference_score,
        }
        contributions = self._component_contributions(weights_used, available_scores)
        base_score = weighted_score(weights_used, available_scores)
        profile = normalize_risk_profile(query.risk_profile)
        risk_adjustment_score = risk_adjustment(self.config, category, query.risk_profile)
        final_score = max(0.0, min(100.0, base_score + risk_adjustment_score))
        alignment = preference_alignment(country_preference_score, risk_adjustment_score, query.country)
        filter_reasons = self._filter_reasons_v3(row, query, effective_rank_source, effective_rank)

        rules_passed = [
            "version=v3",
            f"category={category}",
            f"risk_profile={profile}",
            f"preference_alignment={alignment}",
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
            country_match_score=round(country_preference_score, 4),
            preference_alignment=alignment,
            base_score=round(base_score, 4),
            risk_adjustment=round(risk_adjustment_score, 4),
            recommendation_confidence=round(confidence_score, 4),
            confidence_reason=confidence_assessment.reason,
            scoring_version=self.config.scoring_version,
            decision_policy_version=self.config.decision_policy_version,
            explanation_version=self.config.explanation_version,
            filter_reasons=filter_reasons,
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

    def _confidence_assessment(
        self,
        row: RecommendationCandidate,
        query: RecommendationQuery,
        completeness_score: float,
    ):
        source_ranks = [int(row.source_ranks[source]) for source in SOURCE_ORDER if row.source_ranks.get(source) is not None]
        spread_ratio = None
        if len(source_ranks) > 1:
            spread = max(source_ranks) - min(source_ranks)
            denominator = max(max(source_ranks), int(query.target_rank or max(source_ranks)), 1)
            spread_ratio = spread / denominator
        return build_confidence_assessment(
            completeness_score=completeness_score,
            source_count=len(source_ranks),
            source_spread_ratio=spread_ratio,
            missing_ielts_for_query=bool(query.ielts_score is not None and row.ielts_min is None),
            config=self.config,
        )

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

        if (
            query.ielts_score is not None
            and row.ielts_min is not None
            and (float(row.ielts_min) - float(query.ielts_score)) >= float(self.config.ielts_shortfall_risk_shift_threshold)
        ):
            category = self._shift_riskier(category)

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

    def _build_pool_context(
        self,
        rows: list[RecommendationCandidate],
        query: RecommendationQuery,
    ) -> dict[int, dict[str, object]]:
        if not rows or query.target_rank is None or int(query.target_rank) <= 0:
            return {}

        ranked: list[tuple[int, RecommendationCandidate]] = []
        for row in rows:
            effective_rank, _ = self._choose_effective_rank(row, query)
            if effective_rank is not None:
                ranked.append((effective_rank, row))
        if not ranked:
            return {}

        ranked.sort(key=lambda item: (item[0], item[1].canonical_university_id))
        pool_size = len(ranked)
        max_rank = ranked[-1][0]
        elite_pool = (
            pool_size >= int(self.config.elite_pool_min_size)
            and int(query.target_rank) <= int(self.config.elite_pool_target_rank_cap)
            and max_rank <= (float(query.target_rank) * float(self.config.elite_pool_rank_ceiling_ratio))
        )

        context: dict[int, dict[str, object]] = {}
        for index, (effective_rank, row) in enumerate(ranked):
            context[row.canonical_university_id] = {
                "pool_size": pool_size,
                "pool_position": index,
                "elite_pool": elite_pool,
            }
        return context

    def _elite_pool_category(
        self,
        *,
        row: RecommendationCandidate,
        query: RecommendationQuery,
        effective_rank: int,
        ielts_margin: Optional[float],
        pool_context: dict[str, object],
    ) -> tuple[str, str]:
        pool_size = int(pool_context.get("pool_size") or 1)
        pool_position = int(pool_context.get("pool_position") or 0)
        profile = self._normalize_risk_profile(query.risk_profile)

        if profile == "conservative":
            reach_share, target_share = 0.2, 0.4
        elif profile == "aggressive":
            reach_share, target_share = 0.6, 0.25
        else:
            reach_share, target_share = 0.4, 0.4

        reach_cutoff = max(1, math.ceil(pool_size * reach_share))
        target_cutoff = min(pool_size, reach_cutoff + max(1, math.ceil(pool_size * target_share)))

        if pool_position < reach_cutoff:
            category = "reach"
            reason = (
                f"Reach: within this elite filtered pool, rank #{effective_rank} sits in the most ambitious band "
                f"for target #{int(query.target_rank or 0)}."
            )
        elif pool_position < target_cutoff:
            category = "target"
            reason = (
                f"Target: within this elite filtered pool, rank #{effective_rank} sits in the balanced middle band "
                f"for target #{int(query.target_rank or 0)}."
            )
        else:
            category = "safety"
            reason = (
                f"Safety: within this elite filtered pool, rank #{effective_rank} sits in the safer end of the shortlist "
                f"for target #{int(query.target_rank or 0)}."
            )

        if ielts_margin is not None:
            if ielts_margin <= -float(self.config.ielts_shortfall_risk_shift_threshold):
                reason += f" IELTS is short by {abs(ielts_margin):.2f}, which makes it riskier."
            elif ielts_margin < 0:
                reason += f" IELTS is slightly short by {abs(ielts_margin):.2f}."
            else:
                reason += f" IELTS margin is {ielts_margin:.2f}."
        elif query.ielts_score is not None and row.ielts_min is None:
            reason += " IELTS requirement is missing, so confidence is reduced."
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
        return risk_adjustment(self.config, category, risk_profile)

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
        return normalize_risk_profile(value)

    def _country_policy(self, query: RecommendationQuery) -> str:
        return normalize_country_policy(query.country_policy, default=self.config.country_match_policy)

    def _resolve_preference_weights(self, query: RecommendationQuery) -> dict[str, float]:
        return resolve_preference_weights(self.config, query.preference_weights)

    def _country_match_score(self, candidate_country: Optional[str], preferred_country: Optional[str]) -> Optional[float]:
        return country_match_score(candidate_country, preferred_country)

    def _preference_alignment(
        self,
        country_match_score: Optional[float],
        risk_adjustment: float,
        preferred_country: Optional[str],
    ) -> str:
        return preference_alignment(country_match_score or 0.0, risk_adjustment, preferred_country)

    def _filter_reasons_v3(
        self,
        row: RecommendationCandidate,
        query: RecommendationQuery,
        effective_rank_source: str,
        effective_rank: int,
    ) -> list[str]:
        reasons = [f"effective rank #{effective_rank} from {effective_rank_source.lower()} data is available"]
        country_policy = self._country_policy(query)
        if query.country and row.country:
            if row.country.strip().lower() == query.country.strip().lower():
                reasons.append(f"country matches {query.country}")
            elif country_policy == "soft_preference":
                reasons.append(f"country differs from {query.country}, but soft preference keeps it eligible")
        elif query.country and country_policy == "hard_filter":
            reasons.append(f"country filter is locked to {query.country}")
        if query.ielts_score is None:
            reasons.append("IELTS filter was not required")
        elif row.ielts_min is None:
            reasons.append("IELTS requirement is missing, so the row stays eligible with reduced confidence")
        elif query.ielts_score + 1e-9 >= row.ielts_min:
            reasons.append(f"IELTS {query.ielts_score} covers requirement {row.ielts_min}")
        else:
            reasons.append(f"IELTS {query.ielts_score} is below requirement {row.ielts_min}, so risk increases")
        return reasons

    def _log_v3_summary(
        self,
        query: RecommendationQuery,
        initial_candidates: int,
        filtered_candidates: int,
        grouped: dict[str, list[RecommendationResult]],
    ) -> None:
        top_rows = []
        for category in CATEGORY_ORDER:
            if grouped[category]:
                row = grouped[category][0]
                top_rows.append(
                    {
                        "category": category,
                        "university": row.university_name,
                        "score": row.matching_score,
                    }
                )
        LOGGER.info(
            "recommendation_v3_summary request=%s config_version=%s scoring_version=%s policy_version=%s counts=%s top=%s",
            {
                "target_rank": query.target_rank,
                "risk_profile": self._normalize_risk_profile(query.risk_profile),
                "country": query.country,
                "country_policy": self._country_policy(query),
                "ielts_score": query.ielts_score,
            },
            self.config.config_version,
            self.config.scoring_version,
            self.config.decision_policy_version,
            {
                "before_filter": initial_candidates,
                "after_filter": filtered_candidates,
                "reach": len(grouped["reach"]),
                "target": len(grouped["target"]),
                "safety": len(grouped["safety"]),
            },
            top_rows,
        )

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
        return build_v3_explanation(
            category_reason=breakdown.category_reason or "Category not available.",
            category=breakdown.category or "target",
            effective_rank=breakdown.effective_rank_used,
            target_rank=query.target_rank,
            ielts_margin=breakdown.ielts_margin,
            confidence_label=breakdown.confidence_label,
            country_preference=query.country,
            country_policy=self._country_policy(query),
            candidate_country=row.country,
            country_match_score=breakdown.country_match_score,
            risk_profile=self._normalize_risk_profile(query.risk_profile),
            risk_adjustment=breakdown.risk_adjustment or 0.0,
        )

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
    payload = {
        "canonical_university_id": row.canonical_university_id,
        "university_name": row.university_name,
        "country": row.country,
        "aggregated_rank": row.aggregated_rank,
        "gpa_requirement": row.gpa_min,
        "ielts_requirement": row.ielts_min,
        "toefl_requirement": row.toefl_min,
        "duolingo_requirement": row.duolingo_min,
        "score": row.matching_score,
        "category": row.category,
        "preference_alignment": row.preference_alignment,
        "recommendation_confidence": row.recommendation_confidence,
        "confidence_reason": row.confidence_reason,
        "scoring_version": row.scoring_version,
        "decision_policy_version": row.decision_policy_version,
        "explanation_version": row.explanation_version,
        "explanation": row.explanation,
        "score_breakdown": asdict(row.score_breakdown),
        "aggregation_method_version": row.aggregation_method_version,
    }
    deadline_info = _build_deadline_info(row)
    if deadline_info is not None:
        payload["deadline_info"] = deadline_info
    ielts_fit_info = _build_ielts_fit_info(row)
    if ielts_fit_info is not None:
        payload["ielts_fit_info"] = ielts_fit_info
    toefl_fit_info = _build_toefl_fit_info(row)
    if toefl_fit_info is not None:
        payload["toefl_fit_info"] = toefl_fit_info
    gpa_fit_info = _build_gpa_fit_info(row)
    if gpa_fit_info is not None:
        payload["gpa_fit_info"] = gpa_fit_info
    duolingo_fit_info = _build_duolingo_fit_info(row)
    if duolingo_fit_info is not None:
        payload["duolingo_fit_info"] = duolingo_fit_info
    admission_composite = _build_admission_composite(
        deadline_info=deadline_info,
        fit_signals={
            "ielts": ielts_fit_info,
            "toefl": toefl_fit_info,
            "gpa": gpa_fit_info,
            "duolingo": duolingo_fit_info,
        },
    )
    if admission_composite is not None:
        payload["admission_composite"] = admission_composite
    decision_output = _build_decision_output(
        deadline_info=deadline_info,
        fit_signals={
            "ielts": ielts_fit_info,
            "toefl": toefl_fit_info,
            "gpa": gpa_fit_info,
            "duolingo": duolingo_fit_info,
        },
        admission_composite=admission_composite,
    )
    if decision_output is not None:
        payload["decision_output"] = decision_output
    decision_strategy = _build_decision_strategy(payload)
    if decision_strategy is not None:
        payload["decision_strategy"] = decision_strategy
    return payload


def _build_deadline_info(row: RecommendationResult) -> dict[str, object] | None:
    if interpret_deadline_decision is None:
        return None

    metadata = row.metadata if isinstance(row.metadata, dict) else {}
    deadline = metadata.get("deadline")
    deadline_candidates = metadata.get("deadline_candidates")
    if deadline is None and deadline_candidates is None:
        return None

    interpretation = interpret_deadline_decision(
        deadline=deadline if isinstance(deadline, str) else None,
        diagnostics={"deadline_candidates": deadline_candidates},
    )
    recommended_deadline = interpretation.get("recommended_deadline")
    if not isinstance(recommended_deadline, str) or not recommended_deadline:
        return None

    return {
        "recommended_deadline": recommended_deadline,
        "deadline_type": interpretation.get("recommended_deadline_type"),
        "urgency": interpretation.get("deadline_urgency"),
        "reason": interpretation.get("deadline_reason"),
    }


def _build_ielts_fit_info(row: RecommendationResult) -> dict[str, object] | None:
    metadata = row.metadata if isinstance(row.metadata, dict) else {}
    return _build_requirement_fit_info(
        subject="IELTS",
        user_score=metadata.get("user_ielts"),
        required_score=row.ielts_min,
        comfortably_above_threshold=0.5,
        slightly_below_threshold=-0.5,
        require_four_point_scale=False,
    )


def _build_toefl_fit_info(row: RecommendationResult) -> dict[str, object] | None:
    metadata = row.metadata if isinstance(row.metadata, dict) else {}
    return _build_requirement_fit_info(
        subject="TOEFL",
        user_score=metadata.get("user_toefl"),
        required_score=row.toefl_min,
        comfortably_above_threshold=5.0,
        slightly_below_threshold=-5.0,
        require_four_point_scale=False,
    )

def _build_gpa_fit_info(row: RecommendationResult) -> dict[str, object] | None:
    metadata = row.metadata if isinstance(row.metadata, dict) else {}
    return _build_requirement_fit_info(
        subject="GPA",
        user_score=metadata.get("user_gpa"),
        required_score=row.gpa_min,
        comfortably_above_threshold=0.3,
        slightly_below_threshold=-0.3,
        require_four_point_scale=True,
    )


def _build_duolingo_fit_info(row: RecommendationResult) -> dict[str, object] | None:
    metadata = row.metadata if isinstance(row.metadata, dict) else {}
    return _build_requirement_fit_info(
        subject="Duolingo",
        user_score=metadata.get("user_duolingo"),
        required_score=row.duolingo_min,
        comfortably_above_threshold=10.0,
        slightly_below_threshold=-10.0,
        require_four_point_scale=False,
    )


def _build_requirement_fit_info(
    *,
    subject: str,
    user_score: object,
    required_score: object,
    comfortably_above_threshold: float,
    slightly_below_threshold: float,
    require_four_point_scale: bool,
) -> dict[str, object] | None:
    if not isinstance(user_score, (int, float)) or not isinstance(required_score, (int, float)):
        return None

    user_value = float(user_score)
    required_value = float(required_score)

    if require_four_point_scale and not (
        0.0 <= user_value <= 4.0 and 0.0 <= required_value <= 4.0
    ):
        return None

    margin = round(user_value - required_value, 2)

    if margin >= comfortably_above_threshold:
        fit_band = "comfortably_above"
        fit_urgency = "low"
    elif margin >= 0.0:
        fit_band = "meets_requirement"
        fit_urgency = "medium"
    elif margin >= slightly_below_threshold:
        fit_band = "slightly_below"
        fit_urgency = "high"
    else:
        fit_band = "well_below"
        fit_urgency = "high"

    reason = _build_requirement_fit_reason(
        subject=subject,
        user_value=user_value,
        required_value=required_value,
        margin=margin,
    )

    return {
        "required_score": required_value,
        "user_score": user_value,
        "margin": margin,
        "fit_band": fit_band,
        "fit_urgency": fit_urgency,
        "reason": reason,
    }


def _build_requirement_fit_reason(
    *,
    subject: str,
    user_value: float,
    required_value: float,
    margin: float,
) -> str:
    if subject in {"IELTS", "GPA"}:
        fmt = lambda value: f"{value:.1f}"
    else:
        fmt = lambda value: f"{int(value)}" if float(value).is_integer() else f"{value:.1f}"

    if abs(margin) < 1e-9:
        return f"{subject} {fmt(user_value)} exactly meets the required {fmt(required_value)}"
    if margin > 0:
        return f"{subject} {fmt(user_value)} is {fmt(margin)} above the required {fmt(required_value)}"
    return f"{subject} {fmt(user_value)} is {fmt(abs(margin))} below the required {fmt(required_value)}"


def _build_admission_composite(
    *,
    deadline_info: dict[str, object] | None,
    fit_signals: dict[str, dict[str, object] | None],
) -> dict[str, object] | None:
    concern_tokens = _build_concern_tokens(deadline_info=deadline_info, fit_signals=fit_signals)
    usable_fit_signals = [
        signal
        for signal in fit_signals.values()
        if isinstance(signal, dict) and isinstance(signal.get("fit_band"), str)
    ]

    if not usable_fit_signals and deadline_info is None:
        return None

    readiness = _determine_admission_readiness(
        deadline_info=deadline_info,
        fit_signals=usable_fit_signals,
    )
    risk = _determine_admission_risk(
        deadline_info=deadline_info,
        fit_signals=usable_fit_signals,
    )
    top_concerns = _top_concerns(concern_tokens)
    reason = _build_admission_composite_reason(
        readiness=readiness,
        risk=risk,
        deadline_info=deadline_info,
        fit_signals=usable_fit_signals,
    )

    return {
        "admission_readiness": readiness,
        "admission_risk": risk,
        "top_concerns": top_concerns,
        "top_concern_labels": [_concern_label(token) for token in top_concerns],
        "reason": reason,
    }


def _build_concern_tokens(
    *,
    deadline_info: dict[str, object] | None,
    fit_signals: dict[str, dict[str, object] | None],
) -> list[str]:
    tokens: list[str] = []

    if isinstance(deadline_info, dict):
        deadline_type = str(deadline_info.get("deadline_type") or "")
        deadline_urgency = str(deadline_info.get("urgency") or "")
        if deadline_type == "early":
            tokens.append("early_deadline")
        if deadline_urgency == "high":
            tokens.append("high_urgency_deadline")
        elif deadline_urgency == "medium":
            tokens.append("medium_urgency_deadline")

    for subject, signal in fit_signals.items():
        if not isinstance(signal, dict):
            continue
        fit_band = str(signal.get("fit_band") or "")
        if fit_band in {"well_below", "slightly_below", "meets_requirement", "comfortably_above"}:
            tokens.append(f"{subject}_{fit_band}")

    return tokens


def _determine_admission_readiness(
    *,
    deadline_info: dict[str, object] | None,
    fit_signals: list[dict[str, object]],
) -> str:
    if not fit_signals:
        return "unknown"

    fit_bands = [str(signal.get("fit_band") or "") for signal in fit_signals]
    slightly_below_count = sum(1 for band in fit_bands if band == "slightly_below")

    if "well_below" in fit_bands or slightly_below_count >= 2:
        return "weak"

    if all(band == "comfortably_above" for band in fit_bands):
        return "strong"

    has_early_high_deadline = (
        isinstance(deadline_info, dict)
        and str(deadline_info.get("deadline_type") or "") == "early"
        and str(deadline_info.get("urgency") or "") == "high"
    )

    if (
        "slightly_below" in fit_bands
        or "meets_requirement" in fit_bands
        or has_early_high_deadline
    ):
        return "moderate"

    return "moderate"


def _determine_admission_risk(
    *,
    deadline_info: dict[str, object] | None,
    fit_signals: list[dict[str, object]],
) -> str:
    if not fit_signals and deadline_info is None:
        return "unknown"
    if not fit_signals:
        return "unknown"

    fit_bands = [str(signal.get("fit_band") or "") for signal in fit_signals]
    slightly_below_count = sum(1 for band in fit_bands if band == "slightly_below")

    if "well_below" in fit_bands or slightly_below_count >= 2:
        return "high"

    has_early_high_deadline = (
        isinstance(deadline_info, dict)
        and str(deadline_info.get("deadline_type") or "") == "early"
        and str(deadline_info.get("urgency") or "") == "high"
    )

    if "slightly_below" in fit_bands or "meets_requirement" in fit_bands or has_early_high_deadline:
        return "medium"

    if all(band in {"comfortably_above", "meets_requirement"} for band in fit_bands):
        return "low"

    return "unknown"


def _top_concerns(tokens: list[str]) -> list[str]:
    unique_tokens: list[str] = []
    for token in tokens:
        if token not in unique_tokens:
            unique_tokens.append(token)

    ordered = sorted(
        unique_tokens,
        key=lambda token: (
            concern_priority_level(token),
            _concern_type_order(token),
            token,
        ),
    )
    return ordered[:3]


def _concern_label(token: str) -> str:
    definition = concern_definition(token)
    return str(definition["label"])


def concern_definition(token: str) -> dict[str, object]:
    if token in CONCERN_DEFINITIONS:
        return dict(CONCERN_DEFINITIONS[token])
    return {
        "label": token.replace("_", " ").capitalize(),
        "priority_level": 3,
    }


def concern_priority_level(token: str) -> int:
    definition = concern_definition(token)
    priority_level = definition.get("priority_level", 3)
    try:
        return int(priority_level)
    except (TypeError, ValueError):
        return 3


def _concern_type_order(token: str) -> int:
    if token.startswith("ielts_"):
        return 0
    if token.startswith("toefl_"):
        return 1
    if token.startswith("gpa_"):
        return 2
    if token.startswith("duolingo_"):
        return 3
    if token.endswith("_deadline"):
        return 4
    return 5


def _build_admission_composite_reason(
    *,
    readiness: str,
    risk: str,
    deadline_info: dict[str, object] | None,
    fit_signals: list[dict[str, object]],
) -> str:
    if readiness == "unknown" and risk == "unknown":
        return "Admission readiness could not be determined from available structured signals."

    fit_bands = [str(signal.get("fit_band") or "") for signal in fit_signals]
    has_early_deadline = (
        isinstance(deadline_info, dict)
        and str(deadline_info.get("deadline_type") or "") == "early"
    )
    has_below = any(band in {"slightly_below", "well_below"} for band in fit_bands)
    has_meets = "meets_requirement" in fit_bands

    if has_below:
        return "This option appears higher risk because one or more requirement-fit signals are below requirement."
    if has_early_deadline and has_meets:
        return "This option has an early deadline and mixed requirement-fit signals."
    if has_meets:
        return "This option has mixed requirement-fit signals, with some scores only meeting the requirement."
    if all(band == "comfortably_above" for band in fit_bands) and fit_bands:
        return "This option looks strong because all visible requirement-fit signals meet or exceed requirements."
    if has_early_deadline:
        return "This option has an early deadline and otherwise stable requirement-fit signals."
    return "This option shows a mixed admission-readiness picture across the available structured signals."


def _build_decision_output(
    *,
    deadline_info: dict[str, object] | None,
    fit_signals: dict[str, dict[str, object] | None],
    admission_composite: dict[str, object] | None,
) -> dict[str, object] | None:
    usable_fit_signals = [
        signal
        for signal in fit_signals.values()
        if isinstance(signal, dict) and isinstance(signal.get("fit_band"), str)
    ]
    fit_signal_count = len(usable_fit_signals)
    if isinstance(admission_composite, dict):
        readiness = str(admission_composite.get("admission_readiness") or "unknown")
        risk = str(admission_composite.get("admission_risk") or "unknown")
    else:
        readiness = "unknown"
        risk = "unknown"

    if readiness == "weak" or risk == "high":
        action = "improve_profile_first"
    elif (
        isinstance(deadline_info, dict)
        and str(deadline_info.get("deadline_type") or "") == "early"
        and str(deadline_info.get("urgency") or "") == "high"
        and readiness in {"strong", "moderate"}
        and risk != "high"
    ):
        action = "apply_early"
    elif readiness == "moderate" or risk == "medium":
        action = "apply_with_caution"
    elif readiness == "strong" and risk == "low":
        action = "apply"
    elif readiness in {"strong", "moderate"} and risk in {"low", "medium"} and deadline_info is None and fit_signal_count <= 1:
        action = "monitor"
    elif readiness == "unknown" and risk == "unknown":
        action = "insufficient_data"
    else:
        action = "monitor"

    strength_map = {
        "apply_early": "strong",
        "apply": "strong",
        "apply_with_caution": "moderate",
        "improve_profile_first": "strong",
        "monitor": "weak",
        "insufficient_data": "unknown",
    }
    reason_map = {
        "apply_early": "This option should be prioritized because it has an early deadline and the visible requirement-fit signals are still workable.",
        "apply": "This option looks ready for application because visible requirement-fit signals meet or exceed requirements with no major risk signal.",
        "apply_with_caution": "This option is still viable, but should be approached carefully because the admission profile shows moderate readiness or medium risk.",
        "improve_profile_first": "This option currently looks risky because one or more visible requirement-fit signals fall below requirement or overall readiness is weak.",
        "monitor": "This option may be worth tracking, but the current structured signals are not strong enough to prioritize immediate action.",
        "insufficient_data": "There is not enough structured admission signal data to make a confident action recommendation.",
    }
    next_steps_map = {
        "apply_early": [
            "Prepare documents now",
            "Submit before the early deadline",
            "Double-check requirement-sensitive materials",
        ],
        "apply": [
            "Prepare a normal application submission",
            "Review deadlines and required documents",
            "Proceed with application planning",
        ],
        "apply_with_caution": [
            "Review the requirement gaps carefully",
            "Decide whether this is still worth applying to",
            "Prepare supporting materials early",
        ],
        "improve_profile_first": [
            "Prioritize improving below-threshold requirement areas",
            "Avoid treating this as a safe application right now",
            "Reassess after profile improvement",
        ],
        "monitor": [
            "Track this option while gathering more admission details",
            "Compare it with stronger options first",
        ],
        "insufficient_data": [
            "Collect more structured admission data",
            "Do not rely on this option alone yet",
        ],
    }

    return {
        "decision_action": action,
        "decision_strength": strength_map[action],
        "decision_reason": reason_map[action],
        "recommended_next_steps": next_steps_map[action][:3],
    }


def _build_decision_strategy(row_dict: dict[str, object]) -> dict[str, object] | None:
    decision_output = row_dict.get("decision_output")
    if not isinstance(decision_output, dict):
        return None

    action = str(decision_output.get("decision_action") or "")
    reason = str(decision_output.get("decision_reason") or "").strip()
    concern_tokens = _decision_strategy_concerns(row_dict)

    if action == "apply_early":
        primary_strategy = "Submit early while requirements are already acceptable"
        supporting_actions = [
            "Prepare documents immediately",
            "Lock in recommendation letters",
            "Review personal statement once more",
        ]
        risk_mitigation: list[str] = []
        if any(token in {"high_urgency_deadline", "medium_urgency_deadline"} or token.endswith("_meets_requirement") or token.endswith("_slightly_below") or token.endswith("_well_below") for token in concern_tokens):
            risk_mitigation.append("Double-check requirement-sensitive components")
        timeline_hint = "Complete submission before early deadline"
    elif action == "apply":
        primary_strategy = "Proceed with application under current profile"
        supporting_actions = [
            "Finalize application materials",
            "Ensure requirement alignment",
        ]
        risk_mitigation = []
        if any(token.endswith("_meets_requirement") for token in concern_tokens):
            risk_mitigation.append("Strengthen weaker components if possible")
        timeline_hint = "Submit within standard deadline window"
    elif action == "apply_with_caution":
        primary_strategy = "Apply but expect some risk in current profile"
        supporting_actions = [
            "Prioritize strongest materials",
            "Highlight strengths clearly",
        ]
        risk_mitigation = [
            "Address weaker requirements proactively",
            "Consider parallel safer options",
        ]
        timeline_hint = "Do not delay submission; allow buffer time"
    elif action == "improve_profile_first":
        primary_strategy = "Delay application and improve profile first"
        supporting_actions = [
            "Retake exams or improve academic metrics",
            "Strengthen supporting materials",
        ]
        risk_mitigation = [
            "Avoid applying under current profile",
        ]
        timeline_hint = "Target next available admission cycle"
    elif action == "insufficient_data":
        primary_strategy = "Collect missing requirement information first"
        supporting_actions = [
            "Verify admission requirements",
            "Complete missing profile inputs",
        ]
        risk_mitigation = [
            "Avoid making decisions on incomplete data",
        ]
        timeline_hint = "Re-evaluate after completing data"
    else:
        primary_strategy = "Track the option while clarifying the strongest application path"
        supporting_actions = [
            "Monitor updates to admission requirements",
            "Compare this option with stronger alternatives",
        ]
        risk_mitigation = [
            "Avoid overcommitting before more structured signals are available",
        ]
        timeline_hint = "Reassess once stronger timing or fit signals are available"

    supporting_actions, risk_mitigation, timeline_hint = _apply_strategy_concern_adjustments(
        concern_tokens=concern_tokens,
        supporting_actions=supporting_actions,
        risk_mitigation=risk_mitigation,
        timeline_hint=timeline_hint,
    )

    return {
        "primary_strategy": primary_strategy,
        "supporting_actions": supporting_actions[:3],
        "risk_mitigation": risk_mitigation[:3],
        "timeline_hint": timeline_hint,
        "reason": reason,
    }


def _decision_strategy_concerns(row_dict: dict[str, object]) -> list[str]:
    surface_signals = row_dict.get("surfaceSignals")
    if isinstance(surface_signals, list):
        concerns: list[str] = []
        for signal in surface_signals:
            if not isinstance(signal, dict):
                continue
            concern = signal.get("concern")
            if isinstance(concern, str) and concern and concern not in concerns:
                concerns.append(concern)
        if concerns:
            return concerns

    fit_signals = {
        "ielts": row_dict.get("ielts_fit_info"),
        "toefl": row_dict.get("toefl_fit_info"),
        "gpa": row_dict.get("gpa_fit_info"),
        "duolingo": row_dict.get("duolingo_fit_info"),
    }
    concerns = _build_concern_tokens(
        deadline_info=row_dict.get("deadline_info") if isinstance(row_dict.get("deadline_info"), dict) else None,
        fit_signals=fit_signals,
    )
    admission_composite = row_dict.get("admission_composite")
    if isinstance(admission_composite, dict):
        top_concerns = admission_composite.get("top_concerns")
        if isinstance(top_concerns, list):
            for token in top_concerns:
                if isinstance(token, str) and token and token not in concerns:
                    concerns.append(token)
    return concerns


def _apply_strategy_concern_adjustments(
    *,
    concern_tokens: list[str],
    supporting_actions: list[str],
    risk_mitigation: list[str],
    timeline_hint: str,
) -> tuple[list[str], list[str], str]:
    extra_supporting: list[str] = []
    extra_risk: list[str] = []

    if "gpa_meets_requirement" in concern_tokens:
        extra_supporting.append("Pay attention to GPA-sensitive evaluation")
    if "ielts_slightly_below" in concern_tokens:
        extra_risk.append("Consider retaking IELTS to reduce risk")
    if "toefl_slightly_below" in concern_tokens:
        extra_risk.append("Consider retaking TOEFL to reduce risk")
    if "duolingo_slightly_below" in concern_tokens:
        extra_risk.append("Consider retaking Duolingo to reduce risk")
    if "early_deadline" in concern_tokens:
        timeline_hint = "Move quickly so the application is ready before the early deadline"

    merged_supporting: list[str] = []
    for action in [*extra_supporting, *supporting_actions]:
        if action not in merged_supporting:
            merged_supporting.append(action)

    merged_risk: list[str] = []
    for action in [*risk_mitigation, *extra_risk]:
        if action not in merged_risk:
            merged_risk.append(action)

    return merged_supporting, merged_risk, timeline_hint


def _fmt_score(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"
