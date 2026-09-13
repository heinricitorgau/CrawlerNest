from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

from crawlernest.core.database.settings import DatabaseSettings
from crawlernest.core.dataset import DEFAULT_RANKING_YEAR

MODULE_ROOT = Path(__file__).resolve().parents[2]
CORE_RECOMMENDATION_DIR = MODULE_ROOT / "crawlernest-core"
if str(CORE_RECOMMENDATION_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_RECOMMENDATION_DIR))

from recommendation_engine import (  # type: ignore[import-not-found]
    concern_definition,
    concern_priority_level,
    RecommendationQuery,
    RecommendationRepository,
    default_recommendation_config,
    grouped_recommendations_to_dict,
    recommend_universities_v3,
)

ADMISSION_RESOLVED_FIELDS = frozenset({"ielts", "toefl", "gpa", "duolingo", "deadline"})

try:
    import psycopg2
except ImportError:  # pragma: no cover - environment-dependent
    psycopg2 = None  # type: ignore


class RecommendationService:
    MAX_SURFACED_SIGNALS = 2
    SCENARIO_PRESET_ORDER = (
        "ielts_plus_0_5",
        "toefl_plus_5",
        "gpa_plus_0_2",
        "target_rank_tighter_20",
    )
    EFFORT_LEVELS = {
        "ielts_plus_0_5": "high",
        "toefl_plus_5": "medium",
        "gpa_plus_0_2": "medium",
        "target_rank_tighter_20": "low",
    }
    EFFORT_RANK = {"low": 0, "medium": 1, "high": 2}
    IMPACT_RANK = {"low": 0, "medium": 1, "high": 2}

    def __init__(self, db_settings: DatabaseSettings | None = None) -> None:
        self._db_settings = db_settings or DatabaseSettings.from_env()

    def recommend(self, profile: dict[str, Any]) -> dict[str, Any]:
        if psycopg2 is None:
            raise RuntimeError("psycopg2 is required for recommendation mode")

        query = self._build_query(profile)
        conn = psycopg2.connect(
            host=self._db_settings.host,
            port=self._db_settings.port,
            database=self._db_settings.database,
            user=self._db_settings.user,
            password=self._db_settings.password,
        )
        try:
            repo = RecommendationRepository(conn)
            config = default_recommendation_config()
            payload = self._run_recommendation_pipeline(repo, query, config=config)
        finally:
            conn.close()

        selected_plan = self._normalize_plan_name(
            profile.get("selectedPlan") or profile.get("selected_plan")
        )
        scenario_input = self._extract_scenario_input(profile)
        items, counts = self._flatten_grouped_results(payload)
        application_plan = self._build_application_plan(items)
        application_plans = self._build_application_plans(items)
        plan_comparison = self._build_plan_comparison(application_plans)
        plan_delta = self._build_plan_delta(application_plans, plan_comparison)
        selected_plan_comparison = self._build_selected_plan_comparison(
            application_plans,
            plan_comparison,
            selected_plan,
        )
        scenario_simulation = self._build_scenario_simulation(
            query=query,
            scenario_input=scenario_input,
        )
        scenario_comparison = self._build_scenario_comparison(query=query)
        best_scenario_insight = self._build_best_scenario_insight(scenario_comparison)
        improvement_priority = self._build_improvement_priority(
            scenario_comparison=scenario_comparison,
            best_scenario_insight=best_scenario_insight,
        )
        next_action_guide = self._build_next_action_guide(
            plan_comparison=plan_comparison,
            selected_plan_comparison=selected_plan_comparison,
            scenario_simulation=scenario_simulation,
            scenario_comparison=scenario_comparison,
            best_scenario_insight=best_scenario_insight,
            improvement_priority=improvement_priority,
        )
        decision_summary = self._build_decision_summary(
            query=query,
            application_plans=application_plans,
            plan_comparison=plan_comparison,
            selected_plan_comparison=selected_plan_comparison,
            best_scenario_insight=best_scenario_insight,
            scenario_simulation=scenario_simulation,
            scenario_comparison=scenario_comparison,
            improvement_priority=improvement_priority,
            next_action_guide=next_action_guide,
        )
        decision_summary_compact = self._build_decision_summary_compact(
            application_plans=application_plans,
            plan_comparison=plan_comparison,
            plan_delta=plan_delta,
            best_scenario_insight=best_scenario_insight,
            improvement_priority=improvement_priority,
            next_action_guide=next_action_guide,
        )
        summary = self._build_summary(query=query, counts=counts, total_items=len(items))
        assistant_reply, paragraphs = self._build_assistant_reply(
            query=query,
            counts=counts,
            items=items,
            decision_summary_compact=decision_summary_compact,
            application_plan=application_plan,
            application_plans=application_plans,
            plan_comparison=plan_comparison,
            plan_delta=plan_delta,
            selected_plan_comparison=selected_plan_comparison,
            scenario_simulation=scenario_simulation,
            scenario_comparison=scenario_comparison,
            best_scenario_insight=best_scenario_insight,
            improvement_priority=improvement_priority,
            next_action_guide=next_action_guide,
        )

        metadata = payload.get("metadata", {}) if isinstance(payload.get("metadata"), dict) else {}
        metadata = {
            **metadata,
            "totalCount": len(items),
        }

        return {
            "summary": summary,
            "assistantReply": assistant_reply,
            "assistantReplyParagraphs": paragraphs,
            "items": items,
            **({"applicationPlan": application_plan} if application_plan is not None else {}),
            **({"applicationPlans": application_plans} if application_plans else {}),
            **({"planComparison": plan_comparison} if plan_comparison is not None else {}),
            **({"planDelta": plan_delta} if plan_delta is not None else {}),
            **({"selectedPlanComparison": selected_plan_comparison} if selected_plan_comparison is not None else {}),
            **({"scenarioSimulation": scenario_simulation} if scenario_simulation is not None else {}),
            **({"scenarioComparison": scenario_comparison} if scenario_comparison is not None else {}),
            **({"bestScenarioInsight": best_scenario_insight} if best_scenario_insight is not None else {}),
            **({"improvementPriority": improvement_priority} if improvement_priority is not None else {}),
            **({"nextActionGuide": next_action_guide} if next_action_guide is not None else {}),
            **({"decisionSummary": decision_summary} if decision_summary is not None else {}),
            **({"decisionSummaryCompact": decision_summary_compact} if decision_summary_compact is not None else {}),
            "groups": {
                "reach": payload.get("reach", []),
                "target": payload.get("target", []),
                "safety": payload.get("safety", []),
            },
            "metadata": metadata,
            "profile": self._query_to_profile(query, selected_plan=selected_plan, scenario_input=scenario_input),
        }

    def _build_query(self, profile: dict[str, Any]) -> RecommendationQuery:
        country = self._as_optional_str(profile.get("country"))
        country_policy = self._as_optional_str(profile.get("countryPolicy")) or self._as_optional_str(
            profile.get("country_policy")
        )
        ielts_score = self._as_optional_float(profile.get("ielts")) or self._as_optional_float(
            profile.get("ielts_score")
        ) or self._as_optional_float(profile.get("ieltsScore"))
        toefl_score = self._as_optional_float(profile.get("toefl")) or self._as_optional_float(
            profile.get("toefl_score")
        ) or self._as_optional_float(profile.get("toeflScore"))
        gpa_score = self._as_optional_float(profile.get("gpa")) or self._as_optional_float(
            profile.get("gpa_score")
        ) or self._as_optional_float(profile.get("gpaScore"))
        duolingo_score = self._as_optional_float(profile.get("duolingo")) or self._as_optional_float(
            profile.get("duolingo_score")
        ) or self._as_optional_float(profile.get("duolingoScore"))
        target_rank = self._as_optional_int(profile.get("targetRank")) or self._as_optional_int(
            profile.get("target_rank")
        ) or 100
        risk_profile = self._as_optional_str(profile.get("riskProfile")) or self._as_optional_str(
            profile.get("risk_profile")
        ) or "balanced"
        preferred_ranking_source = self._as_optional_str(
            profile.get("preferredRankingSource")
        ) or self._as_optional_str(profile.get("preferred_ranking_source"))
        limit = self._as_optional_int(profile.get("limit")) or 5
        # Not the wall clock: the warehouse has rows for one year, so
        # datetime.now().year starts returning nothing the moment it rolls
        # past the snapshot -- an empty result that reads like a data outage.
        ranking_year = self._as_optional_int(profile.get("rankingYear")) or self._as_optional_int(
            profile.get("ranking_year")
        ) or DEFAULT_RANKING_YEAR
        preference_weights = profile.get("preferenceWeights") or profile.get("preference_weights") or {}
        if not isinstance(preference_weights, dict):
            preference_weights = {}

        return RecommendationQuery(
            country=country,
            country_policy=country_policy or "hard_filter",
            ielts_score=ielts_score,
            toefl_score=toefl_score,
            gpa_score=gpa_score,
            duolingo_score=duolingo_score,
            target_rank=target_rank,
            risk_profile=risk_profile,
            preference_weights={
                str(key): float(value)
                for key, value in preference_weights.items()
                if self._is_number(value)
            },
            preferred_ranking_source=preferred_ranking_source,
            limit=max(1, min(int(limit), 20)),
            ranking_year=ranking_year,
        )

    def _run_recommendation_pipeline(
        self,
        repo: RecommendationRepository,
        query: RecommendationQuery,
        *,
        config: Any,
    ) -> dict[str, Any]:
        effective_country = (
            query.country
            if query.country and (query.country_policy or config.country_match_policy) == "hard_filter"
            else None
        )
        candidates = repo.fetch_candidates(
            ranking_year=query.ranking_year,
            country=effective_country,
        )
        grouped = recommend_universities_v3(candidates, query, config=config)
        return grouped_recommendations_to_dict(grouped)

    def _flatten_grouped_results(
        self,
        payload: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, int]]:
        items: list[dict[str, Any]] = []
        counts: dict[str, int] = {}

        for category in ("reach", "target", "safety"):
            rows = payload.get(category, [])
            if not isinstance(rows, list):
                continue
            counts[category] = len(rows)
            for row in rows:
                if not isinstance(row, dict):
                    continue
                breakdown = row.get("score_breakdown", {}) if isinstance(row.get("score_breakdown"), dict) else {}
                deadline_highlight = self._build_deadline_highlight(row.get("deadline_info"))
                ielts_highlight = self._build_ielts_fit_highlight(row.get("ielts_fit_info"))
                toefl_highlight = self._build_requirement_fit_highlight("TOEFL", row.get("toefl_fit_info"))
                gpa_highlight = self._build_requirement_fit_highlight("GPA", row.get("gpa_fit_info"))
                duolingo_highlight = self._build_requirement_fit_highlight("Duolingo", row.get("duolingo_fit_info"))
                admission_composite = self._build_admission_composite(row.get("admission_composite"))
                admission_resolved = self._build_admission_resolved(row)
                admission_resolved_lines = self._build_admission_resolved_lines(admission_resolved)
                decision_output = self._build_decision_output(row.get("decision_output"))
                decision_output = self._append_admission_trust_to_decision_output(
                    decision_output,
                    admission_resolved,
                )
                decision_strategy = self._build_decision_strategy(row.get("decision_strategy"))

                item = {
                    "canonicalUniversityId": row.get("canonical_university_id"),
                    "universityName": row.get("university_name"),
                    "country": row.get("country"),
                    "aggregatedRank": row.get("aggregated_rank"),
                    "gpaRequirement": row.get("gpa_requirement"),
                    "ieltsRequirement": row.get("ielts_requirement"),
                    "toeflRequirement": row.get("toefl_requirement"),
                    "duolingoRequirement": row.get("duolingo_requirement"),
                    "matchingScore": row.get("score"),
                    "category": row.get("category") or category,
                    "decision": row.get("category") or category,
                    "preferenceAlignment": row.get("preference_alignment"),
                    "recommendationConfidence": row.get("recommendation_confidence"),
                    "confidence": row.get("recommendation_confidence"),
                    "confidenceReason": row.get("confidence_reason"),
                    "reason": row.get("explanation"),
                    "fitSummary": row.get("explanation"),
                    "rankingSource": breakdown.get("effective_rank_source"),
                    "rank": breakdown.get("effective_rank_used") or row.get("aggregated_rank"),
                    "riskLevel": row.get("category") or category,
                    "scoreBreakdown": breakdown,
                    **({"deadlineInfo": row.get("deadline_info")} if isinstance(row.get("deadline_info"), dict) else {}),
                    **({"deadlineHighlight": deadline_highlight} if deadline_highlight is not None else {}),
                    **({"ieltsFitInfo": row.get("ielts_fit_info")} if isinstance(row.get("ielts_fit_info"), dict) else {}),
                    **({"ieltsFitHighlight": ielts_highlight} if ielts_highlight is not None else {}),
                    **({"toeflFitInfo": row.get("toefl_fit_info")} if isinstance(row.get("toefl_fit_info"), dict) else {}),
                    **({"toeflFitHighlight": toefl_highlight} if toefl_highlight is not None else {}),
                    **({"gpaFitInfo": row.get("gpa_fit_info")} if isinstance(row.get("gpa_fit_info"), dict) else {}),
                    **({"gpaFitHighlight": gpa_highlight} if gpa_highlight is not None else {}),
                    **({"duolingoFitInfo": row.get("duolingo_fit_info")} if isinstance(row.get("duolingo_fit_info"), dict) else {}),
                    **({"duolingoFitHighlight": duolingo_highlight} if duolingo_highlight is not None else {}),
                    **({"admissionComposite": admission_composite} if admission_composite is not None else {}),
                    **({"decisionOutput": decision_output} if decision_output is not None else {}),
                    **({"decisionStrategy": decision_strategy} if decision_strategy is not None else {}),
                    **({"admissionResolved": admission_resolved} if admission_resolved else {}),
                    **({"admissionResolvedLines": admission_resolved_lines} if admission_resolved_lines else {}),
                }

                surface_signals = self._rank_signals_for_surface(item)
                if surface_signals:
                    item["surfaceSignals"] = surface_signals

                items.append(item)

        return items, counts

    def _build_summary(
        self,
        *,
        query: RecommendationQuery,
        counts: dict[str, int],
        total_items: int,
    ) -> str:
        parts = [f"Built {total_items} recommendation candidates"]
        if query.country:
            parts.append(f"for {query.country}")
        if query.ielts_score is not None:
            parts.append(f"with IELTS {query.ielts_score}")
        if query.target_rank is not None:
            parts.append(f"targeting rank {query.target_rank}")
        if counts:
            spread = ", ".join(
                f"{category}={count}" for category, count in counts.items() if count > 0
            )
            if spread:
                parts.append(f"({spread})")
        return " ".join(parts) + "."

    def _build_assistant_reply(
        self,
        *,
        query: RecommendationQuery,
        counts: dict[str, int],
        items: list[dict[str, Any]],
        application_plan: dict[str, Any] | None = None,
        application_plans: list[dict[str, Any]] | None = None,
        plan_comparison: dict[str, Any] | None = None,
        plan_delta: dict[str, Any] | None = None,
        selected_plan_comparison: dict[str, Any] | None = None,
        scenario_simulation: dict[str, Any] | None = None,
        scenario_comparison: dict[str, Any] | None = None,
        best_scenario_insight: dict[str, Any] | None = None,
        improvement_priority: dict[str, Any] | None = None,
        next_action_guide: dict[str, Any] | None = None,
        decision_summary_compact: dict[str, Any] | None = None,
    ) -> tuple[str, list[str]]:
        if not items:
            paragraphs = [
                "I checked the current recommendation path but did not find any candidates that fit the profile you provided.",
                "If you want, we can widen the target rank, relax the country filter, or adjust the language score assumptions.",
            ]
            return "\n\n".join(paragraphs), paragraphs

        summary_line = self._build_compact_summary_line(decision_summary_compact)
        top_names = [str(item.get("universityName")) for item in items[:3] if item.get("universityName")]
        first = top_names[0] if top_names else "the top result"
        country_text = f" in {query.country}" if query.country else ""

        paragraphs = []
        if summary_line:
            paragraphs.append(summary_line)
        paragraphs.append(
            f"I built a recommendation slice{country_text} and {first} currently looks like the strongest fit in the retrieved results."
        )

        if top_names:
            paragraphs.append(
                "The shortlist that stands out most right now is "
                + ", ".join(top_names)
                + "."
            )

        spread = [f"{category} {count}" for category, count in counts.items() if count > 0]
        if spread:
            paragraphs.append(
                "The current recommendation spread is "
                + ", ".join(spread)
                + "."
            )

        if query.ielts_score is not None or query.target_rank is not None:
            profile_bits = []
            if query.ielts_score is not None:
                profile_bits.append(f"IELTS {query.ielts_score}")
            if query.toefl_score is not None:
                profile_bits.append(f"TOEFL {int(query.toefl_score) if float(query.toefl_score).is_integer() else query.toefl_score}")
            if query.gpa_score is not None:
                profile_bits.append(f"GPA {query.gpa_score}")
            if query.duolingo_score is not None:
                profile_bits.append(
                    f"Duolingo {int(query.duolingo_score) if float(query.duolingo_score).is_integer() else query.duolingo_score}"
                )
            if query.target_rank is not None:
                profile_bits.append(f"target rank {query.target_rank}")
            paragraphs.append(
                "This pass was grounded in " + " and ".join(profile_bits) + "."
            )

        surfaced_notes = self._build_surfaced_signal_notes(items[0]) if items else []
        if surfaced_notes:
            paragraphs.append("This option shows a few key considerations.")
            paragraphs.extend(surfaced_notes[: self.MAX_SURFACED_SIGNALS])

        composite_note = self._build_admission_composite_note(items[0]) if items else None
        resolved_note = self._build_admission_resolved_note(items[0]) if items else None
        if resolved_note:
            paragraphs.append(resolved_note)
        if composite_note:
            paragraphs.append(composite_note)
        decision_note = self._build_decision_output_note(items[0]) if items else None
        if decision_note:
            paragraphs.append(decision_note)
        strategy_note = self._build_decision_strategy_note(items[0]) if items else None
        if strategy_note:
            paragraphs.append(strategy_note)
        application_plan_note = self._build_application_plan_note(application_plan)
        if application_plan_note:
            paragraphs.extend(application_plan_note)
        multi_plan_note = self._build_multi_plan_note(application_plans, plan_comparison)
        if multi_plan_note:
            paragraphs.extend(multi_plan_note)
        plan_delta_note = self._build_plan_delta_note(plan_delta)
        if plan_delta_note:
            paragraphs.extend(plan_delta_note)
        selected_plan_comparison_note = self._build_selected_plan_comparison_note(selected_plan_comparison)
        if selected_plan_comparison_note:
            paragraphs.extend(selected_plan_comparison_note)
        scenario_simulation_note = self._build_scenario_simulation_note(scenario_simulation)
        if scenario_simulation_note:
            paragraphs.extend(scenario_simulation_note)
        scenario_comparison_note = self._build_scenario_comparison_note(
            scenario_comparison,
            best_scenario_insight,
        )
        if scenario_comparison_note:
            paragraphs.extend(scenario_comparison_note)
        improvement_priority_note = self._build_improvement_priority_note(improvement_priority)
        if improvement_priority_note:
            paragraphs.extend(improvement_priority_note)
        next_action_guide_note = self._build_next_action_guide_note(next_action_guide)
        if next_action_guide_note:
            paragraphs.extend(next_action_guide_note)

        return "\n\n".join(paragraphs), paragraphs

    def _query_to_profile(
        self,
        query: RecommendationQuery,
        *,
        selected_plan: str | None = None,
        scenario_input: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        profile = {
            "country": query.country,
            "countryPolicy": query.country_policy,
            "ielts": query.ielts_score,
            "toefl": query.toefl_score,
            "gpa": query.gpa_score,
            "duolingo": query.duolingo_score,
            "targetRank": query.target_rank,
            "riskProfile": query.risk_profile,
            "preferredRankingSource": query.preferred_ranking_source,
            "limit": query.limit,
            "rankingYear": query.ranking_year,
            "preferenceWeights": query.preference_weights,
        }
        if selected_plan is not None:
            profile["selectedPlan"] = selected_plan
        if scenario_input is not None:
            profile["scenario"] = scenario_input
        return profile

    def _as_optional_str(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _build_deadline_highlight(self, deadline_info: Any) -> dict[str, Any] | None:
        if not isinstance(deadline_info, dict):
            return None
        date = deadline_info.get("recommended_deadline")
        if not isinstance(date, str) or not date:
            return None

        deadline_type = str(deadline_info.get("deadline_type") or "unknown")
        urgency = str(deadline_info.get("urgency") or "unknown")
        reason = str(deadline_info.get("reason") or "").strip()

        if deadline_type != "unknown":
            message_prefix = f"{deadline_type.capitalize()} deadline on {date}"
        else:
            message_prefix = f"Deadline on {date}"

        if urgency == "high":
            message = f"{message_prefix} should be prioritized."
        elif urgency == "medium":
            message = f"{message_prefix} deserves planning attention."
        elif urgency == "low":
            message = f"{message_prefix} is currently lower urgency."
        else:
            message = f"{message_prefix} is available."

        payload: dict[str, Any] = {
            "date": date,
            "type": deadline_type,
            "urgency": urgency,
            "message": message,
        }
        if reason:
            payload["reason"] = reason
        return payload

    def _build_deadline_note(self, item: dict[str, Any]) -> str | None:
        highlight = item.get("deadlineHighlight")
        if not isinstance(highlight, dict):
            return None
        message = highlight.get("message")
        if not isinstance(message, str) or not message:
            return None
        reason = highlight.get("reason")
        if isinstance(reason, str) and reason:
            return f"Deadline note: {message} Reason: {reason}"
        return f"Deadline note: {message}"

    def _build_ielts_fit_highlight(self, ielts_fit_info: Any) -> dict[str, Any] | None:
        return self._build_requirement_fit_highlight("IELTS", ielts_fit_info)

    def _build_requirement_fit_highlight(self, subject: str, fit_info: Any) -> dict[str, Any] | None:
        if not isinstance(fit_info, dict):
            return None

        required_score = fit_info.get("required_score")
        user_score = fit_info.get("user_score")
        margin = fit_info.get("margin")
        fit_band = str(fit_info.get("fit_band") or "unknown")
        fit_urgency = str(fit_info.get("fit_urgency") or "unknown")
        reason = str(fit_info.get("reason") or "").strip()

        if not isinstance(required_score, (int, float)) or not isinstance(user_score, (int, float)):
            return None
        if not isinstance(margin, (int, float)):
            return None

        margin_value = float(margin)
        payload: dict[str, Any] = {
            "requiredScore": float(required_score),
            "userScore": float(user_score),
            "margin": margin_value,
            "fitBand": fit_band,
            "fitUrgency": fit_urgency,
            "message": self._build_requirement_fit_message(subject, fit_band, margin_value),
        }
        if reason:
            payload["reason"] = reason
        return payload

    def _build_requirement_fit_message(self, subject: str, fit_band: str, margin_value: float) -> str:
        if subject in {"IELTS", "GPA"}:
            margin_text = f"{abs(margin_value):.1f}"
        else:
            margin_text = (
                str(int(abs(margin_value)))
                if float(abs(margin_value)).is_integer()
                else f"{abs(margin_value):.1f}"
            )

        if fit_band == "comfortably_above":
            return f"{subject} +{margin_text} above requirement"
        if fit_band == "meets_requirement":
            return f"{subject} meets requirement"
        if fit_band in {"slightly_below", "well_below"}:
            return f"{subject} {margin_text} below requirement"
        return f"{subject} fit available"

    def _build_requirement_notes(self, item: dict[str, Any]) -> list[str]:
        notes: list[str] = []
        for label, key in (
            ("IELTS", "ieltsFitInfo"),
            ("TOEFL", "toeflFitInfo"),
            ("GPA", "gpaFitInfo"),
            ("Duolingo", "duolingoFitInfo"),
        ):
            info = item.get(key)
            if not isinstance(info, dict):
                continue
            reason = info.get("reason")
            if not isinstance(reason, str) or not reason:
                continue
            fit_band = str(info.get("fit_band") or info.get("fitBand") or "")
            if fit_band in {"slightly_below", "well_below"}:
                notes.append(f"{label} note: {reason}, so this option is higher risk.")
            else:
                notes.append(f"{label} note: {reason}.")
        return notes

    def _rank_signals_for_surface(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        ranked: list[dict[str, Any]] = []

        for signal_type, info_key, highlight_key in (
            ("ielts", "ieltsFitInfo", "ieltsFitHighlight"),
            ("toefl", "toeflFitInfo", "toeflFitHighlight"),
            ("gpa", "gpaFitInfo", "gpaFitHighlight"),
            ("duolingo", "duolingoFitInfo", "duolingoFitHighlight"),
        ):
            info = item.get(info_key)
            highlight = item.get(highlight_key)
            if not isinstance(info, dict) or not isinstance(highlight, dict):
                continue
            fit_band = str(info.get("fit_band") or info.get("fitBand") or "")
            concern = f"{signal_type}_{fit_band}" if fit_band else ""
            if not concern:
                continue
            definition = concern_definition(concern)
            priority_level = concern_priority_level(concern)
            ranked.append(
                {
                    "type": signal_type,
                    "concern": concern,
                    "label": definition["label"],
                    "message": highlight.get("message"),
                    "urgency": info.get("fit_urgency") or info.get("fitUrgency") or "unknown",
                    "priorityLevel": priority_level,
                    "priorityScore": priority_level * 10 + self._surface_type_order(signal_type),
                    "emphasized": False,
                }
            )

        deadline_info = item.get("deadlineInfo")
        deadline_highlight = item.get("deadlineHighlight")
        if isinstance(deadline_info, dict) and isinstance(deadline_highlight, dict):
            urgency = str(deadline_info.get("urgency") or deadline_highlight.get("urgency") or "unknown")
            concern = self._deadline_concern_from_info(deadline_info)
            if concern:
                definition = concern_definition(concern)
                priority_level = concern_priority_level(concern)
                ranked.append(
                    {
                        "type": "deadline",
                        "concern": concern,
                        "label": definition["label"],
                        "message": deadline_highlight.get("message"),
                        "urgency": urgency,
                        "priorityLevel": priority_level,
                        "priorityScore": priority_level * 10 + self._surface_type_order("deadline"),
                        "emphasized": False,
                    }
                )

        composite = item.get("admissionComposite")
        top_concerns = composite.get("topConcerns") if isinstance(composite, dict) else None
        if isinstance(top_concerns, list):
            allowed = {token for token in top_concerns if isinstance(token, str)}
            ranked = [signal for signal in ranked if str(signal.get("concern") or "") in allowed]

        ordered = sorted(
            ranked,
            key=lambda signal: (
                int(signal.get("priorityLevel", 99)),
                int(signal.get("priorityScore", 999)),
                self._surface_type_order(str(signal.get("type") or "")),
            ),
        )
        for index, signal in enumerate(ordered):
            signal["emphasized"] = index < self.MAX_SURFACED_SIGNALS
        return ordered

    def _deadline_concern_from_info(self, deadline_info: dict[str, Any]) -> str | None:
        deadline_type = str(deadline_info.get("deadline_type") or "")
        urgency = str(deadline_info.get("urgency") or "")
        if deadline_type == "early":
            return "early_deadline"
        if urgency == "high":
            return "high_urgency_deadline"
        if urgency == "medium":
            return "medium_urgency_deadline"
        return None

    def _surface_type_order(self, signal_type: str) -> int:
        order = {
            "ielts": 0,
            "toefl": 1,
            "gpa": 2,
            "duolingo": 3,
            "deadline": 4,
        }
        return order.get(signal_type, 99)

    def _build_surfaced_signal_notes(self, item: dict[str, Any]) -> list[str]:
        signals = item.get("surfaceSignals")
        if not isinstance(signals, list):
            return []

        notes: list[str] = []
        for signal in signals:
            if not isinstance(signal, dict) or not signal.get("emphasized"):
                continue
            signal_type = str(signal.get("type") or "")
            if signal_type == "deadline":
                note = self._build_deadline_note(item)
            else:
                note = self._build_requirement_note_for_type(item, signal_type)
            if note:
                notes.append(note)
        return notes

    def _build_requirement_note_for_type(self, item: dict[str, Any], signal_type: str) -> str | None:
        key_map = {
            "ielts": ("IELTS", "ieltsFitInfo"),
            "toefl": ("TOEFL", "toeflFitInfo"),
            "gpa": ("GPA", "gpaFitInfo"),
            "duolingo": ("Duolingo", "duolingoFitInfo"),
        }
        pair = key_map.get(signal_type)
        if pair is None:
            return None
        label, key = pair
        info = item.get(key)
        if not isinstance(info, dict):
            return None
        reason = info.get("reason")
        if not isinstance(reason, str) or not reason:
            return None
        fit_band = str(info.get("fit_band") or info.get("fitBand") or "")
        if fit_band in {"slightly_below", "well_below"}:
            return f"{label} note: {reason}, so this option is higher risk."
        return f"{label} note: {reason}."

    def _append_admission_trust_to_decision_output(
        self,
        decision_output: dict[str, Any] | None,
        admission_resolved: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not isinstance(decision_output, dict):
            return decision_output
        if not self._has_conflicting_admission_signal(admission_resolved):
            return decision_output

        reason = decision_output.get("decisionReason")
        if not isinstance(reason, str) or not reason:
            return decision_output

        message = "Some requirement signals are inconsistent across sources."
        if message in reason:
            return decision_output

        return {
            **decision_output,
            "decisionReason": self._append_sentence(reason, message),
        }

    def _build_admission_resolved(self, row: dict[str, Any]) -> dict[str, dict[str, Any]]:
        raw = row.get("admission_resolved") or row.get("admissionResolved")
        if not isinstance(raw, dict):
            return {}

        resolved: dict[str, dict[str, Any]] = {}
        for field in sorted(ADMISSION_RESOLVED_FIELDS):
            source = raw.get(field)
            if source is None:
                continue
            mapped = self._map_resolved_admission_field(source)
            if mapped is not None:
                resolved[field] = mapped
        return resolved

    def _map_resolved_admission_field(self, source: Any) -> dict[str, Any] | None:
        if isinstance(source, dict):
            value = source.get("resolved_value", source.get("value"))
            confidence = source.get("confidence")
            source_count = source.get("source_count", source.get("sourceCount"))
            status = source.get("status")
        else:
            value = getattr(source, "resolved_value", getattr(source, "value", None))
            confidence = getattr(source, "confidence", None)
            source_count = getattr(source, "source_count", getattr(source, "sourceCount", None))
            status = getattr(source, "status", None)

        if confidence is None or source_count is None or not isinstance(status, str):
            return None

        payload: dict[str, Any] = {
            "value": value,
            "confidence": confidence,
            "sourceCount": source_count,
            "status": status,
        }
        return payload

    def _build_admission_resolved_lines(self, resolved: dict[str, dict[str, Any]]) -> list[str]:
        lines: list[str] = []
        for field in ("ielts", "toefl", "gpa", "duolingo", "deadline"):
            info = resolved.get(field)
            if not isinstance(info, dict):
                continue
            line = self._format_admission_resolved_line(field, info)
            if line is not None:
                lines.append(line)
        return lines

    def _build_admission_resolved_note(self, item: dict[str, Any]) -> str | None:
        lines = item.get("admissionResolvedLines")
        if not isinstance(lines, list):
            return None
        return next((line for line in lines if isinstance(line, str) and line), None)

    def _format_admission_resolved_line(self, field: str, info: dict[str, Any]) -> str | None:
        value = info.get("value")
        confidence = info.get("confidence")
        source_count = info.get("sourceCount")
        status = str(info.get("status") or "")
        if value is None or not isinstance(source_count, int):
            return None

        label = {
            "ielts": "IELTS",
            "toefl": "TOEFL",
            "gpa": "GPA",
            "duolingo": "Duolingo",
            "deadline": "Deadline",
        }.get(field, field.capitalize())
        value_text = self._format_admission_resolved_value(value)

        if status == "conflict":
            return f"{label} requirement: {value_text} (conflicting sources)"
        if status == "needs_review":
            return f"{label} requirement: {value_text} (needs verification)"

        confidence_label = self._admission_resolved_confidence_label(confidence)
        source_label = "source" if source_count == 1 else "sources"
        return (
            f"{label} requirement: {value_text} "
            f"(based on {source_count} {source_label}, {confidence_label} confidence)"
        )

    def _format_admission_resolved_value(self, value: Any) -> str:
        if isinstance(value, dict):
            parts = [
                f"{key} {value[key]}"
                for key in ("early", "final", "rolling")
                if key in value and value[key] is not None
            ]
            if parts:
                return ", ".join(parts)
            return json.dumps(value, sort_keys=True)
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    def _admission_resolved_confidence_label(self, confidence: Any) -> str:
        if not isinstance(confidence, (int, float)):
            return "unknown"
        if confidence >= 0.8:
            return "high"
        if confidence >= 0.6:
            return "medium"
        return "low"

    def _build_admission_composite(self, composite: Any) -> dict[str, Any] | None:
        if not isinstance(composite, dict):
            return None
        readiness = composite.get("admission_readiness")
        risk = composite.get("admission_risk")
        top_concerns = composite.get("top_concerns")
        top_concern_labels = composite.get("top_concern_labels")
        reason = composite.get("reason")
        if not isinstance(readiness, str) or not isinstance(risk, str):
            return None
        if not isinstance(top_concerns, list):
            top_concerns = []
        if not isinstance(top_concern_labels, list):
            top_concern_labels = []
        normalized_concerns = [str(token) for token in top_concerns[:3] if isinstance(token, str)]
        normalized_labels = [str(label) for label in top_concern_labels[:3] if isinstance(label, str) and label]
        if not normalized_labels and normalized_concerns:
            normalized_labels = [token.replace("_", " ").capitalize() for token in normalized_concerns]
        payload: dict[str, Any] = {
            "admissionReadiness": readiness,
            "admissionRisk": risk,
            "topConcerns": normalized_concerns,
            "topConcernLabels": normalized_labels,
        }
        if isinstance(reason, str) and reason:
            payload["reason"] = reason
        return payload

    def _build_admission_composite_note(self, item: dict[str, Any]) -> str | None:
        composite = item.get("admissionComposite")
        if not isinstance(composite, dict):
            return None
        readiness = composite.get("admissionReadiness")
        risk = composite.get("admissionRisk")
        top_concern_labels = composite.get("topConcernLabels")
        reason = composite.get("reason")
        if not isinstance(readiness, str) or not isinstance(risk, str):
            return None
        concern_text = None
        if isinstance(top_concern_labels, list):
            labels = [str(label) for label in top_concern_labels if isinstance(label, str) and label]
            if labels:
                concern_text = "; ".join(labels)
        if isinstance(reason, str) and reason and concern_text:
            return (
                f"Admission note: readiness is {readiness} and risk is {risk}. "
                f"Top concerns: {concern_text}. Reason: {reason}"
            )
        if isinstance(reason, str) and reason:
            return f"Admission note: readiness is {readiness} and risk is {risk}. Reason: {reason}"
        return f"Admission note: readiness is {readiness} and risk is {risk}."

    def _build_decision_output(self, decision_output: Any) -> dict[str, Any] | None:
        if not isinstance(decision_output, dict):
            return None
        action = decision_output.get("decision_action")
        strength = decision_output.get("decision_strength")
        reason = decision_output.get("decision_reason")
        next_steps = decision_output.get("recommended_next_steps")
        if not isinstance(action, str) or not isinstance(strength, str) or not isinstance(reason, str):
            return None
        if not isinstance(next_steps, list):
            next_steps = []
        return {
            "decisionAction": action,
            "decisionStrength": strength,
            "decisionReason": reason,
            "recommendedNextSteps": [
                step for step in next_steps[:3] if isinstance(step, str) and step
            ],
        }

    def _build_decision_strategy(self, decision_strategy: Any) -> dict[str, Any] | None:
        if not isinstance(decision_strategy, dict):
            return None
        primary = decision_strategy.get("primary_strategy")
        supporting = decision_strategy.get("supporting_actions")
        mitigation = decision_strategy.get("risk_mitigation")
        timeline = decision_strategy.get("timeline_hint")
        reason = decision_strategy.get("reason")
        if not isinstance(primary, str) or not isinstance(timeline, str) or not isinstance(reason, str):
            return None
        if not isinstance(supporting, list):
            supporting = []
        if not isinstance(mitigation, list):
            mitigation = []
        return {
            "primaryStrategy": primary,
            "supportingActions": [step for step in supporting[:3] if isinstance(step, str) and step],
            "riskMitigation": [step for step in mitigation[:3] if isinstance(step, str) and step],
            "timelineHint": timeline,
            "reason": reason,
        }

    def _build_decision_output_note(self, item: dict[str, Any]) -> str | None:
        decision = item.get("decisionOutput")
        if not isinstance(decision, dict):
            return None
        action = decision.get("decisionAction")
        strength = decision.get("decisionStrength")
        reason = decision.get("decisionReason")
        next_steps = decision.get("recommendedNextSteps")
        if not isinstance(action, str) or not isinstance(strength, str) or not isinstance(reason, str):
            return None
        action_label = action.replace("_", " ").capitalize()
        note = f"Suggested action: {action_label}. Confidence: {strength.capitalize()}. Reason: {reason}"
        if isinstance(next_steps, list):
            usable_steps = [step for step in next_steps[:2] if isinstance(step, str) and step]
            if usable_steps:
                note += " Next steps: " + "; ".join(usable_steps)
        return note

    def _build_decision_strategy_note(self, item: dict[str, Any]) -> str | None:
        strategy = item.get("decisionStrategy")
        if not isinstance(strategy, dict):
            return None
        primary = strategy.get("primaryStrategy")
        supporting = strategy.get("supportingActions")
        mitigation = strategy.get("riskMitigation")
        if not isinstance(primary, str) or not primary:
            return None
        parts = [f"Strategy: {primary}."]
        if isinstance(supporting, list):
            usable_supporting = [step for step in supporting[:1] if isinstance(step, str) and step]
            if usable_supporting:
                parts.append(f"Focus on {usable_supporting[0]}.")
        if isinstance(mitigation, list):
            usable_mitigation = [step for step in mitigation[:1] if isinstance(step, str) and step]
            if usable_mitigation:
                parts.append("Risk mitigation: " + usable_mitigation[0] + ".")
        return " ".join(parts)

    def _build_application_plan(self, items: list[dict[str, Any]]) -> dict[str, Any] | None:
        grouped = self._build_application_plan_groups(items)
        return self._build_application_plan_from_grouped(grouped, plan_name="balanced")

    def _build_application_plans(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped = self._build_application_plan_groups(items)
        plans: list[dict[str, Any]] = []

        balanced = self._build_application_plan_from_grouped(grouped, plan_name="balanced")
        if balanced is not None:
            plans.append(balanced)

        conservative_grouped = {
            "reach": list(grouped["reach"][:1]),
            "target": list(grouped["target"][:2]),
            "safety": list(grouped["safety"][:2]),
        }
        conservative = self._build_application_plan_from_grouped(
            conservative_grouped,
            plan_name="conservative",
        )
        if conservative is not None and self._is_valid_application_plan_variant(conservative):
            plans.append(conservative)

        aggressive_grouped = {
            "reach": list(grouped["reach"][:2]),
            "target": list(grouped["target"][:2]),
            "safety": list(grouped["safety"][:1]),
        }
        aggressive = self._build_application_plan_from_grouped(
            aggressive_grouped,
            plan_name="aggressive",
        )
        if aggressive is not None and self._is_valid_application_plan_variant(aggressive):
            plans.append(aggressive)

        return plans

    def _build_application_plan_groups(
        self,
        items: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        if not items:
            return {"reach": [], "target": [], "safety": []}

        grouped: dict[str, list[dict[str, Any]]] = {
            "reach": [],
            "target": [],
            "safety": [],
        }

        for item in items:
            if not isinstance(item, dict):
                continue
            category = self._application_plan_group(item)
            if category is None:
                continue
            grouped[category].append(self._application_plan_item(item))

        for category in grouped:
            grouped[category] = sorted(
                grouped[category],
                key=lambda row: (
                    -float(row.get("matchingScore", 0.0)),
                    str(row.get("universityName") or ""),
                ),
            )[:2]

        return grouped

    def _build_application_plan_from_grouped(
        self,
        grouped: dict[str, list[dict[str, Any]]],
        *,
        plan_name: str,
    ) -> dict[str, Any] | None:
        if not any(grouped.values()):
            return None

        risk_counts = {"high": 0, "medium": 0, "low": 0}
        for rows in grouped.values():
            for row in rows:
                risk = row.get("risk")
                if isinstance(risk, str) and risk in risk_counts:
                    risk_counts[risk] += 1
        plan_items = [
            row
            for rows in grouped.values()
            for row in rows
            if isinstance(row, dict)
        ]

        reach_count = len(grouped["reach"])
        target_count = len(grouped["target"])
        safety_count = len(grouped["safety"])
        primary_choice = self._build_application_plan_primary_choice(grouped)
        quality_adjustment = self._build_application_plan_quality_adjustment(
            target=grouped["target"],
            safety=grouped["safety"],
        )
        warnings = self._build_application_plan_warnings(
            reach_count=reach_count,
            target_count=target_count,
            safety_count=safety_count,
            total_count=reach_count + target_count + safety_count,
            risk_distribution=self._build_application_plan_risk_label(
                risk_counts=risk_counts,
                safety_count=safety_count,
            ),
        )
        confidence = self._build_application_plan_confidence(
            reach_count=reach_count,
            target_count=target_count,
            safety_count=safety_count,
            primary_choice=primary_choice,
            quality_adjustment=quality_adjustment,
        )

        public_grouped = {
            category: [self._application_plan_public_item(row) for row in rows]
            for category, rows in grouped.items()
        }

        confidence_reason = self._append_admission_trust_to_plan_confidence_reason(
            self._build_application_plan_confidence_reason(
                target_count=target_count,
                safety_count=safety_count,
                warnings=warnings,
                quality_adjustment=quality_adjustment,
                confidence=confidence,
            ),
            plan_items,
        )

        return {
            "planName": plan_name,
            "reach": public_grouped["reach"],
            "target": public_grouped["target"],
            "safety": public_grouped["safety"],
            "planSummary": (
                f"Balanced plan with {reach_count} reach, {target_count} target, "
                f"and {safety_count} safety options."
                if plan_name == "balanced"
                else f"{plan_name.capitalize()} plan with {reach_count} reach, {target_count} target, "
                f"and {safety_count} safety options."
            ),
            "riskDistribution": self._build_application_plan_risk_distribution(
                risk_counts=risk_counts,
                safety_count=safety_count,
            ),
            "recommendedStrategy": self._build_application_plan_strategy(
                reach_count=reach_count,
                target_count=target_count,
                safety_count=safety_count,
                risk_counts=risk_counts,
            ),
            **({"primaryChoice": primary_choice} if primary_choice is not None else {}),
            "planWarnings": warnings,
            "planConfidence": confidence,
            "planConfidenceReason": confidence_reason,
        }

    def _is_valid_application_plan_variant(self, plan: dict[str, Any]) -> bool:
        plan_name = str(plan.get("planName") or "")
        reach = plan.get("reach")
        target = plan.get("target")
        safety = plan.get("safety")
        if not isinstance(reach, list) or not isinstance(target, list) or not isinstance(safety, list):
            return False

        if plan_name == "conservative":
            return len(safety) >= 1 and len(reach) <= 1
        if plan_name == "aggressive":
            return len(reach) >= 1 and len(safety) <= 1
        return True

    def _build_plan_comparison(self, application_plans: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not application_plans:
            return None

        plan_map = {
            str(plan.get("planName")): plan
            for plan in application_plans
            if isinstance(plan, dict) and isinstance(plan.get("planName"), str)
        }
        confidence_rank = {"high": 2, "medium": 1, "low": 0}

        balanced = plan_map.get("balanced")
        if (
            isinstance(balanced, dict)
            and confidence_rank.get(str(balanced.get("planConfidence")), -1) == 2
        ):
            recommended = balanced
        else:
            candidates = [
                plan
                for plan_name in ("conservative", "aggressive")
                for plan in [plan_map.get(plan_name)]
                if isinstance(plan, dict)
            ]
            recommended = balanced
            if candidates:
                recommended = candidates[0]
                for candidate in candidates[1:]:
                    recommended = self._prefer_application_plan(recommended, candidate, confidence_rank)
        if not isinstance(recommended, dict):
            recommended = next((plan for plan in application_plans if isinstance(plan, dict)), None)
        if not isinstance(recommended, dict):
            return None

        recommended_name = str(recommended.get("planName") or "balanced")
        reason = self._build_plan_comparison_reason(recommended)
        tradeoffs = self._build_plan_tradeoffs(application_plans, recommended_name)
        return {
            "recommendedPlan": recommended_name,
            "reason": reason,
            "tradeoffs": tradeoffs,
        }

    def _prefer_application_plan(
        self,
        current: dict[str, Any],
        candidate: dict[str, Any],
        confidence_rank: dict[str, int],
    ) -> dict[str, Any]:
        current_confidence = confidence_rank.get(str(current.get("planConfidence")), -1)
        candidate_confidence = confidence_rank.get(str(candidate.get("planConfidence")), -1)
        if candidate_confidence > current_confidence:
            return candidate
        if candidate_confidence < current_confidence:
            return current

        current_reach = len(current.get("reach") or []) if isinstance(current.get("reach"), list) else 0
        candidate_reach = len(candidate.get("reach") or []) if isinstance(candidate.get("reach"), list) else 0
        current_safety = len(current.get("safety") or []) if isinstance(current.get("safety"), list) else 0
        candidate_safety = len(candidate.get("safety") or []) if isinstance(candidate.get("safety"), list) else 0
        current_target = len(current.get("target") or []) if isinstance(current.get("target"), list) else 0
        candidate_target = len(candidate.get("target") or []) if isinstance(candidate.get("target"), list) else 0
        current_name = str(current.get("planName") or "")
        candidate_name = str(candidate.get("planName") or "")

        if (
            candidate_name == "aggressive"
            and current_name == "conservative"
            and candidate_reach > current_reach
            and candidate_target >= current_target
            and candidate_target > 0
        ):
            return candidate
        if (
            candidate_name == "conservative"
            and current_name == "aggressive"
            and (candidate_safety > current_safety or (candidate_target == 0 and current_target == 0))
        ):
            return candidate
        if candidate_name == "conservative" and current_name != "conservative":
            return candidate
        return current

    def _build_plan_comparison_reason(self, plan: dict[str, Any]) -> str:
        plan_name = str(plan.get("planName") or "balanced")
        confidence = str(plan.get("planConfidence") or "medium")
        if plan_name == "balanced":
            return "Balanced is recommended because it keeps the strongest overall mix with stable confidence."
        if plan_name == "conservative":
            return f"Conservative is recommended because it preserves safer coverage with {confidence} confidence."
        return f"Aggressive is recommended because it keeps more upside options while still holding {confidence} confidence."

    def _build_plan_tradeoffs(
        self,
        application_plans: list[dict[str, Any]],
        recommended_plan: str,
    ) -> list[str]:
        tradeoffs: list[str] = []
        for plan in application_plans:
            if not isinstance(plan, dict):
                continue
            plan_name = str(plan.get("planName") or "")
            if not plan_name or plan_name == recommended_plan:
                continue
            tradeoffs.append(
                f"{plan_name.capitalize()}: {self._build_plan_tradeoff_line(plan)}"
            )
        return tradeoffs[:2]

    def _build_plan_tradeoff_line(self, plan: dict[str, Any]) -> str:
        confidence = str(plan.get("planConfidence") or "medium")
        risk_distribution = str(plan.get("riskDistribution") or "")
        risk_label = risk_distribution.removeprefix("Overall plan risk: ").split(" ", 1)[0] if risk_distribution else "moderate"
        return f"{confidence} confidence with {risk_label} plan risk."

    def _build_selected_plan_comparison(
        self,
        application_plans: list[dict[str, Any]] | None,
        plan_comparison: dict[str, Any] | None,
        selected_plan_name: str | None,
    ) -> dict[str, Any] | None:
        if not application_plans or not isinstance(plan_comparison, dict) or selected_plan_name is None:
            return None

        recommended_name = self._normalize_plan_name(plan_comparison.get("recommendedPlan"))
        if recommended_name is None or selected_plan_name == recommended_name:
            return None

        plan_map = {
            str(plan.get("planName")): plan
            for plan in application_plans
            if isinstance(plan, dict) and isinstance(plan.get("planName"), str)
        }
        recommended_plan = plan_map.get(recommended_name)
        selected_plan = plan_map.get(selected_plan_name)
        if not isinstance(recommended_plan, dict) or not isinstance(selected_plan, dict):
            return None

        differences = self._build_selected_plan_difference_lines(
            selected_plan=selected_plan,
            recommended_plan=recommended_plan,
        )
        summary = self._build_selected_plan_summary(
            selected_plan=selected_plan,
            recommended_plan=recommended_plan,
        )
        return {
            "selectedPlan": selected_plan_name,
            "recommendedPlan": recommended_name,
            "summary": summary,
            "differences": differences,
        }

    def _build_selected_plan_difference_lines(
        self,
        *,
        selected_plan: dict[str, Any],
        recommended_plan: dict[str, Any],
    ) -> list[str]:
        lines: list[str] = []

        selected_safety = len(selected_plan.get("safety") or []) if isinstance(selected_plan.get("safety"), list) else 0
        recommended_safety = len(recommended_plan.get("safety") or []) if isinstance(recommended_plan.get("safety"), list) else 0
        if selected_safety < recommended_safety:
            lines.append("The selected plan keeps less safety coverage than the recommended plan.")
        elif selected_safety > recommended_safety:
            lines.append("The selected plan keeps more safety coverage than the recommended plan.")

        selected_confidence = self._plan_confidence_rank(selected_plan)
        recommended_confidence = self._plan_confidence_rank(recommended_plan)
        if selected_confidence < recommended_confidence:
            lines.append("The selected plan has lower overall confidence than the recommended plan.")
        elif selected_confidence > recommended_confidence:
            lines.append("The selected plan has higher overall confidence than the recommended plan.")

        selected_warnings = self._plan_warning_count(selected_plan)
        recommended_warnings = self._plan_warning_count(recommended_plan)
        if selected_warnings > recommended_warnings:
            lines.append("The selected plan carries more warning signals than the recommended plan.")
        elif selected_warnings < recommended_warnings:
            lines.append("The selected plan carries fewer warning signals than the recommended plan.")

        selected_reach = len(selected_plan.get("reach") or []) if isinstance(selected_plan.get("reach"), list) else 0
        recommended_reach = len(recommended_plan.get("reach") or []) if isinstance(recommended_plan.get("reach"), list) else 0
        if selected_reach > recommended_reach:
            lines.append("The selected plan keeps more upside through reach options.")
        elif selected_reach < recommended_reach:
            lines.append("The selected plan reduces reach exposure compared with the recommended plan.")

        return lines[:3]

    def _build_selected_plan_summary(
        self,
        *,
        selected_plan: dict[str, Any],
        recommended_plan: dict[str, Any],
    ) -> str:
        selected_safety = len(selected_plan.get("safety") or []) if isinstance(selected_plan.get("safety"), list) else 0
        recommended_safety = len(recommended_plan.get("safety") or []) if isinstance(recommended_plan.get("safety"), list) else 0
        selected_reach = len(selected_plan.get("reach") or []) if isinstance(selected_plan.get("reach"), list) else 0
        recommended_reach = len(recommended_plan.get("reach") or []) if isinstance(recommended_plan.get("reach"), list) else 0

        more_conservative = selected_safety > recommended_safety or selected_reach < recommended_reach
        more_aggressive = selected_safety < recommended_safety or selected_reach > recommended_reach

        if more_conservative and not more_aggressive:
            return "This plan trades upside for more safety."
        if more_aggressive and not more_conservative:
            return "This plan trades safety for more upside."
        return "This plan changes the balance of safety, confidence, and upside compared with the recommended plan."

    def _build_scenario_simulation(
        self,
        *,
        query: RecommendationQuery,
        scenario_input: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if scenario_input is None or psycopg2 is None:
            return None

        simulated_query = self._build_simulated_query(query, scenario_input)
        conn = psycopg2.connect(
            host=self._db_settings.host,
            port=self._db_settings.port,
            database=self._db_settings.database,
            user=self._db_settings.user,
            password=self._db_settings.password,
        )
        try:
            repo = RecommendationRepository(conn)
            config = default_recommendation_config()
            original_payload = self._run_recommendation_pipeline(repo, query, config=config)
            simulated_payload = self._run_recommendation_pipeline(repo, simulated_query, config=config)
        finally:
            conn.close()

        original_items, _ = self._flatten_grouped_results(original_payload)
        simulated_items, _ = self._flatten_grouped_results(simulated_payload)
        original_plans = self._build_application_plans(original_items)
        simulated_plans = self._build_application_plans(simulated_items)
        original_comparison = self._build_plan_comparison(original_plans)
        simulated_comparison = self._build_plan_comparison(simulated_plans)
        before_name = self._normalize_plan_name(
            original_comparison.get("recommendedPlan") if isinstance(original_comparison, dict) else None
        )
        after_name = self._normalize_plan_name(
            simulated_comparison.get("recommendedPlan") if isinstance(simulated_comparison, dict) else None
        )
        if before_name is None or after_name is None:
            return None

        original_plan = self._find_plan_by_name(original_plans, before_name)
        simulated_plan = self._find_plan_by_name(simulated_plans, after_name)
        if not isinstance(original_plan, dict) or not isinstance(simulated_plan, dict):
            return None

        change_summary = self._build_scenario_change_summary(before_name, after_name)
        key_differences = self._build_scenario_key_differences(
            before_name=before_name,
            after_name=after_name,
            before_plan=original_plan,
            after_plan=simulated_plan,
        )
        return {
            "scenarioInput": scenario_input,
            "recommendedPlanBefore": before_name,
            "recommendedPlanAfter": after_name,
            "changeSummary": change_summary,
            "keyDifferences": key_differences,
        }

    def _build_scenario_comparison(
        self,
        *,
        query: RecommendationQuery,
    ) -> dict[str, Any] | None:
        scenario_presets = self._valid_scenario_presets(query)
        if not scenario_presets or psycopg2 is None:
            return None

        conn = psycopg2.connect(
            host=self._db_settings.host,
            port=self._db_settings.port,
            database=self._db_settings.database,
            user=self._db_settings.user,
            password=self._db_settings.password,
        )
        try:
            repo = RecommendationRepository(conn)
            config = default_recommendation_config()
            baseline_payload = self._run_recommendation_pipeline(repo, query, config=config)
            baseline_items, _ = self._flatten_grouped_results(baseline_payload)
            baseline_plans = self._build_application_plans(baseline_items)
            baseline_comparison = self._build_plan_comparison(baseline_plans)
            baseline_name = self._normalize_plan_name(
                baseline_comparison.get("recommendedPlan") if isinstance(baseline_comparison, dict) else None
            )
            baseline_plan = self._find_plan_by_name(baseline_plans, baseline_name or "")
            if baseline_name is None or not isinstance(baseline_plan, dict):
                return None

            scenarios: list[dict[str, Any]] = []
            for scenario_key, scenario_input in scenario_presets:
                simulated_query = self._build_simulated_query(query, scenario_input)
                simulated_payload = self._run_recommendation_pipeline(repo, simulated_query, config=config)
                simulated_items, _ = self._flatten_grouped_results(simulated_payload)
                simulated_plans = self._build_application_plans(simulated_items)
                simulated_comparison = self._build_plan_comparison(simulated_plans)
                after_name = self._normalize_plan_name(
                    simulated_comparison.get("recommendedPlan") if isinstance(simulated_comparison, dict) else None
                )
                after_plan = self._find_plan_by_name(simulated_plans, after_name or "")
                if after_name is None or not isinstance(after_plan, dict):
                    continue
                scenarios.append(
                    {
                        "scenarioKey": scenario_key,
                        "scenarioLabel": self._scenario_label(scenario_key),
                        "recommendedPlanAfter": after_name,
                        "changeSummary": self._build_scenario_change_summary(baseline_name, after_name),
                        "keyDifferences": self._build_scenario_key_differences(
                            before_name=baseline_name,
                            after_name=after_name,
                            before_plan=baseline_plan,
                            after_plan=after_plan,
                        ),
                    }
                )
        finally:
            conn.close()

        if not scenarios:
            return None
        return {
            "baselineRecommendedPlan": baseline_name,
            "scenarios": [
                {
                    "scenarioKey": str(scenario.get("scenarioKey") or ""),
                    "scenarioLabel": str(scenario.get("scenarioLabel") or ""),
                    "recommendedPlanAfter": str(scenario.get("recommendedPlanAfter") or ""),
                    "changeSummary": str(scenario.get("changeSummary") or ""),
                    "keyDifferences": [
                        str(line)
                        for line in scenario.get("keyDifferences", [])
                        if isinstance(line, str) and line
                    ],
                }
                for scenario in scenarios[:4]
            ],
        }

    def _build_best_scenario_insight(
        self,
        scenario_comparison: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not isinstance(scenario_comparison, dict):
            return None
        scenarios = scenario_comparison.get("scenarios")
        if not isinstance(scenarios, list) or not scenarios:
            return None

        preset_rank = {key: index for index, key in enumerate(self.SCENARIO_PRESET_ORDER)}
        candidates = [scenario for scenario in scenarios if isinstance(scenario, dict)]
        if not candidates:
            return None

        best = min(
            candidates,
            key=lambda scenario: (
                0 if self._scenario_changes_plan_favorably(
                    str(scenario_comparison.get("baselineRecommendedPlan") or ""),
                    str(scenario.get("recommendedPlanAfter") or ""),
                ) else 1,
                0 if self._scenario_improves_confidence(scenario) else 1,
                0 if self._scenario_improves_safety(scenario) else 1,
                preset_rank.get(str(scenario.get("scenarioKey") or ""), len(self.SCENARIO_PRESET_ORDER)),
            ),
        )

        if self._scenario_changes_plan_favorably(
            str(scenario_comparison.get("baselineRecommendedPlan") or ""),
            str(best.get("recommendedPlanAfter") or ""),
        ):
            reason = "This scenario most improves the recommendation outcome."
        elif self._scenario_improves_confidence(best) and not self._scenario_reduces_safety(best):
            reason = "This scenario most improves plan confidence without increasing instability."
        else:
            reason = "This scenario gives the clearest improvement among the tested options."

        return {
            "scenarioKey": best.get("scenarioKey"),
            "scenarioLabel": best.get("scenarioLabel"),
            "reason": reason,
        }

    def _build_improvement_priority(
        self,
        *,
        scenario_comparison: dict[str, Any] | None,
        best_scenario_insight: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not isinstance(scenario_comparison, dict):
            return None
        scenarios = scenario_comparison.get("scenarios")
        if not isinstance(scenarios, list) or not scenarios:
            return None

        preset_rank = {key: index for index, key in enumerate(self.SCENARIO_PRESET_ORDER)}
        candidates = [scenario for scenario in scenarios if isinstance(scenario, dict)]
        if not candidates:
            return None

        best = min(
            candidates,
            key=lambda scenario: (
                -self.IMPACT_RANK[self._scenario_impact_level(scenario, scenario_comparison)],
                self.EFFORT_RANK[self._scenario_effort_level(str(scenario.get("scenarioKey") or ""))],
                preset_rank.get(str(scenario.get("scenarioKey") or ""), len(self.SCENARIO_PRESET_ORDER)),
            ),
        )

        scenario_key = str(best.get("scenarioKey") or "")
        scenario_label = str(best.get("scenarioLabel") or "")
        effort_level = self._scenario_effort_level(scenario_key)
        impact_level = self._scenario_impact_level(best, scenario_comparison)
        priority_tier = self._priority_tier(impact_level=impact_level, effort_level=effort_level)
        priority_reason = self._priority_reason(impact_level=impact_level, effort_level=effort_level)

        return {
            "recommendedScenarioKey": scenario_key,
            "recommendedScenarioLabel": scenario_label,
            "priorityReason": priority_reason,
            "effortLevel": effort_level,
            "impactLevel": impact_level,
            "priorityTier": priority_tier,
        }

    def _build_next_action_guide(
        self,
        *,
        plan_comparison: dict[str, Any] | None,
        selected_plan_comparison: dict[str, Any] | None,
        scenario_simulation: dict[str, Any] | None,
        scenario_comparison: dict[str, Any] | None,
        best_scenario_insight: dict[str, Any] | None,
        improvement_priority: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        current_focus = "plan"
        if isinstance(selected_plan_comparison, dict):
            current_focus = "plan"
        elif isinstance(scenario_simulation, dict) or isinstance(scenario_comparison, dict):
            current_focus = "scenario"

        if isinstance(improvement_priority, dict):
            scenario_key = improvement_priority.get("recommendedScenarioKey")
            scenario_label = improvement_priority.get("recommendedScenarioLabel")
            if isinstance(scenario_key, str) and scenario_key and isinstance(scenario_label, str) and scenario_label:
                return {
                    "currentFocus": current_focus,
                    "suggestedNextAction": self._suggested_improvement_action_text(scenario_key, scenario_label),
                    "actionType": "improve_profile",
                    "reason": "This is the most practical improvement to strengthen your current plan.",
                    "suggestedTarget": {
                        "type": "scenario",
                        "key": scenario_key,
                        "label": scenario_label,
                    },
                }

        if isinstance(best_scenario_insight, dict):
            scenario_key = best_scenario_insight.get("scenarioKey")
            scenario_label = best_scenario_insight.get("scenarioLabel")
            if isinstance(scenario_key, str) and scenario_key and isinstance(scenario_label, str) and scenario_label:
                return {
                    "currentFocus": current_focus,
                    "suggestedNextAction": f"Explore {scenario_label} scenario",
                    "actionType": "explore_scenario",
                    "reason": "This scenario has the strongest impact on your outcomes.",
                    "suggestedTarget": {
                        "type": "scenario",
                        "key": scenario_key,
                        "label": scenario_label,
                    },
                }

        if isinstance(plan_comparison, dict):
            recommended_plan = plan_comparison.get("recommendedPlan")
            if isinstance(recommended_plan, str) and recommended_plan:
                return {
                    "currentFocus": current_focus,
                    "suggestedNextAction": f"Focus on the {recommended_plan.capitalize()} plan",
                    "actionType": "focus_plan",
                    "reason": "This plan currently offers the best balance for your profile.",
                    "suggestedTarget": {
                        "type": "plan",
                        "key": recommended_plan,
                        "label": recommended_plan.capitalize(),
                    },
                }

        return None

    def _build_decision_summary(
        self,
        *,
        query: RecommendationQuery,
        application_plans: list[dict[str, Any]] | None,
        plan_comparison: dict[str, Any] | None,
        selected_plan_comparison: dict[str, Any] | None,
        best_scenario_insight: dict[str, Any] | None,
        scenario_simulation: dict[str, Any] | None,
        scenario_comparison: dict[str, Any] | None,
        improvement_priority: dict[str, Any] | None,
        next_action_guide: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not isinstance(plan_comparison, dict) or not application_plans:
            return None

        recommended_plan_name = self._normalize_plan_name(plan_comparison.get("recommendedPlan"))
        recommended_plan = self._find_plan_by_name(application_plans, recommended_plan_name or "")
        if recommended_plan_name is None or not isinstance(recommended_plan, dict):
            return None

        decision_summary: dict[str, Any] = {
            "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
            "profileSnapshot": self._build_profile_snapshot(query),
            "recommendedPlan": self._build_recommended_plan_summary(
                recommended_plan_name=recommended_plan_name,
                recommended_plan=recommended_plan,
            ),
        }
        top_recommendation = self._build_top_recommendation_summary(recommended_plan)
        if top_recommendation is not None:
            decision_summary["topRecommendation"] = top_recommendation
        next_action = self._build_next_action_summary(next_action_guide)
        if next_action is not None:
            decision_summary["nextAction"] = next_action

        selected_plan_summary = self._build_selected_plan_summary_payload(
            application_plans=application_plans,
            selected_plan_comparison=selected_plan_comparison,
        )
        if selected_plan_summary is not None:
            decision_summary["selectedPlan"] = selected_plan_summary

        plan_comparison_summary = self._build_decision_plan_comparison_summary(
            selected_plan_comparison
        )
        if plan_comparison_summary is not None:
            decision_summary["planComparison"] = plan_comparison_summary

        best_scenario_summary = self._build_best_scenario_summary(
            best_scenario_insight=best_scenario_insight,
            scenario_simulation=scenario_simulation,
            scenario_comparison=scenario_comparison,
        )
        if best_scenario_summary is not None:
            decision_summary["bestScenario"] = best_scenario_summary

        improvement_priority_summary = self._build_improvement_priority_summary(
            improvement_priority
        )
        if improvement_priority_summary is not None:
            decision_summary["improvementPriority"] = improvement_priority_summary

        return decision_summary

    def _build_decision_summary_compact(
        self,
        *,
        application_plans: list[dict[str, Any]] | None,
        plan_comparison: dict[str, Any] | None,
        plan_delta: dict[str, Any] | None,
        best_scenario_insight: dict[str, Any] | None,
        improvement_priority: dict[str, Any] | None,
        next_action_guide: dict[str, Any] | None,
    ) -> dict[str, str] | None:
        if not application_plans or not isinstance(plan_comparison, dict):
            return None

        recommended_plan_name = self._normalize_plan_name(plan_comparison.get("recommendedPlan"))
        recommended_plan = self._find_plan_by_name(application_plans, recommended_plan_name or "")
        if recommended_plan_name is None or not isinstance(recommended_plan, dict):
            return None

        return {
            "plan": recommended_plan_name.capitalize(),
            "confidence": self._compact_confidence(recommended_plan.get("planConfidence")),
            "risk": self._compact_risk(recommended_plan.get("riskDistribution")),
            "topReason": self._compact_top_reason(plan_delta, plan_comparison),
            "nextStep": self._compact_next_step(
                improvement_priority=improvement_priority,
                best_scenario_insight=best_scenario_insight,
                next_action_guide=next_action_guide,
            ),
        }

    def _compact_confidence(self, value: Any) -> str:
        if isinstance(value, str) and value:
            return value.capitalize()
        return "Unknown"

    def _compact_risk(self, risk_distribution: Any) -> str:
        if not isinstance(risk_distribution, str) or not risk_distribution:
            return "Unknown"
        prefix = "Overall plan risk:"
        if risk_distribution.startswith(prefix):
            raw = risk_distribution.removeprefix(prefix).strip().split(" ", 1)[0]
            return raw.strip(" .").capitalize() if raw else "Unknown"
        return risk_distribution.strip().split(" ", 1)[0].strip(" .").capitalize()

    def _compact_top_reason(
        self,
        plan_delta: dict[str, Any] | None,
        plan_comparison: dict[str, Any],
    ) -> str:
        if isinstance(plan_delta, dict):
            lines = plan_delta.get("comparisonAgainstAlternatives")
            if isinstance(lines, list):
                first_line = next((line for line in lines if isinstance(line, str) and line), None)
                if first_line:
                    return first_line
        reason = plan_comparison.get("reason")
        if isinstance(reason, str) and reason:
            return reason
        return "Strong coverage with stable requirements"

    def _compact_next_step(
        self,
        *,
        improvement_priority: dict[str, Any] | None,
        best_scenario_insight: dict[str, Any] | None,
        next_action_guide: dict[str, Any] | None,
    ) -> str:
        if isinstance(improvement_priority, dict):
            label = improvement_priority.get("recommendedScenarioLabel") or improvement_priority.get("label")
            if isinstance(label, str) and label:
                return label
        if isinstance(best_scenario_insight, dict):
            label = best_scenario_insight.get("scenarioLabel") or best_scenario_insight.get("label")
            if isinstance(label, str) and label:
                return label
        if isinstance(next_action_guide, dict):
            action = next_action_guide.get("suggestedNextAction") or next_action_guide.get("action")
            if isinstance(action, str) and action:
                return action
        return "Review application plan"

    def _build_compact_summary_line(self, decision_summary_compact: dict[str, Any] | None) -> str | None:
        if not isinstance(decision_summary_compact, dict):
            return None
        plan = decision_summary_compact.get("plan")
        confidence = decision_summary_compact.get("confidence")
        next_step = decision_summary_compact.get("nextStep")
        if not all(isinstance(value, str) and value for value in (plan, confidence, next_step)):
            return None
        return f"Recommended plan: {plan}. Confidence: {confidence}. Next step: {next_step}."

    def _build_profile_snapshot(self, query: RecommendationQuery) -> dict[str, Any]:
        snapshot: dict[str, Any] = {}
        if query.country:
            snapshot["country"] = query.country
        if query.ielts_score is not None:
            snapshot["ielts"] = query.ielts_score
        if query.toefl_score is not None:
            snapshot["toefl"] = query.toefl_score
        if query.gpa_score is not None:
            snapshot["gpa"] = query.gpa_score
        if query.duolingo_score is not None:
            snapshot["duolingo"] = query.duolingo_score
        if query.target_rank is not None:
            snapshot["targetRank"] = query.target_rank
        return snapshot

    def _build_recommended_plan_summary(
        self,
        *,
        recommended_plan_name: str,
        recommended_plan: dict[str, Any],
    ) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "plan": recommended_plan_name,
        }
        for key, source_key in (
            ("summary", "planSummary"),
            ("confidence", "planConfidence"),
            ("confidenceReason", "planConfidenceReason"),
        ):
            value = recommended_plan.get(source_key)
            if isinstance(value, str) and value:
                summary[key] = value
        return summary

    def _build_selected_plan_summary_payload(
        self,
        *,
        application_plans: list[dict[str, Any]] | None,
        selected_plan_comparison: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not application_plans or not isinstance(selected_plan_comparison, dict):
            return None
        selected_plan_name = self._normalize_plan_name(selected_plan_comparison.get("selectedPlan"))
        selected_plan = self._find_plan_by_name(application_plans, selected_plan_name or "")
        if selected_plan_name is None or not isinstance(selected_plan, dict):
            return None
        summary: dict[str, Any] = {
            "plan": selected_plan_name,
        }
        plan_summary = selected_plan.get("planSummary")
        if isinstance(plan_summary, str) and plan_summary:
            summary["summary"] = plan_summary
        return summary

    def _build_decision_plan_comparison_summary(
        self,
        selected_plan_comparison: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not isinstance(selected_plan_comparison, dict):
            return None
        summary_text = selected_plan_comparison.get("summary")
        differences = selected_plan_comparison.get("differences")
        payload: dict[str, Any] = {}
        if isinstance(summary_text, str) and summary_text:
            payload["summary"] = summary_text
        if isinstance(differences, list):
            clean_differences = [
                str(line) for line in differences if isinstance(line, str) and line
            ][:2]
            if clean_differences:
                payload["differences"] = clean_differences
        return payload or None

    def _build_top_recommendation_summary(
        self,
        recommended_plan: dict[str, Any],
    ) -> dict[str, Any] | None:
        primary_choice = recommended_plan.get("primaryChoice")
        if not isinstance(primary_choice, dict):
            return None
        bucket = primary_choice.get("bucket")
        if not isinstance(bucket, str) or bucket not in {"reach", "target", "safety"}:
            return None
        bucket_items = recommended_plan.get(bucket)
        if not isinstance(bucket_items, list) or not bucket_items:
            return None
        top_item = bucket_items[0]
        if not isinstance(top_item, dict):
            return None
        payload: dict[str, Any] = {}
        university = top_item.get("universityName")
        decision = top_item.get("decision")
        reason = top_item.get("reason")
        if isinstance(university, str) and university:
            payload["university"] = university
        if isinstance(decision, str) and decision:
            payload["decision"] = decision
        if isinstance(reason, str) and reason:
            payload["reason"] = reason
        return payload or None

    def _build_best_scenario_summary(
        self,
        *,
        best_scenario_insight: dict[str, Any] | None,
        scenario_simulation: dict[str, Any] | None,
        scenario_comparison: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not isinstance(best_scenario_insight, dict):
            return None
        scenario_label = best_scenario_insight.get("scenarioLabel")
        scenario_key = best_scenario_insight.get("scenarioKey")
        if not isinstance(scenario_label, str) or not scenario_label:
            return None

        effect = None
        if isinstance(scenario_comparison, dict) and isinstance(scenario_key, str):
            scenarios = scenario_comparison.get("scenarios")
            if isinstance(scenarios, list):
                for scenario in scenarios:
                    if (
                        isinstance(scenario, dict)
                        and str(scenario.get("scenarioKey") or "") == scenario_key
                    ):
                        change_summary = scenario.get("changeSummary")
                        if isinstance(change_summary, str) and change_summary:
                            effect = change_summary
                        break
        if effect is None and isinstance(scenario_simulation, dict):
            change_summary = scenario_simulation.get("changeSummary")
            if isinstance(change_summary, str) and change_summary:
                effect = change_summary

        payload: dict[str, Any] = {
            "scenario": scenario_label,
        }
        if isinstance(effect, str) and effect:
            payload["effect"] = effect
        return payload

    def _build_improvement_priority_summary(
        self,
        improvement_priority: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not isinstance(improvement_priority, dict):
            return None
        payload: dict[str, Any] = {}
        action = improvement_priority.get("recommendedScenarioLabel")
        impact = improvement_priority.get("impactLevel")
        effort = improvement_priority.get("effortLevel")
        reason = improvement_priority.get("priorityReason")
        if isinstance(action, str) and action:
            payload["action"] = action
        if isinstance(impact, str) and impact:
            payload["impact"] = impact
        if isinstance(effort, str) and effort:
            payload["effort"] = effort
        if isinstance(reason, str) and reason:
            payload["reason"] = reason
        return payload or None

    def _build_next_action_summary(
        self,
        next_action_guide: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not isinstance(next_action_guide, dict):
            return None
        suggested_target = (
            next_action_guide.get("suggestedTarget")
            if isinstance(next_action_guide.get("suggestedTarget"), dict)
            else {}
        )
        action_type = suggested_target.get("type")
        action = next_action_guide.get("suggestedNextAction")
        reason = next_action_guide.get("reason")
        payload: dict[str, Any] = {}
        if next_action_guide.get("actionType") == "improve_profile":
            payload["type"] = "improvement"
        elif isinstance(action_type, str) and action_type in {"plan", "scenario"}:
            payload["type"] = action_type
        if isinstance(action, str) and action:
            payload["action"] = action
        if isinstance(reason, str) and reason:
            payload["reason"] = reason
        return payload or None

    def _build_simulated_query(
        self,
        query: RecommendationQuery,
        scenario_input: dict[str, Any],
    ) -> RecommendationQuery:
        ielts_delta = scenario_input.get("ielts_delta")
        toefl_delta = scenario_input.get("toefl_delta")
        gpa_delta = scenario_input.get("gpa_delta")
        target_rank_delta = scenario_input.get("target_rank_delta")
        return RecommendationQuery(
            country=query.country,
            country_policy=query.country_policy,
            ielts_score=self._apply_delta(
                query.ielts_score, ielts_delta, minimum=0.0, maximum=9.0
            ),
            toefl_score=self._apply_delta(
                query.toefl_score, toefl_delta, minimum=0.0, maximum=120.0
            ),
            gpa_score=self._apply_delta(
                query.gpa_score, gpa_delta, minimum=0.0, maximum=4.0
            ),
            duolingo_score=query.duolingo_score,
            target_rank=self._apply_rank_delta(query.target_rank, target_rank_delta),
            risk_profile=query.risk_profile,
            preference_weights=dict(query.preference_weights),
            preferred_ranking_source=query.preferred_ranking_source,
            limit=query.limit,
            ranking_year=query.ranking_year,
        )

    def _build_scenario_change_summary(self, before_name: str, after_name: str) -> str:
        if before_name != after_name:
            return f"The recommended plan shifts from {before_name} to {after_name} under this scenario."
        return "The recommended plan remains stable under this scenario."

    def _build_scenario_key_differences(
        self,
        *,
        before_name: str,
        after_name: str,
        before_plan: dict[str, Any],
        after_plan: dict[str, Any],
    ) -> list[str]:
        lines: list[str] = []

        before_confidence = self._plan_confidence_rank(before_plan)
        after_confidence = self._plan_confidence_rank(after_plan)
        if after_confidence > before_confidence:
            lines.append("Overall plan confidence improves under this scenario.")
        elif after_confidence < before_confidence:
            lines.append("Overall plan confidence decreases under this scenario.")

        before_safety = len(before_plan.get("safety") or []) if isinstance(before_plan.get("safety"), list) else 0
        after_safety = len(after_plan.get("safety") or []) if isinstance(after_plan.get("safety"), list) else 0
        if after_safety > before_safety:
            lines.append("Safety coverage improves under this scenario.")
        elif after_safety < before_safety:
            lines.append("Safety coverage becomes more limited.")

        aggressiveness_shift = self._compare_plan_aggressiveness(
            before_name=before_name,
            after_name=after_name,
            before_plan=before_plan,
            after_plan=after_plan,
        )
        if aggressiveness_shift == "more_aggressive":
            lines.append("The plan mix becomes more aggressive.")
        elif aggressiveness_shift == "more_conservative":
            lines.append("The plan mix becomes more conservative.")

        return lines[:3]

    def _compare_plan_aggressiveness(
        self,
        *,
        before_name: str,
        after_name: str,
        before_plan: dict[str, Any],
        after_plan: dict[str, Any],
    ) -> str | None:
        plan_rank = {"conservative": 0, "balanced": 1, "aggressive": 2}
        before_rank = plan_rank.get(before_name)
        after_rank = plan_rank.get(after_name)
        if before_rank is not None and after_rank is not None and after_rank != before_rank:
            return "more_aggressive" if after_rank > before_rank else "more_conservative"

        before_reach = len(before_plan.get("reach") or []) if isinstance(before_plan.get("reach"), list) else 0
        after_reach = len(after_plan.get("reach") or []) if isinstance(after_plan.get("reach"), list) else 0
        before_safety = len(before_plan.get("safety") or []) if isinstance(before_plan.get("safety"), list) else 0
        after_safety = len(after_plan.get("safety") or []) if isinstance(after_plan.get("safety"), list) else 0
        if after_reach > before_reach or after_safety < before_safety:
            return "more_aggressive"
        if after_reach < before_reach or after_safety > before_safety:
            return "more_conservative"
        return None

    def _valid_scenario_presets(self, query: RecommendationQuery) -> list[tuple[str, dict[str, Any]]]:
        presets: list[tuple[str, dict[str, Any]]] = []
        for scenario_key in self.SCENARIO_PRESET_ORDER:
            scenario_input = self._scenario_preset_input(scenario_key)
            if self._scenario_preset_is_valid(query, scenario_key):
                presets.append((scenario_key, scenario_input))
        return presets[:4]

    def _scenario_preset_input(self, scenario_key: str) -> dict[str, Any]:
        mapping = {
            "ielts_plus_0_5": {"ielts_delta": 0.5},
            "toefl_plus_5": {"toefl_delta": 5},
            "gpa_plus_0_2": {"gpa_delta": 0.2},
            "target_rank_tighter_20": {"target_rank_delta": -20},
        }
        return dict(mapping.get(scenario_key, {}))

    def _scenario_preset_is_valid(self, query: RecommendationQuery, scenario_key: str) -> bool:
        if scenario_key == "ielts_plus_0_5":
            return query.ielts_score is not None
        if scenario_key == "toefl_plus_5":
            return query.toefl_score is not None
        if scenario_key == "gpa_plus_0_2":
            return query.gpa_score is not None
        if scenario_key == "target_rank_tighter_20":
            return query.target_rank is not None
        return False

    def _scenario_label(self, scenario_key: str) -> str:
        labels = {
            "ielts_plus_0_5": "IELTS +0.5",
            "toefl_plus_5": "TOEFL +5",
            "gpa_plus_0_2": "GPA +0.2",
            "target_rank_tighter_20": "Target rank -20",
        }
        return labels.get(scenario_key, scenario_key)

    def _is_favorable_plan_shift(self, before_name: str, after_name: str) -> bool:
        plan_rank = {"conservative": 0, "balanced": 1, "aggressive": 2}
        before_rank = plan_rank.get(before_name, -1)
        after_rank = plan_rank.get(after_name, -1)
        return after_rank > before_rank

    def _plan_safety_count(self, plan: dict[str, Any]) -> int:
        safety = plan.get("safety")
        if not isinstance(safety, list):
            return 0
        return len(safety)

    def _scenario_changes_plan_favorably(self, baseline_name: str, after_name: str) -> bool:
        return self._is_favorable_plan_shift(baseline_name, after_name)

    def _scenario_improves_confidence(self, scenario: dict[str, Any]) -> bool:
        key_differences = scenario.get("keyDifferences")
        if not isinstance(key_differences, list):
            return False
        return any(
            isinstance(line, str) and line == "Overall plan confidence improves under this scenario."
            for line in key_differences
        )

    def _scenario_improves_safety(self, scenario: dict[str, Any]) -> bool:
        key_differences = scenario.get("keyDifferences")
        if not isinstance(key_differences, list):
            return False
        return any(
            isinstance(line, str) and line == "Safety coverage improves under this scenario."
            for line in key_differences
        )

    def _scenario_reduces_safety(self, scenario: dict[str, Any]) -> bool:
        key_differences = scenario.get("keyDifferences")
        if not isinstance(key_differences, list):
            return False
        return any(
            isinstance(line, str) and line == "Safety coverage becomes more limited."
            for line in key_differences
        )

    def _scenario_effort_level(self, scenario_key: str) -> str:
        return self.EFFORT_LEVELS.get(scenario_key, "high")

    def _scenario_impact_level(
        self,
        scenario: dict[str, Any],
        scenario_comparison: dict[str, Any],
    ) -> str:
        baseline_name = str(scenario_comparison.get("baselineRecommendedPlan") or "")
        after_name = str(scenario.get("recommendedPlanAfter") or "")
        favorable_shift = self._scenario_changes_plan_favorably(baseline_name, after_name)
        confidence_improves = self._scenario_improves_confidence(scenario)
        safety_improves = self._scenario_improves_safety(scenario)
        change_summary = str(scenario.get("changeSummary") or "")

        if favorable_shift or (confidence_improves and safety_improves):
            return "high"
        if confidence_improves or safety_improves or (
            change_summary and change_summary != "The recommended plan remains stable under this scenario."
        ):
            return "medium"
        return "low"

    def _priority_tier(self, *, impact_level: str, effort_level: str) -> str:
        if (impact_level == "high" and effort_level in {"low", "medium"}) or (
            impact_level == "medium" and effort_level == "low"
        ):
            return "high"
        if (
            (impact_level == "high" and effort_level == "high")
            or (impact_level == "medium" and effort_level == "medium")
            or (impact_level == "low" and effort_level == "low")
        ):
            return "medium"
        return "low"

    def _priority_reason(self, *, impact_level: str, effort_level: str) -> str:
        if (impact_level == "high" and effort_level in {"low", "medium"}) or (
            impact_level == "medium" and effort_level == "low"
        ):
            if impact_level == "high":
                return "This scenario offers strong improvement potential with manageable effort."
            return "This scenario gives meaningful plan improvement without requiring the highest effort."
        if (
            (impact_level == "high" and effort_level == "high")
            or (impact_level == "medium" and effort_level == "medium")
            or (impact_level == "low" and effort_level == "low")
        ):
            if impact_level == "high":
                return "This scenario may help, but the expected gain and effort are more balanced."
            return "This scenario is still useful, though it is not the clearest first improvement."
        if impact_level == "medium" and effort_level == "high":
            return "This scenario appears less efficient because the expected gain is limited relative to effort."
        return "This scenario is not the strongest first improvement under the tested options."

    def _build_plan_delta(
        self,
        application_plans: list[dict[str, Any]] | None,
        plan_comparison: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not application_plans or not isinstance(plan_comparison, dict):
            return None

        recommended_name = plan_comparison.get("recommendedPlan")
        if not isinstance(recommended_name, str) or not recommended_name:
            return None

        plan_map = {
            str(plan.get("planName")): plan
            for plan in application_plans
            if isinstance(plan, dict) and isinstance(plan.get("planName"), str)
        }
        recommended_plan = plan_map.get(recommended_name)
        if not isinstance(recommended_plan, dict):
            return None

        comparison_lines: list[str] = []
        for alternative_name in ("balanced", "conservative", "aggressive"):
            if alternative_name == recommended_name:
                continue
            alternative_plan = plan_map.get(alternative_name)
            if not isinstance(alternative_plan, dict):
                continue
            comparison_lines.extend(
                self._build_plan_delta_lines_for_alternative(
                    recommended_name=recommended_name,
                    recommended_plan=recommended_plan,
                    alternative_name=alternative_name,
                    alternative_plan=alternative_plan,
                )
            )
            if len(comparison_lines) >= 4:
                break

        return {
            "recommendedPlan": recommended_name,
            "comparisonAgainstAlternatives": comparison_lines[:4],
        }

    def _build_plan_delta_lines_for_alternative(
        self,
        *,
        recommended_name: str,
        recommended_plan: dict[str, Any],
        alternative_name: str,
        alternative_plan: dict[str, Any],
    ) -> list[str]:
        lines: list[str] = []

        recommended_safety = len(recommended_plan.get("safety") or []) if isinstance(recommended_plan.get("safety"), list) else 0
        alternative_safety = len(alternative_plan.get("safety") or []) if isinstance(alternative_plan.get("safety"), list) else 0
        if recommended_safety > 0 and alternative_safety == 0:
            lines.append(
                f"The {recommended_name} plan keeps safety coverage that the {alternative_name} plan does not."
            )
        elif recommended_safety == 0 and alternative_safety > 0:
            lines.append(
                f"The {alternative_name} plan keeps more safety coverage than the {recommended_name} plan."
            )

        recommended_confidence = self._plan_confidence_rank(recommended_plan)
        alternative_confidence = self._plan_confidence_rank(alternative_plan)
        if recommended_confidence > alternative_confidence:
            lines.append(
                f"The {recommended_name} plan has higher overall confidence than the {alternative_name} plan."
            )
        elif recommended_confidence < alternative_confidence:
            lines.append(
                f"The {alternative_name} plan has higher overall confidence than the {recommended_name} plan."
            )

        recommended_warnings = self._plan_warning_count(recommended_plan)
        alternative_warnings = self._plan_warning_count(alternative_plan)
        if recommended_warnings < alternative_warnings:
            lines.append(
                f"The {recommended_name} plan carries fewer warning signals than the {alternative_name} plan."
            )
        elif recommended_warnings > alternative_warnings:
            lines.append(
                f"The {recommended_name} plan carries more warning signals than the {alternative_name} plan."
            )

        recommended_reach = len(recommended_plan.get("reach") or []) if isinstance(recommended_plan.get("reach"), list) else 0
        alternative_reach = len(alternative_plan.get("reach") or []) if isinstance(alternative_plan.get("reach"), list) else 0
        if recommended_reach > alternative_reach:
            lines.append(
                f"The {recommended_name} plan keeps more upside through reach options than the {alternative_name} plan."
            )
        elif recommended_reach < alternative_reach:
            lines.append(
                f"The {recommended_name} plan reduces reach exposure compared with the {alternative_name} plan."
            )

        return lines[:2]

    def _plan_confidence_rank(self, plan: dict[str, Any]) -> int:
        confidence_rank = {"high": 2, "medium": 1, "low": 0}
        return confidence_rank.get(str(plan.get("planConfidence") or ""), -1)

    def _plan_warning_count(self, plan: dict[str, Any]) -> int:
        warnings = plan.get("planWarnings")
        if not isinstance(warnings, list):
            return 0
        return len([warning for warning in warnings if isinstance(warning, str) and warning])

    def _application_plan_group(self, item: dict[str, Any]) -> str | None:
        matching_score = self._application_plan_score(item.get("matchingScore"))
        decision = item.get("decisionOutput")
        admission_composite = item.get("admissionComposite")
        if matching_score is None:
            return None
        decision_action = (
            str(decision.get("decisionAction") or "")
            if isinstance(decision, dict)
            else ""
        )
        admission_risk = (
            str(admission_composite.get("admissionRisk") or "")
            if isinstance(admission_composite, dict)
            else ""
        )
        score = matching_score

        if score < 0.75 or decision_action == "apply_with_caution":
            return "reach"
        if 0.75 <= score <= 0.9 and decision_action in {"apply", "apply_early"}:
            return "target"
        if score > 0.9 and admission_risk == "low":
            return "safety"
        return None

    def _application_plan_score(self, value: Any) -> float | None:
        if not isinstance(value, (int, float)):
            return None
        score = float(value)
        if score > 1.0:
            return score / 100.0
        return score

    def _application_plan_risk(self, item: dict[str, Any]) -> str | None:
        composite = item.get("admissionComposite")
        if not isinstance(composite, dict):
            return None
        risk = composite.get("admissionRisk")
        if isinstance(risk, str) and risk in {"high", "medium", "low"}:
            return risk
        return None

    def _application_plan_item(self, item: dict[str, Any]) -> dict[str, Any]:
        decision = item.get("decisionOutput") if isinstance(item.get("decisionOutput"), dict) else {}
        strategy = item.get("decisionStrategy") if isinstance(item.get("decisionStrategy"), dict) else {}
        composite = item.get("admissionComposite") if isinstance(item.get("admissionComposite"), dict) else {}
        return {
            "universityName": item.get("universityName"),
            "decision": decision.get("decisionAction"),
            "strategy": strategy.get("primaryStrategy"),
            "risk": composite.get("admissionRisk"),
            "reason": decision.get("decisionReason"),
            "matchingScore": float(item.get("matchingScore", 0.0) or 0.0),
            "admissionResolved": item.get("admissionResolved") if isinstance(item.get("admissionResolved"), dict) else {},
        }

    def _application_plan_public_item(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "universityName": item.get("universityName"),
            "decision": item.get("decision"),
            "strategy": item.get("strategy"),
            "risk": item.get("risk"),
            "reason": item.get("reason"),
        }

    def _build_application_plan_risk_label(
        self,
        *,
        risk_counts: dict[str, int],
        safety_count: int,
    ) -> str:
        high_count = risk_counts.get("high", 0)
        medium_count = risk_counts.get("medium", 0)
        low_count = risk_counts.get("low", 0)

        if high_count > 0 and safety_count == 0:
            return "high"
        elif low_count >= max(high_count, medium_count) and safety_count > 0 and low_count >= high_count + medium_count:
            return "low"
        return "moderate"

    def _build_application_plan_risk_distribution(
        self,
        *,
        risk_counts: dict[str, int],
        safety_count: int,
    ) -> str:
        high_count = risk_counts.get("high", 0)
        medium_count = risk_counts.get("medium", 0)
        low_count = risk_counts.get("low", 0)
        overall = self._build_application_plan_risk_label(
            risk_counts=risk_counts,
            safety_count=safety_count,
        )
        return (
            f"Overall plan risk: {overall} "
            f"(high={high_count}, medium={medium_count}, low={low_count})."
        )

    def _build_application_plan_strategy(
        self,
        *,
        reach_count: int,
        target_count: int,
        safety_count: int,
        risk_counts: dict[str, int],
    ) -> str:
        if risk_counts.get("high", 0) > 0 and safety_count == 0:
            return "This plan leans risky. Consider adding 1–2 safer options."
        if safety_count >= 2 and safety_count > max(reach_count, target_count):
            return "You can proceed confidently with this plan. Focus on execution and timeline."
        return "This is a balanced plan. Prioritize target schools while keeping reach as upside."

    def _build_application_plan_primary_choice(
        self,
        grouped: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any] | None:
        target = grouped.get("target") or []
        safety = grouped.get("safety") or []
        reach = grouped.get("reach") or []

        if target:
            row = target[0]
            return {
                "universityName": row.get("universityName"),
                "bucket": "target",
                "reason": "Best balance of fit and manageable risk among target options.",
            }
        if safety:
            row = safety[0]
            return {
                "universityName": row.get("universityName"),
                "bucket": "safety",
                "reason": "Most stable option available in the current plan.",
            }
        if reach:
            row = reach[0]
            return {
                "universityName": row.get("universityName"),
                "bucket": "reach",
                "reason": "Highest-upside option available, but the plan is currently risk-heavy.",
            }
        return None

    def _build_application_plan_warnings(
        self,
        *,
        reach_count: int,
        target_count: int,
        safety_count: int,
        total_count: int,
        risk_distribution: str,
    ) -> list[str]:
        warnings: list[str] = []
        if safety_count == 0:
            warnings.append("No safety options included")
        if target_count == 0:
            warnings.append("Plan lacks stable target options")
        if reach_count >= 2 or risk_distribution == "high":
            warnings.append("Plan leans high-risk")
        if total_count <= 2:
            warnings.append("Plan is narrow and may need more coverage")
        return warnings[:3]

    def _build_application_plan_confidence(
        self,
        *,
        reach_count: int,
        target_count: int,
        safety_count: int,
        primary_choice: dict[str, Any] | None,
        quality_adjustment: int = 0,
    ) -> str:
        total_count = reach_count + target_count + safety_count
        if total_count == 0:
            return "low"

        score = 0
        if target_count >= 1:
            score += 1
        if safety_count >= 1:
            score += 1
        if isinstance(primary_choice, dict) and primary_choice.get("bucket") == "target":
            score += 1

        if target_count == 0:
            score -= 1
        if safety_count == 0:
            score -= 1
        if reach_count >= 2:
            score -= 1
        if reach_count > 0 and target_count == 0 and safety_count == 0:
            score -= 2
        score += quality_adjustment

        if score >= 2:
            confidence = "high"
        elif score >= 0:
            confidence = "medium"
        else:
            confidence = "low"

        if confidence == "high" and (target_count == 0 or safety_count == 0 or quality_adjustment < 0):
            return "medium"
        return confidence

    def _build_application_plan_quality_adjustment(
        self,
        *,
        target: list[dict[str, Any]],
        safety: list[dict[str, Any]],
    ) -> int:
        positive = 0
        negative = 0
        first_target = target[0] if target else None
        first_safety = safety[0] if safety else None

        if isinstance(first_target, dict):
            score = self._application_plan_score(first_target.get("matchingScore"))
            if score is not None and score >= 0.82:
                positive = 1
            elif score is not None and score < 0.78:
                negative = -1

        if isinstance(first_safety, dict):
            score = self._application_plan_score(first_safety.get("matchingScore"))
            if score is not None and score >= 0.92:
                positive = 1
            elif score is not None and score < 0.90:
                negative = -1

        if positive > 0:
            return 1
        if negative < 0:
            return -1
        return 0

    def _build_application_plan_confidence_reason(
        self,
        *,
        target_count: int,
        safety_count: int,
        warnings: list[str],
        quality_adjustment: int,
        confidence: str,
    ) -> str:
        has_target = target_count > 0
        has_safety = safety_count > 0
        has_warnings = bool(warnings)

        if confidence == "high":
            if has_target and has_safety and quality_adjustment >= 0:
                return "This plan has both target and safety coverage, and the strongest options look stable."
            return "This plan looks well supported by both structure and fit quality."

        if confidence == "medium":
            if has_warnings or not has_target or not has_safety:
                return "This plan has some stable structure, but at least one core bucket is weaker or less secure."
            return "This plan is workable, but its overall coverage or option quality is mixed."

        if has_warnings or not has_target or not has_safety:
            return "This plan is missing stable coverage or leans too heavily on risky options."
        return "This plan currently looks fragile because safer or stronger options are limited."

    def _append_admission_trust_to_plan_confidence_reason(
        self,
        reason: str,
        plan_items: list[dict[str, Any]],
    ) -> str:
        signals = self._admission_resolved_signals_from_items(plan_items)
        if not signals:
            return reason

        low_confidence_message = "Some requirement signals have low confidence."
        consistent_message = "Requirement signals are consistent across sources."

        if any(self._admission_signal_confidence(signal) < 0.6 for signal in signals):
            return self._append_sentence(reason, low_confidence_message)

        if all(
            str(signal.get("status") or "") == "accepted"
            and self._admission_signal_confidence(signal) >= 0.8
            for signal in signals
        ):
            return self._append_sentence(reason, consistent_message)

        return reason

    def _admission_resolved_signals_from_items(
        self,
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        signals: list[dict[str, Any]] = []
        for item in items:
            resolved = item.get("admissionResolved")
            if not isinstance(resolved, dict):
                continue
            for field in ("ielts", "toefl", "gpa", "duolingo", "deadline"):
                signal = resolved.get(field)
                if isinstance(signal, dict):
                    signals.append(signal)
        return signals

    def _has_conflicting_admission_signal(self, admission_resolved: dict[str, dict[str, Any]]) -> bool:
        return any(
            isinstance(signal, dict) and str(signal.get("status") or "") == "conflict"
            for signal in admission_resolved.values()
        )

    def _admission_signal_confidence(self, signal: dict[str, Any]) -> float:
        confidence = signal.get("confidence")
        if isinstance(confidence, (int, float)):
            return float(confidence)
        return 0.0

    def _append_sentence(self, text: str, sentence: str) -> str:
        if sentence in text:
            return text
        separator = " " if text.endswith((".", "!", "?")) else ". "
        return f"{text}{separator}{sentence}"

    def _build_application_plan_note(self, application_plan: dict[str, Any] | None) -> list[str]:
        if not isinstance(application_plan, dict):
            return []

        def render_group(name: str, rows: Any) -> str:
            if not isinstance(rows, list) or not rows:
                return f"{name}: none."
            names = [
                str(row.get("universityName"))
                for row in rows
                if isinstance(row, dict) and row.get("universityName")
            ]
            return f"{name}: {', '.join(names)}." if names else f"{name}: none."

        paragraphs = ["I built a structured application plan."]
        paragraphs.append(render_group("Reach", application_plan.get("reach")))
        paragraphs.append(render_group("Target", application_plan.get("target")))
        paragraphs.append(render_group("Safety", application_plan.get("safety")))

        summary = application_plan.get("planSummary")
        if isinstance(summary, str) and summary:
            paragraphs.append(summary)
        risk_distribution = application_plan.get("riskDistribution")
        if isinstance(risk_distribution, str) and risk_distribution:
            paragraphs.append(risk_distribution)
        strategy = application_plan.get("recommendedStrategy")
        if isinstance(strategy, str) and strategy:
            paragraphs.append(strategy)
        primary_choice = application_plan.get("primaryChoice")
        plan_confidence = application_plan.get("planConfidence")
        plan_confidence_reason = application_plan.get("planConfidenceReason")
        plan_warnings = application_plan.get("planWarnings")
        if isinstance(primary_choice, dict) and isinstance(plan_confidence, str):
            paragraphs.append(
                f"Primary choice: {primary_choice.get('universityName')}. Plan confidence: {plan_confidence}."
            )
            if isinstance(plan_confidence_reason, str) and plan_confidence_reason:
                paragraphs.append(plan_confidence_reason)
            if isinstance(plan_warnings, list):
                warnings = [str(w) for w in plan_warnings if isinstance(w, str) and w]
                if warnings:
                    paragraphs.append("Warnings: " + "; ".join(warnings[:3]) + ".")
                else:
                    paragraphs.append("No major warning signals stand out in the current plan.")
        return paragraphs

    def _build_multi_plan_note(
        self,
        application_plans: list[dict[str, Any]] | None,
        plan_comparison: dict[str, Any] | None,
    ) -> list[str]:
        if not application_plans or not isinstance(plan_comparison, dict):
            return []

        recommended_plan = plan_comparison.get("recommendedPlan")
        reason = plan_comparison.get("reason")
        tradeoffs = plan_comparison.get("tradeoffs")
        if not isinstance(recommended_plan, str) or not recommended_plan:
            return []

        paragraphs = ["I built multiple application strategies for you."]
        paragraphs.append(
            f"Recommended plan: {recommended_plan.capitalize()}. This is the plan the system currently prefers."
        )
        if isinstance(reason, str) and reason:
            paragraphs.append(reason)
        if isinstance(tradeoffs, list):
            lines = [str(line) for line in tradeoffs if isinstance(line, str) and line]
            paragraphs.extend(lines[:2])
        return paragraphs

    def _build_plan_delta_note(self, plan_delta: dict[str, Any] | None) -> list[str]:
        if not isinstance(plan_delta, dict):
            return []
        lines = plan_delta.get("comparisonAgainstAlternatives")
        if not isinstance(lines, list):
            return []
        usable_lines = [str(line) for line in lines if isinstance(line, str) and line]
        if not usable_lines:
            return []
        return [
            "Why this plan stands out: How the recommended plan differs from the alternatives."
        ] + usable_lines[:4]

    def _build_selected_plan_comparison_note(
        self,
        selected_plan_comparison: dict[str, Any] | None,
    ) -> list[str]:
        if not isinstance(selected_plan_comparison, dict):
            return []
        summary = selected_plan_comparison.get("summary")
        differences = selected_plan_comparison.get("differences")
        if not isinstance(summary, str) or not summary:
            return []
        usable_differences = []
        if isinstance(differences, list):
            usable_differences = [str(line) for line in differences if isinstance(line, str) and line]
        return [
            f"Compared with the recommended plan: {summary}"
        ] + usable_differences[:3]

    def _build_scenario_simulation_note(
        self,
        scenario_simulation: dict[str, Any] | None,
    ) -> list[str]:
        if not isinstance(scenario_simulation, dict):
            return []
        summary = scenario_simulation.get("changeSummary")
        key_differences = scenario_simulation.get("keyDifferences")
        if not isinstance(summary, str) or not summary:
            return []
        usable_lines: list[str] = []
        if isinstance(key_differences, list):
            usable_lines = [str(line) for line in key_differences if isinstance(line, str) and line]
        return ["Under this scenario:", summary] + usable_lines[:3]

    def _build_scenario_comparison_note(
        self,
        scenario_comparison: dict[str, Any] | None,
        best_scenario_insight: dict[str, Any] | None,
    ) -> list[str]:
        if not isinstance(scenario_comparison, dict) or not isinstance(best_scenario_insight, dict):
            return []
        scenario_label = best_scenario_insight.get("scenarioLabel")
        reason = best_scenario_insight.get("reason")
        scenarios = scenario_comparison.get("scenarios")
        if not isinstance(scenario_label, str) or not scenario_label or not isinstance(reason, str) or not reason:
            return []
        if not isinstance(scenarios, list) or not scenarios:
            return []

        lines = [
            "I tested several improvement scenarios.",
            f"Most helpful tested scenario: {scenario_label}.",
            "This changes the outcome the most among the tested scenarios.",
            f"Why: {reason}",
        ]

        scenario_summaries: list[str] = []
        for scenario in scenarios[:2]:
            if not isinstance(scenario, dict):
                continue
            label = scenario.get("scenarioLabel")
            change_summary = scenario.get("changeSummary")
            key_differences = scenario.get("keyDifferences")
            if not isinstance(label, str) or not isinstance(change_summary, str):
                continue
            summary_text = change_summary.replace(" under this scenario.", "").replace("The recommended plan ", "")
            detail = ""
            if isinstance(key_differences, list) and key_differences:
                first_difference = next((line for line in key_differences if isinstance(line, str) and line), None)
                if isinstance(first_difference, str):
                    detail = " " + first_difference.replace(" under this scenario.", "").replace("The plan mix becomes ", "").replace("Safety coverage ", "safety coverage ").replace("Overall plan confidence ", "confidence ")
            scenario_summaries.append(f"{label}: {summary_text}.{detail}".strip())

        if scenario_summaries:
            lines.extend(scenario_summaries)
        return lines

    def _build_improvement_priority_note(
        self,
        improvement_priority: dict[str, Any] | None,
    ) -> list[str]:
        if not isinstance(improvement_priority, dict):
            return []
        label = improvement_priority.get("recommendedScenarioLabel")
        impact = improvement_priority.get("impactLevel")
        effort = improvement_priority.get("effortLevel")
        reason = improvement_priority.get("priorityReason")
        if not all(isinstance(value, str) and value for value in (label, impact, effort, reason)):
            return []
        return [
            f"Most worthwhile improvement: {label}.",
            f"Impact: {impact}. Effort: {effort}.",
            "This is the best first improvement after balancing impact and effort.",
            reason,
        ]

    def _build_next_action_guide_note(
        self,
        next_action_guide: dict[str, Any] | None,
    ) -> list[str]:
        if not isinstance(next_action_guide, dict):
            return []
        suggested_next_action = next_action_guide.get("suggestedNextAction")
        reason = next_action_guide.get("reason")
        action_type = next_action_guide.get("actionType")
        suggested_target = next_action_guide.get("suggestedTarget")
        if not isinstance(suggested_next_action, str) or not suggested_next_action:
            return []
        if not isinstance(reason, str) or not reason:
            return []
        target_label = (
            str(suggested_target.get("label") or "")
            if isinstance(suggested_target, dict)
            else ""
        )
        if action_type == "focus_plan" and target_label:
            return [
                f"Suggested next step: Focus on the {target_label} plan.",
                "This is the clearest plan choice for your current profile.",
            ]
        if action_type == "explore_scenario" and target_label:
            return [
                f"Suggested next step: Explore {target_label}.",
                "This is the strongest scenario to test next.",
            ]
        if action_type == "improve_profile" and target_label:
            return [
                f"Suggested next step: Prioritize {target_label}.",
                "This is the most practical improvement to strengthen your current plan.",
            ]
        return [
            f"Suggested next step: {suggested_next_action}.",
            reason,
        ]

    def _suggested_improvement_action_text(self, scenario_key: str, scenario_label: str) -> str:
        if scenario_key == "ielts_plus_0_5":
            return "Improve IELTS by 0.5"
        if scenario_key == "toefl_plus_5":
            return "Improve TOEFL by 5"
        if scenario_key == "gpa_plus_0_2":
            return "Improve GPA by 0.2"
        if scenario_key == "target_rank_tighter_20":
            return "Tighten target rank by 20"
        return f"Explore {scenario_label}"

    def _normalize_plan_name(self, value: Any) -> str | None:
        text = self._as_optional_str(value)
        if text in {"balanced", "conservative", "aggressive"}:
            return text
        return None

    def _extract_scenario_input(self, profile: dict[str, Any]) -> dict[str, Any] | None:
        raw_scenario = profile.get("scenario")
        scenario: dict[str, Any] | None = None
        if isinstance(raw_scenario, dict):
            scenario = raw_scenario
        elif isinstance(raw_scenario, str):
            try:
                parsed = json.loads(raw_scenario)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                scenario = parsed
        if scenario is None:
            return None

        normalized: dict[str, Any] = {}
        ielts_delta = self._clamp_optional_number(scenario.get("ielts_delta"), minimum=-2.0, maximum=2.0)
        toefl_delta = self._clamp_optional_number(scenario.get("toefl_delta"), minimum=-20.0, maximum=20.0)
        gpa_delta = self._clamp_optional_number(scenario.get("gpa_delta"), minimum=-1.0, maximum=1.0)
        target_rank_delta = self._clamp_optional_int(scenario.get("target_rank_delta"), minimum=-100, maximum=100)

        if ielts_delta not in (None, 0.0):
            normalized["ielts_delta"] = ielts_delta
        if toefl_delta not in (None, 0.0):
            normalized["toefl_delta"] = int(toefl_delta) if float(toefl_delta).is_integer() else toefl_delta
        if gpa_delta not in (None, 0.0):
            normalized["gpa_delta"] = gpa_delta
        if target_rank_delta not in (None, 0):
            normalized["target_rank_delta"] = target_rank_delta

        return normalized or None

    def _clamp_optional_number(self, value: Any, *, minimum: float, maximum: float) -> float | None:
        if not isinstance(value, (int, float)):
            return None
        return max(minimum, min(float(value), maximum))

    def _clamp_optional_int(self, value: Any, *, minimum: int, maximum: int) -> int | None:
        if not isinstance(value, (int, float)):
            return None
        return max(minimum, min(int(value), maximum))

    def _apply_delta(
        self,
        value: float | None,
        delta: Any,
        *,
        minimum: float,
        maximum: float,
    ) -> float | None:
        if value is None or not isinstance(delta, (int, float)):
            return value
        return max(minimum, min(float(value) + float(delta), maximum))

    def _apply_rank_delta(self, value: int | None, delta: Any) -> int | None:
        if value is None or not isinstance(delta, (int, float)):
            return value
        return max(1, int(value + int(delta)))

    def _find_plan_by_name(
        self,
        plans: list[dict[str, Any]] | None,
        plan_name: str,
    ) -> dict[str, Any] | None:
        if not plans:
            return None
        return next(
            (
                plan
                for plan in plans
                if isinstance(plan, dict) and str(plan.get("planName") or "") == plan_name
            ),
            None,
        )

    def _as_optional_int(self, value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _as_optional_float(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _is_number(self, value: Any) -> bool:
        try:
            float(value)
        except (TypeError, ValueError):
            return False
        return True
