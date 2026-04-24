from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


ALLOWED_FIELDS = frozenset(
    {
        "ielts",
        "toefl",
        "gpa",
        "duolingo",
        "deadline",
        "deadline_type",
        "country",
        "program_level",
    }
)
ALLOWED_SOURCE_TYPES = frozenset(
    {
        "official_admission_page",
        "official_program_page",
        "ranking_source",
        "aggregator",
        "manual_seed",
        "unknown",
    }
)
ALLOWED_EXTRACTION_METHODS = frozenset({"rule_based", "heuristic", "manual", "unknown"})
ALLOWED_STATUSES = frozenset({"accepted", "needs_review", "rejected", "conflict"})
ALLOWED_DEADLINE_TYPES = frozenset(
    {"early", "final", "rolling", "international", "domestic", "general", "unknown"}
)

DEFAULT_CONFIDENCE = {
    ("official_admission_page", "rule_based"): 0.85,
    ("official_program_page", "rule_based"): 0.80,
    ("ranking_source", "rule_based"): 0.75,
    ("aggregator", "rule_based"): 0.65,
    ("manual_seed", "manual"): 0.90,
}
UNKNOWN_CONFIDENCE = 0.40
ANOMALY_PENALTY = 0.20
MISSING_EVIDENCE_PENALTY = 0.10
MIN_ANOMALY_CONFIDENCE = 0.10


@dataclass(slots=True)
class AdmissionSignal:
    field: str
    value: Any
    source_url: str | None
    source_type: str
    confidence: float
    extraction_method: str
    evidence_text: str | None
    status: str
    notes: str | None = None


def build_admission_signal(
    *,
    field: str,
    value: Any,
    source_url: str | None = None,
    source_type: str = "unknown",
    extraction_method: str = "unknown",
    evidence_text: str | None = None,
    status: str = "accepted",
    notes: str | None = None,
    confidence: float | None = None,
    anomaly: bool = False,
    validate: bool = True,
) -> AdmissionSignal:
    signal = AdmissionSignal(
        field=field,
        value=value,
        source_url=source_url,
        source_type=source_type,
        confidence=(
            calculate_default_confidence(
                source_type=source_type,
                extraction_method=extraction_method,
                evidence_text=evidence_text,
                anomaly=anomaly,
            )
            if confidence is None
            else clamp_confidence(confidence)
        ),
        extraction_method=extraction_method,
        evidence_text=evidence_text,
        status=status,
        notes=notes,
    )
    if validate:
        validate_admission_signal(signal)
    return signal


def calculate_default_confidence(
    *,
    source_type: str,
    extraction_method: str,
    evidence_text: str | None = None,
    anomaly: bool = False,
) -> float:
    if source_type == "unknown" or extraction_method == "unknown":
        confidence = UNKNOWN_CONFIDENCE
    else:
        confidence = DEFAULT_CONFIDENCE.get((source_type, extraction_method), UNKNOWN_CONFIDENCE)

    if anomaly:
        confidence = max(MIN_ANOMALY_CONFIDENCE, confidence - ANOMALY_PENALTY)
    if not _has_text(evidence_text):
        confidence -= MISSING_EVIDENCE_PENALTY
    return clamp_confidence(confidence)


def validate_admission_signal(signal: AdmissionSignal) -> list[str]:
    errors: list[str] = []

    if signal.field not in ALLOWED_FIELDS:
        errors.append(f"invalid_field:{signal.field}")
    if signal.source_type not in ALLOWED_SOURCE_TYPES:
        errors.append(f"invalid_source_type:{signal.source_type}")
    if signal.extraction_method not in ALLOWED_EXTRACTION_METHODS:
        errors.append(f"invalid_extraction_method:{signal.extraction_method}")
    if signal.status not in ALLOWED_STATUSES:
        errors.append(f"invalid_status:{signal.status}")
    if not isinstance(signal.confidence, (int, float)) or not 0.0 <= signal.confidence <= 1.0:
        errors.append("invalid_confidence")

    if signal.field in ALLOWED_FIELDS:
        errors.extend(_validate_field_value(signal.field, signal.value))

    if errors:
        signal.status = "needs_review"
    return errors


def clamp_confidence(confidence: float) -> float:
    return round(min(1.0, max(0.0, float(confidence))), 4)


def _validate_field_value(field: str, value: Any) -> list[str]:
    if field == "ielts":
        return [] if _number_in_range(value, 0.0, 9.0) else ["invalid_ielts_value"]
    if field == "toefl":
        return [] if _int_in_range(value, 0, 120) else ["invalid_toefl_value"]
    if field == "gpa":
        return [] if _number_in_range(value, 0.0, 4.0) else ["invalid_gpa_value"]
    if field == "duolingo":
        return [] if _int_in_range(value, 0, 160) else ["invalid_duolingo_value"]
    if field == "deadline":
        return [] if _is_iso_date(value) else ["invalid_deadline_value"]
    if field == "deadline_type":
        return [] if value in ALLOWED_DEADLINE_TYPES else ["invalid_deadline_type_value"]
    return []


def _number_in_range(value: Any, minimum: float, maximum: float) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return minimum <= float(value) <= maximum


def _int_in_range(value: Any, minimum: int, maximum: int) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, float) and value.is_integer():
        parsed = int(value)
    else:
        return False
    return minimum <= parsed <= maximum


def _is_iso_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _has_text(value: str | None) -> bool:
    return isinstance(value, str) and bool(value.strip())
