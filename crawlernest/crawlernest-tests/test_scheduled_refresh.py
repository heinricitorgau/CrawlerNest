"""The scheduler's command: once per source, isolated failures, one run at a time."""

from __future__ import annotations

import fcntl
import json
import tempfile
import unittest
from pathlib import Path

from crawlernest.pipeline.commands.scheduled_refresh import RefreshAlreadyRunning, run_scheduled_refresh


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


class TestTheCommandIsRegistered(unittest.TestCase):
    def test_run_pipeline_parses_scheduled_refresh(self):
        from crawlernest.run_pipeline import _REMAINING_COMMAND_HANDLERS, build_parser

        args = build_parser().parse_args(["scheduled-refresh", "--sources", "THE"])
        self.assertEqual("scheduled-refresh", args.command)
        self.assertIsNone(args.ranking_year)
        self.assertIn("scheduled-refresh", _REMAINING_COMMAND_HANDLERS)


if __name__ == "__main__":
    unittest.main()
