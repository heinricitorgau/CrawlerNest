"""Re-ingesting a source must replace what it published, not fail or accumulate.

Two separate defects made this impossible, and both were hit by hand before they
were fixed:

``run_label`` is built from the prefix, year and universe, so a second ingest of
the same source and year produced the same label and failed on the partial
unique index. Every correction had to hand-edit the previous run's label first.
The analytics bridge already upserted through that same index; the multi-source
path inserted blindly. They now behave the same way.

``ranking_record`` is upserted per university, so the second defect was quieter:
a university that dropped out of a corrected payload kept its old rank forever,
and downstream nothing distinguished it from one the source still ranks. Rows
are stamped with the run id, so the ones this run did not write are removed.

These run against a real database because the behaviour under test is a unique
index and a delete, neither of which a fake exercises.

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
for mod in ("crawlernest-core", "crawlernest-jobs"):
    path = str(PACKAGE_ROOT / mod)
    if path not in sys.path:
        sys.path.insert(0, path)

#: A year no crawl covers, so the rows here cannot collide with real ones.
ISOLATED_YEAR = 1899
SOURCE = "ARWU"


def _record(name: str, rank: int) -> dict:
    return {
        "id": f"idem:{ISOLATED_YEAR}:{name.lower().replace(' ', '-')}",
        "name": name,
        "country": "United States",
        "year": ISOLATED_YEAR,
        "ranking_type": "world",
        "rank": rank,
        "score": 50.0,
        "url": "https://example.invalid",
        "metadata": {"raw_source": SOURCE},
    }


@unittest.skipUnless(
    os.getenv("CRAWLERNEST_RUN_PG_TESTS") == "1", "PostgreSQL integration tests are opt-in"
)
class TestIngestIsIdempotent(unittest.TestCase):
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

    def tearDown(self):
        self._clear()
        self.conn.close()

    def _clear(self):
        with self.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM warehouse.ranking_record WHERE ranking_year = %s", (ISOLATED_YEAR,)
            )
            cur.execute(
                "DELETE FROM analytics.aggregated_rankings WHERE ranking_year = %s",
                (ISOLATED_YEAR,),
            )
            cur.execute(
                "DELETE FROM analytics.aggregation_runs WHERE ranking_year = %s", (ISOLATED_YEAR,)
            )
        self.conn.commit()

    def _ingest(self, names_and_ranks, batch_id):
        from crawlernest.pipeline.commands.canonical import ingest_rankings_payload

        return ingest_rankings_payload(
            source=SOURCE,
            payload=[_record(n, r) for n, r in names_and_ranks],
            ranking_year=ISOLATED_YEAR,
            ranking_type="world",
            source_version=None,
            pg_host=self.dsn["host"],
            pg_port=self.dsn["port"],
            pg_database=self.dsn["database"],
            pg_user=self.dsn["user"],
            pg_password=self.dsn["password"],
            batch_id=batch_id,
        )

    def _record_count(self):
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM warehouse.ranking_record WHERE ranking_year = %s",
                (ISOLATED_YEAR,),
            )
            return cur.fetchone()[0]

    def _run_count(self):
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM analytics.aggregation_runs WHERE ranking_year = %s",
                (ISOLATED_YEAR,),
            )
            return cur.fetchone()[0]

    def test_the_same_payload_twice_is_a_no_op(self):
        """Used to fail outright on the run_label unique index."""
        rows = [("Harvard University", 1), ("Stanford University", 2)]
        self._ingest(rows, "idem-a")
        first, runs_first = self._record_count(), self._run_count()
        self.assertGreater(first, 0, "fixture did not land")

        self._ingest(rows, "idem-b")

        self.assertEqual(self._record_count(), first, "a repeat ingest changed the row count")
        self.assertEqual(self._run_count(), runs_first, "a repeat ingest added a second run row")

    def test_a_shrinking_payload_removes_what_is_gone(self):
        """The quiet half: a dropped university used to keep its rank forever."""
        self._ingest([("Harvard University", 1), ("Stanford University", 2)], "idem-a")
        self.assertEqual(self._record_count(), 2)

        self._ingest([("Harvard University", 1)], "idem-b")

        self.assertEqual(self._record_count(), 1,
                         "the university missing from the second payload kept its record")

    def test_a_rank_change_is_applied(self):
        """The check that the prune has not simply deleted everything."""
        self._ingest([("Harvard University", 1)], "idem-a")
        self._ingest([("Harvard University", 7)], "idem-b")

        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT rank_position FROM warehouse.ranking_record WHERE ranking_year = %s",
                (ISOLATED_YEAR,),
            )
            ranks = [r[0] for r in cur.fetchall()]
        self.assertEqual(ranks, [7])


if __name__ == "__main__":
    unittest.main()
