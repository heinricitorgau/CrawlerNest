from __future__ import annotations

from pathlib import Path
from typing import Iterable

from crawlernest_admission_crawler.crawl_bridge import (
    CrawlBridgeSummary,
    crawl_admission_records,
)
from crawlernest_admission_crawler.models import AdmissionRecord
from crawlernest_crawler_core.logger import Logger

#: The HTML checked in beside the crawler. Used unless a caller explicitly
#: asks to go live.
DEFAULT_SNAPSHOT_DIR = (
    Path(__file__).resolve().parent.parent
    / "crawlernest"
    / "crawlernest-admission-crawler"
    / "crawl_snapshots"
)


class AdmissionCrawlerEngine:
    """Produce admission records for the staging pipeline.

    This used to return one hardcoded MIT record from ExampleUniversityCrawler,
    because nothing connected it to the crawler that actually reads university
    pages. It now drives that crawler through crawl_bridge.

    **Offline by default.** Constructing this and calling run() reads the
    checked-in HTML snapshots. Going out to real university websites takes
    ``live=True`` and is never something a caller does by accident -- the
    previous default sent tests and any bare ``AdmissionCrawlerEngine()`` at
    live sites, which took five minutes and put load on eight universities.
    """

    def __init__(
        self,
        *,
        snapshot_dir: Path | None = None,
        live: bool = False,
        only: Iterable[str] | None = None,
        rate_limit_seconds: float = 1.0,
    ) -> None:
        if live and snapshot_dir is not None:
            raise ValueError("pass either live=True or snapshot_dir, not both")
        self.snapshot_dir = None if live else (snapshot_dir or DEFAULT_SNAPSHOT_DIR)
        self.only = list(only) if only is not None else None
        self.rate_limit_seconds = rate_limit_seconds
        self.last_summary: CrawlBridgeSummary | None = None

    def run(self) -> list[AdmissionRecord]:
        mode = "snapshot" if self.snapshot_dir else "live HTTP"
        Logger.info(f"Starting Admission Crawler Engine ({mode})")

        records, summary = crawl_admission_records(
            snapshot_dir=self.snapshot_dir,
            only=self.only,
            rate_limit_seconds=self.rate_limit_seconds,
        )
        self.last_summary = summary

        Logger.info(
            f"Collected {summary.usable_record_count} admission records from "
            f"{summary.urls_attempted} URLs across "
            f"{summary.universities_attempted} universities"
        )
        if summary.skipped_record_count:
            Logger.info(
                f"Skipped {summary.skipped_record_count} unusable page(s): "
                f"{summary.skipped_by_status}"
            )

        self._print_quality_summary(records, summary)
        return records

    @staticmethod
    def _print_quality_summary(
        records: list[AdmissionRecord],
        summary: CrawlBridgeSummary,
    ) -> None:
        """Report what the crawl produced, counting real flags.

        The anomaly counts used to read attributes that AdmissionRecord has
        never had, so every one of them reported zero regardless of what the
        crawl found. They now come from the flagged_fields the extractor
        actually set, which is where the crawler records a value it rejected.
        """
        try:
            from crawlernest.interfaces.cli.crawl_quality_summary import print_crawl_quality_summary
        except ModuleNotFoundError:
            try:
                from legacy.cli.crawl_quality_summary import print_crawl_quality_summary
            except ModuleNotFoundError:  # pragma: no cover - reporting is optional
                return

        flags: list[str] = []
        for record in records:
            payload = record.raw_payload or {}
            flags.extend(payload.get("flagged_fields", []))

        print_crawl_quality_summary(
            {
                "total_records": len(records),
                "anomalies": {
                    "input_truncated": sum(
                        1 for r in records if (r.raw_payload or {}).get("input_truncated")
                    ),
                    "invalid_ielts": flags.count("invalid_ielts"),
                    "invalid_toefl": flags.count("invalid_toefl"),
                    "invalid_duolingo": flags.count("invalid_duolingo"),
                    "invalid_gpa": flags.count("invalid_gpa"),
                    "invalid_deadline": flags.count("invalid_deadline"),
                    "invalid_degree_level": flags.count("invalid_degree_level"),
                    "source_host_mismatch": flags.count("source_host_mismatch"),
                },
                # The printer renders exactly two sections, "anomalies"
                # and "resolution". Naming this anything else prints an
                # empty heading, which is what it did before.
                "resolution": {
                    "pages_attempted": summary.urls_attempted,
                    "pages_usable": summary.usable_record_count,
                    **summary.skipped_by_status,
                },
            }
        )
