import unittest
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent

sys.path.insert(0, str(PACKAGE_ROOT / "crawlernest-core"))
sys.path.insert(0, str(PACKAGE_ROOT / "crawlernest-extractors"))

from extractor import DataExtractor, ScoreValidator

class TestScoreValidator(unittest.TestCase):
    def test_ielts_validation(self):
        self.assertTrue(ScoreValidator.is_valid('ielts', 7.0))
        self.assertTrue(ScoreValidator.is_valid('ielts', 9.0))
        self.assertFalse(ScoreValidator.is_valid('ielts', 10.0))

    def test_gpa_validation(self):
        self.assertTrue(ScoreValidator.is_valid('gpa', 3.5))
        self.assertFalse(ScoreValidator.is_valid('gpa', 5.0))

class TestDataExtractor(unittest.TestCase):
    def setUp(self):
        self.extractor = DataExtractor()

    def test_extract_master_section(self):
        html = """
        <html>
            <h2 class="univ-section-title">Postgraduate</h2><p>Target Content</p>
            <h2 class="univ-section-title">Contact Us</h2>
        </html>
        """
        section = self.extractor.extract_master_section(html)
        self.assertIn("Target Content", section)

    def test_extract_requirements(self):
        html = """
        <div class="postgraduate">
            <p>IELTS: 7.5</p>
            <p>GPA: 3.2+</p>
            <p>Application Deadline: Dec 31, 2025</p>
        </div>
        """
        reqs = self.extractor.extract_requirements(html)
        self.assertEqual(reqs.ielts, 7.5)
        self.assertEqual(reqs.gpa, 3.2)
        self.assertEqual(reqs.application_deadline_text, "Dec 31, 2025")

if __name__ == '__main__':
    unittest.main()
