"""Programme, intake and fetch granularity on admission rows, before the database.

warehouse.admission_record now keys a requirement by page, degree level,
programme and intake, and says what the number applies to. The CHECK
constraints in crawlernest-schema/admission_postgresql.sql are the last line;
these pin the Python that has to produce rows those constraints accept, and
that refuses the rest with a message naming the fields.
"""

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from crawlernest_admission_crawler.models import WarehouseReadyAdmissionRow  # noqa: E402
from crawlernest_admission_crawler.source_identity import (  # noqa: E402
    admission_entity_host,
    admission_programme_key,
)
from crawlernest_admission_crawler.warehouse_mapper import (  # noqa: E402
    intake_year_basis_for,
    map_staging_rows_to_warehouse_rows,
    requirement_scope_for,
)


def _staging(**extra):
    row = {
        "university_name": "Imperial College London",
        "normalized_university_name": "imperial college london",
        "source_url": "https://www.imperial.ac.uk/study/requirements/english-language",
        "country": "United Kingdom",
        "ielts_requirement": 7.0,
        "toefl_requirement": 100,
        "extracted_at": "2026-09-14T10:00:00+00:00",
        "degree_level": "postgraduate",
    }
    row.update(extra)
    return row


class TestProgrammeKey(unittest.TestCase):
    def test_spacing_and_case_do_not_make_a_second_programme(self):
        self.assertEqual(
            admission_programme_key("Faculty of Engineering", "MSc  Computing"),
            admission_programme_key("faculty of engineering ", "msc computing"),
        )

    def test_no_names_is_the_empty_key_the_schema_requires(self):
        self.assertEqual("", admission_programme_key(None, None))
        self.assertEqual("", admission_programme_key("  ", ""))

    def test_faculty_and_programme_stay_distinguishable(self):
        self.assertNotEqual(admission_programme_key("Engineering", None), admission_programme_key(None, "Engineering"))


class TestRequirementScope(unittest.TestCase):
    def test_scope_is_derived_from_the_names(self):
        self.assertEqual("programme", requirement_scope_for(faculty=None, programme_name="MSc Computing"))
        self.assertEqual("faculty", requirement_scope_for(faculty="Engineering", programme_name=None))
        self.assertEqual("unspecified", requirement_scope_for(faculty=None, programme_name=None))

    def test_an_institution_minimum_is_never_guessed(self):
        """That a number is a floor for every programme is something the page must say."""
        self.assertNotEqual("institution_minimum", requirement_scope_for(faculty=None, programme_name=None))
        self.assertEqual(
            "institution_minimum",
            requirement_scope_for(faculty=None, programme_name=None, declared="institution_minimum"),
        )

    def test_a_declared_scope_that_contradicts_the_names_is_refused(self):
        for faculty, programme, declared in (
            (None, None, "programme"),
            ("Engineering", "MSc Computing", "faculty"),
            (None, "MSc Computing", "institution_minimum"),
            (None, None, "university"),
        ):
            with self.subTest(declared=declared, programme=programme):
                with self.assertRaises(ValueError):
                    requirement_scope_for(faculty=faculty, programme_name=programme, declared=declared)


class TestIntakeYear(unittest.TestCase):
    def test_a_year_never_travels_without_how_it_was_known(self):
        with self.assertRaisesRegex(ValueError, "needs intake_year_basis"):
            intake_year_basis_for(2026, None)
        with self.assertRaisesRegex(ValueError, "without an intake_year"):
            intake_year_basis_for(None, "page_stated")
        self.assertEqual("page_stated", intake_year_basis_for(2026, "page_stated"))
        self.assertEqual("unknown", intake_year_basis_for(None, None))


class TestStagingRowsMapWithGranularity(unittest.TestCase):
    def test_todays_rows_land_as_unspecified_unknown_intake(self):
        """Every current source: one number per page, scope and intake not established."""
        row = map_staging_rows_to_warehouse_rows([_staging()])[0]
        self.assertEqual(("unspecified", None, None), (row.requirement_scope, row.faculty, row.programme_name))
        self.assertEqual((None, "unknown", "unknown"), (row.intake_year, row.intake_year_basis, row.fetch_mode))

    def test_a_programme_row_carries_its_programme(self):
        row = map_staging_rows_to_warehouse_rows([
            _staging(faculty=" Engineering ", programme_name="MSc Advanced Computing",
                     intake_year=2027, intake_year_basis="page_stated",
                     fetch_mode="live", fetched_at="2026-09-14T09:59:00+00:00")
        ])[0]
        self.assertEqual("programme", row.requirement_scope)
        self.assertEqual("Engineering", row.faculty)
        self.assertEqual(2027, row.intake_year)
        self.assertEqual(datetime(2026, 9, 14, 9, 59, tzinfo=timezone.utc), row.fetched_at)

    def test_a_live_fetch_without_a_time_is_refused(self):
        with self.assertRaisesRegex(ValueError, "needs fetched_at"):
            map_staging_rows_to_warehouse_rows([_staging(fetch_mode="live")])


class _RecordingCursor:
    def __init__(self):
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.statements.append((sql, params))

    def fetchone(self):
        return (True,)


class _RecordingConnection:
    def __init__(self):
        self.cursor_obj = _RecordingCursor()

    def cursor(self):
        return self.cursor_obj


class TestTheWriterKeysOnProgrammeAndIntake(unittest.TestCase):
    def test_the_upsert_targets_the_full_natural_key(self):
        from crawlernest_admission_crawler.warehouse_writer import _upsert_rows

        conn = _RecordingConnection()
        row = WarehouseReadyAdmissionRow(
            university_name="Imperial College London",
            normalized_university_name="imperial college london",
            source_url="https://www.imperial.ac.uk/study/requirements/english-language",
            country="United Kingdom",
            ielts_requirement=7.0,
            toefl_requirement=100,
            extracted_at=datetime(2026, 9, 14, tzinfo=timezone.utc),
            source_entity_id="www.imperial.ac.uk/study/requirements/english-language",
            degree_level="postgraduate",
            faculty="Engineering",
            programme_name="MSc Computing",
            requirement_scope="programme",
            intake_year=2027,
            intake_year_basis="page_stated",
        )
        inserted, updated = _upsert_rows(conn, schema_name="warehouse", table_name="admission_record", rows=[row])

        sql, params = conn.cursor_obj.statements[-1]
        self.assertIn("ON CONFLICT (source_code, source_entity_id, degree_level, programme_key, intake_year)", sql)
        self.assertIn("engineering|msc computing", params)
        self.assertEqual(sql.count("%s"), len(params), "placeholders and parameters must line up")
        self.assertEqual((1, 0), (inserted, updated))


class TestEntityHost(unittest.TestCase):
    def test_the_host_names_the_institution_not_the_page(self):
        self.assertEqual("www.ucl.ac.uk", admission_entity_host("www.ucl.ac.uk/study/english-language-requirements"))
        self.assertIsNone(admission_entity_host(""))


if __name__ == "__main__":
    unittest.main()
