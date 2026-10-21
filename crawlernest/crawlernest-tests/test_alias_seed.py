"""``run_pipeline seed-university-alias``: it adds an alias and leaves the university it names alone.

It used to upsert that university, which rewrote ``display_name_normalized`` in title case -- every other row is
lower case, and ``ranking_decision_preview`` joins on it -- and reported every existing university as created. It
also stored the alias in title case, which the dedup index does not fold, so a second seed added a second row.

The warehouse cases run in one transaction that is rolled back, and opt in like the rest of the suite:

    CRAWLERNEST_RUN_PG_TESTS=1 CRAWLERNEST_PG_PASSWORD=test \\
        python3 crawlernest/crawlernest-tests/run_tests.py
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent
for _p in (str(PACKAGE_ROOT / "packages"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from crawlernest_ranking_crawler.alias_seed import (  # noqa: E402
    normalize_alias,
    normalize_display_name,
    seed_university_alias,
)

EXISTING = "crawlernest-aliasseed-fixture-existing"
MERGED = "crawlernest-aliasseed-fixture-merged"


class TestStoredForms(unittest.TestCase):
    def test_a_display_name_is_stored_in_lower_case(self) -> None:
        self.assertEqual("northumbria university at newcastle", normalize_display_name("Northumbria University at Newcastle"))
        self.assertEqual("university of mit", normalize_display_name("  University  of MIT "))

    def test_an_alias_is_stored_as_seed_alias_file_stores_it(self) -> None:
        self.assertEqual("northumbria university qahe london campus",
                         normalize_alias("Northumbria University QAHE- London campus"))


@unittest.skipUnless(os.getenv("CRAWLERNEST_RUN_PG_TESTS") == "1", "PostgreSQL integration tests are opt-in")
class TestSeedAgainstPostgres(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import psycopg2

        cls.conn = psycopg2.connect(
            host=os.getenv("CRAWLERNEST_PG_HOST", "localhost"),
            port=int(os.getenv("CRAWLERNEST_PG_PORT", "5432")),
            dbname=os.getenv("CRAWLERNEST_PG_DATABASE", "clawer"),
            user=os.getenv("CRAWLERNEST_PG_USER", "test"),
            password=os.getenv("CRAWLERNEST_PG_PASSWORD", ""),
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.conn.close()

    def setUp(self) -> None:
        self.cur = self.conn.cursor()
        self.ids = {}
        for slug, name, status in ((EXISTING, "Aliasseed Fixture University", "active"),
                                   (MERGED, "Aliasseed Merged Fixture University", "merged")):
            self.cur.execute(
                "INSERT INTO warehouse.canonical_university (canonical_slug, display_name, display_name_normalized, status) "
                "VALUES (%s, %s, lower(%s), %s) RETURNING canonical_university_id", (slug, name, name, status))
            self.ids[slug] = self.cur.fetchone()[0]

    def tearDown(self) -> None:
        self.cur.close()
        self.conn.rollback()

    def _canonical(self, canonical_id: int) -> tuple:
        self.cur.execute("SELECT display_name, display_name_normalized, updated_at FROM warehouse.canonical_university "
                         "WHERE canonical_university_id = %s", (canonical_id,))
        return self.cur.fetchone()

    def _aliases(self, canonical_id: int) -> list[tuple]:
        self.cur.execute("SELECT alias_text, alias_normalized FROM warehouse.university_alias "
                         "WHERE canonical_university_id = %s ORDER BY alias_id", (canonical_id,))
        return self.cur.fetchall()

    def test_an_existing_university_is_not_rewritten(self) -> None:
        before = self._canonical(self.ids[EXISTING])
        summary = seed_university_alias(self.cur, canonical_name="Aliasseed Fixture University", alias="Aliasseed U.")

        self.assertEqual(self.ids[EXISTING], summary.canonical_university_id)
        self.assertFalse(summary.created_canonical)
        self.assertEqual(before, self._canonical(self.ids[EXISTING]))
        self.assertEqual([("Aliasseed U.", "aliasseed u")], self._aliases(self.ids[EXISTING]))

    def test_the_name_is_matched_without_regard_to_case(self) -> None:
        summary = seed_university_alias(self.cur, canonical_name="ALIASSEED FIXTURE UNIVERSITY", alias="Aliasseed U.")
        self.assertEqual(self.ids[EXISTING], summary.canonical_university_id)
        self.assertEqual("Aliasseed Fixture University", self._canonical(self.ids[EXISTING])[0])

    def test_seeding_twice_adds_one_row(self) -> None:
        seed_university_alias(self.cur, canonical_name="Aliasseed Fixture University", alias="Aliasseed U.")
        again = seed_university_alias(self.cur, canonical_name="Aliasseed Fixture University", alias="ALIASSEED U")

        self.assertFalse(again.created_alias)
        self.assertEqual(1, len(self._aliases(self.ids[EXISTING])))

    def test_a_merged_away_university_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "is merged"):
            seed_university_alias(self.cur, canonical_name="Aliasseed Merged Fixture University", alias="Aliasseed M")
        self.assertEqual([], self._aliases(self.ids[MERGED]))

    def test_a_new_university_is_created_in_the_stored_form(self) -> None:
        summary = seed_university_alias(self.cur, canonical_name="Aliasseed Brand New University", alias="ABNU")

        self.assertTrue(summary.created_canonical)
        name, normalized, _ = self._canonical(summary.canonical_university_id)
        self.assertEqual(("Aliasseed Brand New University", "aliasseed brand new university"), (name, normalized))


if __name__ == "__main__":
    unittest.main()
