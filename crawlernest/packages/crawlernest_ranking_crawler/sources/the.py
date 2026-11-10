from __future__ import annotations

from pathlib import Path

from crawlernest_ranking_crawler.sources.base import RankingSource


class THECrawler(RankingSource):
    """Times Higher Education world rankings. The crawl itself lives in crawlernest-jobs/the_crawler.py."""

    name = "THE"

    def crawl(self, *, year: int, output_dir: Path) -> Path:
        # Imported at call time: crawlernest-jobs is on sys.path where the pipeline runs, not everywhere
        # this package is imported.
        from the_crawler import crawl_the_rankings

        return crawl_the_rankings(year=year, output_dir=output_dir)
