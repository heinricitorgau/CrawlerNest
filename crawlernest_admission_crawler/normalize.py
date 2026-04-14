from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Iterable

from crawlernest_admission_crawler.models import AdmissionRecord, NormalizedAdmissionRow

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
                raw_payload=record.raw_payload,
            )
        )
    return normalized_rows


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
