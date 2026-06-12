from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from crawlernest_ranking_crawler.postgres_driver import get_psycopg2
from crawlernest_ranking_crawler.subjects.contracts import (
    NormalizedSubjectRankingRow,
    SUPPORTED_QS_SUBJECT_KEYS,
    normalize_qs_subject_key,
    normalize_qs_subject_row,
)
from crawlernest_ranking_crawler.subjects.writer import write_subject_ranking_rows

DEFAULT_SNAPSHOT_ROOT = Path(__file__).resolve().parents[2] / "crawlernest" / "crawlernest-kb" / "qs_subject_rankings"
DEFAULT_UNIVERSE_ROOT = Path(__file__).resolve().parents[2] / "crawlernest" / "crawlernest-kb" / "qs_universes"

QS_SUBJECT_SOURCE_NAMES = {
    "computer-science": "Computer Science and Information Systems",
    "electrical-engineering": "Engineering - Electrical and Electronic",
    "business-management": "Business & Management Studies",
}


@dataclass(frozen=True, slots=True)
class QSSubjectIngestionSummary:
    subject_key: str
    ranking_year: int
    raw_count: int
    normalized_count: int
    resolved_count: int
    unresolved_count: int
    inserted_row_count: int
    updated_row_count: int
    source: str
    sample_normalized_row: dict[str, Any] | None


def fetch_qs_subject_rows(
    subject_key: str,
    year: int,
    *,
    snapshot_root: Path | None = None,
    api_url_template: str | None = None,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    normalized_subject = normalize_qs_subject_key(subject_key)
    template = api_url_template or os.getenv("CRAWLERNEST_QS_SUBJECT_API_TEMPLATE", "")
    if template:
        try:
            rows = _fetch_api_rows(template, normalized_subject, year, timeout=timeout)
            if rows:
                return rows
        except Exception:
            # Phase 2 must remain reproducible offline; snapshots are the deterministic fallback.
            pass
    return load_qs_subject_snapshot(normalized_subject, year, snapshot_root=snapshot_root)


def load_qs_subject_snapshot(
    subject_key: str,
    year: int,
    *,
    snapshot_root: Path | None = None,
) -> list[dict[str, Any]]:
    normalized_subject = normalize_qs_subject_key(subject_key)
    root = snapshot_root or DEFAULT_SNAPSHOT_ROOT
    candidates = [
        # prefer the richer universe crawl cache when available
        DEFAULT_UNIVERSE_ROOT / str(year) / "subject" / normalized_subject / "standardized_rows.json",
        root / str(year) / f"{normalized_subject}.json",
        root / f"{year}_{normalized_subject}.json",
    ]
    for path in candidates:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows = _coerce_rows(payload)
            if rows:
                return rows
    raise FileNotFoundError(
        f"No QS subject snapshot found for {normalized_subject} {year}. "
        f"Looked under {root} and {DEFAULT_UNIVERSE_ROOT}."
    )


def normalize_qs_subject_rows(raw_rows: list[dict[str, Any]], *, subject_key: str, year: int) -> list[dict[str, Any]]:
    return [normalize_qs_subject_row(row, subject_key, year) for row in raw_rows]


def run_qs_subject_ingestion(
    *,
    subject_key: str,
    year: int,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
    snapshot_root: Path | None = None,
    limit: int = 0,
    rollback: bool = False,
) -> QSSubjectIngestionSummary:
    raw_rows = fetch_qs_subject_rows(subject_key, year, snapshot_root=snapshot_root)
    if limit > 0:
        raw_rows = raw_rows[:limit]
    normalized_rows = normalize_qs_subject_rows(raw_rows, subject_key=subject_key, year=year)

    psycopg2 = get_psycopg2()
    conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        database=pg_database,
        user=pg_user,
        password=pg_password,
    )
    try:
        materialized, unresolved = resolve_subject_rows(conn, normalized_rows)
        write_summary = write_subject_ranking_rows(
            conn,
            materialized,
            run_id=f"qs-subject-{normalize_qs_subject_key(subject_key)}-{year}",
        )
        if rollback:
            conn.rollback()
        else:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return QSSubjectIngestionSummary(
        subject_key=normalize_qs_subject_key(subject_key),
        ranking_year=year,
        raw_count=len(raw_rows),
        normalized_count=len(normalized_rows),
        resolved_count=len(materialized),
        unresolved_count=len(unresolved),
        inserted_row_count=write_summary.inserted_row_count,
        updated_row_count=write_summary.updated_row_count,
        source="QS",
        sample_normalized_row=(normalized_rows[0] if normalized_rows else None),
    )


def run_qs_subject_rankings_ingestion(
    *,
    year: int,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
    snapshot_root: Path | None = None,
    limit: int = 0,
    rollback: bool = False,
) -> list[QSSubjectIngestionSummary]:
    return [
        run_qs_subject_ingestion(
            subject_key=subject_key,
            year=year,
            pg_host=pg_host,
            pg_port=pg_port,
            pg_database=pg_database,
            pg_user=pg_user,
            pg_password=pg_password,
            snapshot_root=snapshot_root,
            limit=limit,
            rollback=rollback,
        )
        for subject_key in sorted(SUPPORTED_QS_SUBJECT_KEYS)
    ]


