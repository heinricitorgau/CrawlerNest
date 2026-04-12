from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from crawlernest_ranking_crawler.normalize import NormalizedRankingRow
from crawlernest_ranking_crawler.validator import validate_ranking_staging_rows
from crawlernest_ranking_crawler.write_adapter import (
    PostgresRankingWriteAdapter,
    RankingWriteAdapter,
    SQLiteRankingWriteAdapter,
)


@dataclass(slots=True)
class RankingStagingIngestSummary:
    staging_file: str
    write_target: str
    target_location: str
    table_name: str
    total_rows: int
    valid_row_count: int
    invalid_row_count: int
    duplicate_row_count: int
    inserted_row_count: int
    skipped_existing_row_count: int
    mode: str
    error_samples: list[dict[str, Any]]
    duplicate_samples: list[dict[str, Any]]


def ingest_ranking_staging_file(
    staging_file: Path,
    sqlite_db_path: Path,
    *,
    allow_partial: bool = False,
    write_target: str = "sqlite",
    postgres_log_path: Path | None = None,
) -> RankingStagingIngestSummary:
    validation = validate_ranking_staging_rows(staging_file)
    summary = validation.summary

    if not allow_partial and (summary.invalid_row_count > 0 or summary.duplicate_row_count > 0):
        raise ValueError(
            "staging validation failed; rerun after fixing invalid/duplicate rows or pass allow_partial=True"
        )

    adapter = build_write_adapter(
        write_target=write_target,
        sqlite_db_path=sqlite_db_path,
        postgres_log_path=postgres_log_path,
    )
    write_result = adapter.write_rows(_coerce_valid_rows(validation.valid_rows))

    return RankingStagingIngestSummary(
        staging_file=str(staging_file),
        write_target=write_result.write_target,
        target_location=write_result.target_location,
        table_name=write_result.table_name,
        total_rows=summary.total_rows,
        valid_row_count=summary.valid_row_count,
        invalid_row_count=summary.invalid_row_count,
        duplicate_row_count=summary.duplicate_row_count,
        inserted_row_count=write_result.inserted_row_count,
        skipped_existing_row_count=write_result.skipped_existing_row_count,
        mode="partial" if allow_partial else "strict",
        error_samples=summary.error_samples,
        duplicate_samples=summary.duplicate_samples,
    )


def ingest_summary_to_dict(summary: RankingStagingIngestSummary) -> dict[str, Any]:
    return asdict(summary)

def build_write_adapter(
    *,
    write_target: str,
    sqlite_db_path: Path,
    postgres_log_path: Path | None,
) -> RankingWriteAdapter:
    if write_target == "sqlite":
        return SQLiteRankingWriteAdapter(sqlite_db_path=sqlite_db_path)
    if write_target == "postgres":
        target_path = postgres_log_path or sqlite_db_path.with_name("postgres_ranking_write_requests.jsonl")
        return PostgresRankingWriteAdapter(request_log_path=target_path)
    raise ValueError(f"Unsupported write target: {write_target}")


def _coerce_valid_rows(rows: list[dict[str, Any]]) -> list[NormalizedRankingRow]:
    coerced_rows: list[NormalizedRankingRow] = []
    for row in rows:
        coerced_rows.append(
            NormalizedRankingRow(
                university_name=str(row["university_name"]),
                normalized_university_name=str(row["normalized_university_name"]),
                source=str(row["source"]),
                rank=int(row["rank"]),
                year=int(row["year"]),
                source_url=row.get("source_url"),
                extracted_at=datetime.fromisoformat(str(row["extracted_at"])),
            )
        )
    return coerced_rows
