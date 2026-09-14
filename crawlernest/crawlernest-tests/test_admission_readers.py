"""Admission readers go through one rule, and carry the admission caveats.

Seven readers used to collapse a university's admission rows with MIN(). That
was harmless with one row per page, and wrong once a source writes programme
rows or a second intake: it quotes the least demanding programme, or last year's
bar, as the university's. The rule now lives once, in
warehouse.v_admission_requirement_institution / _summary
(crawlernest-schema/admission_postgresql.sql).

Three things keep it that way:

* the Java test fixtures, which build their own tables on a bare database in CI,
  carry the views byte-for-byte;
* no reader aggregates a requirement column over admission_record itself;
* against PostgreSQL, the views do what the rule says, and the Python previews
  and caveats read them.

    CRAWLERNEST_RUN_PG_TESTS=1 CRAWLERNEST_PG_PASSWORD=test \\
        python3 crawlernest/crawlernest-tests/run_tests.py
"""

from __future__ import annotations

import os
import re
import sys
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SCHEMA = REPO_ROOT / "crawlernest" / "crawlernest-schema" / "admission_postgresql.sql"
FIXTURES = REPO_ROOT / "crawlernest" / "servise_for_java" / "src" / "test" / "resources" / "sql"
VIEW_NAMES = ("v_admission_requirement_institution", "v_admission_requirement_summary")


def _view_statement(text: str, name: str) -> str:
    match = re.search(rf"CREATE OR REPLACE VIEW warehouse\.{name} AS.*?;", text, re.S)
    if match is None:
        raise AssertionError(f"{name} not found")
    return " ".join(match.group(0).split())


