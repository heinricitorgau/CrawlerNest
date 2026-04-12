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
        return all_results
