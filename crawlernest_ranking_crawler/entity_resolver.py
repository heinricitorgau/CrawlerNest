from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from crawlernest_ranking_crawler.postgres_driver import get_psycopg2

RESOLVED = "resolved"
UNRESOLVED = "unresolved"


@dataclass(slots=True)
class EntityResolutionSummary:
    target_table: str
    total_rows: int
    resolved_row_count: int
    unresolved_row_count: int


def resolve_university(
    cur: "psycopg2.extensions.cursor",
    normalized_name: str,
) -> tuple[int | None, str]:
    cur.execute(
        """
        SELECT canonical_university_id
        FROM warehouse.canonical_universities
        WHERE normalized_name = %s
        """,
        (normalized_name,),
    )
    row = cur.fetchone()
    if row is not None:
        return int(row[0]), RESOLVED

    cur.execute(
        """
        SELECT university_id
        FROM warehouse.university_aliases
        WHERE source_school_name = %s
        """,
        (normalized_name,),
    )
    row = cur.fetchone()
    if row is not None:
        return int(row[0]), RESOLVED

    return None, UNRESOLVED


def resolve_ranking_preview_entities(
    *,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
    target_schema: str = "warehouse",
    target_table: str = "ranking_records_preview",
) -> EntityResolutionSummary:
    psycopg2 = get_psycopg2()
    conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        database=pg_database,
        user=pg_user,
        password=pg_password,
    )
    try:
        with conn.cursor() as cur:
            _ensure_resolution_tables(cur)
            rows = _load_preview_rows(cur, target_schema=target_schema, target_table=target_table)

            resolved_row_count = 0
            unresolved_row_count = 0

            for row_id, normalized_name in rows:
                canonical_id, status = resolve_university(cur, normalized_name)
                cur.execute(
                    f"""
                    UPDATE {target_schema}.{target_table}
                    SET canonical_university_id = %s,
                        entity_resolution_status = %s
                    WHERE id = %s
                    """,
                    (canonical_id, status, row_id),
                )
                if status == RESOLVED:
                    resolved_row_count += 1
                else:
                    unresolved_row_count += 1

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return EntityResolutionSummary(
        target_table=f"{target_schema}.{target_table}",
        total_rows=len(rows),
        resolved_row_count=resolved_row_count,
        unresolved_row_count=unresolved_row_count,
    )


def entity_resolution_summary_to_dict(summary: EntityResolutionSummary) -> dict[str, Any]:
    return asdict(summary)


def _ensure_resolution_tables(cur: "psycopg2.extensions.cursor") -> None:
    cur.execute("CREATE SCHEMA IF NOT EXISTS warehouse")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS warehouse.canonical_universities (
            canonical_university_id BIGSERIAL PRIMARY KEY,
            normalized_name TEXT NOT NULL UNIQUE,
            display_name TEXT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS warehouse.university_aliases (
            alias_id BIGSERIAL PRIMARY KEY,
            university_id BIGINT NOT NULL
                REFERENCES warehouse.canonical_universities(canonical_university_id),
            source_name TEXT NOT NULL DEFAULT 'manual',
            source_school_name TEXT NOT NULL UNIQUE,
            match_type TEXT NOT NULL DEFAULT 'exact',
            confidence_score REAL NOT NULL DEFAULT 1.0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def _load_preview_rows(
    cur: "psycopg2.extensions.cursor",
    *,
    target_schema: str,
    target_table: str,
) -> list[tuple[int, str]]:
    cur.execute(
        f"""
        SELECT id, normalized_university_name
        FROM {target_schema}.{target_table}
        ORDER BY id ASC
        """
    )
    return [(int(row[0]), str(row[1])) for row in cur.fetchall()]