def resolve_subject_rows(
    conn: object,
    normalized_rows: list[dict[str, Any]],
) -> tuple[list[NormalizedSubjectRankingRow], list[dict[str, Any]]]:
    resolved: list[NormalizedSubjectRankingRow] = []
    unresolved: list[dict[str, Any]] = []
    with conn.cursor() as cur:
        source_id = _ensure_qs_source(cur)
        for row in normalized_rows:
            match = _resolve_canonical(cur, source_id=source_id, row=row)
            if match is None:
                unresolved.append(row)
                continue
            canonical_university_id, source_mapping_id = match
            resolved.append(
                NormalizedSubjectRankingRow(
                    source_code=str(row["source_code"]),
                    subject_key=str(row["subject_key"]),
                    ranking_year=int(row["ranking_year"]),
                    rank_position=None if row["rank_position"] is None else int(row["rank_position"]),
                    rank_display=str(row["rank_display"]),
                    university_name=str(row["university_name"]),
                    university_name_normalized=str(row["university_name_normalized"]),
                    country_hint=None if row.get("country_hint") is None else str(row.get("country_hint")),
                    canonical_university_id=canonical_university_id,
                    score=None if row.get("score") is None else float(row["score"]),
                    score_scale=None if row.get("score_scale") is None else float(row["score_scale"]),
                    source_entity_id=None if row.get("source_entity_id") is None else str(row.get("source_entity_id")),
                    source_mapping_id=source_mapping_id,
                    source_url=None if row.get("source_url") is None else str(row.get("source_url")),
                    raw_payload=dict(row.get("raw_payload") or {}),
                    metadata={"phase": "subject-ranking-phase-2"},
                )
            )
    return resolved, unresolved


def summary_to_dict(summary: QSSubjectIngestionSummary) -> dict[str, Any]:
    return asdict(summary)


def _fetch_api_rows(template: str, subject_key: str, year: int, *, timeout: int) -> list[dict[str, Any]]:
    url = template.format(
        subject_key=subject_key,
        subject=subject_key,
        year=year,
        qs_subject=QS_SUBJECT_SOURCE_NAMES[subject_key],
        query=urlencode({"subject": subject_key, "year": year}),
    )
    request = Request(url, headers={"User-Agent": "CrawlerNest/subject-ranking-phase-2"})
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return _coerce_rows(payload)


def _coerce_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "items", "data", "rankings", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [dict(item) for item in value if isinstance(item, dict)]
        nested = payload.get("data")
        if isinstance(nested, dict):
            return _coerce_rows(nested)
    raise ValueError("QS subject payload must be a JSON array or an object containing rows/items/data")


def _ensure_qs_source(cur: object) -> int:
    cur.execute(
        """
        INSERT INTO warehouse.ranking_source (
            source_code,
            source_name,
            source_version,
            metadata
        ) VALUES ('QS', 'QS World University Rankings', 'subject-phase-2', '{}'::jsonb)
        ON CONFLICT (source_code) DO UPDATE SET
            source_name = EXCLUDED.source_name,
            is_active = TRUE
        RETURNING ranking_source_id
        """
    )
    row = cur.fetchone()
    return int(row[0])


def _resolve_canonical(cur: object, *, source_id: int, row: dict[str, Any]) -> tuple[int, int | None] | None:
    source_entity_id = str(row.get("source_entity_id") or "")
    if source_entity_id:
        cur.execute(
            """
            SELECT canonical_university_id, source_mapping_id
            FROM warehouse.source_university_mapping
            WHERE ranking_source_id = %s
              AND source_entity_id = %s
              AND is_active = TRUE
            LIMIT 1
            """,
            (source_id, source_entity_id),
        )
        existing = cur.fetchone()
        if existing:
            return int(existing[0]), int(existing[1])

    normalized_name = str(row["university_name_normalized"])
    canonical_id = _find_canonical_by_name(cur, normalized_name)
    if canonical_id is None:
        return None
    mapping_id = _upsert_source_mapping(cur, source_id=source_id, source_entity_id=source_entity_id, canonical_id=canonical_id)
    return canonical_id, mapping_id


def _find_canonical_by_name(cur: object, normalized_name: str) -> int | None:
    cur.execute(
        """
        SELECT canonical_university_id
        FROM warehouse.canonical_university
        WHERE display_name_normalized = %s
          AND status = 'active'
        ORDER BY canonical_university_id ASC
        LIMIT 1
        """,
        (normalized_name,),
    )
    row = cur.fetchone()
    if row:
        return int(row[0])

    cur.execute(
        """
        SELECT canonical_university_id
        FROM warehouse.university_alias
        WHERE alias_normalized = %s
        ORDER BY is_primary DESC, alias_id ASC
        LIMIT 1
        """,
        (normalized_name,),
    )
    row = cur.fetchone()
    return None if row is None else int(row[0])


def _upsert_source_mapping(cur: object, *, source_id: int, source_entity_id: str, canonical_id: int) -> int | None:
    if not source_entity_id:
        return None
    cur.execute(
        """
        INSERT INTO warehouse.source_university_mapping (
            ranking_source_id,
            source_entity_id,
            canonical_university_id,
            match_method,
            confidence_score,
            metadata,
            last_seen_at
        ) VALUES (%s, %s, %s, 'normalized_exact', 1.0, '{"phase": "subject-ranking-phase-2"}'::jsonb, CURRENT_TIMESTAMP)
        ON CONFLICT (ranking_source_id, source_entity_id) DO UPDATE SET
            canonical_university_id = EXCLUDED.canonical_university_id,
            match_method = EXCLUDED.match_method,
            confidence_score = EXCLUDED.confidence_score,
            is_active = TRUE,
            metadata = EXCLUDED.metadata,
            last_seen_at = CURRENT_TIMESTAMP
        RETURNING source_mapping_id
        """,
        (source_id, source_entity_id, canonical_id),
    )
    row = cur.fetchone()
    return None if row is None else int(row[0])
