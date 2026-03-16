import unittest
import sqlite3
import sys
import os

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db_writer import DBWriter
from models import University, AdmissionRequirements

class TestDBWriter(unittest.TestCase):
    def setUp(self):
        # Use a temporary test database
        self.test_db = "test_clawer.db"
        # Create schema in test db
        conn = sqlite3.connect(self.test_db)
        # In modular structure, schema is in crawlernest-schema
        schema_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'crawlernest-schema', 'schema.sql'))
        with open(schema_path, "r") as f:
            conn.executescript(f.read())
        conn.close()
        self.writer = DBWriter(self.test_db)

    def tearDown(self):
        self.writer.close()
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_upsert_university(self):
        uni = University(rank="1", name="Test University", country="Testland")
        uni_id = self.writer.upsert_university(uni)
        self.assertIsInstance(uni_id, int)
        
        # Verify it exists in DB
        self.writer.cur.execute("SELECT display_name FROM universities WHERE university_id = ?", (uni_id,))
        row = self.writer.cur.fetchone()
        self.assertEqual(row[0], "Test University")

    def test_insert_admission_requirements(self):
        uni = University(rank="1", name="Test University", country="Testland")
        uni_id = self.writer.upsert_university(uni)
        
        reqs = AdmissionRequirements(ielts=7.5, gpa=3.8)
        self.writer.insert_admission_requirements(uni_id, reqs)
        
        self.writer.cur.execute("SELECT ielts_min, gpa_min FROM admission_requirements WHERE university_id = ?", (uni_id,))
        row = self.writer.cur.fetchone()
        self.assertEqual(row[0], 7.5)
        self.assertEqual(row[1], 3.8)

if __name__ == '__main__':
    unittest.main()
