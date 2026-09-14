from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from crawlernest_admission_crawler.models import (
    DEGREE_LEVELS,
    FETCH_LIVE,
    FETCH_MODES,
    UNKNOWN_DEGREE_LEVEL,
)
from crawlernest_admission_crawler.source_identity import admission_source_entity_id

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
MIN_DUOLINGO = 10
MAX_DUOLINGO = 160
MIN_GPA = 0.0
MAX_GPA = 4.0
VALID_DEGREE_LEVELS = frozenset({*DEGREE_LEVELS, UNKNOWN_DEGREE_LEVEL})


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

            # Checked here as well as by ck_admission_record_ranges, so a bad
            # value is reported against its staging line rather than aborting
            # an ingest halfway with a constraint violation.
            if payload.get("duolingo_requirement") is not None:
                duolingo = _as_int(payload.get("duolingo_requirement"))
                if duolingo is None or duolingo < MIN_DUOLINGO or duolingo > MAX_DUOLINGO:
                    row_errors.append("invalid_duolingo_requirement")

            if payload.get("gpa_requirement") is not None:
                gpa = _as_float(payload.get("gpa_requirement"))
                if gpa is None or gpa < MIN_GPA or gpa > MAX_GPA:
                    row_errors.append("invalid_gpa_requirement")

            if payload.get("degree_level") is not None:
                if payload.get("degree_level") not in VALID_DEGREE_LEVELS:
                    row_errors.append("invalid_degree_level")

            if payload.get("application_deadline") is not None:
                deadline = payload.get("application_deadline")
                if not isinstance(deadline, str):
                    row_errors.append("invalid_application_deadline")
                else:
                    try:
                        date.fromisoformat(deadline)
                    except ValueError:
                        row_errors.append("invalid_application_deadline_isoformat")

            row_errors.extend(_fetch_errors(payload))

            if row_errors:
                invalid_row_count += 1
                _maybe_add_sample(error_samples, line_number, row_errors, payload)
                continue

            # Matches uq_admission_record_source_entity. Keying on
            # normalized_university_name, as this used to, both rejected rows
            # the warehouse would happily hold and changed shape whenever the
            # resolver changed its mind about a name.
            dedupe_key = (
                admission_source_entity_id(source_url),
                str(payload.get("degree_level") or UNKNOWN_DEGREE_LEVEL),
            )
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


def _fetch_errors(payload: dict[str, Any]) -> list[str]:
    """Fetch provenance, checked at the staging gate.

    ck_admission_record_fetch would refuse a live row with no time, but only at
    the very end, with no line number. A naive timestamp it would accept, and
    TIMESTAMPTZ would read it in the session's zone -- so the fetch date the
    stale-data caveat prints could be off by a day with nothing failing.
    """
    errors: list[str] = []
    fetch_mode = payload.get("fetch_mode")
    if fetch_mode is not None and fetch_mode not in FETCH_MODES:
        errors.append("invalid_fetch_mode")

    fetched_at = payload.get("fetched_at")
    if fetched_at is not None:
        parsed = None
        if isinstance(fetched_at, str) and fetched_at.strip():
            try:
                parsed = datetime.fromisoformat(fetched_at)
            except ValueError:
                pass
        if parsed is None:
            errors.append("invalid_fetched_at_isoformat")
        elif parsed.utcoffset() is None:
            errors.append("fetched_at_missing_timezone")

    if fetch_mode == FETCH_LIVE and fetched_at is None:
        errors.append("live_fetch_missing_fetched_at")
    return errors


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
