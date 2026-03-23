from __future__ import annotations

import json
from typing import Any

from .integrator import IntegrationDiagnostics
from .types import StandardizedRankingRecord, UnifiedRankingRecord


class MultiSourceRepository:
    """
    PostgreSQL repository for multi-source ingestion.
    Expects psycopg2-like connection.
    """

    def __init__(self, conn: Any):
        self.conn = conn

    def upsert_ranking_sources(self, sources: list[tuple[str, str, str | None]]) -> dict[str, int]:
        # (source_code, source_name, source_version)
        source_codes = sorted(set([s[0] for s in sources if s and s[0]]))
        with self.conn.cursor() as cur:
            for code, name, version in sources:
                cur.execute(
                    """
                    INSERT INTO warehouse.ranking_source (source_code, source_name, source_version)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (source_code)
                    DO UPDATE SET
                        source_name = EXCLUDED.source_name,
                        source_version = COALESCE(EXCLUDED.source_version, warehouse.ranking_source.source_version)
                    """,
                    (code, name, version),
                )
            cur.execute(
                """
                SELECT ranking_source_id, source_code
                FROM warehouse.ranking_source
                WHERE source_code = ANY(%s)
                """,
                (source_codes,),
            )
            rows = cur.fetchall()
        self.conn.commit()
        return {str(code): int(source_id) for source_id, code in rows}

    def upsert_source_university_mappings(self, unified_rows: list[UnifiedRankingRecord], source_id_map: dict[str, int]) -> None:
        with self.conn.cursor() as cur:
            for row in unified_rows:
                if row.canonical_university_id is None:
                    continue
                ranking_source_id = source_id_map.get(row.source)
                if ranking_source_id is None:
                    continue
                cur.execute(
                    """
                    INSERT INTO warehouse.source_university_mapping (
                        ranking_source_id, source_entity_id, canonical_university_id,
                        match_method, confidence_score, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (ranking_source_id, source_entity_id)
                    DO UPDATE SET
                        canonical_university_id = EXCLUDED.canonical_university_id,
                        match_method = EXCLUDED.match_method,
                        confidence_score = EXCLUDED.confidence_score,
                        metadata = EXCLUDED.metadata,
                        last_seen_at = CURRENT_TIMESTAMP
                    """,
                    (
                        ranking_source_id,
                        row.source_entity_id,
                        row.canonical_university_id,
                        row.matching_method,
                        row.confidence_score,
                        json.dumps(row.metadata, ensure_ascii=False),
                    ),
                )
        self.conn.commit()

    def upsert_ranking_records(self, unified_rows: list[UnifiedRankingRecord], source_id_map: dict[str, int]) -> None:
        with self.conn.cursor() as cur:
            for row in unified_rows:
                if row.canonical_university_id is None:
                    continue
                ranking_source_id = source_id_map.get(row.source)
                if ranking_source_id is None:
                    continue
                cur.execute(
                    """
                    INSERT INTO warehouse.ranking_record (
                        canonical_university_id,
                        ranking_source_id,
                        ranking_year,
                        ranking_type,
                        rank_position,
                        score,
                        source_version,
                        source_url,
                        metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (canonical_university_id, ranking_source_id, ranking_year, ranking_type)
                    DO UPDATE SET
                        rank_position = EXCLUDED.rank_position,
                        score = EXCLUDED.score,
                        source_version = COALESCE(EXCLUDED.source_version, warehouse.ranking_record.source_version),
                        source_url = COALESCE(EXCLUDED.source_url, warehouse.ranking_record.source_url),
                        metadata = EXCLUDED.metadata,
                        ingested_at = CURRENT_TIMESTAMP
                    """,
                    (
                        row.canonical_university_id,
                        ranking_source_id,
                        row.year,
                        row.ranking_type,
                        row.rank,
                        row.score,
                        row.source_version,
                        row.source_url,
                        json.dumps(row.metadata, ensure_ascii=False),
                    ),
                )
        self.conn.commit()

    def log_ingestion(self, source_code: str, diagnostics: IntegrationDiagnostics, inserted_count: int, updated_count: int, batch_id: str | None = None) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO analytics.source_ingestion_log (
                    source_code, batch_id, finished_at, records_in,
                    matched_count, unresolved_count, inserted_count, updated_count, details_json
                ) VALUES (%s, %s, CURRENT_TIMESTAMP, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    source_code,
                    batch_id,
                    diagnostics.total_records,
                    diagnostics.total_records - diagnostics.unresolved_count,
                    diagnostics.unresolved_count,
                    inserted_count,
                    updated_count,
                    json.dumps(
                        {
                            "unique_resolution_keys": diagnostics.unique_resolution_keys,
                            "duplicate_resolution_saves": diagnostics.duplicate_resolution_saves,
                            "by_source_count": diagnostics.by_source_count,
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
        self.conn.commit()

    def log_missing_entities(self, raw_rows: list[StandardizedRankingRecord], unified_rows: list[UnifiedRankingRecord]) -> None:
        with self.conn.cursor() as cur:
            for raw, unified in zip(raw_rows, unified_rows):
                if unified.canonical_university_id is not None:
                    continue
                cur.execute(
                    """
                    INSERT INTO analytics.missing_entity_log (
                        source_code, source_entity_id, raw_name, normalized_name,
                        country_hint, ranking_year, ranking_type, details_json
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        raw.source,
                        raw.source_entity_id,
                        raw.university_name,
                        unified.metadata.get("normalized_name") if isinstance(unified.metadata, dict) else None,
                        raw.country_hint,
                        raw.ranking_year,
                        raw.ranking_type,
                        json.dumps({"matching_method": unified.matching_method}, ensure_ascii=False),
                    ),
                )
        self.conn.commit()

    def log_merge_diagnostics(self, diagnostics: IntegrationDiagnostics, batch_id: str | None = None) -> None:
        with self.conn.cursor() as cur:
            for source_code, cnt in diagnostics.by_source_count.items():
                cur.execute(
                    """
                    INSERT INTO analytics.merge_diagnostics (
                        batch_id,
                        source_code,
                        total_records,
                        unique_resolution_keys,
                        duplicate_resolution_saves,
                        avg_candidates,
                        details_json
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        batch_id,
                        source_code,
                        cnt,
                        diagnostics.unique_resolution_keys,
                        diagnostics.duplicate_resolution_saves,
                        None,
                        json.dumps(
                            {
                                "unresolved_count": diagnostics.unresolved_count,
                                "by_source_count": diagnostics.by_source_count,
                            },
                            ensure_ascii=False,
                        ),
                    ),
                )
        self.conn.commit()
