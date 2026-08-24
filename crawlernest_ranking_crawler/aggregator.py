"""The shape a decision-preview row is built from.

This module also held aggregate_rankings(), which grouped warehouse-ready
ranking rows by (normalized name, year) and averaged their ranks. Its only
caller was the ``aggregate-ranking-preview`` command, deleted along with the
rest of the landing chain (see docs/migrations/RANKING_SCHEMA_CONVERGENCE.md).
decision_writer.load_aggregated_rows_from_postgres() now derives these fields
from analytics.aggregated_rankings instead.

Not to be confused with crawlernest/crawlernest-core/ranking_aggregation/,
which is the live weighted aggregation behind analytics.aggregated_rankings.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AggregatedRankingRow:
    normalized_university_name: str
    ranking_year: int
    aggregated_rank: float
    source_count: int
    std_deviation: float
    aggregation_method: str
    sources: dict[str, int]
