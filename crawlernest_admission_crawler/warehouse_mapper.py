from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from crawlernest_admission_crawler.models import (
    FETCH_LIVE,
    FETCH_MODES,
    FETCH_UNKNOWN,
    INTAKE_UNKNOWN,
    INTAKE_YEAR_BASES,
    REQUIREMENT_SCOPES,
    SCOPE_FACULTY,
    SCOPE_PROGRAMME,
    SCOPE_UNSPECIFIED,
    UNKNOWN_DEGREE_LEVEL,
    WarehouseReadyAdmissionRow,
)
from crawlernest_admission_crawler.postgres_driver import get_psycopg2
from crawlernest_admission_crawler.source_identity import admission_source_entity_id


def load_staging_rows_from_jsonl(staging_file: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with staging_file.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def load_staging_rows_from_postgres(
    *,
    table_name: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> list[dict[str, Any]]:
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
            fetch_columns = (
                "fetched_at, fetch_mode"
                if _has_fetch_columns(cur, table_name)
                # A staging table no ingest has touched since the crawler began
                # recording fetches: none of its rows had one recorded.
                else f"NULL::timestamptz AS fetched_at, '{FETCH_UNKNOWN}' AS fetch_mode"
            )
            cur.execute(
                f"""
                SELECT
                    university_name,
                    normalized_university_name,
                    source_url,
                    country,
                    ielts_requirement,
                    toefl_requirement,
                    extracted_at,
                    duolingo_requirement,
                    gpa_requirement,
                    application_deadline,
                    degree_level,
                    raw_payload,
                    {fetch_columns}
                FROM {table_name}
                ORDER BY normalized_university_name ASC, source_url ASC
                """
            )
            result_rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "university_name": row[0],
            "normalized_university_name": row[1],
            "source_url": row[2],
            "country": row[3],
            "ielts_requirement": row[4],
            "toefl_requirement": row[5],
            "extracted_at": row[6].isoformat() if hasattr(row[6], "isoformat") else str(row[6]),
            "duolingo_requirement": row[7],
            "gpa_requirement": row[8],
            "application_deadline": row[9].isoformat() if hasattr(row[9], "isoformat") else row[9],
            "degree_level": row[10],
            "raw_payload": row[11],
            "fetched_at": row[12].isoformat() if row[12] is not None else None,
            "fetch_mode": row[13],
        }
        for row in result_rows
    ]


def _has_fetch_columns(cur: Any, table_name: str) -> bool:
    cur.execute(
        """
        SELECT COUNT(*) FROM information_schema.columns
        WHERE table_name = %s
          AND table_schema = COALESCE(%s, current_schema())
          AND column_name IN ('fetched_at', 'fetch_mode')
        """,
        (table_name.rsplit(".", 1)[-1], table_name.rsplit(".", 1)[0] if "." in table_name else None),
    )
    return int(cur.fetchone()[0]) == 2


def requirement_scope_for(
    *,
    faculty: str | None,
    programme_name: str | None,
    declared: str | None = None,
) -> str:
    """The scope a row's requirement applies to.

    Derived from the names when the source did not declare it: a programme name
    makes it a programme requirement, a faculty alone a faculty one, neither
    ``unspecified``. ``institution_minimum`` is never derived -- that a number is
    a floor for every programme is something the page has to say.

    A declared scope that contradicts the names is refused here, with the names
    in the message, rather than by the database's CHECK with none.
    """
    derived = SCOPE_PROGRAMME if programme_name else SCOPE_FACULTY if faculty else SCOPE_UNSPECIFIED
    if not declared:
        return derived
    if declared not in REQUIREMENT_SCOPES:
        raise ValueError(f"requirement_scope {declared!r} is not one of {', '.join(REQUIREMENT_SCOPES)}")
    names_required = {SCOPE_PROGRAMME: bool(programme_name), SCOPE_FACULTY: bool(faculty) and not programme_name}
    if declared in names_required and not names_required[declared]:
        raise ValueError(
            f"requirement_scope {declared!r} does not fit faculty={faculty!r} programme_name={programme_name!r}"
        )
    if declared not in names_required and (faculty or programme_name):
        raise ValueError(
            f"requirement_scope {declared!r} applies to no single programme, but the row names "
            f"faculty={faculty!r} programme_name={programme_name!r}"
        )
    return declared


