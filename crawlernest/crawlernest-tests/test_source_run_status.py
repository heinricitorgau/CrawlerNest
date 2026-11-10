"""THE and ARWU crawl through the crawler package: one status rule, one health check, one run_status.json."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from arwu_crawler import TruncatedTableError
from crawlernest.pipeline.commands import canonical
from crawlernest.run_pipeline import _qs_run_status
from crawlernest_ranking_crawler.sources import ARWUCrawler, RankingSource, THECrawler
from crawlernest_ranking_crawler.sources.base import (
    check_snapshot_rows,
    classify_failure,
    read_run_status,
    run_status_for,
)
from ranking_edition import EditionMismatchError, snapshot_edition_ok
from snapshot_guard import SnapshotRegressionError
from transport import NetworkError

DATABASES = Path(__file__).resolve().parents[1] / "crawlernest-kb" / "databases"


def _rows(count=3, year=2026):
    return [{"id": f"u{i}", "name": f"University {i}", "rank": i + 1, "year": year} for i in range(count)]


def _snapshot(rows, year=2026):
    return {
        "metadata": {"source": "THE", "edition": {"ranking_year": year, "verified": True}},
        "rows": rows,
    }


class _FakeSource(RankingSource):
    name = "THE"

    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error

    def crawl(self, *, year, output_dir):
        if self.error is not None:
            raise self.error
        path = Path(output_dir) / f"the_rankings_{year}.json"
        path.write_text(json.dumps(self.payload), encoding="utf-8")
        return path


class TestStatusRule(unittest.TestCase):
    def test_rule(self):
        cases = [
            ("", 10, "live", "ok"),
            ("", 10, "", "ok"),
            ("", 10, "snapshot", "degraded"),
            ("health_check_failed", 10, "live", "degraded"),
            ("network_error", 0, "live", "failed"),
            ("", 0, "live", "empty"),
        ]
        for classification, count, backing, expected in cases:
            with self.subTest(classification=classification, count=count, backing=backing):
                kwargs = dict(failure_classification=classification, standardized_count=count, run_backing=backing)
                self.assertEqual(expected, run_status_for(**kwargs))
                # QS writes its status with the same rule, not a copy of it.
                self.assertEqual(expected, _qs_run_status(**kwargs))


class TestClassifyFailure(unittest.TestCase):
    def test_typed_crawler_errors(self):
        self.assertEqual("network_error", classify_failure(NetworkError("timed out")))
        self.assertEqual("edition_mismatch", classify_failure(EditionMismatchError("page is 2025")))
        self.assertEqual("truncated_table", classify_failure(TruncatedTableError("30 of 1000 rows")))
        self.assertEqual("snapshot_regression", classify_failure(SnapshotRegressionError("shrank")))

    def test_subclass_keeps_its_parents_classification(self):
        class _Stricter(EditionMismatchError):
            pass

        self.assertEqual("edition_mismatch", classify_failure(_Stricter("x")))

    def test_unknown_is_never_guessed_into_a_network_failure(self):
        self.assertEqual("crawl_failed", classify_failure(RuntimeError("403 challenge page")))
        self.assertEqual("crawl_failed", classify_failure(ValueError("bad json")))


class TestSnapshotHealth(unittest.TestCase):
    def problems(self, rows):
        return check_snapshot_rows(rows, ranking_year=2026)

    def test_healthy(self):
        self.assertEqual([], self.problems(_rows()))

    def test_unranked_rows_are_not_a_problem(self):
        rows = _rows()
        rows[2]["rank"] = None
        self.assertEqual([], self.problems(rows))

    def test_each_problem_is_named(self):
        self.assertEqual(["snapshot has no rows"], self.problems([]))
        self.assertEqual(["snapshot has no rows"], self.problems(None))

        blank = _rows()
        blank[0]["name"] = "  "
        self.assertEqual(["1 row(s) have no name"], self.problems(blank))

        no_id = _rows()
        no_id[1]["id"] = ""
        self.assertEqual(["1 row(s) have no id"], self.problems(no_id))

        repeated = _rows()
        repeated[2]["id"] = repeated[0]["id"]
        self.assertEqual(["1 row(s) repeat an id another row already has"], self.problems(repeated))

        unranked = [{**row, "rank": None} for row in _rows()]
        self.assertEqual(["no row has a rank"], self.problems(unranked))

        self.assertEqual(["rows carry year(s) 2025, not 2026"], self.problems(_rows(year=2025)))
        self.assertIn("1 row(s) are not objects", self.problems(_rows() + ["x"]))

    def test_every_committed_the_and_arwu_snapshot_is_healthy(self):
        files = sorted(DATABASES.glob("the_rankings_20*.json")) + sorted(DATABASES.glob("arwu_rankings_20*.json"))
        self.assertGreaterEqual(len(files), 2, "no committed THE/ARWU snapshots found")
        for path in files:
            with self.subTest(snapshot=path.name):
                payload = json.loads(path.read_text(encoding="utf-8"))
                year = int(path.stem.rsplit("_", 1)[1])
                self.assertEqual([], check_snapshot_rows(payload["rows"], ranking_year=year))


class TestRankingSourceRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)
        self.status_file = self.out / "source_runs" / "THE" / "2026" / "run_status.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_successful_crawl(self):
        run = _FakeSource(_snapshot(_rows())).run(year=2026, output_dir=self.out)
        status = read_run_status(self.status_file)
        self.assertEqual(self.status_file, run.status_path)
        self.assertEqual("ok", status["status"])
        self.assertEqual("", status["failure_classification"])
        self.assertEqual(3, status["standardized_count"])
        self.assertEqual("the_rankings_2026.json", status["snapshot_file"])
        self.assertEqual({"ok": True, "problems": []}, status["health"])
        self.assertTrue(status["run_id"].startswith("the-world-2026-"))
        # The same reader that vets a QS status accepts this one.
        self.assertTrue(snapshot_edition_ok(status, ranking_year=2026))

    def test_status_file_is_not_picked_up_as_a_snapshot(self):
        _FakeSource(_snapshot(_rows())).run(year=2026, output_dir=self.out)
        self.assertEqual(["the_rankings_2026.json"], [p.name for p in self.out.glob("the_rankings_*.json")])

    def test_unhealthy_snapshot_is_degraded_and_still_returned(self):
        rows = _rows()
        rows[1]["id"] = rows[0]["id"]
        run = _FakeSource(_snapshot(rows)).run(year=2026, output_dir=self.out)
        self.assertEqual("degraded", run.status)
        self.assertEqual("health_check_failed", run.record["failure_classification"])
        self.assertEqual(["1 row(s) repeat an id another row already has"], run.summary()["health_problems"])
        self.assertIsNotNone(run.snapshot_path)

    def test_failed_crawl_writes_status_and_reraises_the_same_exception(self):
        error = NetworkError("connection reset")
        with self.assertRaises(NetworkError) as caught:
            _FakeSource(error=error).run(year=2026, output_dir=self.out)
        self.assertIs(error, caught.exception)
        status = read_run_status(self.status_file)
        self.assertEqual("failed", status["status"])
        self.assertEqual("network_error", status["failure_classification"])
        self.assertEqual("NetworkError", status["error_type"])
        self.assertEqual(0, status["standardized_count"])
        self.assertNotIn("last_success", status)

    def test_failed_crawl_keeps_the_run_the_snapshot_on_disk_came_from(self):
        good = _FakeSource(_snapshot(_rows())).run(year=2026, output_dir=self.out)
        for _ in range(2):  # a second failure must not lose it either
            with self.assertRaises(EditionMismatchError):
                _FakeSource(error=EditionMismatchError("page is 2025")).run(year=2026, output_dir=self.out)
            status = read_run_status(self.status_file)
            self.assertEqual("edition_mismatch", status["failure_classification"])
            self.assertEqual(good.record["run_id"], status["last_success"]["run_id"])
            self.assertEqual("the_rankings_2026.json", status["last_success"]["snapshot_file"])

    def test_status_dir_override(self):
        elsewhere = self.out / "elsewhere"
        run = _FakeSource(_snapshot(_rows())).run(year=2026, output_dir=self.out, status_dir=elsewhere)
        self.assertEqual(elsewhere / "THE" / "2026" / "run_status.json", run.status_path)
        self.assertFalse(self.status_file.exists())

    def test_real_sources_call_the_existing_crawlers(self):
        target = self.out / "x.json"
        with mock.patch("the_crawler.crawl_the_rankings", return_value=target) as the:
            self.assertEqual(target, THECrawler().crawl(year=2026, output_dir=self.out))
        the.assert_called_once_with(year=2026, output_dir=self.out)
        with mock.patch("arwu_crawler.crawl_arwu_rankings", return_value=target) as arwu:
            self.assertEqual(target, ARWUCrawler().crawl(year=2026, output_dir=self.out))
        arwu.assert_called_once_with(year=2026, output_dir=self.out)
        self.assertEqual(("THE", "ARWU"), (THECrawler.name, ARWUCrawler.name))


class TestIngestionRecordsStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)
        self.status_file = self.out / "source_runs" / "THE" / "2026" / "run_status.json"

    def tearDown(self):
        self.tmp.cleanup()

    def ingest(self, source):
        return canonical._ingest_world_rankings(
            source, label="the-rankings", ranking_year=2026, output_dir=self.out, status_dir=None,
            pg_host=None, pg_port=5432, pg_database=None, pg_user=None, pg_password=None, skip_seed=True,
        )

    def test_ingested_run_records_what_the_warehouse_took(self):
        taken = mock.Mock(aggregated_row_count=3, matched_count=2, unresolved_count=1)
        with mock.patch.object(canonical, "ingest_rankings_payload", return_value=taken) as ingest:
            summary = self.ingest(_FakeSource(_snapshot(_rows())))
        self.assertEqual("THE", ingest.call_args.kwargs["source"])
        self.assertEqual(3, len(ingest.call_args.kwargs["payload"]))
        self.assertNotIn("batch_id", ingest.call_args.kwargs)
        self.assertEqual("ok", summary["run_status"])
        self.assertEqual(3, summary["rows_crawled"])
        self.assertEqual(str(self.status_file), summary["run_status_file"])
        status = read_run_status(self.status_file)
        self.assertTrue(status["ingested"])
        self.assertEqual((2, 1, 3), (status["matched_count"], status["unresolved_count"], status["aggregated_rows"]))

    def test_ingest_failure_is_failed_and_reraised(self):
        with mock.patch.object(canonical, "ingest_rankings_payload", side_effect=RuntimeError("db down")):
            with self.assertRaisesRegex(RuntimeError, "db down"):
                self.ingest(_FakeSource(_snapshot(_rows())))
        status = read_run_status(self.status_file)
        self.assertEqual("failed", status["status"])
        self.assertEqual("ingest_failed", status["failure_classification"])
        self.assertFalse(status["ingested"])

    def test_crawl_failure_never_reaches_the_warehouse(self):
        with mock.patch.object(canonical, "ingest_rankings_payload") as ingest:
            with self.assertRaises(NetworkError):
                self.ingest(_FakeSource(error=NetworkError("dns")))
        ingest.assert_not_called()
        self.assertEqual("network_error", read_run_status(self.status_file)["failure_classification"])


if __name__ == "__main__":
    unittest.main()
