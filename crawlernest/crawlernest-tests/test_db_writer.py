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


if __name__ == "__main__":
    unittest.main()
