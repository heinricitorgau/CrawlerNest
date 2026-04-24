from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from crawlernest_admission_crawler.signals import AdmissionSignal, clamp_confidence


SOURCE_TYPE_PRIORITY = {
    "official_admission_page": 0,
    "official_program_page": 1,
    "ranking_source": 2,
    "aggregator": 3,
    "unknown": 4,
}
EXTRACTION_METHOD_PRIORITY = {
    "rule_based": 0,
    "heuristic": 1,
    "manual": 2,
    "unknown": 3,
}
NUMERIC_CONSERVATIVE_FIELDS = frozenset({"ielts", "gpa"})
DEADLINE_TYPES = ("early", "final", "rolling")
COUNTRY_ALIASES = {
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "united kingdom": "United Kingdom",
    "great britain": "United Kingdom",
    "usa": "United States",
    "u.s.": "United States",
    "us": "United States",
    "united states": "United States",
    "united states of america": "United States",
}


@dataclass(slots=True)
class ResolvedAdmissionField:
    field: str
    resolved_value: Any | None
    confidence: float
    source_count: int
    sources: list[str]
    resolution_reason: str
    status: str


def resolve_admission_signals(
    signals: list[AdmissionSignal],
) -> dict[str, ResolvedAdmissionField]:
    grouped_signals: dict[str, list[AdmissionSignal]] = defaultdict(list)
    for signal in signals:
        grouped_signals[signal.field].append(signal)

    return {
        field: resolve_admission_field(field, field_signals)
        for field, field_signals in grouped_signals.items()
    }


def resolve_admission_field(
    field: str,
    signals: list[AdmissionSignal],
) -> ResolvedAdmissionField:
    usable_signals = [signal for signal in signals if signal.status != "rejected"]
    if not usable_signals:
        return ResolvedAdmissionField(
            field=field,
            resolved_value=None,
            confidence=0.0,
            source_count=0,
            sources=[],
            resolution_reason="no usable signals found",
            status="missing",
        )

    ranked_signals = sorted(usable_signals, key=_ranking_key)
    sources = _sources(ranked_signals)
    source_count = len(ranked_signals)
    confidence = _aggregate_confidence(ranked_signals)
    value_result = _resolve_value(field, ranked_signals)

    if all(signal.status == "needs_review" for signal in ranked_signals):
        status = "needs_review"
    elif value_result["conflict"]:
        status = "conflict"
    else:
        status = "accepted"

    return ResolvedAdmissionField(
        field=field,
        resolved_value=value_result["value"],
        confidence=confidence,
        source_count=source_count,
        sources=sources,
        resolution_reason=value_result["reason"],
        status=status,
    )


def _resolve_value(field: str, ranked_signals: list[AdmissionSignal]) -> dict[str, Any]:
    values = [_canonical_value(field, signal.value) for signal in ranked_signals]
    unique_values = _unique_values(values)
    if len(unique_values) == 1:
        return {
            "value": unique_values[0],
            "reason": "all usable signals agree",
            "conflict": False,
        }

    if field in NUMERIC_CONSERVATIVE_FIELDS and all(_is_number(value) for value in values):
        return {
            "value": max(values),
            "reason": "multiple values found, using highest requirement",
            "conflict": False,
        }

    if field == "deadline":
        return {
            "value": _merge_deadlines(ranked_signals),
            "reason": "multiple deadline values found, grouped by deadline_type",
            "conflict": False,
        }

    return {
        "value": _canonical_value(field, ranked_signals[0].value),
        "reason": "conflicting non-numeric values found, using best-ranked signal",
        "conflict": True,
    }


def _merge_deadlines(ranked_signals: list[AdmissionSignal]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for signal in ranked_signals:
        deadline_type, deadline_value = _deadline_parts(signal)
        if deadline_type not in DEADLINE_TYPES or deadline_value is None:
            continue
        if deadline_type not in merged:
            merged[deadline_type] = deadline_value
    return merged


def _deadline_parts(signal: AdmissionSignal) -> tuple[str, str | None]:
    value = signal.value
    if isinstance(value, dict):
        deadline_type = value.get("deadline_type") or value.get("type")
        deadline_value = value.get("deadline") or value.get("value")
        if isinstance(deadline_type, str) and isinstance(deadline_value, str):
            return deadline_type.lower(), deadline_value

    for candidate in (signal.notes, signal.evidence_text):
        deadline_type = _extract_deadline_type(candidate)
        if deadline_type is not None:
            return deadline_type, value if isinstance(value, str) else None

    return "unknown", value if isinstance(value, str) else None


def _extract_deadline_type(text: str | None) -> str | None:
    if not isinstance(text, str):
        return None
    normalized = text.strip().lower()
    if normalized in DEADLINE_TYPES:
        return normalized
    for deadline_type in DEADLINE_TYPES:
        if f"deadline_type={deadline_type}" in normalized or f"deadline_type:{deadline_type}" in normalized:
            return deadline_type
        if deadline_type in normalized:
            return deadline_type
    return None


def _aggregate_confidence(signals: list[AdmissionSignal]) -> float:
    max_confidence = max(signal.confidence for signal in signals)
    count_bonus = min(0.05 * (len(signals) - 1), 0.15)
    return clamp_confidence(max_confidence + count_bonus)


def _ranking_key(signal: AdmissionSignal) -> tuple[float, int, int]:
    return (
        -signal.confidence,
        SOURCE_TYPE_PRIORITY.get(signal.source_type, SOURCE_TYPE_PRIORITY["unknown"]),
        EXTRACTION_METHOD_PRIORITY.get(
            signal.extraction_method,
            EXTRACTION_METHOD_PRIORITY["unknown"],
        ),
    )


def _canonical_value(field: str, value: Any) -> Any:
    if field == "country" and isinstance(value, str):
        normalized = value.strip().lower()
        return COUNTRY_ALIASES.get(normalized, value.strip())
    return value


def _unique_values(values: list[Any]) -> list[Any]:
    unique: list[Any] = []
    for value in values:
        if value not in unique:
            unique.append(value)
    return unique


def _sources(signals: list[AdmissionSignal]) -> list[str]:
    return [signal.source_url for signal in signals if signal.source_url is not None]


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
