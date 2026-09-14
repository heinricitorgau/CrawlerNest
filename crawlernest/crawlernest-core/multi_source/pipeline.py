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
from .reviews import MappingReviewApplication, apply_mapping_reviews, refuse_reappeared_reviews
from .types import StandardizedRankingRecord, UnifiedRankingRecord

logger = logging.getLogger("MultiSourceRankingPipeline")

#: A batch that would keep less than this share of an edition's existing rows is
#: refused. Real editions move by a few percent; the QS 2026 table and its
#: predecessor differ by one row in 1,504.
MIN_RETAINED_RATIO = 0.9


class ShrinkingBatchError(RuntimeError):
    """A batch would prune most of an edition it only partly re-crawled."""

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
    run_id: str | None = None
    rows_written: int = 0
    rows_updated: int = 0
    years_aggregated: list[int] = field(default_factory=list)
    aggregated_row_count: int = 0
    # A human override that nobody can see is worse than no override at all.
    mapping_reviews: dict[str, object] = field(default_factory=dict)


class MultiSourceRankingPipeline:
    def _refuse_shrinking_batch(
        self,
        unified_rows: Sequence[UnifiedRankingRecord],
        source_id_map: dict[str, int],
        ranking_type: str,
    ) -> None:
        incoming: dict[tuple[str, int], int] = {}
        for row in unified_rows:
            if row.canonical_university_id is None or str(row.ranking_type or "world").lower() != ranking_type.lower():
                continue
            key = (row.source, int(row.year))
            incoming[key] = incoming.get(key, 0) + 1
        for (source_code, year), count in sorted(incoming.items()):
            existing = self.multi_source_repo.count_ranking_records(
                ranking_source_id=source_id_map[source_code], ranking_year=year, ranking_type=ranking_type
            )
            if existing and count < existing * MIN_RETAINED_RATIO:
                raise ShrinkingBatchError(
                    f"{source_code} {year} {ranking_type}: this batch resolves {count} rows but the "
                    f"warehouse holds {existing}; ingesting it would prune {existing - count}. "
                    "Re-crawl the whole edition, or pass allow_shrink=True if the edition really shrank."
                )

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
        enable_aggregation: bool = True,
        allow_shrink: bool = False,
    ) -> MultiSourceIngestionSummary:
        """Resolve, write and (with a batch_id) prune one batch.

        ``allow_shrink`` lifts the guard below for a deliberate replacement by a
        smaller edition. Without it a batch that would prune more than
        ``1 - MIN_RETAINED_RATIO`` of an edition's existing rows is refused before
        any write: the prune deletes every row the batch did not carry, so a
        ``run --limit 30`` against a held edition used to reduce it to 30 rows.
        """
        raw_rows = list(standardized_records)
        if not raw_rows:
            return MultiSourceIngestionSummary(
                standardized_count=0,
                unified_count=0,
                matched_count=0,
                unresolved_count=0,
                duplicate_input_count=0,
                by_source_count={},
                run_id=batch_id,
                rows_written=0,
                rows_updated=0,
                years_aggregated=[],
                aggregated_row_count=0,
            )

        unified_rows, diagnostics = integrate_sources(raw_rows, resolver=self.resolver)
        source_defs = self._collect_source_defs(raw_rows)
        source_id_map = self.multi_source_repo.upsert_ranking_sources(source_defs)

        # Human decisions outrank the resolver, and have to be applied here:
        # before the mapping upsert, whose ON CONFLICT would overwrite them, and
        # before the ranking_record upsert, which is what actually credits a
        # source to a university. Applied any later and a decision is both
        # transient and ineffective.
        reviews = self.multi_source_repo.load_mapping_reviews(sorted(source_id_map))
        unified_rows, review_application = apply_mapping_reviews(unified_rows, reviews)

        # A decision that did not apply because its entity came back under a new
        # source_entity_id stops the run here, before the first warehouse write.
        # Ingesting past it would re-credit rejected false matches with no error.
        refuse_reappeared_reviews(
            reviews,
            review_application,
            ((row.source, row.source_entity_id, row.university_name) for row in raw_rows),
        )
        if review_application.unapplied_reviews:
            # Not refused: the entity is simply absent from this batch (a partial
            # run, a universe that does not contain it, a source that dropped it),
            # so nothing is misattributed. Logged so it is never quiet either.
            logger.warning(
                "%s standing mapping review(s) had no row in this batch and were not applied: %s%s",
                len(review_application.unapplied_reviews),
                ", ".join(f"{code}:{eid}" for code, eid in review_application.unapplied_reviews[:5]),
                " ..." if len(review_application.unapplied_reviews) > 5 else "",
            )
        if review_application.applied:
            logger.info(
                "applied %s human mapping reviews (confirmed=%s remapped=%s rejected=%s)",
                review_application.applied,
                review_application.confirmed,
                review_application.remapped,
                review_application.rejected,
            )

        if batch_id and not allow_shrink:
            self._refuse_shrinking_batch(unified_rows, source_id_map, ranking_type)

        self.multi_source_repo.upsert_source_university_mappings(unified_rows, source_id_map)
        if review_application.rejected_keys:
            self.multi_source_repo.deactivate_rejected_mappings(
                review_application.rejected_keys, source_id_map
            )
        rows_written = self.multi_source_repo.upsert_ranking_records(
            unified_rows,
            source_id_map,
            run_id=batch_id,
        )

        # Re-ingesting a corrected or larger payload must replace what the
        # source published, not merge with what it published last time. Without
        # this, a university that drops out of the payload keeps its old rank
        # indefinitely, and downstream nothing distinguishes it from one the
        # source still ranks.
        #
        # Needs a batch_id to be safe: with no run id to compare against, every
        # row would look superseded.
        superseded_removed = 0
        if batch_id:
            for source_code, ranking_source_id in sorted(source_id_map.items()):
                years_for_source = {
                    int(row.year)
                    for row in unified_rows
                    if row.source == source_code
                    and row.canonical_university_id is not None
                    and str(row.ranking_type or "world").lower() == ranking_type.lower()
                }
                for year in sorted(years_for_source):
                    superseded_removed += self.multi_source_repo.prune_superseded_records(
                        ranking_source_id=ranking_source_id,
                        ranking_year=year,
                        ranking_type=ranking_type,
                        run_id=batch_id,
                    )

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
        aggregated_row_count = 0
        aggregated_years: list[int] = []
        if enable_aggregation:
            aggregated_row_count = self._refresh_aggregations(years, ranking_type=ranking_type, run_label_prefix=run_label_prefix)
            aggregated_years = years

        matched_count = sum(1 for row in unified_rows if row.canonical_university_id is not None)
        summary = MultiSourceIngestionSummary(
            standardized_count=len(raw_rows),
            unified_count=len(unified_rows),
            matched_count=matched_count,
            unresolved_count=len(unified_rows) - matched_count,
            duplicate_input_count=duplicate_input_count,
            by_source_count=dict(diagnostics.by_source_count),
            run_id=batch_id,
            rows_written=rows_written,
            rows_updated=0,
            years_aggregated=aggregated_years,
            aggregated_row_count=aggregated_row_count,
            mapping_reviews=review_application.to_dict(),
        )
        universe_counts: dict[tuple[int, str, str], int] = {}
        for row in unified_rows:
            if row.canonical_university_id is None:
                continue
            key = (
                int(row.year),
                str(getattr(row, "universe_type", "global")),
                str(getattr(row, "universe_key", "global")),
            )
            universe_counts[key] = universe_counts.get(key, 0) + 1
        for (year, universe_type, universe_key), count in sorted(universe_counts.items()):
            logger.info(
                "[INGEST] run_id=%s rows_written=%s rows_updated=%s year=%s universe=%s/%s",
                batch_id,
                count,
                0,
                year,
                universe_type,
                universe_key,
            )
        logger.info(
            "Multi-source ingestion complete: run_id=%s rows=%s rows_written=%s matched=%s unresolved=%s duplicates=%s years=%s aggregated_rows=%s",
            summary.run_id,
            summary.standardized_count,
            summary.rows_written,
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
        grouped_inputs: dict[tuple[int, str, str], list[RankingRecordInput]] = {}
        grouped_outputs: dict[tuple[int, str, str], list] = {}
        for row in records:
            grouped_inputs.setdefault((row.year, row.universe_type, row.universe_key), []).append(row)
        for row in outputs:
            grouped_outputs.setdefault((row.year, row.universe_type, row.universe_key), []).append(row)

        for (year, universe_type, universe_key), year_outputs in sorted(grouped_outputs.items()):
            year_inputs = grouped_inputs.get((year, universe_type, universe_key), [])
            run_id = self.aggregation_repo.create_aggregation_run(
                year=year,
                universe_type=universe_type,
                universe_key=universe_key,
                config=self.aggregation_config,
                input_record_count=len(year_inputs),
                run_label=f"{run_label_prefix}_{year}_{universe_type}_{universe_key}",
                notes=f"Refreshed from warehouse.ranking_record ({ranking_type}, {universe_type}:{universe_key})",
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
            universe_type=str(getattr(row, "universe_type", "global")),
            universe_key=str(getattr(row, "universe_key", "global")),
            rank=row.rank,
            score=row.score,
            metadata_json=dict(row.metadata or {}),
        )
        for row in rows
        if row.canonical_university_id is not None
    ]
