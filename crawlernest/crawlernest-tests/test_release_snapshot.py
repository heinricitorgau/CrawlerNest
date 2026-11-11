"""scripts/release_snapshot.py: the comparison a release manifest and a backup drill rest on.

The database paths run in the release-snapshot CI job and in the drill itself; these pin the logic that decides
pass or fail without a database.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "release_snapshot.py"
_spec = importlib.util.spec_from_file_location("release_snapshot", _PATH)
release_snapshot = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release_snapshot)


def _counts(**overrides):
    counts = {
        "ranking_records_by_source_year": {"QS": {"2026": 10}, "THE": {"2026": 5}},
        "aggregated_rows_by_year_universe": {"2026": {"global": 12}},
        "relation_rows": {"analytics.aggregated_rankings": 12, "warehouse.us_institution": None},
        "user_data_rows": {"warehouse.app_user": 0},
    }
    counts.update(overrides)
    return counts


class CompareTest(unittest.TestCase):
    def test_a_matching_database_has_no_problems(self):
        self.assertEqual(release_snapshot.compare({"counts": _counts()}, _counts()), [])

    def test_every_difference_is_named_by_its_path(self):
        actual = _counts(ranking_records_by_source_year={"QS": {"2026": 9}, "THE": {"2026": 5}, "ARWU": {"2026": 1}})
        problems = release_snapshot.compare({"counts": _counts()}, actual)
        self.assertIn("ranking_records_by_source_year.QS.2026: expected 10, got 9", problems)
        self.assertIn("ranking_records_by_source_year.ARWU: expected None, got {'2026': 1}", problems)

    def test_user_rows_fail_a_release_unless_its_manifest_records_them(self):
        actual = _counts(user_data_rows={"warehouse.app_user": 2})
        self.assertEqual(
            release_snapshot.compare({"counts": _counts()}, actual),
            ["user data: warehouse.app_user has 2 row(s); a release holds none"],
        )
        self.assertEqual(release_snapshot.compare({"counts": _counts(), "contains_user_data": True}, actual), [])

    def test_editions_held_are_listed_newest_first(self):
        self.assertEqual(
            release_snapshot.coverage_from_counts(_counts()),
            {"QS": [2026], "THE": [2026]},
        )

    def test_user_data_is_excluded_by_schema_and_table_pattern(self):
        for pattern in ("warehouse.app_user", "warehouse.password_reset_token", "warehouse.saved_*", "desk.*", "agent_state.*"):
            self.assertIn(pattern, release_snapshot.USER_DATA_PATTERNS)


if __name__ == "__main__":
    unittest.main()
