from __future__ import annotations

from crawlernest_admission_crawler.crawlers.example_university import ExampleUniversityCrawler
from crawlernest_admission_crawler.models import AdmissionRecord
from crawlernest_crawler_core.logger import Logger


class AdmissionCrawlerEngine:
    def __init__(self) -> None:
        self.crawlers = [ExampleUniversityCrawler()]

    def run(self) -> list[AdmissionRecord]:
        Logger.info("Starting Admission Crawler Engine")

        all_results: list[AdmissionRecord] = []
        for crawler in self.crawlers:
            all_results.extend(crawler.crawl())

        Logger.info(f"Collected {len(all_results)} admission records")

        # === Crawl Quality Summary Integration ===
        try:
            from crawlernest.interfaces.cli.crawl_quality_summary import print_crawl_quality_summary
        except ModuleNotFoundError:
            from legacy.cli.crawl_quality_summary import print_crawl_quality_summary
        # 假設這裡 all_results 已經有 anomaly/resolution 欄位，否則需 mock summary
        summary = {
            "total_records": len(all_results),
            "anomalies": {
                "input_truncated": sum(1 for r in all_results if getattr(r, 'input_truncated', False)),
                "invalid_ielts": sum(1 for r in all_results if getattr(r, 'invalid_ielts', False)),
                "invalid_toefl": sum(1 for r in all_results if getattr(r, 'invalid_toefl', False)),
                "invalid_gpa": sum(1 for r in all_results if getattr(r, 'invalid_gpa', False)),
                "invalid_deadline": sum(1 for r in all_results if getattr(r, 'invalid_deadline', False)),
                "source_host_mismatch": sum(1 for r in all_results if getattr(r, 'source_host_mismatch', False)),
            },
            "resolution": {
                "suspicious_mapping": sum(1 for r in all_results if getattr(r, 'suspicious_merge', False)),
                "country_mismatch": sum(1 for r in all_results if getattr(r, 'country_mismatch', False)),
                "manual_review": sum(1 for r in all_results if getattr(r, 'manual_review', False)),
            },
        }
        print_crawl_quality_summary(summary)
        return all_results
