from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from crawlernest_admission_crawler.models import WarehouseReadyAdmissionRow
from crawlernest_admission_crawler.postgres_driver import get_psycopg2


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
                    raw_payload
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
            "raw_payload": row[7],
        }
        for row in result_rows
    ]


def map_staging_rows_to_warehouse_rows(rows: list[dict[str, Any]]) -> list[WarehouseReadyAdmissionRow]:
    mapped_rows: list[WarehouseReadyAdmissionRow] = []
    for row in rows:
        mapped_rows.append(
            WarehouseReadyAdmissionRow(
                university_name=str(row["university_name"]),
                normalized_university_name=str(row["normalized_university_name"]),
                source_url=str(row["source_url"]),
                country=_optional_text(row.get("country")),
                ielts_requirement=_optional_float(row.get("ielts_requirement")),
                toefl_requirement=_optional_int(row.get("toefl_requirement")),
                extracted_at=datetime.fromisoformat(str(row["extracted_at"])),
                canonical_university_id=None,
                entity_resolution_status="unresolved",
                raw_payload=row.get("raw_payload") if isinstance(row.get("raw_payload"), dict) else None,
            )
        )
    return mapped_rows


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


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
