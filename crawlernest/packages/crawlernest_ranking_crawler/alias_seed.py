from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

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
            summary = seed_university_alias(cur, canonical_name=canonical_name, alias=alias)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return summary


def seed_university_alias(
    cur: "psycopg2.extensions.cursor",
    *,
    canonical_name: str,
    alias: str,
) -> UniversityAliasSeedSummary:
    """Point ``alias`` at the canonical named ``canonical_name``, creating that canonical only if none exists.

    Writes nothing to an existing canonical. This used to upsert it, which rewrote ``display_name`` and
    ``display_name_normalized`` -- the latter in title case, where every other row is lower case, and
    ``ranking_decision_preview`` joins on it -- and reported every existing canonical as created.
    """
    normalized_canonical_name = normalize_display_name(canonical_name)
    normalized_alias = normalize_alias(alias)
    if not normalized_canonical_name:
        raise ValueError("canonical_name must not be empty")
    if not normalized_alias:
        raise ValueError("alias must not be empty")

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
    return UniversityAliasSeedSummary(
        canonical_university_id=canonical_id,
        canonical_name=canonical_name,
        normalized_canonical_name=normalized_canonical_name,
        alias=alias,
        normalized_alias=normalized_alias,
        created_canonical=created_canonical,
        created_alias=created_alias,
    )


def normalize_display_name(name: str) -> str:
    """The form stored in ``canonical_university.display_name_normalized``: whitespace collapsed, lower case."""
    return normalize_university_name(name or "").lower()


def normalize_alias(alias_text: str) -> str:
    """The form stored in ``university_alias.alias_normalized``, as ``scripts/seed_alias_file.py`` writes it.

    Lower case with punctuation folded to spaces. The title-case form this module used to write never matched
    the dedup index's other rows, so a second seed of the same alias added a second row.
    """
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(alias_text or "").strip().lower()).split())


def alias_seed_summary_to_dict(summary: UniversityAliasSeedSummary) -> dict[str, Any]:
    return asdict(summary)


def _get_or_create_canonical(
    cur: "psycopg2.extensions.cursor",
    *,
    canonical_name: str,
    normalized_canonical_name: str,
) -> tuple[int, bool]:
    canonical_slug = _build_canonical_slug(canonical_name, normalized_canonical_name)
    cur.execute(
        """
        SELECT canonical_university_id, status, metadata ->> 'merged_into'
        FROM warehouse.canonical_university
        WHERE canonical_slug = %s OR lower(display_name) = lower(%s)
        """,
        (canonical_slug, canonical_name.strip()),
    )
    rows = cur.fetchall()
    if len(rows) > 1:
        ids = ", ".join(str(int(r[0])) for r in rows)
        raise ValueError(f"canonical name {canonical_name!r} matches several canonical universities ({ids}); name one exactly")
    if rows:
        canonical_id, status, merged_into = int(rows[0][0]), rows[0][1], rows[0][2]
        if status != "active":
            # An alias on a merged-away record would resolve a source to a university that is no longer shown.
            where = f"; it was merged into {merged_into}" if merged_into else ""
            raise ValueError(f"canonical {canonical_id} {canonical_name!r} is {status}{where}")
        return canonical_id, False

    cur.execute(
        """
        INSERT INTO warehouse.canonical_university (
            canonical_slug,
            display_name,
            display_name_normalized,
            status
        )
        VALUES (%s, %s, %s, 'active')
        RETURNING canonical_university_id
        """,
        (canonical_slug, canonical_name.strip(), normalized_canonical_name),
    )
    return int(cur.fetchone()[0]), True


def _ensure_alias_points_to_canonical(
    cur: "psycopg2.extensions.cursor",
    *,
    canonical_university_id: int,
    alias: str,
    normalized_alias: str,
) -> bool:
    cur.execute(
        """
        SELECT canonical_university_id
        FROM warehouse.university_alias
        WHERE alias_normalized = %s
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
        INSERT INTO warehouse.university_alias (
            canonical_university_id,
            alias_text,
            alias_normalized,
            source_name,
            is_primary,
            is_abbreviation,
            metadata
        ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT DO NOTHING
        """,
        (
            canonical_university_id,
            alias,
            normalized_alias,
            "manual",
            False,
            _looks_like_abbreviation(alias),
            '{"seed_origin":"seed-university-alias","match_type":"exact","confidence_score":1.0}',
        ),
    )
    return True


def _build_canonical_slug(canonical_name: str, normalized_canonical_name: str) -> str:
    base = normalized_canonical_name or normalize_university_name(canonical_name)
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    return slug or "canonical-university"


def _looks_like_abbreviation(alias: str) -> bool:
    compact = re.sub(r"[^A-Za-z]", "", alias)
    return bool(compact) and compact.isupper() and len(compact) <= 10
