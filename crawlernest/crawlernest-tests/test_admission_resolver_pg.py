"""The admission resolver against PostgreSQL: unified mappings, provenance, guardrails.

What the unit tests cannot show: that mappings land in
warehouse.source_university_mapping under source_code with no ranking_source_id,
that every row of a page gets the same mapping id, that a rejection retires the
mapping and clears the rows, and that a decision stranded by a moved page stops
the run before anything is written.

Rows live in a scratch copy of warehouse.admission_record, so the eight real
admission rows are never touched; mappings, reviews and events use a host no
real university has, and are removed afterwards.

    CRAWLERNEST_RUN_PG_TESTS=1 CRAWLERNEST_PG_PASSWORD=test \\
        python3 crawlernest/crawlernest-tests/run_tests.py
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (str(REPO_ROOT), str(REPO_ROOT / "crawlernest" / "crawlernest-core")):
    if path not in sys.path:
        sys.path.insert(0, path)

HOST = "pgtest-admissions.example"
PAGE = f"{HOST}/english-language-requirements"
OLD_PAGE = f"{HOST}/old/english-language-requirements"
TABLE = "admission_record_pgtest"
UNIVERSITIES = {
    "a": ("crawlernest-admission-pgtest-a", "Admission Pgtest Fixture University"),
    "b": ("crawlernest-admission-pgtest-b", "Admission Pgtest Other Institute"),
}


@unittest.skipUnless(os.getenv("CRAWLERNEST_RUN_PG_TESTS") == "1", "PostgreSQL integration tests are opt-in")
class TestAdmissionResolverAgainstPostgres(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg2

        cls.dsn = {
            "host": os.getenv("CRAWLERNEST_PG_HOST", "localhost"),
            "port": int(os.getenv("CRAWLERNEST_PG_PORT", "5432")),
            "dbname": os.getenv("CRAWLERNEST_PG_DATABASE", "clawer"),
            "user": os.getenv("CRAWLERNEST_PG_USER", "test"),
            "password": os.getenv("CRAWLERNEST_PG_PASSWORD", ""),
        }
        cls.conn = psycopg2.connect(**cls.dsn)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def setUp(self):
        self._clear()
        with self.conn.cursor() as cur:
            cur.execute(
                f"CREATE TABLE warehouse.{TABLE} "
                "(LIKE warehouse.admission_record INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES)"
            )
            self.uni = {}
            for key, (slug, name) in UNIVERSITIES.items():
                cur.execute(
                    "INSERT INTO warehouse.canonical_university (canonical_slug, display_name, display_name_normalized)"
                    " VALUES (%s, %s, %s) RETURNING canonical_university_id",
                    (slug, name, name.lower()),
                )
                self.uni[key] = cur.fetchone()[0]
        self.conn.commit()
        self._add_rows(PAGE, UNIVERSITIES["a"][1])

    def tearDown(self):
        self.conn.rollback()
        self._clear()

    def _clear(self):
        with self.conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS warehouse.{TABLE}")
            cur.execute("DELETE FROM warehouse.mapping_review WHERE source_entity_id LIKE %s", (f"{HOST}%",))
            cur.execute("DELETE FROM warehouse.source_university_mapping WHERE source_entity_id LIKE %s", (f"{HOST}%",))
            cur.execute("DELETE FROM analytics.entity_resolution_event WHERE source_entity_id LIKE %s", (f"{HOST}%",))
            cur.execute(
                "DELETE FROM warehouse.canonical_university WHERE canonical_slug = ANY(%s)",
                ([slug for slug, _ in UNIVERSITIES.values()],),
            )
        self.conn.commit()

    def _add_rows(self, entity_id, name):
        with self.conn.cursor() as cur:
            for degree in ("postgraduate", "undergraduate"):
                cur.execute(
                    f"""
                    INSERT INTO warehouse.{TABLE} (
                        source_code, source_entity_id, source_url, university_name,
                        normalized_university_name, degree_level, ielts_requirement, extracted_at
                    ) VALUES ('university_site', %s, %s, %s, %s, %s, 6.5, now())
                    """,
                    (entity_id, f"https://{entity_id}", name, name.lower(), degree),
                )
        self.conn.commit()

    def _rename_rows(self, name, entity_id=None):
        with self.conn.cursor() as cur:
            cur.execute(
                f"UPDATE warehouse.{TABLE} SET university_name = %s, source_entity_id = COALESCE(%s, source_entity_id)",
                (name, entity_id),
            )
        self.conn.commit()

    def _review(self, entity_id, decision, canonical):
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO warehouse.mapping_review (
                    source_code, source_entity_id, reviewed_source_name, reviewed_match_method,
                    decision, decided_canonical_university_id, decided_by
                ) VALUES ('university_site', %s, %s, 'exact_display', %s, %s, 'pgtest')
                """,
                (entity_id, UNIVERSITIES["a"][1], decision, canonical),
            )
        self.conn.commit()

    def _resolve(self):
        from crawlernest_admission_crawler.entity_resolver import resolve_admission_preview_entities

        return resolve_admission_preview_entities(
            pg_host=self.dsn["host"],
            pg_port=self.dsn["port"],
            pg_database=self.dsn["dbname"],
            pg_user=self.dsn["user"],
            pg_password=self.dsn["password"],
            target_table=TABLE,
        )

    def _mappings(self):
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT source_mapping_id, source_code, ranking_source_id, canonical_university_id, is_active"
                " FROM warehouse.source_university_mapping WHERE source_entity_id LIKE %s ORDER BY 1",
                (f"{HOST}%",),
            )
            return cur.fetchall()

    def _rows(self):
        with self.conn.cursor() as cur:
            cur.execute(
                f"SELECT degree_level, canonical_university_id, source_mapping_id, entity_resolution_status"
                f" FROM warehouse.{TABLE} ORDER BY degree_level"
            )
            return cur.fetchall()

    def test_a_page_gets_one_unified_mapping_and_every_row_names_it(self):
        summary = self._resolve()

        mappings = self._mappings()
        self.assertEqual(1, len(mappings))
        mapping_id, source_code, ranking_source_id, canonical, active = mappings[0]
        self.assertEqual(("university_site", None, self.uni["a"], True), (source_code, ranking_source_id, canonical, active))
        self.assertEqual({(self.uni["a"], mapping_id)}, {(row[1], row[2]) for row in self._rows()})
        self.assertEqual((2, 1), (summary.total_rows, summary.entity_count))

        with self.conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM warehouse.source_mapping WHERE source_entity_id LIKE %s", (f"{HOST}%",))
            self.assertEqual(0, cur.fetchone()[0], "the legacy table is no longer written")

    def test_a_new_name_on_a_mapped_page_is_held_not_reassigned(self):
        self._resolve()
        self._rename_rows(UNIVERSITIES["b"][1])

        summary = self._resolve()

        self.assertEqual(1, summary.held_by_existing_mapping_count)
        self.assertEqual({self.uni["a"]}, {row[1] for row in self._rows()})
        self.assertEqual([self.uni["a"]], [m[3] for m in self._mappings()])

    def test_a_rejection_retires_the_mapping_and_clears_the_rows(self):
        self._resolve()
        self._review(PAGE, "rejected", None)

        summary = self._resolve()

        self.assertEqual(1, summary.retired_mapping_count)
        self.assertEqual([False], [m[4] for m in self._mappings()])
        self.assertEqual({(None, None, "human_rejected")}, {row[1:] for row in self._rows()})

    def test_a_decision_stranded_by_a_moved_page_stops_the_run_before_any_write(self):
        from multi_source.reviews import UnappliedReviewError

        self._review(OLD_PAGE, "confirmed", self.uni["a"])

        with self.assertRaises(UnappliedReviewError):
            self._resolve()

        self.assertEqual([], self._mappings(), "no mapping may be written")
        self.assertEqual({(None, None)}, {row[1:3] for row in self._rows()}, "no row may be resolved")


if __name__ == "__main__":
    unittest.main()
