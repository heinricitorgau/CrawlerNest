from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from crawlernest_ranking_crawler.postgres_driver import get_psycopg2
from crawlernest_ranking_crawler.subjects.contracts import NormalizedSubjectRankingRow


@dataclass(frozen=True, slots=True)
class SubjectRankingWriteSummary:
    row_count: int
    inserted_row_count: int
    updated_row_count: int
    subject_record_count: int
    target_location: str
    mode: str = "persistent"


def write_subject_ranking_rows(
    conn: object,
    rows: Iterable[NormalizedSubjectRankingRow],
    *,
    run_id: str | None = None,
) -> SubjectRankingWriteSummary:
    materialized_rows = list(rows)
    inserted = 0
    updated = 0
    with conn.cursor() as cur:
        ensure_subject_ranking_schema(cur)
        ranking_source_ids = _ranking_source_ids(cur, {row.source_code for row in materialized_rows})
        subject_ids = _subject_ids(cur)
        for row in materialized_rows:
            status = _upsert_subject_row(
                cur,
                row=row,
                ranking_source_id=ranking_source_ids[row.source_code],
                subject_id=subject_ids[row.subject_key],
                run_id=run_id,
            )
            if status == "inserted":
                inserted += 1
            else:
                updated += 1
        subject_record_count = _count_subject_records(cur)
    return SubjectRankingWriteSummary(
        row_count=len(materialized_rows),
        inserted_row_count=inserted,
        updated_row_count=updated,
        subject_record_count=subject_record_count,
        target_location="warehouse.subject_ranking_record",
    )


