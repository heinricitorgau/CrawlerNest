from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from entity_resolution import EntityResolver
from ranking_aggregation import RankingRecordInput, RankingAggregator, default_aggregation_config
from ranking_aggregation.config import AggregationConfig
from ranking_aggregation.repository import RankingAggregationRepository

from .integrator import IntegrationDiagnostics, integrate_sources
from .repository import MultiSourceRepository
from .types import StandardizedRankingRecord, UnifiedRankingRecord

logger = logging.getLogger("MultiSourceRankingPipeline")

SOURCE_NAME_MAP = {
    "QS": "QS World University Rankings",
    "THE": "Times Higher Education World University Rankings",
    "ARWU": "Academic Ranking of World Universities",
}


@dataclass(frozen=True)
class MultiSourceIngestionSummary:
    standardized_count: int
    unified_count: int
    matched_count: int
    unresolved_count: int
    duplicate_input_count: int
    by_source_count: dict[str, int]
    years_aggregated: list[int] = field(default_factory=list)
    aggregated_row_count: int = 0


class MultiSourceRankingPipeline:
    def __init__(
        self,
        resolver: EntityResolver,
        multi_source_repo: MultiSourceRepository,
        aggregation_repo: RankingAggregationRepository,
        aggregation_config: AggregationConfig | None = None,
    ):
        self.resolver = resolver
        self.multi_source_repo = multi_source_repo
        self.aggregation_repo = aggregation_repo
        self.aggregation_config = aggregation_config or default_aggregation_config()
        self.aggregator = RankingAggregator(config=self.aggregation_config)

    def ingest_records(
        self,
        standardized_records: Iterable[StandardizedRankingRecord],
        *,
        batch_id: str | None = None,
        run_label_prefix: str = "multi_source_ingest",
        ranking_type: str = "world",
    ) -> MultiSourceIngestionSummary:
        raw_rows = list(standardized_records)
        if not raw_rows:
            return MultiSourceIngestionSummary(
                standardized_count=0,
                unified_count=0,
                matched_count=0,
                unresolved_count=0,
                duplicate_input_count=0,
                by_source_count={},
                years_aggregated=[],
                aggregated_row_count=0,
            )

        unified_rows, diagnostics = integrate_sources(raw_rows, resolver=self.resolver)
        source_defs = self._collect_source_defs(raw_rows)
        source_id_map = self.multi_source_repo.upsert_ranking_sources(source_defs)
        self.multi_source_repo.upsert_source_university_mappings(unified_rows, source_id_map)
        self.multi_source_repo.upsert_ranking_records(unified_rows, source_id_map)
        self.multi_source_repo.log_missing_entities(raw_rows, unified_rows)
        self.multi_source_repo.log_merge_diagnostics(diagnostics, batch_id=batch_id)

        duplicate_input_count = self._count_duplicates(raw_rows)
        for source_code, source_count in sorted(diagnostics.by_source_count.items()):
            source_unresolved = sum(1 for row in unified_rows if row.source == source_code and row.canonical_university_id is None)
            source_matched = source_count - source_unresolved
            self.multi_source_repo.log_ingestion(
                source_code,
                IntegrationDiagnostics(
                    total_records=source_count,
                    unique_resolution_keys=diagnostics.unique_resolution_keys,
                    duplicate_resolution_saves=diagnostics.duplicate_resolution_saves + duplicate_input_count,
                    unresolved_count=source_unresolved,
                    by_source_count={source_code: source_count},
                ),
                inserted_count=source_matched,
                updated_count=0,
                batch_id=batch_id,
            )

        years = sorted(
            {
                int(row.year)
                for row in unified_rows
                if row.canonical_university_id is not None and str(row.ranking_type or "world").lower() == ranking_type.lower()
            }
        )
        aggregated_row_count = self._refresh_aggregations(years, ranking_type=ranking_type, run_label_prefix=run_label_prefix)

        matched_count = sum(1 for row in unified_rows if row.canonical_university_id is not None)
        summary = MultiSourceIngestionSummary(
            standardized_count=len(raw_rows),
            unified_count=len(unified_rows),
            matched_count=matched_count,
            unresolved_count=len(unified_rows) - matched_count,
            duplicate_input_count=duplicate_input_count,
            by_source_count=dict(diagnostics.by_source_count),
            years_aggregated=years,
            aggregated_row_count=aggregated_row_count,
        )
        logger.info(
            "Multi-source ingestion complete: rows=%s matched=%s unresolved=%s duplicates=%s years=%s aggregated_rows=%s",
            summary.standardized_count,
            summary.matched_count,
            summary.unresolved_count,
            summary.duplicate_input_count,
            summary.years_aggregated,
            summary.aggregated_row_count,
        )
        return summary

    def _refresh_aggregations(self, years: Sequence[int], *, ranking_type: str, run_label_prefix: str) -> int:
        if not years:
            return 0
        records = self.multi_source_repo.fetch_ranking_inputs(list(years), ranking_type=ranking_type)
        outputs = self.aggregator.aggregate_rankings(records)
        if not outputs:
            return 0
        total = 0
        for year in years:
            year_inputs = [row for row in records if row.year == year]
            year_outputs = [row for row in outputs if row.year == year]
            run_id = self.aggregation_repo.create_aggregation_run(
                year=year,
                config=self.aggregation_config,
                input_record_count=len(year_inputs),
                run_label=f"{run_label_prefix}_{year}",
                notes=f"Refreshed from warehouse.ranking_record ({ranking_type})",
            )
            self.aggregation_repo.upsert_source_weight_config(self.aggregation_config)
            self.aggregation_repo.upsert_aggregated_rankings(run_id, year_outputs)
            self.aggregation_repo.finish_aggregation_run(run_id, len(year_outputs), status="finished")
            total += len(year_outputs)
        return total

    def _collect_source_defs(self, rows: list[StandardizedRankingRecord]) -> list[tuple[str, str, str | None]]:
        seen: set[str] = set()
        out: list[tuple[str, str, str | None]] = []
        for row in rows:
            source_code = str(row.source or "").strip().upper()
            if not source_code or source_code in seen:
                continue
            seen.add(source_code)
            out.append((source_code, SOURCE_NAME_MAP.get(source_code, source_code), row.source_version))
        return out

    def _count_duplicates(self, rows: list[StandardizedRankingRecord]) -> int:
        seen: set[tuple[str, str, int, str]] = set()
        duplicates = 0
        for row in rows:
            key = (
                str(row.source or "").strip().upper(),
                str(row.source_entity_id or "").strip(),
                int(row.ranking_year),
                str(row.ranking_type or "world").strip().lower(),
            )
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
        return duplicates


def build_aggregation_inputs(rows: Iterable[UnifiedRankingRecord]) -> list[RankingRecordInput]:
    return [
        RankingRecordInput(
            canonical_university_id=int(row.canonical_university_id),
            source=row.source,
            year=int(row.year),
            rank=row.rank,
            score=row.score,
            metadata_json=dict(row.metadata or {}),
        )
        for row in rows
        if row.canonical_university_id is not None
    ]
