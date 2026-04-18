from __future__ import annotations

import json
from typing import Any

from .normalizer import normalize_university_name
from .types import CanonicalProfile, ResolutionResult


class EntityResolutionRepository:
    """
    Thin DB adapter for loading canonical profiles and persisting mapping/events.
    Expects a DB-API 2.0 cursor/connection (psycopg2 recommended for PostgreSQL).
    """

    def __init__(self, conn: Any):
        self.conn = conn

    def load_canonical_profiles(self) -> list[CanonicalProfile]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    cu.canonical_university_id,
                    cu.display_name,
                    c.country_name,
                    COALESCE(
                        ARRAY_AGG(ua.alias_text) FILTER (WHERE ua.alias_text IS NOT NULL),
                        ARRAY[]::TEXT[]
                    ) AS aliases
                FROM warehouse.canonical_university cu
                LEFT JOIN warehouse.countries c
                    ON c.country_id = cu.country_id
                LEFT JOIN warehouse.university_alias ua
                    ON ua.canonical_university_id = cu.canonical_university_id
                GROUP BY cu.canonical_university_id, cu.display_name, c.country_name
                """
            )
            rows = cur.fetchall()

        out: list[CanonicalProfile] = []
        for cid, display_name, country_name, aliases in rows:
            out.append(
                CanonicalProfile(
                    canonical_university_id=int(cid),
                    display_name=str(display_name),
                    country_hint=str(country_name).lower() if country_name else None,
                    aliases=tuple(aliases or []),
                )
            )
        return out

    def upsert_source_mapping(self, result: ResolutionResult, threshold_used: float) -> None:
        if result.canonical_university_id is None:
            return
        suspicious_merge = bool(result.metadata.get("suspicious_merge")) if isinstance(result.metadata, dict) else False
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO warehouse.source_mapping (
                    source_name,
                    source_entity_id,
                    canonical_university_id,
                    matched_alias_id,
                    match_method,
                    confidence_score,
                    threshold_used,
                    review_status,
                    metadata
                ) VALUES (%s, %s, %s, NULL, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (source_name, source_entity_id)
                DO UPDATE SET
                    canonical_university_id = EXCLUDED.canonical_university_id,
                    match_method = EXCLUDED.match_method,
                    confidence_score = EXCLUDED.confidence_score,
                    threshold_used = EXCLUDED.threshold_used,
                    review_status = EXCLUDED.review_status,
                    last_seen_at = CURRENT_TIMESTAMP,
                    metadata = EXCLUDED.metadata
                """,
                (
                    result.source_name,
                    result.source_entity_id,
                    result.canonical_university_id,
                    result.matching_method,
                    result.confidence_score,
                    threshold_used,
                    (
                        "manual_review"
                        if suspicious_merge or result.matching_method in {"fuzzy_review", "embedding_review"}
                        else "auto_accepted"
                    ),
                    json.dumps(result.metadata, ensure_ascii=False),
                ),
            )
        self.conn.commit()

    def log_resolution_event(
        self,
        source_name: str,
        source_entity_id: str,
        raw_name: str,
        country_hint: str | None,
        result: ResolutionResult,
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO analytics.entity_resolution_event (
                    source_name,
                    source_entity_id,
                    raw_name,
                    normalized_name,
                    country_hint,
                    candidate_count,
                    match_method,
                    confidence_score,
                    outcome,
                    canonical_university_id,
                    details_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    source_name,
                    source_entity_id,
                    raw_name,
                    normalize_university_name(raw_name),
                    country_hint,
                    result.candidate_count,
                    result.matching_method,
                    result.confidence_score,
                    "matched" if result.canonical_university_id is not None else "unresolved",
                    result.canonical_university_id,
                    json.dumps(result.metadata, ensure_ascii=False),
                ),
            )
        self.conn.commit()
