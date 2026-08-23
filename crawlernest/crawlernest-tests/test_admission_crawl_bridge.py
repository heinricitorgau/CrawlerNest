"""Tests for the crawler-to-pipeline bridge.

The admission crawler extracted IELTS, TOEFL, Duolingo, GPA, deadline and
degree level, wrote a diagnostics report, and dropped every value. The pipeline
meanwhile ran on one hardcoded MIT record. These cover the conversion that
joined them, and the two things that are easy to get wrong once it exists:
letting a page the crawler could not read become a row that claims a
university has no requirements, and letting an "offline" run reach the network.
"""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent
REPO_ROOT = PACKAGE_ROOT.parent

sys.path.insert(0, str(REPO_ROOT))

from crawlernest_admission_crawler.crawl_bridge import (  # noqa: E402
    bridge_summary_to_dict,
    crawl_admission_records,
    to_pipeline_record,
)
from crawlernest_admission_crawler.normalize import normalize_admission_records  # noqa: E402

SNAPSHOT_DIR = PACKAGE_ROOT / "crawlernest-admission-crawler" / "crawl_snapshots"
EXTRACTED_AT = datetime(2026, 8, 22, tzinfo=timezone.utc)


class FakeSummary:
    def __init__(self, *, is_usable=True, flagged_fields=(), input_truncated=False):
        self.is_usable = is_usable
        self.flagged_fields = list(flagged_fields)
        self.input_truncated = input_truncated


class FakeCrawled:
    """The shape crawlers/university_site.py returns."""

    def __init__(self, *, requirements=None, degree_level="postgraduate", crawl_status="success",
                 summary=None, notes=""):
        self.university_name = "University of Oxford"
        self.source_url = "https://www.ox.ac.uk/admissions/graduate/tests"
        self.degree_level = degree_level
        self.requirements = dict(requirements or {})
        self.crawl_status = crawl_status
        self.notes = notes
        self.extraction_summary = summary if summary is not None else FakeSummary()


FULL_REQUIREMENTS = {
    "IELTS": "7.0",
    "TOEFL": "110",
    "Duolingo": "125",
    "GPA": "3.5",
    "deadline": "2025-10-15",
}


class TestFieldConversion(unittest.TestCase):
    def _converted(self, **kwargs):
        return to_pipeline_record(
            FakeCrawled(**kwargs), country="United Kingdom", extracted_at=EXTRACTED_AT
        )

    def test_ielts_becomes_a_float(self):
        self.assertEqual(7.0, self._converted(requirements=FULL_REQUIREMENTS).ielts_requirement)

    def test_toefl_becomes_an_int(self):
        self.assertEqual(110, self._converted(requirements=FULL_REQUIREMENTS).toefl_requirement)

    def test_duolingo_becomes_an_int(self):
        self.assertEqual(125, self._converted(requirements=FULL_REQUIREMENTS).duolingo_requirement)

    def test_gpa_becomes_a_float(self):
        self.assertEqual(3.5, self._converted(requirements=FULL_REQUIREMENTS).gpa_requirement)

    def test_deadline_is_carried_through(self):
        self.assertEqual("2025-10-15", self._converted(requirements=FULL_REQUIREMENTS).application_deadline)

    def test_degree_level_is_carried_through(self):
        self.assertEqual("postgraduate", self._converted(requirements=FULL_REQUIREMENTS).degree_level)

    def test_country_comes_from_the_profile_not_the_page(self):
        # No admission page states its own country; without this the resolver
        # loses country blocking entirely.
        self.assertEqual("United Kingdom", self._converted(requirements=FULL_REQUIREMENTS).country)

    def test_a_missing_field_is_none_not_zero(self):
        record = self._converted(requirements={"TOEFL": "90"})
        self.assertIsNone(record.ielts_requirement)
        self.assertIsNone(record.gpa_requirement)

    def test_an_unparseable_value_is_none(self):
        self.assertIsNone(self._converted(requirements={"IELTS": "n/a"}).ielts_requirement)

    def test_an_empty_degree_level_becomes_none(self):
        # normalize turns None into the 'unknown' the schema requires.
        self.assertIsNone(self._converted(requirements=FULL_REQUIREMENTS, degree_level="").degree_level)


