from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from crawlernest_ranking_crawler.entity_resolver import _ensure_resolution_tables
from crawlernest_ranking_crawler.normalize import normalize_university_name
from crawlernest_ranking_crawler.postgres_driver import get_psycopg2


@dataclass(slots=True)
class UniversityAliasSeedSummary:
    canonical_university_id: int
    canonical_name: str
    normalized_canonical_name: str
    alias: str
    normalized_alias: str
    created_canonical: bool
    created_alias: bool


def add_university_alias(
    canonical_name: str,
    alias: str,
    *,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> UniversityAliasSeedSummary:
    normalized_canonical_name = normalize_university_name(canonical_name)
    normalized_alias = normalize_university_name(alias)
    if not normalized_canonical_name:
        raise ValueError("canonical_name must not be empty")
    if not normalized_alias:
        raise ValueError("alias must not be empty")

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

            canonical_id, created_canonical = _get_or_create_canonical(
                cur,
                canonical_name=canonical_name,
                normalized_canonical_name=normalized_canonical_name,
            )

            created_alias = _ensure_alias_points_to_canonical(
                cur,
                canonical_university_id=canonical_id,
                alias=alias,
                normalized_alias=normalized_alias,
            )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return UniversityAliasSeedSummary(
        canonical_university_id=canonical_id,
        canonical_name=canonical_name,
        normalized_canonical_name=normalized_canonical_name,
        alias=alias,
        normalized_alias=normalized_alias,
        created_canonical=created_canonical,
        created_alias=created_alias,
    )


def alias_seed_summary_to_dict(summary: UniversityAliasSeedSummary) -> dict[str, Any]:
    return asdict(summary)


def _get_or_create_canonical(
    cur: "psycopg2.extensions.cursor",
    *,
    canonical_name: str,
    normalized_canonical_name: str,
) -> tuple[int, bool]:
    cur.execute(
        """
        INSERT INTO warehouse.canonical_universities (normalized_name, display_name)
        VALUES (%s, %s)
        ON CONFLICT (normalized_name) DO NOTHING
        RETURNING canonical_university_id
        """,
        (normalized_canonical_name, canonical_name),
    )
    created = cur.fetchone()
    if created is not None:
        return int(created[0]), True

    cur.execute(
        """
        SELECT canonical_university_id
        FROM warehouse.canonical_universities
        WHERE normalized_name = %s
        """,
        (normalized_canonical_name,),
    )
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("failed to fetch canonical university after upsert")
    return int(row[0]), False


def _ensure_alias_points_to_canonical(
    cur: "psycopg2.extensions.cursor",
    *,
    canonical_university_id: int,
    alias: str,
    normalized_alias: str,
) -> bool:
    cur.execute(
        """
        SELECT university_id
        FROM warehouse.university_aliases
        WHERE source_school_name = %s
        """,
        (normalized_alias,),
    )
    row = cur.fetchone()
    if row is not None:
        existing_canonical_id = int(row[0])
        if existing_canonical_id != canonical_university_id:
            raise ValueError(
                f"alias '{alias}' already points to canonical_university_id={existing_canonical_id}"
            )
        return False

    cur.execute(
        """
        INSERT INTO warehouse.university_aliases (
            university_id,
            source_name,
            source_school_name,
            match_type,
            confidence_score
        ) VALUES (%s, %s, %s, %s, %s)
        """,
        (canonical_university_id, "manual", normalized_alias, "exact", 1.0),
    )
    return True
