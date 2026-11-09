"""Tests for snapshot_guard.py: a crawl may not silently shrink or blank a committed snapshot."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent
for mod in ("crawlernest-core", "crawlernest-jobs"):
    p = str(PACKAGE_ROOT / mod)
    if p not in sys.path:
        sys.path.insert(0, p)

import snapshot_guard  # noqa: E402
from snapshot_guard import (  # noqa: E402
    ALLOW_ENV,
    SnapshotRegressionError,
    check_snapshot_regression,
)


def _row(i: int, **overrides):
    row = {"id": f"u{i}", "name": f"University {i}", "rank": i, "country": "Somewhere"}
    row.update(overrides)
    return row


def _rows(n: int):
    return [_row(i) for i in range(1, n + 1)]


class _Base(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.path = self.dir / "snapshot.json"
        patcher = mock.patch.dict(os.environ, {}, clear=False)
        patcher.start()
        os.environ.pop(ALLOW_ENV, None)
        self.addCleanup(patcher.stop)

    def write_existing(self, payload):
        self.path.write_text(json.dumps(payload), encoding="utf-8")

    def check(self, new_rows, **kw):
        kw.setdefault("label", "TEST 2026")
        return check_snapshot_regression(self.path, new_rows, **kw)


class TestNothingToProtect(_Base):
    def test_no_existing_file_passes(self):
        self.check(_rows(3))

    def test_unparseable_existing_file_passes(self):
        self.path.write_text("{not json", encoding="utf-8")
        self.check(_rows(3))

    def test_identical_rows_pass(self):
        self.write_existing({"rows": _rows(100)})
        self.check(_rows(100))

    def test_growth_passes(self):
        self.write_existing({"rows": _rows(30)})
        self.check(_rows(1000))


class TestRowCountDrop(_Base):
    def test_large_drop_is_refused(self):
        # The 2026-11-03 ARWU crawl: 1,000 rows replaced by the rendered 30.
        self.write_existing({"rows": _rows(1000)})
        with self.assertRaises(SnapshotRegressionError) as ctx:
            self.check(_rows(30))
        self.assertIn("1000", str(ctx.exception))
        self.assertIn("30", str(ctx.exception))

    def test_small_drop_within_tolerance_passes(self):
        self.write_existing({"rows": _rows(1000)})
        self.check(_rows(960))

    def test_drop_just_over_tolerance_is_refused(self):
        self.write_existing({"rows": _rows(1000)})
        with self.assertRaises(SnapshotRegressionError):
            self.check(_rows(949))

    def test_bare_list_snapshots_are_compared(self):
        # QS normalized_snapshot.json is a top-level list, not {"rows": [...]}.
        self.write_existing(_rows(1504))
        with self.assertRaises(SnapshotRegressionError):
            self.check(_rows(50))


class TestFieldLoss(_Base):
    def test_a_row_losing_its_country_is_refused(self):
        # The 2026-11-08 QS crawl: one row came back with country "".
        old = _rows(10)
        new = _rows(10)
        new[4]["country"] = ""
        self.write_existing({"rows": old})
        with self.assertRaises(SnapshotRegressionError) as ctx:
            self.check(new)
        self.assertIn("University 5", str(ctx.exception))
        self.assertIn("country", str(ctx.exception))

    def test_none_counts_as_lost(self):
        old = _rows(10)
        new = _rows(10)
        new[0]["rank"] = None
        self.write_existing({"rows": old})
        with self.assertRaises(SnapshotRegressionError):
            self.check(new)

    def test_a_field_that_was_already_blank_is_not_a_loss(self):
        old = _rows(10)
        old[2]["country"] = ""
        new = _rows(10)
        new[2]["country"] = ""
        self.write_existing({"rows": old})
        self.check(new)

    def test_a_changed_value_is_not_a_loss(self):
        old = _rows(10)
        new = _rows(10)
        new[3]["rank"] = 99
        self.write_existing({"rows": old})
        self.check(new)

    def test_unwatched_fields_are_ignored(self):
        old = [dict(r, score=50.0) for r in _rows(10)]
        new = [dict(r, score=None) for r in _rows(10)]
        self.write_existing({"rows": old})
        self.check(new)

    def test_custom_identity_and_fields(self):
        old = [{"detail_url": f"/u/{i}", "university_name": f"U{i}", "country": "X"} for i in range(5)]
        new = [dict(r) for r in old]
        new[1]["country"] = ""
        self.write_existing(old)
        with self.assertRaises(SnapshotRegressionError):
            self.check(new, id_field="detail_url", fields=("university_name", "country"))

    def test_rows_without_identity_are_skipped_for_field_checks(self):
        self.write_existing({"rows": ["the committed edition"]})
        self.check(_rows(2))


class TestOverride(_Base):
    def test_allow_argument_bypasses(self):
        self.write_existing({"rows": _rows(1000)})
        self.check(_rows(30), allow=True)

    def test_allow_env_bypasses(self):
        self.write_existing({"rows": _rows(1000)})
        with mock.patch.dict(os.environ, {ALLOW_ENV: "1"}):
            self.check(_rows(30))

    def test_allow_env_must_be_truthy(self):
        self.write_existing({"rows": _rows(1000)})
        with mock.patch.dict(os.environ, {ALLOW_ENV: "0"}):
            with self.assertRaises(SnapshotRegressionError):
                self.check(_rows(30))


class TestTheCrawlerKeepsTheFile(unittest.TestCase):
    """THE had no guard at all: whatever the edition page returned was written."""

    def _crawl(self, raw_rows):
        import the_crawler

        out = Path(tempfile.mkdtemp())
        existing = out / "the_rankings_2026.json"
        existing.write_text(json.dumps({"rows": _rows(2000)}), encoding="utf-8")
        edition = mock.Mock(page_url="https://example.test/2026")
        edition.as_meta.return_value = {}
        with mock.patch.object(the_crawler, "_load_verified_edition", return_value=(raw_rows, edition)), \
                mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(ALLOW_ENV, None)
            try:
                the_crawler.crawl_the_rankings(2026, output_dir=out)
                error = None
            except SnapshotRegressionError as exc:
                error = exc
        return error, json.loads(existing.read_text(encoding="utf-8"))

    def test_truncated_edition_is_not_written(self):
        raw = [{"name": f"University {i}", "rank": str(i), "location": "Somewhere", "nid": str(i)}
               for i in range(1, 51)]
        error, content = self._crawl(raw)
        self.assertIsNotNone(error)
        self.assertEqual(2000, len(content["rows"]))


class TestModuleSurface(unittest.TestCase):
    def test_default_fields(self):
        self.assertEqual(("name", "rank", "country"), snapshot_guard.DEFAULT_FIELDS)


if __name__ == "__main__":
    unittest.main()
