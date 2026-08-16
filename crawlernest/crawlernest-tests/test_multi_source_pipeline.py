import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = REPO_ROOT / "crawlernest-core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from entity_resolution import CanonicalProfile, EntityResolver  # noqa: E402
from multi_source import MultiSourceRankingPipeline  # noqa: E402
from multi_source.adapters import ARWUAdapter, THEAdapter  # noqa: E402
from multi_source.types import StandardizedRankingRecord  # noqa: E402
from ranking_aggregation import RankingAggregator, RankingRecordInput  # noqa: E402


class FakeMultiSourceRepository:
    def __init__(self) -> None:
        self.unified_rows = []
        self.raw_rows = []
        #: (ranking_source_id, ranking_year, ranking_type, run_id) per prune call.
        #: Recorded rather than ignored so a pipeline that stops pruning, or
        #: prunes the wrong scope, is visible here and not only in the
        #: PostgreSQL tests.
        self.prune_calls = []

    def upsert_ranking_sources(self, sources):
        return {code: idx for idx, (code, _, _) in enumerate(sources, start=1)}

    def upsert_source_university_mappings(self, unified_rows, source_id_map):
        self.unified_rows.extend(unified_rows)

    def upsert_ranking_records(self, unified_rows, source_id_map, run_id=None):
        self.unified_rows = [row for row in self.unified_rows if row.canonical_university_id is not None]

    def prune_superseded_records(self, *, ranking_source_id, ranking_year, ranking_type, run_id):
        self.prune_calls.append((ranking_source_id, ranking_year, ranking_type, run_id))
        return 0

    def log_missing_entities(self, raw_rows, unified_rows):
        self.raw_rows.extend(raw_rows)

    def log_merge_diagnostics(self, diagnostics, batch_id=None):
        return None

    def log_ingestion(self, source_code, diagnostics, inserted_count, updated_count, batch_id=None):
        return None

    def fetch_ranking_inputs(self, years, ranking_type="world"):
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
            for row in self.unified_rows
            if row.canonical_university_id is not None
            and row.year in set(years)
            and str(row.ranking_type or "").lower() == ranking_type.lower()
        ]


class FakeAggregationRepository:
    def __init__(self) -> None:
        self.outputs_by_scope = {}
        self.run_id = 0

    def create_aggregation_run(self, year, universe_type, universe_key, config, input_record_count, run_label=None, notes=None):
        self.run_id += 1
        return self.run_id

    def upsert_source_weight_config(self, config):
        return None

    def upsert_aggregated_rankings(self, run_id, outputs):
        if outputs:
            key = (outputs[0].year, outputs[0].universe_type, outputs[0].universe_key)
            self.outputs_by_scope[key] = list(outputs)

    def finish_aggregation_run(self, run_id, output_record_count, status="finished"):
        return None


