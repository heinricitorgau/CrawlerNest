"""Tests for reading warehouse.rankings as multi-source input.

warehouse.ranking_record has one writer, and this is what feeds it for QS. The
rules that matter here are which of several rows for one university wins, and
which identifier the resulting mapping is keyed on -- warehouse.subject_ranking_record
has a foreign key into those mappings, so a changed key strands them.
"""
import os
import sys
import unittest
from pathlib import Path

try:
    import psycopg2
except ImportError:
    psycopg2 = None

TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent

sys.path.insert(0, str(PACKAGE_ROOT / "crawlernest-core"))

from multi_source.legacy_source import load_legacy_ranking_records  # noqa: E402


@unittest.skipUnless(
    os.getenv("CRAWLERNEST_RUN_PG_TESTS") == "1", "PostgreSQL integration tests are opt-in"
)
class TestLegacySourceLoader(unittest.TestCase):
    SLUG = "legacy-source-fixture-university"
    NAME = "Legacy Source Fixture University"
    SOURCE = "QSTEST"
    YEAR = 2999

    def setUp(self):
        if psycopg2 is None:
            self.skipTest("psycopg2 not installed")
        self.conn = psycopg2.connect(
            host=os.getenv("CRAWLERNEST_PG_HOST", "localhost"),
            port=int(os.getenv("CRAWLERNEST_PG_PORT", "5432")),
            database=os.getenv("CRAWLERNEST_PG_DATABASE", "clawer"),
            user=os.getenv("CRAWLERNEST_PG_USER", "test"),
            password=os.getenv("CRAWLERNEST_PG_PASSWORD", ""),
        )
        self.conn.autocommit = True
        self._cleanup()
        self.university_id = self._insert_university()

    def tearDown(self):
        try:
            self._cleanup()
        finally:
            self.conn.close()

    def _cleanup(self):
        with self.conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM warehouse.rankings
                WHERE ranking_year = %s AND upper(ranking_source) = %s
                """,
                (self.YEAR, self.SOURCE),
            )
            cur.execute(
                "DELETE FROM warehouse.universities WHERE school_slug = %s", (self.SLUG,)
            )

    def _insert_university(self, qs_profile_path: str = "") -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO warehouse.universities
                    (school_slug, display_name, canonical_name, qs_profile_path)
                VALUES (%s, %s, %s, %s)
                RETURNING university_id
                """,
                (self.SLUG, self.NAME, self.NAME, qs_profile_path),
            )
            return int(cur.fetchone()[0])

    def _insert_ranking(self, rank: int, *, created_at_sql: str = "CURRENT_TIMESTAMP"):
        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO warehouse.rankings
                    (university_id, ranking_source, ranking_type, ranking_year,
                     rank_start, rank_end, created_at)
                VALUES (%s, %s, 'world', %s, %s, %s, {created_at_sql})
                """,
                (self.university_id, self.SOURCE, self.YEAR, rank, rank),
            )

    def _load(self):
        return load_legacy_ranking_records(
            self.conn, source_code=self.SOURCE, ranking_year=self.YEAR
        )

    # ─── Which row wins ───────────────────────────────────────────────────────

    def test_a_worse_newer_rank_beats_a_better_older_one(self):
        # The rule this replaced ordered by rank_start ASC, so a university that
        # slipped down the table kept its old, better position forever.
        self._insert_ranking(10, created_at_sql="CURRENT_TIMESTAMP - INTERVAL '2 days'")
        self._insert_ranking(200)

        records = self._load()
        self.assertEqual(1, len(records), "one row per university, source, year and type")
        self.assertEqual(200, records[0].rank, "the current rank, not the best one ever seen")

    def test_a_better_newer_rank_also_wins(self):
        self._insert_ranking(200, created_at_sql="CURRENT_TIMESTAMP - INTERVAL '2 days'")
        self._insert_ranking(10)
        self.assertEqual(10, self._load()[0].rank)

    def test_ties_within_a_batch_fall_back_to_insertion_order(self):
        # A batch insert shares one timestamp; the serial id decides.
        stamp = "TIMESTAMPTZ '2999-01-01 00:00:00+00'"
        self._insert_ranking(50, created_at_sql=stamp)
        self._insert_ranking(60, created_at_sql=stamp)
        self.assertEqual(60, self._load()[0].rank)

    def test_undated_rows_lose_to_dated_ones(self):
        self._insert_ranking(10, created_at_sql="NULL")
        self._insert_ranking(200)
        self.assertEqual(200, self._load()[0].rank)

    # ─── What comes out ───────────────────────────────────────────────────────

    def test_rows_without_a_rank_are_dropped(self):
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO warehouse.rankings
                    (university_id, ranking_source, ranking_type, ranking_year,
                     rank_start, rank_end)
                VALUES (%s, %s, 'world', %s, NULL, NULL)
                """,
                (self.university_id, self.SOURCE, self.YEAR),
            )
        self.assertEqual([], self._load())

    def test_entity_id_comes_from_the_stored_profile_path(self):
        self._cleanup()
        self.university_id = self._insert_university("/universities/legacy-source-fixture")
        self._insert_ranking(1)
        self.assertEqual("/universities/legacy-source-fixture", self._load()[0].source_entity_id)

    def test_entity_id_falls_back_to_the_slug(self):
        # No stored path and no existing mapping for this source.
        self._insert_ranking(1)
        self.assertEqual(self.SLUG, self._load()[0].source_entity_id)

    def test_the_source_row_is_carried_for_the_review_screen(self):
        self._insert_ranking(1)
        raw = self._load()[0].metadata["raw_row"]
        self.assertEqual(self.NAME, raw["name"])
        self.assertIn("rank", raw)


if __name__ == "__main__":
    unittest.main()
