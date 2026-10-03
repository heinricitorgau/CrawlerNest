from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RankingTrust:
    trust_score: float
    trust_level: str
    coverage_score: float
    consistency_score: float
    std_deviation: float
    notes: list[str]


def build_trust_from_aggregated(row: Any) -> RankingTrust:
    source_count = _safe_int(_get_field(row, "source_count"), default=0)
    std_deviation = _safe_float(_get_field(row, "std_deviation"), default=0.0)

    coverage_score = max(0.0, min(float(source_count) / 3.0, 1.0))
    consistency_score = _build_consistency_score(std_deviation)
    trust_score = (coverage_score * 0.6 + (consistency_score / 100.0) * 0.4) * 100.0

    if trust_score >= 80.0:
        trust_level = "high"
    elif trust_score >= 50.0:
        trust_level = "medium"
    else:
        trust_level = "low"

    notes: list[str] = []
    if source_count >= 3:
        notes.append("Three ranking sources available.")
    elif source_count == 2:
        notes.append("Two ranking sources available.")
    elif source_count == 1:
        notes.append("Only one ranking source available.")

    if std_deviation == 0:
        notes.append("Ranking sources show strong agreement.")
    elif std_deviation < 5:
        notes.append("Ranking sources show strong agreement.")
    elif std_deviation < 15:
        notes.append("Ranking sources show moderate agreement.")
    else:
        notes.append("Large disagreement across sources.")

    return RankingTrust(
        trust_score=round(trust_score, 6),
        trust_level=trust_level,
        coverage_score=round(coverage_score, 6),
        consistency_score=float(consistency_score),
        std_deviation=round(std_deviation, 6),
        notes=notes,
    )


def _build_consistency_score(std_deviation: float) -> float:
    if std_deviation == 0:
        return 100.0
    if std_deviation < 5:
        return 80.0
    if std_deviation < 15:
        return 50.0
    return 20.0


def _get_field(row: Any, field_name: str) -> Any:
    if isinstance(row, dict):
        return row.get(field_name)
    return getattr(row, field_name)


def _safe_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
