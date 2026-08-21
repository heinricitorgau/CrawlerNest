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
sys.path.insert(0, str(PACKAGE_ROOT / "crawlernest-db-writer"))

from db_writer import DBWriter
from models import University, AdmissionRequirements


@unittest.skipUnless(os.getenv("CRAWLERNEST_RUN_PG_TESTS") == "1", "PostgreSQL integration tests are opt-in")
class TestDBWriter(unittest.TestCase):
    def setUp(self):
        if psycopg2 is None:
            self.skipTest("psycopg2 not installed")

        self.config = {
            "db_type": "postgres",
            "host": os.getenv("CRAWLERNEST_PG_HOST", "localhost"),
            "port": int(os.getenv("CRAWLERNEST_PG_PORT", "5432")),
            "database": os.getenv("CRAWLERNEST_PG_DATABASE", "clawer"),
            "user": os.getenv("CRAWLERNEST_PG_USER", "test"),
            "password": os.getenv("CRAWLERNEST_PG_PASSWORD", ""),
        }
        self.writer = DBWriter(**self.config)

    def tearDown(self):
        self.writer.close()

    def test_upsert_university(self):
        uni = University(rank="1", name="Test University", country="Testland")
        uni_id = self.writer.upsert_university(uni)
        self.assertIsInstance(uni_id, int)

        self.writer.cur.execute(
            "SELECT display_name FROM warehouse.universities WHERE university_id = %s",
            (uni_id,),
        )
        row = self.writer.cur.fetchone()
        self.assertEqual(row[0], "Test University")

    def test_insert_admission_requirements(self):
        uni = University(rank="1", name="Test University", country="Testland")
        uni_id = self.writer.upsert_university(uni)

        reqs = AdmissionRequirements(ielts=7.5, gpa=3.8)
        self.writer.insert_admission_requirements(uni_id, reqs)

        self.writer.cur.execute(
            "SELECT ielts_min, gpa_min FROM warehouse.admission_requirements WHERE university_id = %s ORDER BY requirement_id DESC LIMIT 1",
            (uni_id,),
        )
        row = self.writer.cur.fetchone()
        self.assertEqual(float(row[0]), 7.5)
        self.assertEqual(float(row[1]), 3.8)


@unittest.skipUnless(os.getenv("CRAWLERNEST_RUN_PG_TESTS") == "1", "PostgreSQL integration tests are opt-in")
class TestSourceProfilePathIsPersisted(unittest.TestCase):
    """
    The source's own identifier has to survive the write.

    warehouse.universities.qs_profile_path existed and the insert never listed
    it, so the path arrived on every crawl and was dropped every time. It is
    what entity mappings are keyed on for QS, and
    warehouse.subject_ranking_record has a foreign key into those mappings, so
    losing it means a later ingest re-keys and strands the subject rankings.
    """

    NAME = "Profile Path Fixture University"

    def setUp(self):
        if psycopg2 is None:
            self.skipTest("psycopg2 not installed")
        self.writer = DBWriter(
            db_type="postgres",
            host=os.getenv("CRAWLERNEST_PG_HOST", "localhost"),
            port=int(os.getenv("CRAWLERNEST_PG_PORT", "5432")),
            database=os.getenv("CRAWLERNEST_PG_DATABASE", "clawer"),
            user=os.getenv("CRAWLERNEST_PG_USER", "test"),
            password=os.getenv("CRAWLERNEST_PG_PASSWORD", ""),
        )
        self._cleanup()

    def tearDown(self):
        try:
            self._cleanup()
        finally:
            self.writer.close()

    def _cleanup(self):
        self.writer.cur.execute(
            "DELETE FROM warehouse.universities WHERE display_name = %s", (self.NAME,)
        )
        self.writer.commit()

    def _stored_path(self, university_id: int) -> str:
        self.writer.cur.execute(
            "SELECT COALESCE(qs_profile_path, '') FROM warehouse.universities WHERE university_id = %s",
            (university_id,),
        )
        return self.writer.cur.fetchone()[0]

    def test_crawler_path_is_stored(self):
        # The crawler fills University.path; qs_profile_path is never assigned
        # anywhere in the codebase, so this is where the value actually is.
        uni = University(rank="1", name=self.NAME, country="Testland")
        uni.path = "/universities/profile-path-fixture"
        self.assertEqual(
            "/universities/profile-path-fixture",
            self._stored_path(self.writer.upsert_university(uni)),
        )

    def test_explicit_profile_path_wins_over_path(self):
        uni = University(rank="1", name=self.NAME, country="Testland")
        uni.qs_profile_path = "/universities/explicit"
        uni.path = "/universities/fallback"
        self.assertEqual(
            "/universities/explicit",
            self._stored_path(self.writer.upsert_university(uni)),
        )

    def test_a_crawl_without_a_path_does_not_erase_a_stored_one(self):
        # Detail pages fail often enough that a run can produce a university
        # with no path. Blanking the stored one would re-key its mappings.
        first = University(rank="1", name=self.NAME, country="Testland")
        first.path = "/universities/profile-path-fixture"
        university_id = self.writer.upsert_university(first)

        second = University(rank="1", name=self.NAME, country="Testland")
        self.assertEqual(university_id, self.writer.upsert_university(second))
        self.assertEqual(
            "/universities/profile-path-fixture", self._stored_path(university_id)
        )

    def test_a_new_path_replaces_the_stored_one(self):
        first = University(rank="1", name=self.NAME, country="Testland")
        first.path = "/universities/old"
        university_id = self.writer.upsert_university(first)

        second = University(rank="1", name=self.NAME, country="Testland")
        second.path = "/universities/new"
        self.writer.upsert_university(second)
        self.assertEqual("/universities/new", self._stored_path(university_id))


if __name__ == "__main__":
    unittest.main()