class TestMultiSourcePipeline(unittest.TestCase):
    def test_the_and_arwu_adapters_standardize_expected_fields(self):
        the_rows = THEAdapter(default_year=2026).adapt(
            [
                {
                    "id": "the:oxford",
                    "institution": "University of Oxford",
                    "country": "United Kingdom",
                    "rank_position": "1",
                    "scores": {"overall": "98.5"},
                    "profile_url": "https://example.test/the/oxford",
                }
            ]
        )
        arwu_rows = ARWUAdapter(default_year=2026).adapt(
            [
                {
                    "id": "arwu:oxford",
                    "university_name": "University of Oxford",
                    "country": "United Kingdom",
                    "overall_rank": "7",
                    "total_score": None,
                    "url": "https://example.test/arwu/oxford",
                }
            ]
        )

        self.assertEqual(the_rows[0].source, "THE")
        self.assertEqual(the_rows[0].university_name, "University of Oxford")
        self.assertEqual(the_rows[0].rank, 1)
        self.assertAlmostEqual(the_rows[0].score or 0.0, 98.5)
        self.assertEqual(arwu_rows[0].source, "ARWU")
        self.assertEqual(arwu_rows[0].rank, 7)
        self.assertIsNone(arwu_rows[0].score)

    def test_the_adapter_reads_scores_overall_field(self):
        the_rows = THEAdapter(default_year=2026).adapt(
            [
                {
                    "id": "the:oxford",
                    "name": "University of Oxford",
                    "country": "United Kingdom",
                    "rank": "1",
                    "scores_overall": "98.2",
                }
            ]
        )

        self.assertEqual(1, len(the_rows))
        self.assertAlmostEqual(the_rows[0].score or 0.0, 98.2)

    def test_pipeline_aggregates_qs_the_arwu_without_overwrite(self):
        resolver = EntityResolver(
            [
                CanonicalProfile(
                    canonical_university_id=1,
                    display_name="University of Oxford",
                    country_hint="united kingdom",
                    aliases=("Oxford",),
                ),
                CanonicalProfile(
                    canonical_university_id=2,
                    display_name="University of Cambridge",
                    country_hint="united kingdom",
                    aliases=("Cambridge",),
                ),
            ]
        )
        repo = FakeMultiSourceRepository()
        agg_repo = FakeAggregationRepository()
        pipeline = MultiSourceRankingPipeline(resolver=resolver, multi_source_repo=repo, aggregation_repo=agg_repo)

        records = [
            StandardizedRankingRecord("QS", "qs:oxford", "University of Oxford", "United Kingdom", 2026, "world", 3, None),
            StandardizedRankingRecord("THE", "the:oxford", "Oxford", "United Kingdom", 2026, "world", 1, None),
            StandardizedRankingRecord("ARWU", "arwu:oxford", "University of Oxford", "United Kingdom", 2026, "world", 7, None),
            StandardizedRankingRecord("QS", "qs:cambridge", "University of Cambridge", "United Kingdom", 2026, "world", 8, None),
            StandardizedRankingRecord("THE", "the:cambridge", "Cambridge", "United Kingdom", 2026, "world", 4, None),
            StandardizedRankingRecord("ARWU", "arwu:cambridge", "University of Cambridge", "United Kingdom", 2026, "world", 9, None),
        ]

        summary = pipeline.ingest_records(records, batch_id="unit-test", run_label_prefix="unit-test")

        self.assertEqual(summary.standardized_count, 6)
        self.assertEqual(summary.matched_count, 6)
        self.assertEqual(summary.unresolved_count, 0)
        self.assertEqual(summary.by_source_count, {"QS": 2, "THE": 2, "ARWU": 2})
        self.assertEqual(summary.years_aggregated, [2026])
        self.assertEqual(summary.aggregated_row_count, 2)

        outputs = agg_repo.outputs_by_scope[(2026, "global", "global")]
        by_canonical = {row.canonical_university_id: row for row in outputs}
        oxford = by_canonical[1]

        self.assertEqual(oxford.source_ranks, {"QS": 3.0, "THE": 1.0, "ARWU": 7.0})
        self.assertAlmostEqual(oxford.source_normalized_scores["QS"] or 0.0, 0.333333, places=6)
        self.assertAlmostEqual(oxford.source_normalized_scores["THE"] or 0.0, 1.0, places=6)
        self.assertAlmostEqual(oxford.source_normalized_scores["ARWU"] or 0.0, 0.142857, places=6)
        # All three sources present, so the full weighting applies with no
        # renormalisation: 0.222 * 1/3 + 0.654 * 1/1 + 0.124 * 1/7. This is the
        # only case here where the weights move the composite at all -- with QS
        # alone the renormalisation cancels them out.
        self.assertAlmostEqual(oxford.composite_score or 0.0, 0.745714, places=6)
        self.assertEqual(oxford.display_rank, 1)

        cambridge = by_canonical[2]
        self.assertTrue((oxford.composite_score or 0.0) > (cambridge.composite_score or 0.0))
        self.assertEqual(cambridge.display_rank, 2)
        self.assertEqual(len(repo.unified_rows), 6)
        self.assertEqual({row.source for row in repo.unified_rows}, {"QS", "THE", "ARWU"})

    def test_aggregation_isolated_per_universe(self):
        records = [
            RankingRecordInput(
                canonical_university_id=1,
                source="QS",
                year=2026,
                universe_type="global",
                universe_key="global",
                rank=3,
            ),
            RankingRecordInput(
                canonical_university_id=1,
                source="QS",
                year=2026,
                universe_type="region",
                universe_key="europe",
                rank=1,
            ),
            RankingRecordInput(
                canonical_university_id=2,
                source="QS",
                year=2026,
                universe_type="region",
                universe_key="europe",
                rank=2,
            ),
        ]

        outputs = RankingAggregator().aggregate_rankings(records)

        self.assertEqual(3, len(outputs))
        grouped = {(row.universe_type, row.universe_key): [] for row in outputs}
        for row in outputs:
            grouped.setdefault((row.universe_type, row.universe_key), []).append(row)

        self.assertEqual(1, len(grouped[("global", "global")]))
        self.assertEqual(2, len(grouped[("region", "europe")]))
        europe_ranks = sorted(row.display_rank for row in grouped[("region", "europe")])
        self.assertEqual([1, 2], europe_ranks)

    def test_high_confidence_aliases_merge_same_university_across_sources(self):
        resolver = EntityResolver(
            [
                CanonicalProfile(
                    canonical_university_id=10,
                    display_name="Ludwig-Maximilians-Universität München",
                    country_hint="germany",
                ),
            ]
        )
        repo = FakeMultiSourceRepository()
        agg_repo = FakeAggregationRepository()
        pipeline = MultiSourceRankingPipeline(resolver=resolver, multi_source_repo=repo, aggregation_repo=agg_repo)

        records = [
            StandardizedRankingRecord("QS", "qs:lmu", "Ludwig-Maximilians-Universität München", "Germany", 2026, "world", 59, 71.6),
            StandardizedRankingRecord("THE", "the:lmu", "LMU Munich", "Germany", 2026, "world", 34, None),
        ]

        summary = pipeline.ingest_records(records, batch_id="alias-merge-test", run_label_prefix="alias-merge-test")

        self.assertEqual(2, summary.matched_count)
        outputs = agg_repo.outputs_by_scope[(2026, "global", "global")]
        self.assertEqual(1, len(outputs))
        lmu = outputs[0]
        self.assertEqual(10, lmu.canonical_university_id)
        self.assertEqual({"QS": 59.0, "THE": 34.0, "ARWU": None}, lmu.source_ranks)
        self.assertEqual({"QS": 0.222, "THE": 0.654, "ARWU": None}, lmu.source_weights_used)
        # (0.222 * 1/59 + 0.654 * 1/34) / (0.222 + 0.654)
        self.assertAlmostEqual(lmu.composite_score or 0.0, 0.02625, places=5)
        self.assertEqual(2, lmu.metadata["available_rank_count"])


