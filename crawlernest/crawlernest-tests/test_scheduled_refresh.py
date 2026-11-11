"""The scheduler's command: once per source, isolated failures, one run at a time."""

from __future__ import annotations

import fcntl
import json
import tempfile
import unittest
from pathlib import Path

from crawlernest.pipeline.commands.scheduled_refresh import (
    RefreshAlreadyRunning,
    run_scheduled_refresh,
    summarize_history,
)
from crawlernest_ranking_crawler.sources.base import FAILURE_FAMILIES, SourceFailure, failure_family


class TestScheduledRefresh(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.calls: list[tuple[str, int]] = []

    def tearDown(self):
        self.tmp.cleanup()

    def runner(self, source, fail=False):
        def _run(year):
            self.calls.append((source, year))
            if fail:
                raise RuntimeError(f"{source} blocked")
            return {"rows": 10}
        return _run

    def refresh(self, runners, sources=("QS", "THE", "ARWU")):
        return run_scheduled_refresh(
            ranking_year=2026, sources=sources, runners=runners,
            lock_path=self.root / "refresh.lock", status_dir=self.root / "status",
        )

    def test_each_source_runs_once_for_the_edition(self):
        rc = self.refresh({s: self.runner(s) for s in ("QS", "THE", "ARWU")})
        self.assertEqual(0, rc)
        self.assertEqual([("QS", 2026), ("THE", 2026), ("ARWU", 2026)], self.calls)
        status = json.loads((self.root / "status" / "scheduled_refresh_latest.json").read_text())
        self.assertTrue(status["ok"])

    def test_one_failing_source_does_not_stop_the_others_but_fails_the_run(self):
        rc = self.refresh({"QS": self.runner("QS", fail=True), "THE": self.runner("THE"), "ARWU": self.runner("ARWU")})
        self.assertEqual(1, rc)
        self.assertEqual(["QS", "THE", "ARWU"], [s for s, _ in self.calls])
        status = json.loads((self.root / "status" / "scheduled_refresh_latest.json").read_text())
        self.assertEqual([False, True, True], [s["ok"] for s in status["sources"]])
        self.assertIn("QS blocked", status["sources"][0]["error"])

    def test_an_overlapping_run_is_refused(self):
        lock = self.root / "refresh.lock"
        with open(lock, "w") as held:
            fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(RefreshAlreadyRunning):
                self.refresh({"QS": self.runner("QS")}, sources=("QS",))
        self.assertEqual([], self.calls)

    def test_an_unknown_source_is_refused_before_anything_runs(self):
        with self.assertRaises(ValueError):
            self.refresh({"QS": self.runner("QS")}, sources=("QS", "USNEWS"))
        self.assertEqual([], self.calls)


class _Dropped(RuntimeError):
    """Stands in for transport.NetworkError; the scheduler only reads failure_class."""

    failure_class = "network_error"


class _Mismatch(RuntimeError):
    pass


class TestNetworkFailuresAreRetried(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.slept: list[float] = []
        self.now = 0.0

    def tearDown(self):
        self.tmp.cleanup()

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.now += seconds

    def scripted(self, *outcomes):
        """A runner that raises or returns each outcome in turn."""
        script = list(outcomes)
        self.attempts = 0

        def _run(year):
            self.attempts += 1
            item = script.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item
        return _run

    def refresh(self, runner):
        rc = run_scheduled_refresh(
            ranking_year=2026, sources=("THE",), runners={"THE": runner},
            lock_path=self.root / "refresh.lock", status_dir=self.root / "status",
            sleep=self.sleep, clock=lambda: self.now,
        )
        status = json.loads((self.root / "status" / "scheduled_refresh_latest.json").read_text())
        return rc, status["sources"][0]

    def test_network_failure_is_retried_then_succeeds(self):
        rc, src = self.refresh(self.scripted(_Dropped("unreachable"), {"rows": 10}))
        self.assertEqual(0, rc)
        self.assertTrue(src["ok"])
        self.assertEqual([300.0], self.slept)
        self.assertEqual(2, len(src["attempts"]))
        self.assertIn("unreachable", src["attempts"][0]["error"])
        self.assertIsNone(src["attempts"][1]["error"])
        self.assertIsNone(src["failure_class"])

    def test_network_failure_gives_up_after_three_attempts(self):
        rc, src = self.refresh(self.scripted(*[_Dropped("unreachable")] * 3))
        self.assertEqual(1, rc)
        self.assertFalse(src["ok"])
        self.assertEqual([300.0, 900.0], self.slept)
        self.assertEqual(3, len(src["attempts"]))
        self.assertEqual("network_error", src["failure_class"])

    def test_other_failures_are_not_retried(self):
        rc, src = self.refresh(self.scripted(RuntimeError("THE blocked")))
        self.assertEqual(1, rc)
        self.assertEqual([], self.slept)
        self.assertEqual(1, len(src["attempts"]))
        self.assertEqual("RuntimeError", src["failure_class"])
        self.assertIn("THE blocked", src["error"])

    def test_switch_to_non_network_error_stops_retrying(self):
        rc, src = self.refresh(self.scripted(_Dropped("unreachable"), _Mismatch("wrong edition")))
        self.assertEqual(1, rc)
        self.assertEqual([300.0], self.slept)
        self.assertEqual(2, self.attempts)
        self.assertEqual("_Mismatch", src["failure_class"])
        self.assertIn("wrong edition", src["error"])

    def test_no_retry_after_cutoff(self):
        self.now = 5400.0  # the clock is read relative to the refresh start
        start = self.now

        def runner(year):
            self.now = start + 5401.0  # this source alone ran past 90 min
            raise _Dropped("unreachable")

        rc, src = self.refresh(runner)
        self.assertEqual(1, rc)
        self.assertEqual([], self.slept)
        self.assertEqual(1, len(src["attempts"]))
        self.assertEqual("network_error", src["failure_class"])


class TestFailureFamilies(unittest.TestCase):
    """Every source's codes land in one cross-source vocabulary; QS keeps its own codes beside it."""

    def test_qs_codes_map_to_the_shared_families(self):
        self.assertEqual("blocked", failure_family("upstream_blocked"))
        self.assertEqual("blocked", failure_family("blocked"))
        self.assertEqual("layout_changed", failure_family("resolve_not_found"))
        self.assertEqual("http_error", failure_family("fetch_failed"))
        self.assertEqual("source_unavailable", failure_family("upstream_maintenance"))
        self.assertEqual("", failure_family(None))
        self.assertEqual("other", failure_family("RuntimeError"))

    def test_every_family_is_itself_a_family(self):
        for family in set(FAILURE_FAMILIES.values()):
            with self.subTest(family=family):
                self.assertEqual(family, failure_family(family))

    def test_a_qs_failure_reaches_the_refresh_with_its_code_and_family(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def qs(year):
                raise SourceFailure("QS", "upstream_blocked", f"{year}: HTTP 403")

            rc = run_scheduled_refresh(ranking_year=2026, sources=("QS",), runners={"QS": qs},
                                       lock_path=root / "lock", status_dir=root / "status")
            self.assertEqual(1, rc)
            outcome = json.loads((root / "status" / "scheduled_refresh_latest.json").read_text())["sources"][0]
            self.assertEqual("upstream_blocked", outcome["failure_class"])
            self.assertEqual("blocked", outcome["failure_family"])
            self.assertTrue((root / "status" / "scheduled_refresh_history.json").exists())


class TestHistory(unittest.TestCase):
    """What one status file cannot show: the same failure every week, or a table losing rows while every run passes."""

    def _write(self, folder, stamp, outcomes):
        (folder / f"scheduled_refresh_{stamp}.json").write_text(json.dumps({"sources": outcomes}), encoding="utf-8")

    def test_repeated_failures_and_a_slow_slide_are_warned_about(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for i, (qs_ok, the_rows) in enumerate([(True, 1700), (False, 1690), (False, 1650)]):
                qs = ({"source": "QS", "ok": True, "finished_at": f"t{i}", "summary": {"rows": 1500}} if qs_ok else
                      {"source": "QS", "ok": False, "failure_class": "upstream_blocked", "failure_family": "blocked"})
                the = {"source": "THE", "ok": True, "finished_at": f"t{i}", "summary": {"rows_crawled": the_rows}}
                self._write(folder, f"2026110{i + 1}T030000Z", [qs, the])

            history = summarize_history(folder)

            qs = history["sources"]["QS"]
            self.assertEqual((3, 1, 2), (qs["runs"], qs["ok_runs"], qs["consecutive_failures"]))
            self.assertEqual({"blocked": 2}, qs["failures_by_family"])
            self.assertEqual([1700, 1690, 1650], [p["rows"] for p in history["sources"]["THE"]["rows_by_run"]])
            joined = " | ".join(history["warnings"])
            self.assertIn("QS has failed 2 refreshes in a row", joined)
            self.assertIn("THE rows fell from 1690 to 1650", joined)
            self.assertIn("THE rows have fallen three successful refreshes running", joined)

    def test_a_steady_source_raises_no_warning_and_old_runs_age_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self._write(folder, "20261001T030000Z", [{"source": "ARWU", "ok": False, "failure_class": "network_error"}])
            for day in range(2, 14):
                self._write(folder, f"202610{day:02d}T030000Z",
                            [{"source": "ARWU", "ok": True, "finished_at": str(day), "summary": {"rows_crawled": 961}}])
            history = summarize_history(folder)
            self.assertEqual([], history["warnings"])
            self.assertEqual(12, history["runs_read"])
            self.assertEqual({}, history["sources"]["ARWU"]["failures_by_family"])


class TestTheCommandIsRegistered(unittest.TestCase):
    def test_run_pipeline_parses_scheduled_refresh(self):
        from crawlernest.run_pipeline import _REMAINING_COMMAND_HANDLERS, build_parser

        args = build_parser().parse_args(["scheduled-refresh", "--sources", "THE"])
        self.assertEqual("scheduled-refresh", args.command)
        self.assertIsNone(args.ranking_year)
        self.assertIn("scheduled-refresh", _REMAINING_COMMAND_HANDLERS)


if __name__ == "__main__":
    unittest.main()
