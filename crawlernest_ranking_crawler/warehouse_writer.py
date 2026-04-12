from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from crawlernest_ranking_crawler.warehouse_mapper import WarehouseReadyRankingRow

try:
    import psycopg2
except ImportError:  # pragma: no cover - optional dependency in local dev
    psycopg2 = None  # type: ignore[assignment]


@dataclass(slots=True)
class WarehouseLandingWriteSummary:
    row_count: int
    inserted_row_count: int
    skipped_existing_row_count: int
    target_location: str
    table_name: str
    mode: str


def load_warehouse_preview_rows(preview_file: Path) -> list[WarehouseReadyRankingRow]:
    payload = json.loads(preview_file.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("warehouse preview artifact must be a JSON array")

    rows: list[WarehouseReadyRankingRow] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("warehouse preview artifact rows must be JSON objects")
        rows.append(
            WarehouseReadyRankingRow(
                university_name=str(item["university_name"]),
                normalized_university_name=str(item["normalized_university_name"]),
                source=str(item["source"]),
                rank=int(item["rank"]),
                year=int(item["year"]),
                source_url=item.get("source_url"),
                extracted_at=datetime.fromisoformat(str(item["extracted_at"])),
                ranking_year=int(item["ranking_year"]),
                universe_type=str(item["universe_type"]),
                universe_key=str(item["universe_key"]),
                canonical_university_id=(
                    None if item.get("canonical_university_id") is None else int(item["canonical_university_id"])
                ),
                entity_resolution_status=str(item.get("entity_resolution_status", "unresolved")),
                source_resolution_status=str(item.get("source_resolution_status", "direct_source_only")),
            )
        )
    return rows


def write_warehouse_landing_rows(
    rows: list[WarehouseReadyRankingRow],
    *,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
    schema_name: str = "warehouse",
    table_name: str = "ranking_records_preview",
) -> WarehouseLandingWriteSummary:
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is required for warehouse landing writes")

    conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        database=pg_database,
        user=pg_user,
        password=pg_password,
    )
    try:
        inserted, skipped_existing = _insert_rows(
            conn,
            schema_name=schema_name,
            table_name=table_name,
            rows=rows,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return WarehouseLandingWriteSummary(
        row_count=len(rows),
        inserted_row_count=inserted,
        skipped_existing_row_count=skipped_existing,
        target_location=f"postgresql://{pg_host}:{pg_port}/{pg_database}#{schema_name}.{table_name}",
        table_name=f"{schema_name}.{table_name}",
        mode="persistent",
    )


def warehouse_landing_summary_to_dict(summary: WarehouseLandingWriteSummary) -> dict[str, object]:
    return asdict(summary)


def preview_row_to_jsonable(row: WarehouseReadyRankingRow) -> dict[str, object]:
    payload = asdict(row)
    extracted_at = payload.get("extracted_at")
    if isinstance(extracted_at, datetime):
        payload["extracted_at"] = extracted_at.isoformat()
    return payload


def _insert_rows(
    conn: "psycopg2.extensions.connection",
    *,
    schema_name: str,
    table_name: str,
    rows: list[WarehouseReadyRankingRow],
) -> tuple[int, int]:
    inserted = 0
    skipped_existing = 0
    with conn.cursor() as cur:
        _ensure_table(cur, schema_name=schema_name, table_name=table_name)
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO {schema_name}.{table_name} (
                    university_name,
                    normalized_university_name,
                    source,
                    rank,
                    year,
                    source_url,
                    extracted_at,
                    ranking_year,
                    universe_type,
                    universe_key,
                    canonical_university_id,
                    entity_resolution_status,
                    source_resolution_status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (
                    normalized_university_name,
                    source,
                    ranking_year,
                    universe_type,
                    universe_key,
                    rank
                ) DO NOTHING
                RETURNING 1
                """,
                (
                    row.university_name,
                    row.normalized_university_name,
                    row.source,
                    row.rank,
                    row.year,
                    row.source_url,
                    row.extracted_at,
                    row.ranking_year,
                    row.universe_type,
                    row.universe_key,
                    row.canonical_university_id,
                    row.entity_resolution_status,
                    row.source_resolution_status,
                ),
            )
            if cur.fetchone() is not None:
                inserted += 1
            else:
                skipped_existing += 1
    return inserted, skipped_existing


def _ensure_table(
    cur: "psycopg2.extensions.cursor",
    *,
    schema_name: str,
    table_name: str,
) -> None:
    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema_name}.{table_name} (
            id BIGSERIAL PRIMARY KEY,
            university_name TEXT NOT NULL,
            normalized_university_name TEXT NOT NULL,
            source TEXT NOT NULL,
            rank INTEGER NOT NULL,
            year INTEGER NOT NULL,
            source_url TEXT NULL,
            extracted_at TIMESTAMPTZ NOT NULL,
            ranking_year INTEGER NOT NULL,
            universe_type TEXT NOT NULL,
            universe_key TEXT NOT NULL,
            canonical_university_id BIGINT NULL,
            entity_resolution_status TEXT NOT NULL,
            source_resolution_status TEXT NOT NULL,
            UNIQUE (
                normalized_university_name,
                source,
                ranking_year,
                universe_type,
                universe_key,
                rank
            )
        )
        """
    )