def map_staging_rows_to_warehouse_rows(rows: list[dict[str, Any]]) -> list[WarehouseReadyAdmissionRow]:
    mapped_rows: list[WarehouseReadyAdmissionRow] = []
    for row in rows:
        faculty = _optional_text(row.get("faculty"))
        programme_name = _optional_text(row.get("programme_name"))
        intake_year = _optional_int(row.get("intake_year"))
        mapped_rows.append(
            WarehouseReadyAdmissionRow(
                university_name=str(row["university_name"]),
                normalized_university_name=str(row["normalized_university_name"]),
                source_url=str(row["source_url"]),
                country=_optional_text(row.get("country")),
                ielts_requirement=_optional_float(row.get("ielts_requirement")),
                toefl_requirement=_optional_int(row.get("toefl_requirement")),
                extracted_at=datetime.fromisoformat(str(row["extracted_at"])),
                source_entity_id=admission_source_entity_id(str(row["source_url"])),
                duolingo_requirement=_optional_int(row.get("duolingo_requirement")),
                gpa_requirement=_optional_float(row.get("gpa_requirement")),
                application_deadline=_optional_date(row.get("application_deadline")),
                degree_level=str(row.get("degree_level") or UNKNOWN_DEGREE_LEVEL),
                canonical_university_id=None,
                entity_resolution_status="unresolved",
                raw_payload=row.get("raw_payload") if isinstance(row.get("raw_payload"), dict) else None,
                faculty=faculty,
                programme_name=programme_name,
                requirement_scope=requirement_scope_for(
                    faculty=faculty,
                    programme_name=programme_name,
                    declared=_optional_text(row.get("requirement_scope")),
                ),
                intake_year=intake_year,
                intake_year_basis=intake_year_basis_for(intake_year, row.get("intake_year_basis")),
                fetched_at=fetched_at_for(row),
                fetch_mode=fetch_mode_for(row),
            )
        )
    return mapped_rows


def fetched_at_for(row: dict[str, Any]) -> datetime | None:
    fetched_at = _optional_datetime(row.get("fetched_at"))
    if fetched_at is not None and fetched_at.utcoffset() is None:
        # The jsonl and preview paths skip validator.py; TIMESTAMPTZ would read
        # this in the session's zone and shift the caveat's fetch date.
        raise ValueError(f"fetched_at {row.get('fetched_at')!r} has no timezone")
    return fetched_at


def fetch_mode_for(row: dict[str, Any]) -> str:
    mode = _choice(row.get("fetch_mode"), allowed=FETCH_MODES, default=FETCH_UNKNOWN, field_name="fetch_mode")
    if mode == FETCH_LIVE and row.get("fetched_at") in (None, ""):
        raise ValueError("fetch_mode 'live' needs fetched_at: a live fetch always has a time")
    return mode


def intake_year_basis_for(intake_year: int | None, declared: Any) -> str:
    """How the intake year was established; a year never travels without one.

    A year with no stated basis is refused rather than defaulted: whether the
    page said "2026 entry" or someone worked it out from a deadline is exactly
    the difference a reader has to be told.
    """
    basis = _choice(declared, allowed=INTAKE_YEAR_BASES, default=INTAKE_UNKNOWN, field_name="intake_year_basis")
    if intake_year is None and basis != INTAKE_UNKNOWN:
        raise ValueError(f"intake_year_basis {basis!r} given without an intake_year")
    if intake_year is not None and basis == INTAKE_UNKNOWN:
        raise ValueError(
            f"intake_year {intake_year} needs intake_year_basis (page_stated or deadline_inferred)"
        )
    return basis


def _choice(value: Any, *, allowed: tuple[str, ...], default: str, field_name: str) -> str:
    text = _optional_text(value)
    if text is None:
        return default
    if text not in allowed:
        raise ValueError(f"{field_name} {text!r} is not one of {', '.join(allowed)}")
    return text


def _optional_datetime(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    text = str(value).strip()
    return datetime.fromisoformat(text) if text else None


def warehouse_rows_to_jsonable(rows: list[WarehouseReadyAdmissionRow]) -> list[dict[str, Any]]:
    return [_to_jsonable(asdict(row)) for row in rows]


def write_warehouse_preview(rows: list[WarehouseReadyAdmissionRow], output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(warehouse_rows_to_jsonable(rows), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    return date.fromisoformat(text)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
