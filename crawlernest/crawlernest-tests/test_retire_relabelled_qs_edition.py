"""retire_relabelled_qs_edition.compare: the old label is retired only when the new one is the same table."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "retire_relabelled_qs_edition.py"
_spec = importlib.util.spec_from_file_location("retire_relabelled_qs_edition", _PATH)
retire = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(retire)

ARCHIVE = "web_archive:20220426065734"


class CompareTest(unittest.TestCase):
    def test_identical_tables_pass(self):
        old = [(1, 10, "=10", ARCHIVE), (2, 201, "201-250", ARCHIVE)]
        new = [(1, 10, "=10", ARCHIVE), (2, 201, "201-250", ARCHIVE)]
        self.assertEqual([], retire.compare(old, new))

    def test_any_difference_refuses(self):
        old = [(1, 10, "=10", ARCHIVE), (2, 201, "201-250", ARCHIVE)]
        self.assertTrue(any("different rank" in p for p in retire.compare(old, [(1, 11, "11", ARCHIVE), (2, 201, "201-250", ARCHIVE)])))
        self.assertTrue(any("missing from the new" in p for p in retire.compare(old, [(1, 10, "=10", ARCHIVE)])))
        self.assertTrue(any("not in the old" in p for p in retire.compare(old, old + [(3, 5, "5", ARCHIVE)])))

    def test_a_live_crawl_is_never_retired(self):
        old = [(1, 10, "10", "qs-live-2026")]
        self.assertTrue(any("did not come from the archive loader" in p for p in retire.compare(old, old)))

    def test_an_empty_old_year_is_refused(self):
        self.assertIn("the old year holds no QS rows", retire.compare([], []))


if __name__ == "__main__":
    unittest.main()
