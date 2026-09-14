from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import re
from typing import Any, Iterable

from crawlernest_admission_crawler.models import (
    DEGREE_LEVELS,
    UNKNOWN_DEGREE_LEVEL,
    AdmissionRecord,
    NormalizedAdmissionRow,
)

_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(slots=True)
class AdmissionNormalizationSummary:
    input_row_count: int
    output_row_count: int


def normalize_admission_records(records: Iterable[AdmissionRecord]) -> list[NormalizedAdmissionRow]:
    normalized_rows: list[NormalizedAdmissionRow] = []
    for record in records:
        normalized_rows.append(
            NormalizedAdmissionRow(
                university_name=_collapse_whitespace(record.university_name),
                normalized_university_name=normalize_university_name(record.university_name),
                source_url=_collapse_whitespace(record.source_url),
                country=_normalize_optional_text(record.country),
                ielts_requirement=_normalize_ielts(record.ielts_requirement),
                toefl_requirement=_normalize_toefl(record.toefl_requirement),
                extracted_at=_normalize_datetime(record.extracted_at),
                duolingo_requirement=_normalize_duolingo(
                    _prefer(record.duolingo_requirement, record.raw_payload, "duolingo_requirement")
                ),
                gpa_requirement=_normalize_gpa(
                    _prefer(record.gpa_requirement, record.raw_payload, "gpa_requirement")
                ),
                application_deadline=_normalize_deadline(
                    _prefer(record.application_deadline, record.raw_payload, "deadline")
                ),
                degree_level=_normalize_degree_level(
                    _prefer(record.degree_level, record.raw_payload, "degree_level")
                ),
                raw_payload=record.raw_payload,
                fetched_at=record.fetched_at,
                fetch_mode=record.fetch_mode,
            )
        )
    return normalized_rows


def _prefer(explicit: Any, raw_payload: dict[str, Any] | None, key: str) -> Any:
    """Take the field off the record, falling back to raw_payload.

    Crawlers written before these were columns put everything in raw_payload,
    and the sample export still does. Reading both keeps a record from either
    era landing in the same columns.
    """
    if explicit is not None:
        return explicit
    if isinstance(raw_payload, dict):
        return raw_payload.get(key)
    return None


def _normalize_duolingo(value: Any) -> int | None:
    return _bounded_int(value, low=10, high=160)


def _normalize_gpa(value: Any) -> float | None:
    number = _as_float(value)
    if number is None or not (0.0 <= number <= 4.0):
        return None
    return round(number, 2)


def _normalize_deadline(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError:
        # Anything the extractor could not resolve to an ISO date stays in
        # raw_payload rather than being guessed at here.
        return None


def _normalize_degree_level(value: Any) -> str:
    if isinstance(value, str) and value.strip().lower() in DEGREE_LEVELS:
        return value.strip().lower()
    return UNKNOWN_DEGREE_LEVEL


def _bounded_int(value: Any, *, low: int, high: int) -> int | None:
    number = _as_float(value)
    if number is None:
        return None
    as_int = int(number)
    return as_int if low <= as_int <= high else None


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_university_name(name: str) -> str:
    collapsed = _collapse_whitespace(name)
    if not collapsed:
        return ""
    return " ".join(_normalize_token(token) for token in collapsed.split(" "))


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    collapsed = _collapse_whitespace(value)
    return collapsed or None


def _collapse_whitespace(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value.strip())


def _normalize_token(token: str) -> str:
    if token.isupper() and len(token) <= 5:
        return token
    if token.islower() or token.isupper():
        return token.capitalize()
    return token


def _normalize_ielts(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 1)


def _normalize_toefl(value: int | None) -> int | None:
    if value is None:
        return None
    return int(value)


def _normalize_datetime(value: datetime) -> datetime:
    return value
