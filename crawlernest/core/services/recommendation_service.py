from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path
from typing import Any

from crawlernest.core.database.settings import DatabaseSettings

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

try:
    import psycopg2
except ImportError:  # pragma: no cover - environment-dependent
    psycopg2 = None  # type: ignore


class RecommendationService:
    MAX_SURFACED_SIGNALS = 2

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
            payload = grouped_recommendations_to_dict(grouped)
        finally:
            conn.close()

        items, counts = self._flatten_grouped_results(payload)
        application_plan = self._build_application_plan(items)
        application_plans = self._build_application_plans(items)
        plan_comparison = self._build_plan_comparison(application_plans)
        summary = self._build_summary(query=query, counts=counts, total_items=len(items))
        assistant_reply, paragraphs = self._build_assistant_reply(
            query=query,
            counts=counts,
            items=items,
            application_plan=application_plan,
            application_plans=application_plans,
            plan_comparison=plan_comparison,
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
            "groups": {
                "reach": payload.get("reach", []),
                "target": payload.get("target", []),
                "safety": payload.get("safety", []),
            },
            "metadata": metadata,
            "profile": self._query_to_profile(query),
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
        ranking_year = self._as_optional_int(profile.get("rankingYear")) or self._as_optional_int(
            profile.get("ranking_year")
        ) or dt.datetime.now().year
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
                decision_output = self._build_decision_output(row.get("decision_output"))
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
    ) -> tuple[str, list[str]]:
        if not items:
            paragraphs = [
                "I checked the current recommendation path but did not find any candidates that fit the profile you provided.",
                "If you want, we can widen the target rank, relax the country filter, or adjust the language score assumptions.",
            ]
            return "\n\n".join(paragraphs), paragraphs

        top_names = [str(item.get("universityName")) for item in items[:3] if item.get("universityName")]
        first = top_names[0] if top_names else "the top result"
        country_text = f" in {query.country}" if query.country else ""

        paragraphs = [
            f"I built a recommendation slice{country_text} and {first} currently looks like the strongest fit in the retrieved results."
        ]

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

        return "\n\n".join(paragraphs), paragraphs

    def _query_to_profile(self, query: RecommendationQuery) -> dict[str, Any]:
        return {
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
            "planConfidenceReason": self._build_application_plan_confidence_reason(
                target_count=target_count,
                safety_count=safety_count,
                warnings=warnings,
                quality_adjustment=quality_adjustment,
                confidence=confidence,
            ),
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
        paragraphs.append(f"Recommended plan: {recommended_plan.capitalize()}.")
        if isinstance(reason, str) and reason:
            paragraphs.append(reason)
        if isinstance(tradeoffs, list):
            lines = [str(line) for line in tradeoffs if isinstance(line, str) and line]
            paragraphs.extend(lines[:2])
        return paragraphs

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
