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
from ranking_aggregation import RankingRecordInput  # noqa: E402


class FakeMultiSourceRepository:
    def __init__(self) -> None:
        self.unified_rows = []
        self.raw_rows = []

    def upsert_ranking_sources(self, sources):
        return {code: idx for idx, (code, _, _) in enumerate(sources, start=1)}

    def upsert_source_university_mappings(self, unified_rows, source_id_map):
        self.unified_rows.extend(unified_rows)

    def upsert_ranking_records(self, unified_rows, source_id_map):
        self.unified_rows = [row for row in self.unified_rows if row.canonical_university_id is not None]

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
        self.outputs_by_year = {}
        self.run_id = 0

    def create_aggregation_run(self, year, config, input_record_count, run_label=None, notes=None):
        self.run_id += 1
        return self.run_id

    def upsert_source_weight_config(self, config):
        return None

    def upsert_aggregated_rankings(self, run_id, outputs):
        if outputs:
            self.outputs_by_year[outputs[0].year] = list(outputs)

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

        outputs = agg_repo.outputs_by_year[2026]
        by_canonical = {row.canonical_university_id: row for row in outputs}
        oxford = by_canonical[1]

        self.assertEqual(oxford.source_ranks, {"QS": 3.0, "THE": 1.0, "ARWU": 7.0})
        self.assertAlmostEqual(oxford.source_normalized_scores["QS"] or 0.0, 99.866667, places=6)
        self.assertAlmostEqual(oxford.source_normalized_scores["THE"] or 0.0, 100.0, places=6)
        self.assertAlmostEqual(oxford.source_normalized_scores["ARWU"] or 0.0, 99.4, places=6)
        self.assertAlmostEqual(oxford.composite_score or 0.0, 99.796667, places=6)
        self.assertEqual(oxford.display_rank, 1)

        cambridge = by_canonical[2]
        self.assertTrue((oxford.composite_score or 0.0) > (cambridge.composite_score or 0.0))
        self.assertEqual(cambridge.display_rank, 2)
        self.assertEqual(len(repo.unified_rows), 6)
        self.assertEqual({row.source for row in repo.unified_rows}, {"QS", "THE", "ARWU"})


if __name__ == "__main__":
    unittest.main()
