"""Admission crawler engine entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
CORE_DIR = CURRENT_DIR.parent / "crawlernest-crawler-core"
for path in (
    CURRENT_DIR,
    CORE_DIR,
    CURRENT_DIR / "crawlers",
    CURRENT_DIR / "extractors",
    CURRENT_DIR / "site_profiles",
):
    str_path = str(path)
    if str_path not in sys.path:
        sys.path.insert(0, str_path)

from crawlers.university_site import UniversityAdmissionCrawler
from logger import get_logger
from models import AdmissionRecord
from observability import CrawlReport, ExtractionSummary, build_crawl_report


class AdmissionCrawlerEngine:
    """Coordinates admission crawlers for university websites.

    Args:
        snapshot_dir: When set, passed to :class:`UniversityAdmissionCrawler`
            so it reads HTML from local files instead of making live HTTP
            requests.  Useful for testing and CI environments without outbound
            network access.
    """

    def __init__(self, *, snapshot_dir: Path | str | None = None) -> None:
        self.logger = get_logger("crawlernest.admission.engine")
        self.crawlers = {
            "default_university_site": UniversityAdmissionCrawler(
                snapshot_dir=snapshot_dir
            ),
        }

    def crawl_university(
        self,
        *,
        university_name: str,
        base_url: str,
        candidate_urls: list[str] | None = None,
        report_path: Path | str | None = None,
    ) -> tuple[list[AdmissionRecord], CrawlReport]:
        """Crawl admission data for *university_name* and return structured results.

        Args:
            university_name: Display name of the university to crawl.
            base_url: Root URL of the university website.
            candidate_urls: Explicit URL list to crawl.  When ``None``, the
                crawler derives candidates from *base_url*.
            report_path: Optional file path where the :class:`CrawlReport`
                JSON will be written.  Skipped when *None*.

        Returns:
            A 2-tuple ``(records, report)`` where *records* is a list of
            :class:`AdmissionRecord` objects and *report* is the aggregate
            :class:`CrawlReport`.
        """
        crawler = self.crawlers["default_university_site"]
        self.logger.info("Starting admission crawl for %s (%s)", university_name, base_url)

        records = crawler.crawl(
            university_name=university_name,
            base_url=base_url,
            candidate_urls=candidate_urls,
        )

        # Collect per-URL extraction summaries from each record's attached summary.
        summaries: list[ExtractionSummary] = []
        warnings: list[str] = []
        for rec in records:
            if rec.extraction_summary is not None:
                summaries.append(rec.extraction_summary)
            else:
                warnings.append(
                    f"Record for {rec.source_url!r} has no extraction_summary — "
                    "was it built via build_admission_record()?"
                )

        report = build_crawl_report(
            university_name=university_name,
            base_url=base_url,
            summaries=summaries,
            warnings=warnings,
        )

        # Structured log of aggregate results.
        self.logger.info(
            "Crawl complete: total=%d success=%d usable=%d failures=%s anomalies=%s",
            report.total_urls,
            report.success_count,
            report.extraction_success_count,
            report.failure_breakdown,
            report.anomaly_breakdown,
        )

        if report.warnings:
            for warning in report.warnings:
                self.logger.warning("CrawlReport warning: %s", warning)

        if report_path is not None:
            written = report.write_json(report_path)
            self.logger.info("CrawlReport written to %s", written)

        return records, report


def main() -> None:
    engine = AdmissionCrawlerEngine()
    records, report = engine.crawl_university(
        university_name="University of Melbourne",
        base_url="https://study.unimelb.edu.au",
    )
    for record in records:
        print(record)
    print(report.to_dict())


if __name__ == "__main__":
    main()
