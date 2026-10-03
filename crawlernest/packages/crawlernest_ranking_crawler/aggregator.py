from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from statistics import mean, pstdev
from typing import Any


@dataclass(slots=True)
class AggregatedRankingRow:
    normalized_university_name: str
    ranking_year: int
    aggregated_rank: float
    source_count: int
    std_deviation: float
    aggregation_method: str
    sources: dict[str, int]


def aggregate_rankings(rows: list[Any]) -> list[AggregatedRankingRow]:
    grouped: dict[tuple[str, int], list[Any]] = defaultdict(list)

    for row in rows:
        normalized_university_name = str(_get_field(row, "normalized_university_name")).strip()
        if not normalized_university_name:
            continue
        ranking_year = int(_get_field(row, "ranking_year", fallback_field="year"))
        grouped[(normalized_university_name, ranking_year)].append(row)

    results: list[AggregatedRankingRow] = []
    for (normalized_university_name, ranking_year), group in grouped.items():
        sources: dict[str, int] = {}
        ranks: list[int] = []

        for row in group:
            rank_value = _get_field(row, "rank")
            if rank_value is None:
                continue
            source_name = str(_get_field(row, "source")).strip().upper()
            if not source_name:
                continue
            rank = int(rank_value)
            sources[source_name] = rank
            ranks.append(rank)

        if not ranks:
            continue

        results.append(
            AggregatedRankingRow(
                normalized_university_name=normalized_university_name,
                ranking_year=ranking_year,
                aggregated_rank=float(mean(ranks)),
                source_count=len(ranks),
                std_deviation=float(pstdev(ranks)) if len(ranks) > 1 else 0.0,
                aggregation_method="rank_agg_v1",
                sources=dict(sorted(sources.items())),
            )
        )

    return sorted(results, key=lambda row: (row.ranking_year, row.aggregated_rank, row.normalized_university_name))


def aggregated_rows_to_jsonable(rows: list[AggregatedRankingRow]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for row in rows:
        item = asdict(row)
        item["aggregated_rank"] = round(float(row.aggregated_rank), 6)
        item["std_deviation"] = round(float(row.std_deviation), 6)
        payload.append(item)
    return payload


def _get_field(row: Any, field_name: str, *, fallback_field: str | None = None) -> Any:
    if isinstance(row, dict):
        if field_name in row:
            return row[field_name]
        if fallback_field is not None and fallback_field in row:
            return row[fallback_field]
        raise KeyError(field_name)
    if hasattr(row, field_name):
        return getattr(row, field_name)
    if fallback_field is not None and hasattr(row, fallback_field):
        return getattr(row, fallback_field)
    raise AttributeError(field_name)