def write_subject_ranking_rows_to_postgres(
    rows: Iterable[NormalizedSubjectRankingRow],
    *,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
    run_id: str | None = None,
) -> SubjectRankingWriteSummary:
    psycopg2 = get_psycopg2()
    conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        database=pg_database,
        user=pg_user,
        password=pg_password,
    )
    try:
        summary = write_subject_ranking_rows(conn, rows, run_id=run_id)
        conn.commit()
        return summary
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ensure_subject_ranking_schema(cur: object) -> None:
    cur.execute("CREATE SCHEMA IF NOT EXISTS warehouse")
    cur.execute("CREATE SCHEMA IF NOT EXISTS analytics")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS warehouse.ranking_subject (
            subject_id SMALLSERIAL PRIMARY KEY,
            subject_key TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            subject_group TEXT,
            source_aliases JSONB,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        INSERT INTO warehouse.ranking_subject (
            subject_key,
            display_name,
            subject_group,
            source_aliases
        ) VALUES
            (
                'computer-science',
                'Computer Science',
                'Engineering and Technology',
                '{"QS": ["Computer Science and Information Systems"]}'::jsonb
            ),
            (
                'electrical-engineering',
                'Electrical Engineering',
                'Engineering and Technology',
                '{"QS": ["Engineering - Electrical and Electronic"]}'::jsonb
            )
        ON CONFLICT (subject_key) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            subject_group = EXCLUDED.subject_group,
            source_aliases = EXCLUDED.source_aliases,
            is_active = TRUE
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS warehouse.subject_ranking_record (
            subject_ranking_record_id BIGSERIAL PRIMARY KEY,
            canonical_university_id BIGINT NOT NULL
                REFERENCES warehouse.canonical_university(canonical_university_id),
            ranking_source_id SMALLINT NOT NULL
                REFERENCES warehouse.ranking_source(ranking_source_id),
            source_mapping_id BIGINT
                REFERENCES warehouse.source_university_mapping(source_mapping_id),
            subject_id SMALLINT NOT NULL
                REFERENCES warehouse.ranking_subject(subject_id),
            ranking_year INTEGER NOT NULL,
            rank_position INTEGER,
            rank_display TEXT,
            score NUMERIC(8,4),
            score_scale NUMERIC(8,4),
            source_entity_id TEXT,
            source_url TEXT,
            source_version TEXT,
            raw_payload JSONB,
            metadata JSONB,
            ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            run_id TEXT,
            CHECK (rank_position IS NULL OR rank_position > 0),
            CHECK (score IS NULL OR score >= 0),
            UNIQUE (
                canonical_university_id,
                ranking_source_id,
                subject_id,
                ranking_year
            )
        )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_subject_ranking_lookup
            ON warehouse.subject_ranking_record (
                ranking_source_id,
                subject_id,
                ranking_year,
                rank_position
            )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_subject_ranking_canonical
            ON warehouse.subject_ranking_record (
                canonical_university_id,
                ranking_year
            )
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_subject_ranking_subject_year
            ON warehouse.subject_ranking_record (
                subject_id,
                ranking_year,
                rank_position
            )
        """
    )
    cur.execute(
        """
        CREATE OR REPLACE VIEW analytics.v_subject_rankings_latest AS
        SELECT
            srr.subject_ranking_record_id,
            cu.canonical_university_id,
            cu.canonical_slug,
            cu.display_name AS university_name,
            c.country_code,
            c.country_name,
            rs.source_code,
            rs.source_name,
            subj.subject_key,
            subj.display_name AS subject_name,
            srr.ranking_year,
            srr.rank_position,
            srr.rank_display,
            srr.score,
            srr.score_scale,
            srr.source_url,
            srr.metadata,
            srr.updated_at
        FROM warehouse.subject_ranking_record srr
        JOIN warehouse.canonical_university cu
          ON cu.canonical_university_id = srr.canonical_university_id
        JOIN warehouse.ranking_source rs
          ON rs.ranking_source_id = srr.ranking_source_id
        JOIN warehouse.ranking_subject subj
          ON subj.subject_id = srr.subject_id
        LEFT JOIN warehouse.countries c
          ON c.country_id = cu.country_id
        """
    )


def _ranking_source_ids(cur: object, source_codes: set[str]) -> dict[str, int]:
    ids: dict[str, int] = {}
    for source_code in sorted(source_codes):
        cur.execute(
            """
            INSERT INTO warehouse.ranking_source (
                source_code,
                source_name,
                source_version,
                metadata
            ) VALUES (%s, %s, %s, %s::jsonb)
            ON CONFLICT (source_code) DO UPDATE SET
                source_name = EXCLUDED.source_name,
                is_active = TRUE
            RETURNING ranking_source_id
            """,
            (source_code, _source_name(source_code), "subject-phase-1", "{}"),
        )
        row = cur.fetchone()
        ids[source_code] = int(row[0])
    return ids


def _subject_ids(cur: object) -> dict[str, int]:
    cur.execute(
        """
        SELECT subject_key, subject_id
        FROM warehouse.ranking_subject
        WHERE subject_key IN ('computer-science', 'electrical-engineering')
          AND is_active = TRUE
        """
    )
    rows = cur.fetchall()
    ids = {str(row[0]): int(row[1]) for row in rows}
    missing = {"computer-science", "electrical-engineering"} - set(ids)
    if missing:
        raise RuntimeError(f"missing subject seeds: {', '.join(sorted(missing))}")
    return ids


def _upsert_subject_row(
    cur: object,
    *,
    row: NormalizedSubjectRankingRow,
    ranking_source_id: int,
    subject_id: int,
    run_id: str | None,
) -> str:
    get_psycopg2()
    from psycopg2.extras import Json  # type: ignore

    json_payload = Json(row.raw_payload or {})
    json_metadata = Json(row.metadata or {})
    cur.execute(
        """
        INSERT INTO warehouse.subject_ranking_record (
            canonical_university_id,
            ranking_source_id,
            source_mapping_id,
            subject_id,
            ranking_year,
            rank_position,
            rank_display,
            score,
            score_scale,
            source_entity_id,
            source_url,
            source_version,
            raw_payload,
            metadata,
            run_id
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (
            canonical_university_id,
            ranking_source_id,
            subject_id,
            ranking_year
        ) DO UPDATE SET
            source_mapping_id = EXCLUDED.source_mapping_id,
            rank_position = EXCLUDED.rank_position,
            rank_display = EXCLUDED.rank_display,
            score = EXCLUDED.score,
            score_scale = EXCLUDED.score_scale,
            source_entity_id = EXCLUDED.source_entity_id,
            source_url = EXCLUDED.source_url,
            source_version = EXCLUDED.source_version,
            raw_payload = EXCLUDED.raw_payload,
            metadata = EXCLUDED.metadata,
            updated_at = CURRENT_TIMESTAMP,
            run_id = EXCLUDED.run_id
        RETURNING (xmax = 0) AS inserted
        """,
        (
            row.canonical_university_id,
            ranking_source_id,
            row.source_mapping_id,
            subject_id,
            row.ranking_year,
            row.rank_position,
            row.rank_display,
            row.score,
            row.score_scale,
            row.source_entity_id,
            row.source_url,
            row.source_version,
            json_payload,
            json_metadata,
            run_id,
        ),
    )
    result = cur.fetchone()
    return "inserted" if result and bool(result[0]) else "updated"


def _count_subject_records(cur: object) -> int:
    cur.execute("SELECT COUNT(*) FROM warehouse.subject_ranking_record")
    row = cur.fetchone()
    return 0 if row is None else int(row[0])


def _source_name(source_code: str) -> str:
    if source_code == "QS":
        return "QS World University Rankings"
    return source_code
