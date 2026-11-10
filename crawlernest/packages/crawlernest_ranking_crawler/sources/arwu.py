from __future__ import annotations

from pathlib import Path

from crawlernest_ranking_crawler.sources.base import RankingSource


class ARWUCrawler(RankingSource):
    """ShanghaiRanking's ARWU world rankings. The crawl itself lives in crawlernest-jobs/arwu_crawler.py."""

    name = "ARWU"

    def crawl(self, *, year: int, output_dir: Path) -> Path:
        # Imported at call time, for the same reason as THECrawler.
        from arwu_crawler import crawl_arwu_rankings

        return crawl_arwu_rankings(year=year, output_dir=output_dir)
