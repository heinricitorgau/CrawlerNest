"""A university-level ranking summary must not mix in other universes.

``warehouse.ranking_record`` is keyed per universe: a university appears once
per ranking source *and* once per universe it was ranked in. The QS crawler
now writes ``region:*``, ``regional:*``, ``subject:*`` and ``special:*``
universes into this table alongside ``world``. An unscoped
``COUNT(*)``/``MIN(rank_position)`` over a university's rows therefore no
longer describes "the world ranking" it claims to -- verified live against
`clawer`: MIT alone carries ranking_record rows across five different
ranking_type values.

The three readers of this table (this module's ``ranking_scope.py``,
``convergence_preview.py`` and ``canonical_university_detail_preview.py``, plus
a Java copy in ``UniversityPreviewRepository.java``) all filter
``ranking_type='world' AND universe_type='global' AND universe_key='global'``
for exactly this reason.

    CRAWLERNEST_RUN_PG_TESTS=1 CRAWLERNEST_PG_PASSWORD=test \\
        python3 crawlernest/crawlernest-tests/run_tests.py
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from crawlernest.pipeline.ranking_scope import (  # noqa: E402
    DEFAULT_RANKING_TABLE,
    DEFAULT_SCOPE_PARAMS,
    scope_predicate,
)

#: A slug no real crawl would produce, so cleanup can never touch a live row.
FIXTURE_SLUG = "crawlernest-ranking-scope-fixture"
FIXTURE_NAME = "Ranking Scope Fixture University"
#: Chosen worse (numerically larger) than the out-of-scope row's rank, so an
#: unscoped MIN(rank_position) would report the wrong one.
WORLD_RANK = 5
OUT_OF_SCOPE_RANK = 1


class TestScopePredicate(unittest.TestCase):
    """No database needed: the predicate text is what every reader shares."""

    def test_three_placeholders_in_column_order(self):
        sql = scope_predicate("rr")
        self.assertEqual(sql.count("%s"), 3)
        self.assertIn("rr.ranking_type = %s", sql)
        self.assertIn("rr.universe_type = %s", sql)
        self.assertIn("rr.universe_key = %s", sql)

    def test_params_match_the_placeholder_order(self):
        # world, global, global -- the same triple every reader binds.
        self.assertEqual(DEFAULT_SCOPE_PARAMS, ("world", "global", "global"))

    def test_indent_only_affects_continuation_lines(self):
        sql = scope_predicate("m", indent="    ")
        lines = sql.split("\n")
        self.assertFalse(lines[0].startswith(" "))
        self.assertTrue(lines[1].startswith("    AND"))
        self.assertTrue(lines[2].startswith("    AND"))


@unittest.skipUnless(
    os.getenv("CRAWLERNEST_RUN_PG_TESTS") == "1", "PostgreSQL integration tests are opt-in"
)
class TestRankingSummaryReadersIgnoreOtherUniverses(unittest.TestCase):
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
        self.canonical_university_id = self._seed()

    def tearDown(self):
        self._clear()
        self.conn.close()

    def _clear(self):
        with self.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM warehouse.ranking_record"
                " WHERE canonical_university_id IN ("
                "   SELECT canonical_university_id FROM warehouse.canonical_university"
                "   WHERE canonical_slug = %s)",
                (FIXTURE_SLUG,),
            )
            cur.execute(
                "DELETE FROM warehouse.canonical_university WHERE canonical_slug = %s",
                (FIXTURE_SLUG,),
            )
        self.conn.commit()

    def _seed(self) -> int:
        """One university, ranked in the world ranking and in a second universe.

        The second row's rank_position (1) beats the world row's (5): if a
        reader ever drops the scope filter, best_rank comes back 1 -- a rank
        this university never held in the world ranking -- and row_count comes
        back 2 instead of 1.
        """
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO warehouse.canonical_university"
                " (canonical_slug, display_name, display_name_normalized)"
                " VALUES (%s, %s, %s)"
                " ON CONFLICT (canonical_slug) DO UPDATE SET updated_at = CURRENT_TIMESTAMP"
                " RETURNING canonical_university_id",
                (FIXTURE_SLUG, FIXTURE_NAME, FIXTURE_NAME.lower()),
            )
            canonical_university_id = cur.fetchone()[0]

            cur.execute("SELECT ranking_source_id FROM warehouse.ranking_source WHERE source_code = 'QS'")
            row = cur.fetchone()
            if row is None:
                self.skipTest("warehouse.ranking_source has no QS row to attach the fixture to")
            ranking_source_id = row[0]

            for ranking_type, universe_type, universe_key, rank_position in (
                ("world", "global", "global", WORLD_RANK),
                ("region:europe", "region", "europe", OUT_OF_SCOPE_RANK),
            ):
                cur.execute(
                    f"""
                    INSERT INTO warehouse.{DEFAULT_RANKING_TABLE}
                        (canonical_university_id, ranking_source_id, ranking_year,
                         ranking_type, universe_type, universe_key, rank_position)
                    VALUES (%s, %s, 2026, %s, %s, %s, %s)
                    """,
                    (canonical_university_id, ranking_source_id, ranking_type, universe_type, universe_key, rank_position),
                )
        self.conn.commit()
        return canonical_university_id

    def test_canonical_university_detail_preview_reports_the_world_rank_only(self):
        from crawlernest.pipeline.canonical_university_detail_preview import (
            build_canonical_university_detail_preview,
        )

        preview = build_canonical_university_detail_preview(
            **self.dsn_kwargs(),
            canonical_university_id=self.canonical_university_id,
        )

        self.assertIsNotNone(preview.ranking_summary)
        self.assertEqual(preview.ranking_summary.row_count, 1)
        self.assertEqual(preview.ranking_summary.best_rank, WORLD_RANK)
        self.assertEqual(preview.ranking_summary.sources, ["QS"])

    def test_convergence_preview_reports_the_world_rank_only(self):
        from crawlernest.pipeline.convergence_preview import build_convergence_preview

        # Large enough to include every university with any ranking or
        # admission data on this database, so the fixture cannot be pushed out
        # by real rows sorting ahead of it -- picking it out by id rather than
        # relying on it landing near the top of the order.
        rows = build_convergence_preview(**self.dsn_kwargs(), limit=100_000)
        mine = next(
            (r for r in rows if r.canonical_university_id == self.canonical_university_id), None
        )

        self.assertIsNotNone(mine, "fixture university missing from the convergence preview")
        self.assertIsNotNone(mine.ranking_summary)
        self.assertEqual(mine.ranking_summary.row_count, 1)
        self.assertEqual(mine.ranking_summary.best_rank, WORLD_RANK)

    def dsn_kwargs(self) -> dict:
        return {
            "pg_host": self.dsn["host"],
            "pg_port": self.dsn["port"],
            "pg_database": self.dsn["database"],
            "pg_user": self.dsn["user"],
            "pg_password": self.dsn["password"],
        }


if __name__ == "__main__":
    unittest.main()
