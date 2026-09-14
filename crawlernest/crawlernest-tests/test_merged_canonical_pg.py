"""A canonical university merged into another must stay merged.

Two duplicates were merged on 2026-09-14 (İstanbul Bilgi and Boğaziçi, each
carried twice after a snapshot seed ran against the live warehouse). The
duplicate rows are kept, marked status='merged' with metadata.merged_into,
because historical ML runs still reference them. Two writers would quietly undo
that:

- the resolver loaded every canonical, so the merged row's display name kept
  attracting the spelling the merge had moved to an alias of the survivor;
- the analytics bridge re-links legacy universities by slug on every pipeline
  run, which pointed the legacy link straight back at the merged row.

Opt-in, like the other PostgreSQL tests:

    CRAWLERNEST_RUN_PG_TESTS=1 CRAWLERNEST_PG_PASSWORD=test \\
        python3 crawlernest/crawlernest-tests/run_tests.py
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent
REPO_ROOT = PACKAGE_ROOT.parent
for path in (str(PACKAGE_ROOT / "crawlernest-core"), str(REPO_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

SURVIVOR_SLUG = "crawlernest-merge-fixture-survivor"
MERGED_SLUG = "crawlernest-merge-fixture-merged"


@unittest.skipUnless(
    os.getenv("CRAWLERNEST_RUN_PG_TESTS") == "1", "PostgreSQL integration tests are opt-in"
)
class TestAMergedCanonicalStaysMerged(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg2

        cls.psycopg2 = psycopg2
        cls.dsn = {
            "host": os.getenv("CRAWLERNEST_PG_HOST", "localhost"),
            "port": int(os.getenv("CRAWLERNEST_PG_PORT", "5432")),
            "database": os.getenv("CRAWLERNEST_PG_DATABASE", "clawer"),
            "user": os.getenv("CRAWLERNEST_PG_USER", "test"),
            "password": os.getenv("CRAWLERNEST_PG_PASSWORD", ""),
        }

    def setUp(self):
        self.conn = self.psycopg2.connect(**self.dsn)
        self._clear()
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO warehouse.canonical_university (canonical_slug, display_name, display_name_normalized)"
                " VALUES (%s, 'Merge Fixture University', 'merge fixture university')"
                " RETURNING canonical_university_id",
                (SURVIVOR_SLUG,),
            )
            self.survivor_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO warehouse.canonical_university"
                " (canonical_slug, display_name, display_name_normalized, status, metadata)"
                " VALUES (%s, 'Merge Fixture Üniversitesi', 'merge fixture niversitesi', 'merged', %s::jsonb)"
                " RETURNING canonical_university_id",
                (MERGED_SLUG, json.dumps({"merged_into": self.survivor_id})),
            )
            self.merged_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO warehouse.universities (school_slug, display_name)"
                " VALUES (%s, 'Merge Fixture Üniversitesi') RETURNING university_id",
                (MERGED_SLUG,),
            )
            self.university_id = cur.fetchone()[0]
        self.conn.commit()

    def tearDown(self):
        self._clear()
        self.conn.close()

    def _clear(self):
        slugs = [SURVIVOR_SLUG, MERGED_SLUG]
        with self.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM warehouse.canonical_university_link WHERE university_id IN"
                " (SELECT university_id FROM warehouse.universities WHERE school_slug = ANY(%s))",
                (slugs,),
            )
            cur.execute("DELETE FROM warehouse.universities WHERE school_slug = ANY(%s)", (slugs,))
            cur.execute("DELETE FROM warehouse.canonical_university WHERE canonical_slug = ANY(%s)", (slugs,))
        self.conn.commit()

    def test_the_resolver_is_not_offered_the_merged_row(self):
        from entity_resolution.repository import EntityResolutionRepository

        ids = {p.canonical_university_id for p in EntityResolutionRepository(self.conn).load_canonical_profiles()}
        self.assertIn(self.survivor_id, ids)
        self.assertNotIn(self.merged_id, ids)

    def test_the_bridge_links_the_legacy_university_to_the_survivor(self):
        from crawlernest.db import analytics_bridge

        with self.conn.cursor() as cur:
            analytics_bridge._seed_canonical_universities(cur)
            analytics_bridge._seed_canonical_university_links(cur)
            cur.execute(
                "SELECT canonical_university_id FROM warehouse.canonical_university_link WHERE university_id = %s",
                (self.university_id,),
            )
            linked = cur.fetchone()[0]
            cur.execute(
                "SELECT status, metadata ->> 'merged_into' FROM warehouse.canonical_university"
                " WHERE canonical_university_id = %s",
                (self.merged_id,),
            )
            status, merged_into = cur.fetchone()
        self.conn.rollback()

        self.assertEqual(self.survivor_id, linked)
        self.assertEqual(("merged", str(self.survivor_id)), (status, merged_into),
                         "re-seeding by slug must not reactivate the merged row")


if __name__ == "__main__":
    unittest.main()
