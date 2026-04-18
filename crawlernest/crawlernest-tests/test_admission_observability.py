"""Tests for Phase 1 — Crawl & Extract Observability.

Covers:
  - compute_extraction_summary()  — field detection, missing fields, confidence flags, is_usable
  - build_crawl_report()          — aggregate counts, failure_breakdown
  - CrawlReport.write_json()      — JSON output shape
  - build_admission_record()      — extraction_summary attached, crawl_status propagated
  - AdmissionCrawlerEngine        — (records, report) tuple, engine-level warnings
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# ── Path setup ──────────────────────────────────────────────────────────────

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
_CRAWLER_DIR = _REPO_ROOT / "crawlernest-admission-crawler"
_CORE_DIR = _REPO_ROOT / "crawlernest-crawler-core"

for _p in (
    _CRAWLER_DIR,
    _CORE_DIR,
    _CRAWLER_DIR / "crawlers",
    _CRAWLER_DIR / "extractors",
    _CRAWLER_DIR / "site_profiles",
):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

# ── Imports under test ───────────────────────────────────────────────────────

from observability import (
    ExtractionSummary,
    CrawlReport,
    compute_extraction_summary,
    build_crawl_report,
    LANGUAGE_SCORE_FIELDS,
    REQUIRED_ADMISSION_FIELDS,
)
from extractors.admission_requirements import build_admission_record
from models import AdmissionRecord
from engine import AdmissionCrawlerEngine


# ──────────────────────────────────────────────────────────────────────────────
# compute_extraction_summary — happy path
# ──────────────────────────────────────────────────────────────────────────────

class TestComputeExtractionSummaryHappyPath:
    """A successful URL with all required fields."""

    def setup_method(self) -> None:
        self.summary = compute_extraction_summary(
            url="https://example.edu/admissions",
            crawl_status="success",
            requirements={"IELTS": "6.5 overall", "TOEFL": "90 iBT"},
            degree_level="postgraduate",
        )

    def test_url_preserved(self) -> None:
        assert self.summary.url == "https://example.edu/admissions"

    def test_crawl_status_preserved(self) -> None:
        assert self.summary.crawl_status == "success"

    def test_extracted_fields_includes_requirements_and_degree(self) -> None:
        assert "IELTS" in self.summary.extracted_fields
        assert "TOEFL" in self.summary.extracted_fields
        assert "degree_level" in self.summary.extracted_fields

    def test_extracted_fields_count(self) -> None:
        # IELTS + TOEFL + degree_level = 3
        assert self.summary.extracted_fields_count == 3

    def test_has_language_score_true(self) -> None:
        assert self.summary.has_language_score is True

    def test_missing_required_fields_empty(self) -> None:
        assert self.summary.missing_required_fields == []

    def test_is_usable_true(self) -> None:
        assert self.summary.is_usable is True

    def test_confidence_ielts_valid(self) -> None:
        assert self.summary.confidence_flags["IELTS"] is True

    def test_confidence_toefl_valid(self) -> None:
        assert self.summary.confidence_flags["TOEFL"] is True

    def test_confidence_degree_level_valid(self) -> None:
        assert self.summary.confidence_flags["degree_level"] is True


# ──────────────────────────────────────────────────────────────────────────────
# compute_extraction_summary — missing language score
# ──────────────────────────────────────────────────────────────────────────────

class TestComputeExtractionSummaryMissingLanguageScore:
    def setup_method(self) -> None:
        self.summary = compute_extraction_summary(
            url="https://example.edu/admissions",
            crawl_status="success",
            requirements={"GPA": "3.5"},
            degree_level="graduate",
        )

    def test_has_language_score_false(self) -> None:
        assert self.summary.has_language_score is False

    def test_missing_includes_all_language_fields(self) -> None:
        for lang_field in LANGUAGE_SCORE_FIELDS:
            assert lang_field in self.summary.missing_required_fields

    def test_is_usable_false(self) -> None:
        assert self.summary.is_usable is False


# ──────────────────────────────────────────────────────────────────────────────
# compute_extraction_summary — missing degree_level
# ──────────────────────────────────────────────────────────────────────────────

class TestComputeExtractionSummaryMissingDegreeLevel:
    def setup_method(self) -> None:
        self.summary = compute_extraction_summary(
            url="https://example.edu/admissions",
            crawl_status="success",
            requirements={"IELTS": "7.0"},
            degree_level="",
        )

    def test_degree_level_in_missing(self) -> None:
        assert "degree_level" in self.summary.missing_required_fields

    def test_is_usable_false_without_degree(self) -> None:
        assert self.summary.is_usable is False

    def test_degree_level_not_in_extracted(self) -> None:
        assert "degree_level" not in self.summary.extracted_fields


# ──────────────────────────────────────────────────────────────────────────────
# compute_extraction_summary — non-success crawl status
# ──────────────────────────────────────────────────────────────────────────────

class TestComputeExtractionSummaryNonSuccess:
    def test_timeout_not_usable(self) -> None:
        s = compute_extraction_summary(
            url="https://example.edu/admissions",
            crawl_status="timeout",
            requirements={"IELTS": "6.5"},
            degree_level="postgraduate",
        )
        assert s.is_usable is False

    def test_blocked_not_usable(self) -> None:
        s = compute_extraction_summary(
            url="https://example.edu/admissions",
            crawl_status="blocked",
            requirements={"IELTS": "6.5"},
            degree_level="masters",
        )
        assert s.is_usable is False

    def test_empty_not_usable(self) -> None:
        s = compute_extraction_summary(
            url="https://example.edu/admissions",
            crawl_status="empty",
            requirements={},
            degree_level="",
        )
        assert s.is_usable is False


# ──────────────────────────────────────────────────────────────────────────────
# compute_extraction_summary — confidence heuristics
# ──────────────────────────────────────────────────────────────────────────────

class TestConfidenceFlags:
    def test_ielts_low_score_fails(self) -> None:
        s = compute_extraction_summary(
            url="u", crawl_status="success",
            requirements={"IELTS": "2.0"},
            degree_level="postgraduate",
        )
        assert s.confidence_flags["IELTS"] is False

    def test_ielts_high_score_fails(self) -> None:
        s = compute_extraction_summary(
            url="u", crawl_status="success",
            requirements={"IELTS": "10.0"},
            degree_level="postgraduate",
        )
        assert s.confidence_flags["IELTS"] is False

    def test_toefl_too_low_fails(self) -> None:
        s = compute_extraction_summary(
            url="u", crawl_status="success",
            requirements={"TOEFL": "30"},
            degree_level="postgraduate",
        )
        assert s.confidence_flags["TOEFL"] is False

    def test_toefl_120_passes(self) -> None:
        s = compute_extraction_summary(
            url="u", crawl_status="success",
            requirements={"TOEFL": "120"},
            degree_level="postgraduate",
        )
        assert s.confidence_flags["TOEFL"] is True

    def test_unknown_field_non_empty_passes(self) -> None:
        s = compute_extraction_summary(
            url="u", crawl_status="success",
            requirements={"IELTS": "6.5", "some_custom_field": "yes"},
            degree_level="postgraduate",
        )
        assert s.confidence_flags["some_custom_field"] is True

    def test_unknown_field_empty_fails(self) -> None:
        s = compute_extraction_summary(
            url="u", crawl_status="success",
            requirements={"IELTS": "6.5", "some_custom_field": "   "},
            degree_level="postgraduate",
        )
        assert s.confidence_flags["some_custom_field"] is False

    def test_invalid_degree_level_fails(self) -> None:
        s = compute_extraction_summary(
            url="u", crawl_status="success",
            requirements={"IELTS": "6.5"},
            degree_level="space-camp",
        )
        assert s.confidence_flags["degree_level"] is False


# ──────────────────────────────────────────────────────────────────────────────
# build_crawl_report — aggregation
# ──────────────────────────────────────────────────────────────────────────────

def _make_summary(url: str, crawl_status: str = "success", has_lang: bool = True) -> ExtractionSummary:
    reqs = {"IELTS": "6.5"} if has_lang else {}
    return compute_extraction_summary(
        url=url,
        crawl_status=crawl_status,
        requirements=reqs,
        degree_level="postgraduate" if has_lang else "",
    )


class TestBuildCrawlReport:
    def test_total_urls(self) -> None:
        summaries = [_make_summary(f"https://u.edu/{i}") for i in range(3)]
        report = build_crawl_report(
            university_name="Uni X", base_url="https://u.edu", summaries=summaries
        )
        assert report.total_urls == 3

    def test_success_count(self) -> None:
        summaries = [
            _make_summary("https://u.edu/a", crawl_status="success"),
            _make_summary("https://u.edu/b", crawl_status="timeout"),
            _make_summary("https://u.edu/c", crawl_status="blocked"),
        ]
        report = build_crawl_report(
            university_name="Uni X", base_url="https://u.edu", summaries=summaries
        )
        assert report.success_count == 1

    def test_extraction_success_count(self) -> None:
        summaries = [
            _make_summary("https://u.edu/a", crawl_status="success", has_lang=True),
            _make_summary("https://u.edu/b", crawl_status="success", has_lang=False),
        ]
        report = build_crawl_report(
            university_name="Uni X", base_url="https://u.edu", summaries=summaries
        )
        assert report.extraction_success_count == 1

    def test_failure_breakdown(self) -> None:
        summaries = [
            _make_summary("https://u.edu/a", crawl_status="timeout"),
            _make_summary("https://u.edu/b", crawl_status="timeout"),
            _make_summary("https://u.edu/c", crawl_status="blocked"),
        ]
        report = build_crawl_report(
            university_name="Uni X", base_url="https://u.edu", summaries=summaries
        )
        assert report.failure_breakdown["timeout"] == 2
        assert report.failure_breakdown["blocked"] == 1
        assert "success" not in report.failure_breakdown

    def test_warnings_propagated(self) -> None:
        report = build_crawl_report(
            university_name="Uni X",
            base_url="https://u.edu",
            summaries=[],
            warnings=["something odd happened"],
        )
        assert "something odd happened" in report.warnings

    def test_empty_run(self) -> None:
        report = build_crawl_report(
            university_name="Uni X", base_url="https://u.edu", summaries=[]
        )
        assert report.total_urls == 0
        assert report.success_count == 0
        assert report.extraction_success_count == 0
        assert report.failure_breakdown == {}


# ──────────────────────────────────────────────────────────────────────────────
# CrawlReport.write_json — JSON output shape
# ──────────────────────────────────────────────────────────────────────────────

class TestCrawlReportWriteJson:
    def test_json_output_has_required_keys(self) -> None:
        summaries = [_make_summary("https://u.edu/a")]
        report = build_crawl_report(
            university_name="Test University",
            base_url="https://u.edu",
            summaries=summaries,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "report.json"
            written = report.write_json(out_path)
            assert written.exists()
            data = json.loads(written.read_text(encoding="utf-8"))

        for key in (
            "university_name",
            "base_url",
            "total_urls",
            "success_count",
            "extraction_success_count",
            "failure_breakdown",
            "url_results",
            "warnings",
        ):
            assert key in data, f"Missing key: {key}"

    def test_url_results_shape(self) -> None:
        summaries = [_make_summary("https://u.edu/a")]
        report = build_crawl_report(
            university_name="Test University",
            base_url="https://u.edu",
            summaries=summaries,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            data = json.loads(report.write_json(Path(tmpdir) / "r.json").read_text())

        assert len(data["url_results"]) == 1
        row = data["url_results"][0]
        for key in (
            "url", "crawl_status", "extracted_fields", "extracted_fields_count",
            "missing_required_fields", "has_language_score", "confidence_flags", "is_usable",
        ):
            assert key in row, f"url_results row missing key: {key}"

    def test_creates_parent_directories(self) -> None:
        summaries = [_make_summary("https://u.edu/a")]
        report = build_crawl_report(
            university_name="Test University",
            base_url="https://u.edu",
            summaries=summaries,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = Path(tmpdir) / "deep" / "nested" / "report.json"
            written = report.write_json(nested)
            assert written.exists()


# ──────────────────────────────────────────────────────────────────────────────
# build_admission_record — integration between extractor and observability
# ──────────────────────────────────────────────────────────────────────────────

class TestBuildAdmissionRecord:
    def test_extraction_summary_attached(self) -> None:
        rec = build_admission_record(
            university_name="University of Melbourne",
            source_url="https://unimelb.edu.au/admissions",
            degree_level="postgraduate",
            requirements={"IELTS": "6.5 overall", "TOEFL": "90 iBT"},
        )
        assert rec.extraction_summary is not None

    def test_crawl_status_default_success(self) -> None:
        rec = build_admission_record(
            university_name="Uni",
            source_url="https://u.edu/a",
            degree_level="masters",
            requirements={"IELTS": "7.0"},
        )
        assert rec.crawl_status == "success"
        assert rec.extraction_summary.crawl_status == "success"

    def test_crawl_status_timeout_propagated(self) -> None:
        rec = build_admission_record(
            university_name="Uni",
            source_url="https://u.edu/a",
            degree_level="",
            requirements={},
            crawl_status="timeout",
        )
        assert rec.crawl_status == "timeout"
        assert rec.extraction_summary.crawl_status == "timeout"
        assert rec.extraction_summary.is_usable is False

    def test_summary_url_matches_source_url(self) -> None:
        url = "https://u.edu/admissions/postgrad"
        rec = build_admission_record(
            university_name="Uni",
            source_url=url,
            degree_level="postgraduate",
            requirements={"IELTS": "6.5"},
        )
        assert rec.extraction_summary.url == url

    def test_is_usable_false_when_no_language_score(self) -> None:
        rec = build_admission_record(
            university_name="Uni",
            source_url="https://u.edu/a",
            degree_level="bachelor",
            requirements={"GPA": "3.5"},
        )
        assert rec.extraction_summary.is_usable is False


# ──────────────────────────────────────────────────────────────────────────────
# AdmissionCrawlerEngine — returns (records, report) tuple
# ──────────────────────────────────────────────────────────────────────────────

class TestAdmissionCrawlerEngine:
    """Tests for AdmissionCrawlerEngine using snapshot HTML.

    The engine now performs real HTTP crawling — tests must provide a
    snapshot_dir containing pre-fetched HTML so they run offline without
    depending on live network access.

    The snapshot used here is the Melbourne ELR page which has IELTS, TOEFL,
    Duolingo, GPA, deadline, and degree_level — a fully usable record.
    """

    def setup_method(self) -> None:
        # Locate the crawl_snapshots directory relative to this test file.
        _repo_root = _TESTS_DIR.parent
        self._snapshot_dir = _repo_root / "crawlernest-admission-crawler" / "crawl_snapshots"

        self.engine = AdmissionCrawlerEngine(snapshot_dir=self._snapshot_dir)
        # Use the Melbourne profile — its primary URL has a matching snapshot.
        self.records, self.report = self.engine.crawl_university(
            university_name="University of Melbourne",
            base_url="https://study.unimelb.edu.au",
            candidate_urls=[
                "https://study.unimelb.edu.au/admissions/english-language-requirements",
            ],
        )

    def test_returns_tuple(self) -> None:
        assert isinstance(self.records, list)
        assert isinstance(self.report, CrawlReport)

    def test_records_not_empty(self) -> None:
        assert len(self.records) >= 1

    def test_each_record_has_extraction_summary(self) -> None:
        for rec in self.records:
            assert rec.extraction_summary is not None, (
                f"Record {rec.source_url!r} is missing extraction_summary"
            )

    def test_report_total_equals_record_count(self) -> None:
        assert self.report.total_urls == len(self.records)

    def test_report_university_name(self) -> None:
        assert self.report.university_name == "University of Melbourne"

    def test_snapshot_produces_usable_record(self) -> None:
        # Melbourne snapshot has IELTS + degree_level → must be usable.
        assert self.report.extraction_success_count >= 1

    def test_no_engine_warnings_for_snapshot(self) -> None:
        # All records were built via build_admission_record(), so no warnings.
        assert self.report.warnings == []

    def test_report_written_to_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "report.json"
            _, report = self.engine.crawl_university(
                university_name="Test Uni",
                base_url="https://test.edu",
                candidate_urls=[
                    "https://study.unimelb.edu.au/admissions/english-language-requirements",
                ],
                report_path=out,
            )
            assert out.exists()
            data = json.loads(out.read_text())
            assert data["university_name"] == "Test Uni"


# ──────────────────────────────────────────────────────────────────────────────
# Run with pytest or directly
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
