from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = (
    "university_name",
    "normalized_university_name",
    "source",
    "rank",
    "year",
    "source_url",
    "extracted_at",
)

MIN_REASONABLE_YEAR = 1900
MAX_YEAR_OFFSET = 2
MAX_ERROR_SAMPLES = 10


@dataclass(slots=True)
class RankingStagingValidationSummary:
    staging_file: str
    total_rows: int
    valid_row_count: int
    invalid_row_count: int
    duplicate_row_count: int
    error_samples: list[dict[str, Any]]


def validate_ranking_staging_file(staging_file: Path) -> RankingStagingValidationSummary:
    total_rows = 0
    valid_row_count = 0
    invalid_row_count = 0
    duplicate_row_count = 0
    error_samples: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, int, int]] = set()

    current_year = datetime.now().year
    max_reasonable_year = current_year + MAX_YEAR_OFFSET

    with staging_file.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue

            total_rows += 1
            row_errors: list[str] = []

            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                invalid_row_count += 1
                _maybe_add_error_sample(
                    error_samples,
                    line_number,
                    [f"invalid_json: {exc.msg}"],
                    raw_line.strip(),
                )
                continue

            if not isinstance(payload, dict):
                invalid_row_count += 1
                _maybe_add_error_sample(
                    error_samples,
                    line_number,
                    ["row_must_be_json_object"],
                    payload,
                )
                continue

            for field_name in REQUIRED_FIELDS:
                if field_name not in payload:
                    row_errors.append(f"missing_required_field:{field_name}")

            university_name = _as_non_empty_string(payload.get("university_name"))
            normalized_university_name = _as_non_empty_string(payload.get("normalized_university_name"))
            source = _as_non_empty_string(payload.get("source"))

            if university_name is None:
                row_errors.append("invalid_university_name")
            if normalized_university_name is None:
                row_errors.append("invalid_normalized_university_name")
            if source is None:
                row_errors.append("invalid_source")

            rank = payload.get("rank")
            if not isinstance(rank, int) or rank <= 0:
                row_errors.append("invalid_rank")

            year = payload.get("year")
            if not isinstance(year, int) or year < MIN_REASONABLE_YEAR or year > max_reasonable_year:
                row_errors.append("invalid_year")

            extracted_at = payload.get("extracted_at")
            if not isinstance(extracted_at, str) or not extracted_at.strip():
                row_errors.append("invalid_extracted_at")
            else:
                try:
                    datetime.fromisoformat(extracted_at)
                except ValueError:
                    row_errors.append("invalid_extracted_at_isoformat")

            if row_errors:
                invalid_row_count += 1
                _maybe_add_error_sample(error_samples, line_number, row_errors, payload)
                continue

            dedupe_key = (
                university_name,
                source,
                year,
                rank,
            )
            if dedupe_key in seen_keys:
                duplicate_row_count += 1
                _maybe_add_error_sample(error_samples, line_number, ["duplicate_row"], payload)
                continue

            seen_keys.add(dedupe_key)
            valid_row_count += 1

    return RankingStagingValidationSummary(
        staging_file=str(staging_file),
        total_rows=total_rows,
        valid_row_count=valid_row_count,
        invalid_row_count=invalid_row_count,
        duplicate_row_count=duplicate_row_count,
        error_samples=error_samples,
    )


def summary_to_dict(summary: RankingStagingValidationSummary) -> dict[str, Any]:
    return asdict(summary)


def _maybe_add_error_sample(
    error_samples: list[dict[str, Any]],
    line_number: int,
    errors: list[str],
    payload: Any,
) -> None:
    if len(error_samples) >= MAX_ERROR_SAMPLES:
        return
    error_samples.append(
        {
            "line_number": line_number,
            "errors": errors,
            "payload": payload,
        }
    )


def _as_non_empty_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return stripped
