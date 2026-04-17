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
                items.append(
                    {
                        "canonicalUniversityId": row.get("canonical_university_id"),
                        "universityName": row.get("university_name"),
                        "country": row.get("country"),
                        "aggregatedRank": row.get("aggregated_rank"),
                        "ieltsRequirement": row.get("ielts_requirement"),
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
                    }
                )

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
            if query.target_rank is not None:
                profile_bits.append(f"target rank {query.target_rank}")
            paragraphs.append(
                "This pass was grounded in " + " and ".join(profile_bits) + "."
            )

        return "\n\n".join(paragraphs), paragraphs

    def _query_to_profile(self, query: RecommendationQuery) -> dict[str, Any]:
        return {
            "country": query.country,
            "countryPolicy": query.country_policy,
            "ielts": query.ielts_score,
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
