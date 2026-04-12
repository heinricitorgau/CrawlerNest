from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import psycopg2
except ImportError:  # pragma: no cover - optional dependency in local dev
    psycopg2 = None  # type: ignore[assignment]


@dataclass(slots=True)
class WarehouseReadyRankingRow:
    university_name: str
    normalized_university_name: str
    source: str
    rank: int
    year: int
    source_url: str | None
    extracted_at: datetime
    ranking_year: int
    universe_type: str
    universe_key: str
    canonical_university_id: int | None = None
    entity_resolution_status: str = "unresolved"
    source_resolution_status: str = "direct_source_only"


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
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is required for postgres staging preview")

    conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        database=pg_database,
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
                    source,
                    rank,
                    year,
                    source_url,
                    extracted_at
                FROM {table_name}
                ORDER BY year DESC, rank ASC, normalized_university_name ASC
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return [
        {
            "university_name": row[0],
            "normalized_university_name": row[1],
            "source": row[2],
            "rank": row[3],
            "year": row[4],
            "source_url": row[5],
            "extracted_at": row[6].isoformat() if hasattr(row[6], "isoformat") else str(row[6]),
        }
        for row in rows
    ]


def map_staging_rows_to_warehouse_rows(rows: list[dict[str, Any]]) -> list[WarehouseReadyRankingRow]:
    mapped_rows: list[WarehouseReadyRankingRow] = []
    for row in rows:
        extracted_at = datetime.fromisoformat(str(row["extracted_at"]))
        ranking_year = int(row["year"])
        mapped_rows.append(
            WarehouseReadyRankingRow(
                university_name=str(row["university_name"]),
                normalized_university_name=str(row["normalized_university_name"]),
                source=str(row["source"]),
                rank=int(row["rank"]),
                year=ranking_year,
                source_url=row.get("source_url"),
                extracted_at=extracted_at,
                ranking_year=ranking_year,
                universe_type="global",
                universe_key="global",
            )
        )
    return mapped_rows


def warehouse_rows_to_jsonable(rows: list[WarehouseReadyRankingRow]) -> list[dict[str, Any]]:
    return [_to_jsonable(asdict(row)) for row in rows]


def write_warehouse_preview(rows: list[WarehouseReadyRankingRow], output_file: Path) -> None:
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
