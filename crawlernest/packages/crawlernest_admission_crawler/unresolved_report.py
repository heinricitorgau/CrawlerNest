from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from crawlernest_admission_crawler.postgres_driver import get_psycopg2


@dataclass(slots=True)
class UnresolvedAdmissionRow:
    normalized_university_name: str
    occurrence_count: int
    suspicious_event_count: int = 0
    country_mismatch_event_count: int = 0


def get_unresolved_admission_entities(
    *,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
    target_schema: str = "warehouse",
    target_table: str = "admission_record",
    limit: int = 20,
) -> list[UnresolvedAdmissionRow]:
    psycopg2 = get_psycopg2()
    conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        dbname=pg_database,
        user=pg_user,
        password=pg_password,
    )
    try:
        with conn.cursor() as cur:
            if _has_entity_resolution_events_table(cur):
                cur.execute(
                    f"""
                    WITH unresolved_names AS (
                        SELECT
                            normalized_university_name,
                            COUNT(*) AS occurrence_count
                        FROM {target_schema}.{target_table}
                        WHERE entity_resolution_status = 'unresolved'
                        GROUP BY normalized_university_name
                    ),
                    event_stats AS (
                        SELECT
                            normalized_name,
                            COUNT(*) FILTER (
                                WHERE COALESCE((details_json ->> 'suspicious_merge')::boolean, FALSE)
                            ) AS suspicious_event_count,
                            COUNT(*) FILTER (
                                WHERE COALESCE((details_json ->> 'country_mismatch')::boolean, FALSE)
                            ) AS country_mismatch_event_count
                        FROM analytics.entity_resolution_event
                        WHERE source_name = 'university_site'
                        GROUP BY normalized_name
                    )
                    SELECT
                        u.normalized_university_name,
                        u.occurrence_count,
                        COALESCE(e.suspicious_event_count, 0) AS suspicious_event_count,
                        COALESCE(e.country_mismatch_event_count, 0) AS country_mismatch_event_count
                    FROM unresolved_names u
                    LEFT JOIN event_stats e
                        ON e.normalized_name = u.normalized_university_name
                    ORDER BY u.occurrence_count DESC, u.normalized_university_name ASC
                    LIMIT %s
                    """,
                    (max(1, limit),),
                )
            else:
                cur.execute(
                    f"""
                    SELECT
                        normalized_university_name,
                        COUNT(*) AS occurrence_count,
                        0 AS suspicious_event_count,
                        0 AS country_mismatch_event_count
                    FROM {target_schema}.{target_table}
                    WHERE entity_resolution_status = 'unresolved'
                    GROUP BY normalized_university_name
                    ORDER BY occurrence_count DESC, normalized_university_name ASC
                    LIMIT %s
                    """,
                    (max(1, limit),),
                )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        UnresolvedAdmissionRow(
            normalized_university_name=str(row[0]),
            occurrence_count=int(row[1]),
            suspicious_event_count=int(row[2]),
            country_mismatch_event_count=int(row[3]),
        )
        for row in rows
    ]


def unresolved_rows_to_dicts(rows: list[UnresolvedAdmissionRow]) -> list[dict[str, Any]]:
    return [asdict(row) for row in rows]


def write_unresolved_report(rows: list[UnresolvedAdmissionRow], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(unresolved_rows_to_dicts(rows), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _has_entity_resolution_events_table(cur: "psycopg2.extensions.cursor") -> bool:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'analytics'
          AND table_name = 'entity_resolution_event'
        LIMIT 1
        """
    )
    return cur.fetchone() is not None