class TestReviewAndAuditPayload(unittest.TestCase):
    def test_crawl_status_travels_with_the_row(self):
        record = to_pipeline_record(
            FakeCrawled(requirements=FULL_REQUIREMENTS), country="UK", extracted_at=EXTRACTED_AT
        )
        self.assertEqual("success", record.raw_payload["crawl_status"])

    def test_flagged_fields_travel_with_the_row(self):
        record = to_pipeline_record(
            FakeCrawled(
                requirements={"TOEFL": "90"},
                summary=FakeSummary(flagged_fields=["invalid_ielts"]),
            ),
            country="UK",
            extracted_at=EXTRACTED_AT,
        )
        self.assertEqual(["invalid_ielts"], record.raw_payload["flagged_fields"])

    def test_clean_extraction_carries_no_flag_key(self):
        record = to_pipeline_record(
            FakeCrawled(requirements=FULL_REQUIREMENTS), country="UK", extracted_at=EXTRACTED_AT
        )
        self.assertNotIn("flagged_fields", record.raw_payload)

    def test_truncated_input_is_recorded(self):
        record = to_pipeline_record(
            FakeCrawled(requirements=FULL_REQUIREMENTS, summary=FakeSummary(input_truncated=True)),
            country="UK",
            extracted_at=EXTRACTED_AT,
        )
        self.assertTrue(record.raw_payload["input_truncated"])


class TestNormalizationAcceptsBridgeOutput(unittest.TestCase):
    """The bridge feeds the existing staging path; the two must agree."""

    def test_a_converted_record_normalizes_into_a_staging_row(self):
        record = to_pipeline_record(
            FakeCrawled(requirements=FULL_REQUIREMENTS), country="United Kingdom",
            extracted_at=EXTRACTED_AT,
        )
        row = normalize_admission_records([record])[0]
        self.assertEqual(7.0, row.ielts_requirement)
        self.assertEqual(125, row.duolingo_requirement)
        self.assertEqual(3.5, row.gpa_requirement)
        self.assertEqual("2025-10-15", row.application_deadline.isoformat())
        self.assertEqual("postgraduate", row.degree_level)

    def test_a_missing_degree_level_normalizes_to_unknown(self):
        record = to_pipeline_record(
            FakeCrawled(requirements=FULL_REQUIREMENTS, degree_level=""),
            country="UK",
            extracted_at=EXTRACTED_AT,
        )
        # NOT NULL in the schema, and half of the natural key.
        self.assertEqual("unknown", normalize_admission_records([record])[0].degree_level)


@unittest.skipUnless(SNAPSHOT_DIR.is_dir(), "checked-in snapshots are required")
class TestOfflineCrawl(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records, cls.summary = crawl_admission_records(snapshot_dir=SNAPSHOT_DIR)

    def test_the_snapshots_produce_records(self):
        self.assertTrue(self.records)

    def test_only_urls_with_a_snapshot_are_attempted(self):
        # The crawler falls back to live HTTP for any URL it has no snapshot
        # for, so a snapshot run that counted every candidate URL would be
        # putting requests on the wire.
        self.assertEqual(self.summary.usable_record_count, self.summary.urls_attempted)

    def test_urls_without_a_snapshot_are_reported_not_hidden(self):
        self.assertIn("no_snapshot", self.summary.skipped_by_status)

    def test_every_record_carries_a_country(self):
        self.assertTrue(all(record.country for record in self.records))

    def test_records_carry_real_extracted_values(self):
        self.assertTrue(any(r.ielts_requirement is not None for r in self.records))
        self.assertTrue(any(r.toefl_requirement is not None for r in self.records))
        self.assertTrue(any(r.application_deadline is not None for r in self.records))

    def test_summary_is_serialisable(self):
        payload = bridge_summary_to_dict(self.summary)
        self.assertEqual(len(self.records), payload["usable_record_count"])


if __name__ == "__main__":
    unittest.main()