class TestFixturesCarryTheViews(unittest.TestCase):
    """api-tests.yml runs the Java suite on a bare database built from fixtures."""

    def test_every_fixture_that_builds_admission_record_carries_both_views_verbatim(self):
        schema = SCHEMA.read_text(encoding="utf-8")
        fixtures = [
            path for path in sorted(FIXTURES.glob("*_setup.sql"))
            if "CREATE TABLE IF NOT EXISTS warehouse.admission_record" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(3, len(fixtures), [p.name for p in fixtures])
        for path in fixtures:
            text = path.read_text(encoding="utf-8")
            for name in VIEW_NAMES:
                with self.subTest(fixture=path.name, view=name):
                    self.assertEqual(
                        _view_statement(schema, name),
                        _view_statement(text, name),
                        f"{path.name} carries a different {name} from admission_postgresql.sql; "
                        "copy the schema's definition across",
                    )


class TestNoReaderCollapsesRequirementsItself(unittest.TestCase):
    """The views are the only place a requirement column is aggregated over the table."""

    #: MIN/MAX/AVG straight over a requirement column of admission_record (bare or
    #: aliased ar.). Aggregating a column read from the views is fine.
    AGGREGATE = re.compile(r"\b(MIN|MAX|AVG)\(\s*(ar\.|arp\.)?(ielts|toefl|duolingo|gpa)_requirement\s*\)", re.I)

    ROOTS = (
        REPO_ROOT / "crawlernest" / "servise_for_java" / "src" / "main",
        REPO_ROOT / "crawlernest" / "pipeline",
        REPO_ROOT / "crawlernest" / "core",
        REPO_ROOT / "crawlernest" / "crawlernest-core",
        REPO_ROOT / "crawlernest" / "agent",
        REPO_ROOT / "crawlernest" / "crawlernest-schema",
    )

    def test_no_live_reader_aggregates_requirement_columns(self):
        offenders = []
        for root in self.ROOTS:
            for path in root.rglob("*"):
                if path.suffix not in {".java", ".py", ".sql"} or not path.is_file() or path == SCHEMA:
                    continue
                for number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                    # Comments naming the old aggregate explain why it went.
                    if line.strip().startswith(("*", "//", "/*", "#", "--")):
                        continue
                    if self.AGGREGATE.search(line):
                        offenders.append(f"{path.relative_to(REPO_ROOT)}:{number}: {line.strip()}")
        self.assertEqual([], offenders, "read warehouse.v_admission_requirement_* instead")


@unittest.skipUnless(os.getenv("CRAWLERNEST_RUN_PG_TESTS") == "1", "PostgreSQL integration tests are opt-in")
class TestTheViewsApplyTheRule(unittest.TestCase):
    SLUG = "crawlernest-admission-readers-fixture"

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
                "INSERT INTO warehouse.canonical_university (canonical_slug, display_name, display_name_normalized)"
                " VALUES (%s, 'Admission Readers Fixture', 'admission readers fixture') RETURNING canonical_university_id",
                (self.SLUG,),
            )
            self.uid = cur.fetchone()[0]
        self.conn.commit()

    def tearDown(self):
        self.conn.rollback()
        self._clear()

    def _clear(self):
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM warehouse.admission_record WHERE source_entity_id LIKE 'readers-fixture.example/%'")
            cur.execute("DELETE FROM warehouse.canonical_university WHERE canonical_slug = %s", (self.SLUG,))
        self.conn.commit()

    def _row(self, page, *, level="postgraduate", ielts=None, toefl=None, scope="unspecified", programme=None,
             intake=None, basis="unknown", extracted="2026-08-22T10:00:00Z", fetched=None, mode="unknown"):
        key = "" if programme is None else f"|{programme.lower()}"
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO warehouse.admission_record (
                    source_code, source_entity_id, source_url, university_name, normalized_university_name,
                    canonical_university_id, entity_resolution_status, degree_level, programme_name, programme_key,
                    requirement_scope, intake_year, intake_year_basis, ielts_requirement, toefl_requirement,
                    extracted_at, fetched_at, fetch_mode
                ) VALUES ('university_site', %s, %s, 'Admission Readers Fixture', 'admission readers fixture',
                          %s, 'exact', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (f"readers-fixture.example/{page}", f"https://readers-fixture.example/{page}", self.uid, level,
                 programme, key, scope, intake, basis, ielts, toefl, extracted, fetched, mode),
            )
        self.conn.commit()

    def _institution(self):
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT degree_level, ielts_requirement, toefl_requirement, institution_row_count, programme_row_count,"
                " values_differ, intake_year, intake_year_basis FROM warehouse.v_admission_requirement_institution"
                " WHERE canonical_university_id = %s ORDER BY degree_level",
                (self.uid,),
            )
            return cur.fetchall()

    def _summary(self):
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT ielts_requirement, ielts_missing, fetch_dates_recorded, oldest_fetched_on, oldest_extracted_on,"
                " programme_row_count FROM warehouse.v_admission_requirement_summary WHERE canonical_university_id = %s",
                (self.uid,),
            )
            return cur.fetchone()

    def test_a_programme_row_never_becomes_the_university_figure(self):
        self._row("elr", ielts=7.0, toefl=100)
        self._row("elr", ielts=5.5, toefl=70, scope="programme", programme="MSc Easy")

        [(level, ielts, toefl, institution_rows, programme_rows, differ, _intake, _basis)] = self._institution()
        self.assertEqual((7.0, 100, 1, 1, False), (ielts, toefl, institution_rows, programme_rows, differ))

    def test_the_newest_stated_intake_wins_over_older_and_unknown_ones(self):
        self._row("elr", ielts=6.0)
        self._row("elr-2026", ielts=6.5, intake=2026, basis="page_stated")
        self._row("elr-2027", ielts=7.5, intake=2027, basis="deadline_inferred")

        [(_level, ielts, _t, institution_rows, _p, _d, intake, basis)] = self._institution()
        self.assertEqual((7.5, 1, 2027, "deadline_inferred"), (ielts, institution_rows, intake, basis))

    def test_disagreeing_pages_show_the_lowest_bar_and_say_so(self):
        self._row("elr-a", ielts=6.5)
        self._row("elr-b", ielts=7.0)

        [(_level, ielts, _t, institution_rows, _p, differ, _i, _b)] = self._institution()
        self.assertEqual((6.5, 2, True), (ielts, institution_rows, differ))

    def test_ielts_missing_means_missing_at_every_scope(self):
        self._row("elr", toefl=90)
        self.assertTrue(self._summary()[1])
        self._row("elr", ielts=6.0, scope="programme", programme="MSc Somewhere")
        summary = self._summary()
        self.assertIsNone(summary[0], "a programme's IELTS is not the university's")
        self.assertFalse(summary[1], "but an IELTS figure is stored, so the caveat must not claim none is")

    def test_staleness_uses_the_oldest_date_and_every_row(self):
        from crawlernest.core.caveats import ADMISSION_STALE_FETCHED_TEMPLATE, ADMISSION_STALE_UNDATED_TEMPLATE, admission_caveats

        self._row("elr-a", ielts=6.5, extracted="2026-08-22T10:00:00Z", fetched="2026-03-01T23:30:00Z", mode="live")
        self._row("elr-b", ielts=6.5, extracted="2026-07-01T10:00:00Z", fetched="2026-05-01T08:00:00Z", mode="live")
        _ielts, missing, recorded, fetched_on, extracted_on, _p = self._summary()
        self.assertEqual((False, True, date(2026, 3, 1), date(2026, 7, 1)), (missing, recorded, fetched_on, extracted_on))
        row = {"ielts_missing": missing, "fetch_dates_recorded": recorded,
               "oldest_fetched_on": fetched_on, "oldest_extracted_on": extracted_on}
        self.assertEqual([ADMISSION_STALE_FETCHED_TEMPLATE.replace("{date}", "2026-03-01")], admission_caveats(row))

        # One programme row with no fetch time makes the whole university undated.
        self._row("elr-c", ielts=5.0, scope="programme", programme="MSc Undated", extracted="2026-06-15T10:00:00Z")
        _ielts, missing, recorded, fetched_on, extracted_on, _p = self._summary()
        row = {"ielts_missing": missing, "fetch_dates_recorded": recorded,
               "oldest_fetched_on": fetched_on, "oldest_extracted_on": extracted_on}
        self.assertEqual([ADMISSION_STALE_UNDATED_TEMPLATE.replace("{date}", "2026-06-15")], admission_caveats(row))

    def test_the_python_previews_read_the_views_and_carry_the_caveats(self):
        from crawlernest.core.caveats import CAVEAT_IELTS_MISSING
        from crawlernest.pipeline.canonical_university_detail_preview import build_canonical_university_detail_preview

        self._row("elr", toefl=100)
        self._row("elr", ielts=5.5, toefl=60, scope="programme", programme="MSc Low Bar")
        preview = build_canonical_university_detail_preview(
            pg_host=self.dsn["host"], pg_port=self.dsn["port"], pg_database=self.dsn["dbname"],
            pg_user=self.dsn["user"], pg_password=self.dsn["password"], canonical_university_id=self.uid,
        )
        self.assertEqual(2, preview.admission_summary.row_count)
        self.assertEqual(100, preview.admission_summary.best_toefl_requirement, "not the programme's 60")
        self.assertIsNone(preview.admission_summary.best_ielts_requirement, "not the programme's 5.5")
        self.assertEqual(1, preview.admission_summary.programme_row_count)
        self.assertNotIn(CAVEAT_IELTS_MISSING, preview.admission_caveats)
        self.assertTrue(any("extracted on 2026-08-22" in c for c in preview.admission_caveats))


if __name__ == "__main__":
    unittest.main()
