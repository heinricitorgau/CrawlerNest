from __future__ import annotations

import json
from typing import Any, Callable, Sequence

from ranking_aggregation.types import RankingRecordInput

from .continuity import ExistingMapping, MappingReassignmentError, find_reassignments
from .integrator import IntegrationDiagnostics
from .reviews import MappingReview
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
            cur.executemany(
                """
                INSERT INTO warehouse.ranking_source (source_code, source_name, source_version)
                VALUES (%s, %s, %s)
                ON CONFLICT (source_code)
                DO UPDATE SET
                    source_name = EXCLUDED.source_name,
                    source_version = COALESCE(EXCLUDED.source_version, warehouse.ranking_source.source_version)
                """,
                [(code, name, version) for code, name, version in sources],
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
            self._mirror_into_entity_source(cur, sources)
        self.conn.commit()
        return {str(code): int(source_id) for source_id, code in rows}

    @staticmethod
    def _mirror_into_entity_source(cur: Any, sources: list[tuple[str, str, str | None]]) -> None:
        """
        Register the same codes in warehouse.entity_source.

        warehouse.mapping_review.source_code carries a foreign key to that
        table, so a source that is known here but not there cannot be reviewed:
        the first decision filed against it fails on the constraint. Mirroring
        at registration time is what keeps the two in step -- the alternative,
        seeding entity_source from the schema file, only covers sources that
        already existed when the database was bootstrapped.

        Tolerates the table being absent so that a database bootstrapped before
        this schema landed still ingests rather than crashing, which is the
        same allowance load_mapping_reviews makes.
        """
        cur.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'warehouse'
              AND table_name = 'entity_source'
            LIMIT 1
            """
        )
        if cur.fetchone() is None:
            return

        cur.executemany(
            """
            INSERT INTO warehouse.entity_source (source_code, source_kind, display_name)
            VALUES (%s, 'ranking', %s)
            ON CONFLICT (source_code)
            DO UPDATE SET display_name = EXCLUDED.display_name
            """,
            [(code, name) for code, name, _version in sources if code],
        )

    def load_mapping_reviews(self, source_codes: Sequence[str]) -> dict[tuple[str, str], MappingReview]:
        """
        Read the standing human decisions for the sources in this run.

        Keyed by source_code, which is what MappingReview.key has always been.
        The table used to be keyed by ranking_source_id, so this had to invert
        a code-to-id map on the way in and again on the way out; since the
        review table was generalised to cover non-ranking sources -- admission
        pages resolve against the same canonical universities and go through
        the same screen -- the two ends finally speak the same language.

        Read-only by design: the pipeline never writes warehouse.mapping_review.
        Returns {} when the table is absent so that a database bootstrapped
        before this schema landed still ingests rather than crashing.
        """
        codes = sorted({str(code) for code in source_codes if code})
        if not codes:
            return {}

        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'warehouse'
                  AND table_name = 'mapping_review'
                LIMIT 1
                """
            )
            if cur.fetchone() is None:
                return {}

            cur.execute(
                """
                SELECT
                    source_code,
                    source_entity_id,
                    decision,
                    decided_canonical_university_id,
                    decided_by,
                    note,
                    reviewed_source_name
                FROM warehouse.mapping_review
                WHERE source_code = ANY(%s)
                """,
                (codes,),
            )
            rows = cur.fetchall()

        reviews: dict[tuple[str, str], MappingReview] = {}
        for source_code, entity_id, decision, decided_id, decided_by, note, reviewed_name in rows:
            review = MappingReview(
                source_code=str(source_code),
                source_entity_id=str(entity_id),
                decision=str(decision),
                decided_canonical_university_id=None if decided_id is None else int(decided_id),
                decided_by=str(decided_by or "unknown"),
                note=None if note is None else str(note),
                reviewed_source_name=None if reviewed_name is None else str(reviewed_name),
            )
            reviews[review.key] = review
        return reviews

    def load_active_mappings(
        self,
        keys: Sequence[tuple[str, str]],
        source_id_map: dict[str, int] | None = None,
    ) -> dict[tuple[str, str], ExistingMapping]:
        """The active mapping for each (source_code, source_entity_id) that has one.

        Keyed by source_code, so it serves every source -- ranking or not.
        ``source_id_map`` is accepted for the ranking callers that still pass it
        and is no longer needed.
        """
        pairs = sorted({(str(code), str(entity_id)) for code, entity_id in keys if code and entity_id})
        if not pairs:
            return {}
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT m.source_code, m.source_entity_id, m.canonical_university_id,
                       m.match_method, m.confidence_score
                FROM warehouse.source_university_mapping m
                JOIN unnest(%s::text[], %s::text[]) AS k(source_code, source_entity_id)
                  ON k.source_code = m.source_code
                 AND k.source_entity_id = m.source_entity_id
                WHERE m.is_active
                """,
                ([code for code, _ in pairs], [entity_id for _, entity_id in pairs]),
            )
            rows = cur.fetchall()
        return {
            (str(code), str(entity_id)): ExistingMapping(
                canonical_university_id=int(canonical_id),
                match_method=None if method is None else str(method),
                confidence_score=None if confidence is None else float(confidence),
            )
            for code, entity_id, canonical_id, method, confidence in rows
        }

    def upsert_source_university_mappings(self, unified_rows: list[UnifiedRankingRecord], source_id_map: dict[str, int]) -> None:
        """Write a ranking batch's mappings. See :meth:`upsert_entity_mappings`."""
        rows = [row for row in unified_rows if source_id_map.get(row.source) is not None]
        self.upsert_entity_mappings(
            rows,
            source_of=lambda row: row.source,
            ranking_source_id_of=lambda code: source_id_map.get(code),
        )

    def upsert_entity_mappings(
        self,
        rows: Sequence[Any],
        *,
        source_of: Callable[[Any], str],
        ranking_source_id_of: Callable[[str], int | None] = lambda code: None,
    ) -> dict[tuple[str, str], int]:
        """
        Write mappings for any source into warehouse.source_university_mapping.

        ``rows`` are resolved records -- UnifiedRankingRecord or
        entity_resolution's ResolutionResult -- and ``source_of`` reads the source
        code off one. ``ranking_source_id_of`` gives a ranking source's id and
        None for any other source, which the table's composite foreign key
        requires. Returns the source_mapping_id of every mapping written or
        confirmed, keyed by (source_code, source_entity_id).

        Refuses, before writing anything, to move an active mapping to another
        university unless the row carries a human decision. The conflict clause
        repeats that rule, so a mapping moved by a concurrent writer between the
        check and the write is left alone rather than overwritten. See
        multi_source/continuity.py for why an entity's id outranks its name.
        """
        resolved = [row for row in rows if row.canonical_university_id is not None and row.source_entity_id]
        reassignments = find_reassignments(
            resolved,
            self.load_active_mappings([(source_of(row), row.source_entity_id) for row in resolved], None),
            source_of=source_of,
        )
        if reassignments:
            raise MappingReassignmentError(reassignments)

        # One statement cannot update a row twice, so a batch naming one entity
        # more than once keeps its last row -- what sequential writes left.
        by_key: dict[tuple[str, str], tuple[Any, ...]] = {}
        for row in resolved:
            code = source_of(row)
            by_key[(code, str(row.source_entity_id))] = (
                code,
                ranking_source_id_of(code),
                str(row.source_entity_id),
                int(row.canonical_university_id),
                row.matching_method,
                row.confidence_score,
                json.dumps(row.metadata, ensure_ascii=False),
            )
        if not by_key:
            return {}

        from psycopg2.extras import execute_values

        with self.conn.cursor() as cur:
            returned = execute_values(
                cur,
                """
                INSERT INTO warehouse.source_university_mapping (
                    source_code, ranking_source_id, source_entity_id, canonical_university_id,
                    match_method, confidence_score, metadata
                ) VALUES %s
                ON CONFLICT (source_code, source_entity_id)
                DO UPDATE SET
                    canonical_university_id = EXCLUDED.canonical_university_id,
                    match_method = EXCLUDED.match_method,
                    confidence_score = EXCLUDED.confidence_score,
                    metadata = EXCLUDED.metadata,
                    -- A row this run writes is live by definition; without this
                    -- an entity rejected once could never be reinstated by a
                    -- later confirm or remap.
                    is_active = TRUE,
                    last_seen_at = CURRENT_TIMESTAMP
                WHERE warehouse.source_university_mapping.canonical_university_id = EXCLUDED.canonical_university_id
                   OR NOT warehouse.source_university_mapping.is_active
                   OR EXCLUDED.match_method IN ('human_confirmed', 'human_remapped')
                RETURNING source_code, source_entity_id, source_mapping_id
                """,
                list(by_key.values()),
                template="(%s, %s, %s, %s, %s, %s, %s::jsonb)",
                fetch=True,
            )
        self.conn.commit()
        return {(str(code), str(entity_id)): int(mapping_id) for code, entity_id, mapping_id in returned}

    def deactivate_rejected_mappings(
        self,
        rejected_keys: list[tuple[str, str]] | tuple[tuple[str, str], ...],
        source_id_map: dict[str, int] | None = None,
    ) -> int:
        """
        Retire the mappings a reviewer threw out.

        upsert_entity_mappings skips rows whose canonical id is None, so a
        rejected entity is simply never written again and its old row survives
        untouched -- still asserting the match a person just rejected. The
        ranking records are already gone by then, so nothing user-facing is
        wrong, but the mapping table would keep offering the same rejected pair
        up for review forever.

        canonical_university_id is NOT NULL in this table, so the row is
        deactivated rather than blanked. Keyed by source_code, for every source;
        ``source_id_map`` is accepted for old callers and unused.
        """
        keys = sorted({(str(code), str(entity_id)) for code, entity_id in rejected_keys})
        if not keys:
            return 0
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE warehouse.source_university_mapping m
                SET is_active = FALSE,
                    last_seen_at = CURRENT_TIMESTAMP
                FROM unnest(%s::text[], %s::text[]) AS k(source_code, source_entity_id)
                WHERE m.source_code = k.source_code
                  AND m.source_entity_id = k.source_entity_id
                  AND m.is_active
                """,
                ([code for code, _ in keys], [entity_id for _, entity_id in keys]),
            )
            deactivated = max(0, cur.rowcount)
        self.conn.commit()
        return deactivated

    def count_ranking_records(self, *, ranking_source_id: int, ranking_year: int, ranking_type: str) -> int:
        """Rows this source holds for one edition and ranking type: the prune's scope."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT count(*)
                FROM warehouse.ranking_record
                WHERE ranking_source_id = %s
                  AND ranking_year = %s
                  AND ranking_type = %s
                """,
                (ranking_source_id, ranking_year, ranking_type),
            )
            return int(cur.fetchone()[0] or 0)

    def prune_superseded_records(
        self,
        *,
        ranking_source_id: int,
        ranking_year: int,
        ranking_type: str,
        run_id: str,
    ) -> int:
        """Drop this source's rows for this year that the current run did not write.

        The upsert stamps every row it touches with the run id, but it can only
        touch universities the payload contains. Re-ingesting a smaller or
        corrected payload therefore leaves the ones that dropped out behind, with
        their old rank, forever -- and they are indistinguishable downstream from
        rows the source still publishes.

        This is the same rule the analytics bridge applies to
        analytics.aggregated_rankings, for the same reason: these tables are
        current state, and history lives in the run tables.

        Scoped to one source, year and ranking type, so a run cannot delete
        another source's rows or another year's.
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM warehouse.ranking_record
                WHERE ranking_source_id = %s
                  AND ranking_year = %s
                  AND ranking_type = %s
                  AND run_id IS DISTINCT FROM %s
                """,
                (ranking_source_id, ranking_year, ranking_type, run_id),
            )
            removed = int(cur.rowcount or 0)
        self.conn.commit()
        return removed

    def upsert_ranking_records(
        self,
        unified_rows: list[UnifiedRankingRecord],
        source_id_map: dict[str, int],
        run_id: str | None = None,
    ) -> int:
        """
        Write one ranking fact per university, source, year and universe.

        source_mapping_id is looked up from the entity this row came from, so it
        has to run after upsert_source_university_mappings in the same ingest --
        which ingest_records guarantees. It is matched on the university as well
        as the entity: if the two disagree, NULL is the honest answer, not a link
        to a mapping that credits someone else. It is also overwritten on
        conflict, because when two entities resolve to one university the row
        now holds the later one's rank and must name the later one's mapping.
        """
        params: list[tuple[Any, ...]] = []
        for row in unified_rows:
            if row.canonical_university_id is None:
                continue
            ranking_source_id = source_id_map.get(row.source)
            if ranking_source_id is None:
                continue
            params.append(
                (
                    row.canonical_university_id,
                    ranking_source_id,
                    ranking_source_id,
                    row.source_entity_id,
                    row.canonical_university_id,
                    row.year,
                    row.ranking_type,
                    getattr(row, "universe_type", "global"),
                    getattr(row, "universe_key", "global"),
                    row.rank,
                    row.score,
                    row.source_version,
                    row.source_url,
                    json.dumps(row.metadata, ensure_ascii=False),
                    run_id,
                )
            )
        if not params:
            return 0
        with self.conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO warehouse.ranking_record (
                    canonical_university_id,
                    ranking_source_id,
                    source_mapping_id,
                    ranking_year,
                    ranking_type,
                    universe_type,
                    universe_key,
                    rank_position,
                    score,
                    source_version,
                    source_url,
                    metadata,
                    updated_at,
                    run_id
                ) VALUES (
                    %s, %s,
                    (
                        SELECT m.source_mapping_id
                        FROM warehouse.source_university_mapping m
                        WHERE m.ranking_source_id = %s
                          AND m.source_entity_id = %s
                          AND m.canonical_university_id = %s
                    ),
                    %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, CURRENT_TIMESTAMP, %s
                )
                ON CONFLICT (canonical_university_id, ranking_source_id, ranking_year, ranking_type, universe_type, universe_key)
                DO UPDATE SET
                    source_mapping_id = EXCLUDED.source_mapping_id,
                    universe_type = EXCLUDED.universe_type,
                    universe_key = EXCLUDED.universe_key,
                    rank_position = EXCLUDED.rank_position,
                    score = EXCLUDED.score,
                    source_version = COALESCE(EXCLUDED.source_version, warehouse.ranking_record.source_version),
                    source_url = COALESCE(EXCLUDED.source_url, warehouse.ranking_record.source_url),
                    metadata = EXCLUDED.metadata,
                    updated_at = CURRENT_TIMESTAMP,
                    run_id = EXCLUDED.run_id,
                    ingested_at = CURRENT_TIMESTAMP
                """,
                params,
            )
        self.conn.commit()
        return len(params)

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
        params: list[tuple[Any, ...]] = []
        for raw, unified in zip(raw_rows, unified_rows):
            if unified.canonical_university_id is not None:
                continue
            params.append(
                (
                    raw.source,
                    raw.source_entity_id,
                    raw.university_name,
                    unified.metadata.get("normalized_name") if isinstance(unified.metadata, dict) else None,
                    raw.country_hint,
                    raw.ranking_year,
                    raw.ranking_type,
                    json.dumps({"matching_method": unified.matching_method}, ensure_ascii=False),
                )
            )
        if not params:
            return
        with self.conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO analytics.missing_entity_log (
                    source_code, source_entity_id, raw_name, normalized_name,
                    country_hint, ranking_year, ranking_type, details_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                params,
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

    def fetch_ranking_inputs(self, years: list[int], ranking_type: str = "world") -> list[RankingRecordInput]:
        if not years:
            return []
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    rr.canonical_university_id,
                    rs.source_code,
                    rr.ranking_year,
                    rr.universe_type,
                    rr.universe_key,
                    rr.rank_position,
                    rr.score,
                    rr.metadata
                FROM warehouse.ranking_record rr
                JOIN warehouse.ranking_source rs
                  ON rs.ranking_source_id = rr.ranking_source_id
                WHERE rr.ranking_year = ANY(%s)
                  AND rr.ranking_type = %s
                ORDER BY rr.ranking_year, rr.universe_type, rr.universe_key, rr.canonical_university_id, rs.source_code
                """,
                (years, ranking_type),
            )
            rows = cur.fetchall()
        return [
            RankingRecordInput(
                canonical_university_id=int(canonical_university_id),
                source=str(source_code),
                year=int(ranking_year),
                universe_type=str(universe_type or "global"),
                universe_key=str(universe_key or "global"),
                rank=rank_position,
                score=float(score) if score is not None else None,
                metadata_json=dict(metadata or {}),
            )
            for canonical_university_id, source_code, ranking_year, universe_type, universe_key, rank_position, score, metadata in rows
        ]