class TestSupersededRecordsArePruned(unittest.TestCase):
    """The pipeline must ask for a prune, scoped to what it just wrote.

    The database behaviour is covered by test_ingest_idempotency. This covers the
    wiring, which is the part that silently stops happening when somebody
    reorders the ingest steps.
    """

    def _pipeline(self, repo):
        resolver = EntityResolver(
            [
                CanonicalProfile(
                    canonical_university_id=1,
                    display_name="A University",
                    country_hint="taiwan",
                    aliases=(),
                )
            ]
        )
        return MultiSourceRankingPipeline(
            resolver=resolver,
            multi_source_repo=repo,
            aggregation_repo=FakeAggregationRepository(),
        )

    def test_prune_is_requested_per_source_for_the_year_ingested(self):
        repo = FakeMultiSourceRepository()
        self._pipeline(repo).ingest_records(
            [
                StandardizedRankingRecord(
                    "QS", "qs:a", "A University", "Taiwan", 2026, "world", 1, 90.0
                ),
                StandardizedRankingRecord(
                    "THE", "the:a", "A University", "Taiwan", 2026, "world", 2, 88.0
                ),
            ],
            batch_id="prune-test",
            run_label_prefix="prune-test",
        )

        scopes = {(year, rtype, run) for _, year, rtype, run in repo.prune_calls}
        self.assertEqual(
            scopes,
            {(2026, "world", "prune-test")},
            f"expected one scope per ingested year; got {repo.prune_calls}",
        )
        self.assertEqual(
            len({sid for sid, _, _, _ in repo.prune_calls}),
            2,
            "each source must be pruned under its own id, or one source's run id "
            f"would delete another source's rows: {repo.prune_calls}",
        )

    def test_no_batch_id_means_no_prune(self):
        """With no run id to compare against, every row would look superseded."""
        repo = FakeMultiSourceRepository()
        self._pipeline(repo).ingest_records(
            [
                StandardizedRankingRecord(
                    "QS", "qs:a", "A University", "Taiwan", 2026, "world", 1, 90.0
                )
            ],
            batch_id=None,
            run_label_prefix="prune-test",
        )

        self.assertEqual(
            repo.prune_calls, [], "pruning without a run id would empty the table"
        )


if __name__ == "__main__":
    unittest.main()
