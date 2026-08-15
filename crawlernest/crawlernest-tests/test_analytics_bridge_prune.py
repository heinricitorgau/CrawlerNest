"""Superseded aggregated_rankings rows must not survive a later run.

The upsert stamps every row it writes with the current run id, but it can only
touch universities that are *in* the run. One that has dropped out of the source
data keeps its row, its old rank and its old run id indefinitely.

That is served, not merely stored. ``display_rank`` comes from a ROW_NUMBER over
the current run, so a leftover holds a rank the run has also given to somebody
else -- the live table had 163 duplicated ranks from exactly this.
``v_aggregated_rankings_latest`` hides them by joining on the latest run id, but
``AnalyticsService.getRankingTrends`` reads the base table and filters only on
``run.status = 'finished'``; a superseded row's run finished perfectly well.

These run in an isolated ranking year with no source data, because the prune is
scoped by year and universe: the real rows are never in reach.

Opt-in, like the other PostgreSQL tests:

    CRAWLERNEST_RUN_PG_TESTS=1 CRAWLERNEST_PG_PASSWORD=test \\
        python3 crawlernest/crawlernest-tests/run_tests.py
"""

from __future__ import annotations

import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.append(REPO_ROOT)

#: A year the crawler has no data for, so the run legitimately produces no rows
#: and anything left in the scope is by definition superseded.
ISOLATED_YEAR = 1900


@unittest.skipUnless(
    os.getenv("CRAWLERNEST_RUN_PG_TESTS") == "1", "PostgreSQL integration tests are opt-in"
)
class TestSupersededRowsArePruned(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg2

        from crawlernest.db import analytics_bridge

        cls.psycopg2 = psycopg2
        cls.bridge = analytics_bridge
        cls.dsn = {
            "host": os.getenv("CRAWLERNEST_PG_HOST", "localhost"),
            "port": int(os.getenv("CRAWLERNEST_PG_PORT", "5432")),
            "database": os.getenv("CRAWLERNEST_PG_DATABASE", "clawer"),
            "user": os.getenv("CRAWLERNEST_PG_USER", "test"),
            "password": os.getenv("CRAWLERNEST_PG_PASSWORD", ""),
        }

    def setUp(self):
        self.conn = self.psycopg2.connect(**self.dsn)
        self._clear_isolated_year()

    def tearDown(self):
        self._clear_isolated_year()
        self.conn.close()

    def _clear_isolated_year(self):
        with self.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM analytics.aggregated_rankings WHERE ranking_year = %s",
                (ISOLATED_YEAR,),
            )
            cur.execute(
                "DELETE FROM analytics.aggregation_runs WHERE ranking_year = %s",
                (ISOLATED_YEAR,),
            )
        self.conn.commit()

    def _plant_superseded_row(self):
        """A row from an earlier run that finished cleanly and nothing will re-touch."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT canonical_university_id FROM warehouse.canonical_university LIMIT 1")
            row = cur.fetchone()
            if row is None:
                self.skipTest("warehouse.canonical_university is empty")
            university_id = row[0]
            cur.execute(
                "INSERT INTO analytics.aggregation_runs (ranking_year, universe_type,"
                " universe_key, aggregation_method_version, status, finished_at)"
                " VALUES (%s, 'global', 'global', %s, 'finished', CURRENT_TIMESTAMP)"
                " RETURNING aggregation_run_id",
                (ISOLATED_YEAR, self.bridge.AGGREGATION_METHOD_VERSION),
            )
            old_run_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO analytics.aggregated_rankings (aggregation_run_id,"
                " canonical_university_id, ranking_year, universe_type, universe_key,"
                " display_rank, composite_score, coverage_ratio, source_ranks_json,"
                " source_normalized_scores_json, source_weights_used_json,"
                " aggregation_method_version)"
                " VALUES (%s, %s, %s, 'global', 'global', 1, 0.5, 0.222, '{}', '{}', '{}', %s)",
                (old_run_id, university_id, ISOLATED_YEAR, self.bridge.AGGREGATION_METHOD_VERSION),
            )
        self.conn.commit()
        return old_run_id

    def _rows_in_isolated_year(self):
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM analytics.aggregated_rankings WHERE ranking_year = %s",
                (ISOLATED_YEAR,),
            )
            return cur.fetchone()[0]

    def test_a_row_the_run_did_not_produce_is_deleted(self):
        self._plant_superseded_row()
        self.assertEqual(self._rows_in_isolated_year(), 1, "fixture did not land")

        summary = self.bridge.sync_legacy_rankings_to_analytics(
            self.conn, ranking_year=ISOLATED_YEAR
        )

        self.assertEqual(self._rows_in_isolated_year(), 0)
        self.assertEqual(summary.superseded_rankings_removed, 1)

    def test_without_the_prune_the_row_survives(self):
        """Proves the assertion above can fail -- otherwise it tests nothing.

        The defect this guards is silence: the stale row breaks no constraint and
        raises nothing, so only a check that goes red without the prune shows the
        prune is doing the work.
        """
        self._plant_superseded_row()
        real = self.bridge._prune_superseded_rankings
        self.bridge._prune_superseded_rankings = lambda *a, **k: 0
        try:
            self.bridge.sync_legacy_rankings_to_analytics(self.conn, ranking_year=ISOLATED_YEAR)
        finally:
            self.bridge._prune_superseded_rankings = real

        self.assertEqual(self._rows_in_isolated_year(), 1)

    def test_a_clean_run_reports_nothing_removed(self):
        """The counter has to stay at zero when there is nothing stale.

        A prune that deletes on every run would also pass the first test, and
        would quietly be discarding the run's own output.
        """
        summary = self.bridge.sync_legacy_rankings_to_analytics(
            self.conn, ranking_year=ISOLATED_YEAR
        )
        self.assertEqual(summary.superseded_rankings_removed, 0)


if __name__ == "__main__":
    unittest.main()
