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
        summary = self._build_summary(query=query, counts=counts, total_items=len(items))
        assistant_reply, paragraphs = self._build_assistant_reply(
            query=query,
            counts=counts,
            items=items,
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
