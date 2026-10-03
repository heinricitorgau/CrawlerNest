from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from crawlernest_ranking_crawler.trust_layer import RankingTrust, build_trust_from_aggregated


@dataclass(slots=True)
class AggregationExplain:
    sources: dict
    aggregated_rank: float
    source_count: int
    std_deviation: float
    aggregation_method: str


@dataclass(slots=True)
class RankingExplain:
    aggregation: AggregationExplain
    trust: RankingTrust


def build_explain(row: Any) -> RankingExplain:
    sources = _get_sources(row)
    aggregation = AggregationExplain(
        sources=sources,
        aggregated_rank=round(_safe_float(_get_field(row, "aggregated_rank"), default=0.0), 6),
        source_count=_safe_int(_get_field(row, "source_count"), default=0),
        std_deviation=round(_safe_float(_get_field(row, "std_deviation"), default=0.0), 6),
        aggregation_method=str(_get_field(row, "aggregation_method") or ""),
    )
    trust = build_trust_from_aggregated(row)
    return RankingExplain(aggregation=aggregation, trust=trust)


def _get_sources(row: Any) -> dict[str, Any]:
    raw_sources = _get_field(row, "sources") or {}
    if isinstance(raw_sources, dict):
        return dict(sorted(raw_sources.items()))
    return {}


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
