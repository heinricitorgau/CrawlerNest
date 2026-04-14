from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = (
    "university_name",
    "normalized_university_name",
    "source_url",
    "extracted_at",
)

MAX_SAMPLE_COUNT = 5
MIN_IELTS = 0.0
MAX_IELTS = 9.0
MIN_TOEFL = 0
MAX_TOEFL = 120


@dataclass(slots=True)
class AdmissionStagingValidationSummary:
    staging_file: str
    total_rows: int
    valid_row_count: int
    invalid_row_count: int
    duplicate_row_count: int
    error_samples: list[dict[str, Any]]
    duplicate_samples: list[dict[str, Any]]


@dataclass(slots=True)
class AdmissionStagingValidationResult:
    summary: AdmissionStagingValidationSummary
    valid_rows: list[dict[str, Any]]


def validate_admission_staging_file(staging_file: Path) -> AdmissionStagingValidationSummary:
    return validate_admission_staging_rows(staging_file).summary


def validate_admission_staging_rows(staging_file: Path) -> AdmissionStagingValidationResult:
    total_rows = 0
    valid_row_count = 0
    invalid_row_count = 0
    duplicate_row_count = 0
    error_samples: list[dict[str, Any]] = []
    duplicate_samples: list[dict[str, Any]] = []
    valid_rows: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()

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
                _maybe_add_sample(error_samples, line_number, [f"invalid_json: {exc.msg}"], raw_line.strip())
                continue

            if not isinstance(payload, dict):
                invalid_row_count += 1
                _maybe_add_sample(error_samples, line_number, ["row_must_be_json_object"], payload)
                continue

            for field_name in REQUIRED_FIELDS:
                if field_name not in payload:
                    row_errors.append(f"missing_required_field:{field_name}")

            university_name = _as_non_empty_string(payload.get("university_name"))
            normalized_university_name = _as_non_empty_string(payload.get("normalized_university_name"))
            source_url = _as_non_empty_string(payload.get("source_url"))

            if university_name is None:
                row_errors.append("invalid_university_name")
            if normalized_university_name is None:
                row_errors.append("invalid_normalized_university_name")
            if source_url is None:
                row_errors.append("invalid_source_url")

            extracted_at = payload.get("extracted_at")
            if not isinstance(extracted_at, str) or not extracted_at.strip():
                row_errors.append("invalid_extracted_at")
            else:
                try:
                    datetime.fromisoformat(extracted_at)
                except ValueError:
                    row_errors.append("invalid_extracted_at_isoformat")

            if payload.get("ielts_requirement") is not None:
                ielts = _as_float(payload.get("ielts_requirement"))
                if ielts is None or ielts < MIN_IELTS or ielts > MAX_IELTS:
                    row_errors.append("invalid_ielts_requirement")

            if payload.get("toefl_requirement") is not None:
                toefl = _as_int(payload.get("toefl_requirement"))
                if toefl is None or toefl < MIN_TOEFL or toefl > MAX_TOEFL:
                    row_errors.append("invalid_toefl_requirement")

            if row_errors:
                invalid_row_count += 1
                _maybe_add_sample(error_samples, line_number, row_errors, payload)
                continue

            dedupe_key = (normalized_university_name, source_url)
            if dedupe_key in seen_keys:
                duplicate_row_count += 1
                _maybe_add_sample(duplicate_samples, line_number, ["duplicate_row"], payload)
                continue

            seen_keys.add(dedupe_key)
            valid_row_count += 1
            valid_rows.append(payload)

    summary = AdmissionStagingValidationSummary(
        staging_file=str(staging_file),
        total_rows=total_rows,
        valid_row_count=valid_row_count,
        invalid_row_count=invalid_row_count,
        duplicate_row_count=duplicate_row_count,
        error_samples=error_samples,
        duplicate_samples=duplicate_samples,
    )
    return AdmissionStagingValidationResult(summary=summary, valid_rows=valid_rows)


def summary_to_dict(summary: AdmissionStagingValidationSummary) -> dict[str, Any]:
    return asdict(summary)


def _maybe_add_sample(
    samples: list[dict[str, Any]],
    line_number: int,
    errors: list[str],
    payload: Any,
) -> None:
    if len(samples) >= MAX_SAMPLE_COUNT:
        return
    samples.append(
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
    return stripped or None


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _as_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = float(value.strip())
        except ValueError:
            return None
        if parsed.is_integer():
            return int(parsed)
    return None
