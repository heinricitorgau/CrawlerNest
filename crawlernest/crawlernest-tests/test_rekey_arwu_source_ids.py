"""Tests for the ARWU id re-key: the planning half, which decides every write.

The script rewrites warehouse.mapping_review, whose rows are human decisions
that cannot be regenerated. So the plan is held to one rule: every retiring id
resolves to exactly one new id by lookup, or nothing is written at all.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "_rekey_arwu_source_ids", REPO_ROOT / "scripts" / "rekey_arwu_source_ids.py"
)
rekey = importlib.util.module_from_spec(_spec)
# dataclasses resolve the defining module through sys.modules.
sys.modules[_spec.name] = rekey
_spec.loader.exec_module(rekey)

REVIEWS = rekey.REVIEW_TABLE
MAPPINGS = rekey.MAPPING_TABLE


def _crawl_row(name: str, up: str | None, year: int = 2026) -> dict:
    return {
        "id": f"arwu:{up}" if up else f"arwu:name:{name.lower().replace(' ', '-')}",
        "name": name,
        "year": year,
    }


# Three of the live 2026 cases: one where the source slug equals the old name
# slug, one where it does not, and the NOVA id whose slug is not the slug of the
# reviewed name (the id came from the payload's printed name).
CRAWL_2026 = [
    _crawl_row("Ruhr University Bochum", "ruhr-university-bochum"),
    _crawl_row(
        "University of Texas Southwestern Medical Center",
        "the-university-of-texas-southwestern-medical-center-at-dallas",
    ),
    _crawl_row("NOVA University Lisbon", "nova-university-lisbon"),
]


class TestCrosswalk(unittest.TestCase):
    def test_keys_by_edition_and_printed_name_slug(self):
        crosswalk, problems = rekey.crosswalk_from_rows(CRAWL_2026)
        self.assertEqual([], problems)
        self.assertEqual(
            "arwu:the-university-of-texas-southwestern-medical-center-at-dallas",
            crosswalk[(2026, "university-of-texas-southwestern-medical-center")],
        )

    def test_name_derived_rows_are_not_targets(self):
        crosswalk, _ = rekey.crosswalk_from_rows([_crawl_row("Some University", None)])
        self.assertEqual({}, crosswalk, "a name-derived id is no better than the one it replaces")

    def test_one_slug_for_two_institutions_is_a_problem_not_a_guess(self):
        crosswalk, problems = rekey.crosswalk_from_rows(
            [_crawl_row("Northeastern University", "a"), _crawl_row("Northeastern University", "b")]
        )
        self.assertNotIn((2026, "northeastern-university"), crosswalk)
        self.assertEqual(1, len(problems))


class TestPlan(unittest.TestCase):
    def _plan(self, ids_by_table, rows=CRAWL_2026):
        crosswalk, problems = rekey.crosswalk_from_rows(rows)
        self.assertEqual([], problems)
        return rekey.plan_rekey(ids_by_table, crosswalk)

    def test_reviews_and_mappings_are_both_rekeyed_by_lookup(self):
        old = {
            "arwu:2026:ruhr-university-bochum",
            "arwu:2026:university-of-texas-southwestern-medical-center",
            "arwu:2026:nova-university-lisbon",
        }
        plan, problems, _ = self._plan({REVIEWS: set(old), MAPPINGS: set(old)})
        self.assertEqual([], problems)
        pairs = {(s.table, s.old_id): s.new_id for s in plan}
        self.assertEqual(6, len(pairs))
        self.assertEqual(
            "arwu:the-university-of-texas-southwestern-medical-center-at-dallas",
            pairs[(REVIEWS, "arwu:2026:university-of-texas-southwestern-medical-center")],
            "stripping the year would have produced a different, wrong id here",
        )

    def test_an_unresolvable_id_fails_the_whole_plan(self):
        _, problems, _ = self._plan({REVIEWS: {"arwu:2026:no-such-university"}})
        self.assertEqual(1, len(problems))

    def test_an_edition_the_crawl_does_not_cover_is_a_problem(self):
        # The old slug is only reproducible from its own edition's names.
        _, problems, _ = self._plan({REVIEWS: {"arwu:2025:ruhr-university-bochum"}})
        self.assertEqual(1, len(problems))
        self.assertIn("--crawl-year 2025", problems[0])

    def test_a_new_id_that_already_exists_is_not_overwritten(self):
        _, problems, _ = self._plan(
            {MAPPINGS: {"arwu:2026:ruhr-university-bochum", "arwu:ruhr-university-bochum"}}
        )
        self.assertEqual(1, len(problems))
        self.assertIn("already exists", problems[0])

    def test_two_old_ids_landing_on_one_new_id_is_a_problem(self):
        _, problems, _ = self._plan(
            {
                REVIEWS: {
                    "arwu:2026:ruhr-university-bochum",
                    "https://www.shanghairanking.com/institution/ruhr-university-bochum",
                }
            }
        )
        self.assertEqual(1, len(problems))

    def test_profile_url_ids_convert_without_a_crosswalk(self):
        plan, problems, _ = self._plan(
            {REVIEWS: {"https://www.shanghairanking.com/institution/harvard-university"}}
        )
        self.assertEqual([], problems)
        self.assertEqual("arwu:harvard-university", plan[0].new_id)
        self.assertEqual("profile_url", plan[0].via)

    def test_stable_and_name_derived_ids_are_left_alone(self):
        plan, problems, notes = self._plan(
            {REVIEWS: {"arwu:harvard-university", "arwu:name:some-university"}}
        )
        self.assertEqual([], plan)
        self.assertEqual([], problems)
        self.assertEqual(1, len(notes))


class TestCommitNeedsAnAuditTrail(unittest.TestCase):
    def _refused(self, argv):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            rekey.parse_args(argv)

    def test_commit_without_audit_out_is_refused(self):
        self._refused(["--rows-json", "x.json", "--commit"])

    def test_a_crosswalk_source_is_required(self):
        self._refused([])


if __name__ == "__main__":
    unittest.main()
