"""warehouse.institution_lineage, read back through fetch_lineage, against PostgreSQL.

The rule itself is tested without a database in test_rank_delta. This covers
the part a fake cannot: the table's constraints, and that what fetch_lineage
returns is what compute_rank_delta then withholds on. Fixture universities and
events are created and removed here, so a freshly bootstrapped CI database --
which holds none of the real seeded mergers -- runs it the same way.

    CRAWLERNEST_RUN_PG_TESTS=1 CRAWLERNEST_PG_PASSWORD=test \\
        python3 crawlernest/crawlernest-tests/run_tests.py
"""

from __future__ import annotations

import os
import unittest

SLUGS = ("crawlernest-lineage-fixture-old", "crawlernest-lineage-fixture-new", "crawlernest-lineage-fixture-other")


@unittest.skipUnless(
    os.getenv("CRAWLERNEST_RUN_PG_TESTS") == "1", "PostgreSQL integration tests are opt-in"
)
class TestInstitutionLineageTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg2

        cls.psycopg2 = psycopg2
        cls.conn = psycopg2.connect(
            host=os.getenv("CRAWLERNEST_PG_HOST", "localhost"),
            port=int(os.getenv("CRAWLERNEST_PG_PORT", "5432")),
            database=os.getenv("CRAWLERNEST_PG_DATABASE", "clawer"),
            user=os.getenv("CRAWLERNEST_PG_USER", "test"),
            password=os.getenv("CRAWLERNEST_PG_PASSWORD", ""),
        )

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def setUp(self):
        self._clear()
        with self.conn.cursor() as cur:
            self.ids = []
            for slug in SLUGS:
                cur.execute(
                    "INSERT INTO warehouse.canonical_university (canonical_slug, display_name, display_name_normalized)"
                    " VALUES (%s, %s, %s) RETURNING canonical_university_id",
                    (slug, slug, slug),
                )
                self.ids.append(cur.fetchone()[0])
            self.old, self.new, self.other = self.ids
            cur.execute(
                "INSERT INTO warehouse.institution_lineage"
                " (predecessor_canonical_id, successor_canonical_id, effective_year, effective_date, kind, recorded_by)"
                " VALUES (%s, %s, 2024, DATE '2024-10-01', 'merger', 'test')",
                (self.old, self.new),
            )
        self.conn.commit()

    def tearDown(self):
        self._clear()

    def _clear(self):
        with self.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM warehouse.institution_lineage WHERE recorded_by = 'test'"
                " OR predecessor_canonical_id IN (SELECT canonical_university_id FROM warehouse.canonical_university WHERE canonical_slug = ANY(%s))"
                " OR successor_canonical_id IN (SELECT canonical_university_id FROM warehouse.canonical_university WHERE canonical_slug = ANY(%s))",
                (list(SLUGS), list(SLUGS)),
            )
            cur.execute("DELETE FROM warehouse.canonical_university WHERE canonical_slug = ANY(%s)", (list(SLUGS),))
        self.conn.commit()

    def test_fetch_returns_the_events_naming_the_universities_asked_about(self):
        from crawlernest.core.institution_lineage import LineageEvent, fetch_lineage

        self.assertEqual(
            (LineageEvent(self.old, self.new, 2024, "merger"),),
            fetch_lineage(self.conn, [self.new]),
        )
        self.assertEqual((), fetch_lineage(self.conn, [self.other]))

    def test_what_is_fetched_is_what_rank_delta_withholds_on(self):
        from crawlernest.core.institution_lineage import fetch_lineage
        from crawlernest.core.rank_delta import REASON_ENTITY_CHANGED, RankBand, RankObservation, compute_rank_delta

        lineage = fetch_lineage(self.conn, [self.new, self.other])
        current = RankObservation(2026, "QS", RankBand(40, 40))
        prior = RankObservation(2025, "QS", RankBand(44, 44))

        merged = compute_rank_delta(
            current, prior, prior_year=2025, canonical_university_id=self.new, lineage=lineage,
            ingested_years=(2025, 2026),
        )
        unrelated = compute_rank_delta(
            current, prior, prior_year=2025, canonical_university_id=self.other, lineage=lineage,
            ingested_years=(2025, 2026),
        )
        self.assertEqual(REASON_ENTITY_CHANGED, merged.reason)
        self.assertEqual(-4, unrelated.rank_delta)

    def test_the_table_refuses_what_the_rule_cannot_read(self):
        for kind, year, date in (("acquisition", 2024, None), ("merger", 2025, "2024-10-01"), ("merger", 1700, None)):
            with self.subTest(kind=kind, year=year, date=date):
                with self.conn.cursor() as cur, self.assertRaises(self.psycopg2.IntegrityError):
                    try:
                        cur.execute(
                            "INSERT INTO warehouse.institution_lineage"
                            " (predecessor_canonical_id, successor_canonical_id, effective_year, effective_date, kind, recorded_by)"
                            " VALUES (%s, %s, %s, %s, %s, 'test')",
                            (self.other, self.other, year, date, kind),
                        )
                    finally:
                        self.conn.rollback()

    def test_a_repeated_event_is_one_row(self):
        with self.conn.cursor() as cur, self.assertRaises(self.psycopg2.IntegrityError):
            try:
                cur.execute(
                    "INSERT INTO warehouse.institution_lineage"
                    " (predecessor_canonical_id, successor_canonical_id, effective_year, kind, recorded_by)"
                    " VALUES (%s, %s, 2024, 'merger', 'test')",
                    (self.old, self.new),
                )
            finally:
                self.conn.rollback()


if __name__ == "__main__":
    unittest.main()
