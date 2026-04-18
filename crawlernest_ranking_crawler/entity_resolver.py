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
    manual_review_mapping_count: int
    suspicious_mapping_count: int
    country_mismatch_mapping_count: int


def resolve_university(
    cur: "psycopg2.extensions.cursor",
    normalized_name: str,
) -> tuple[int | None, str]:
    # Normalize to lowercase for case-insensitive matching
    normalized_lower = normalized_name.lower().strip() if normalized_name else ""

    cur.execute(
        """
        SELECT canonical_university_id
        FROM warehouse.canonical_university
        WHERE display_name_normalized = %s
        ORDER BY canonical_university_id ASC
        LIMIT 1
        """,
        (normalized_lower,),
    )
    row = cur.fetchone()
    if row is not None:
        return int(row[0]), RESOLVED

    cur.execute(
        """
        SELECT canonical_university_id
        FROM warehouse.university_alias
        WHERE alias_normalized = %s
        ORDER BY canonical_university_id ASC, alias_id ASC
        LIMIT 1
        """,
        (normalized_lower,),
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
            source_names = tuple(sorted({source for _, _, source in rows if source}))

            resolved_row_count = 0
            unresolved_row_count = 0

            for row_id, normalized_name, _source_name in rows:
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

            mapping_stats = _load_mapping_review_stats(cur, source_names=source_names)

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
        manual_review_mapping_count=mapping_stats["manual_review_mapping_count"],
        suspicious_mapping_count=mapping_stats["suspicious_mapping_count"],
        country_mismatch_mapping_count=mapping_stats["country_mismatch_mapping_count"],
    )


def entity_resolution_summary_to_dict(summary: EntityResolutionSummary) -> dict[str, Any]:
    return asdict(summary)


def _ensure_resolution_tables(cur: "psycopg2.extensions.cursor") -> None:
    cur.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'warehouse'
          AND table_name = 'canonical_university'
        LIMIT 1
        """
    )
    if cur.fetchone() is None:
        raise RuntimeError("required table not found: warehouse.canonical_university")

    cur.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'warehouse'
          AND table_name = 'university_alias'
        LIMIT 1
        """
    )
    if cur.fetchone() is None:
        raise RuntimeError("required table not found: warehouse.university_alias")


def _load_preview_rows(
    cur: "psycopg2.extensions.cursor",
    *,
    target_schema: str,
    target_table: str,
) -> list[tuple[int, str, str]]:
    cur.execute(
        f"""
        SELECT id, normalized_university_name, source
        FROM {target_schema}.{target_table}
        ORDER BY id ASC
        """
    )
    return [(int(row[0]), str(row[1]), str(row[2])) for row in cur.fetchall()]


def _load_mapping_review_stats(
    cur: "psycopg2.extensions.cursor",
    *,
    source_names: tuple[str, ...],
) -> dict[str, int]:
    if not source_names:
        return {
            "manual_review_mapping_count": 0,
            "suspicious_mapping_count": 0,
            "country_mismatch_mapping_count": 0,
        }

    cur.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'warehouse'
          AND table_name = 'source_mapping'
        LIMIT 1
        """
    )
    if cur.fetchone() is None:
        return {
            "manual_review_mapping_count": 0,
            "suspicious_mapping_count": 0,
            "country_mismatch_mapping_count": 0,
        }

    cur.execute(
        """
        SELECT
            COUNT(*) FILTER (WHERE review_status = 'manual_review') AS manual_review_mapping_count,
            COUNT(*) FILTER (WHERE COALESCE((metadata ->> 'suspicious_merge')::boolean, FALSE)) AS suspicious_mapping_count,
            COUNT(*) FILTER (WHERE COALESCE((metadata ->> 'country_mismatch')::boolean, FALSE)) AS country_mismatch_mapping_count
        FROM warehouse.source_mapping
        WHERE source_name = ANY(%s)
        """,
        (list(source_names),),
    )
    row = cur.fetchone()
    return {
        "manual_review_mapping_count": 0 if row is None or row[0] is None else int(row[0]),
        "suspicious_mapping_count": 0 if row is None or row[1] is None else int(row[1]),
        "country_mismatch_mapping_count": 0 if row is None or row[2] is None else int(row[2]),
    }
