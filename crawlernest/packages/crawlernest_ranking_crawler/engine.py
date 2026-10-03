from __future__ import annotations

from crawlernest_crawler_core.logger import Logger
from crawlernest_ranking_crawler.models import RankingRecord
from crawlernest_ranking_crawler.sources.qs import QSCrawler


class RankingCrawlerEngine:
    def __init__(self) -> None:
        self.sources = [QSCrawler()]

    def run(self) -> list[RankingRecord]:
        Logger.info("Starting Ranking Crawler Engine")

        all_results: list[RankingRecord] = []
        for source in self.sources:
            all_results.extend(source.crawl())

        Logger.info(f"Collected {len(all_results)} ranking records")
        return all_results
