import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = REPO_ROOT / "crawlernest-core"
JOBS_DIR = REPO_ROOT / "crawlernest-jobs"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))
if str(JOBS_DIR) not in sys.path:
    sys.path.insert(0, str(JOBS_DIR))

from multi_source import MultiSourceRankingPipeline  # noqa: E402
from qs_universe_registry import QS_GLOBAL, get_qs_universe_spec  # noqa: E402


class FakeResolver:
    def resolve_batch(self, records):
        return []


class FakeMultiSourceRepository:
    def upsert_ranking_sources(self, sources):
        return {}

    def upsert_source_university_mappings(self, unified_rows, source_id_map):
        return None

    def upsert_ranking_records(self, unified_rows, source_id_map):
        return None

    def log_missing_entities(self, raw_rows, unified_rows):
        return None

    def log_merge_diagnostics(self, diagnostics, batch_id=None):
        return None

    def log_ingestion(self, source_code, diagnostics, inserted_count, updated_count, batch_id=None):
        return None

    def fetch_ranking_inputs(self, years, ranking_type="world"):
        return []


class FakeAggregationRepository:
    def __init__(self) -> None:
        self.created_runs = 0

    def create_aggregation_run(self, year, universe_type, universe_key, config, input_record_count, run_label=None, notes=None):
        self.created_runs += 1
        return self.created_runs

    def upsert_source_weight_config(self, config):
        return None

    def upsert_aggregated_rankings(self, run_id, outputs):
        return None

    def finish_aggregation_run(self, run_id, output_record_count, status="finished"):
        return None


class TestQSUniverseInvariants(unittest.TestCase):
    def _load_rows(self, universe_type: str, universe_key: str) -> list[dict]:
        path = (
            REPO_ROOT
            / "crawlernest-kb"
            / "qs_universes"
            / "2026"
            / universe_type
            / universe_key
            / "standardized_rows.json"
        )
        return json.loads(path.read_text(encoding="utf-8"))

    def test_region_rows_have_region_universe_metadata(self):
        rows = self._load_rows("region", "europe")
        self.assertGreater(len(rows), 0)
        for row in rows:
            self.assertEqual(row["universe_type"], "region")
            self.assertEqual(row["universe_key"], "europe")
            self.assertEqual(row["ranking_year"], 2026)
            self.assertTrue(row["university_name"])
            self.assertIsNotNone(row["rank"])

    def test_subject_rows_have_subject_universe_metadata(self):
        rows = self._load_rows("subject", "computer-science")
        self.assertGreater(len(rows), 0)
        for row in rows:
            self.assertEqual(row["universe_type"], "subject")
            self.assertEqual(row["universe_key"], "computer-science")
            self.assertEqual(row["ranking_year"], 2026)
            self.assertTrue(row["university_name"])
            self.assertIsNotNone(row["rank"])

    def test_qs_universes_are_allowed_to_materialize_their_own_aggregation_truth(self):
        self.assertTrue(QS_GLOBAL.enable_aggregation)
        self.assertTrue(get_qs_universe_spec("region", "europe").enable_aggregation)
        self.assertTrue(get_qs_universe_spec("subject", "computer-science").enable_aggregation)

    def test_non_global_pipeline_run_can_skip_aggregation(self):
        aggregation_repo = FakeAggregationRepository()
        pipeline = MultiSourceRankingPipeline(
            resolver=FakeResolver(),
            multi_source_repo=FakeMultiSourceRepository(),
            aggregation_repo=aggregation_repo,
        )
        summary = pipeline.ingest_records(
            [],
            ranking_type="subject:computer-science",
            enable_aggregation=False,
        )
        self.assertEqual(summary.aggregated_row_count, 0)
        self.assertEqual(summary.years_aggregated, [])
        self.assertEqual(aggregation_repo.created_runs, 0)


if __name__ == "__main__":
    unittest.main()
