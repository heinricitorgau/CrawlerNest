"""Ranking crawler engine entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
CORE_DIR = CURRENT_DIR.parent / "crawlernest-crawler-core"
for path in (CURRENT_DIR, CORE_DIR, CURRENT_DIR / "sources", CURRENT_DIR / "extractors"):
    str_path = str(path)
    if str_path not in sys.path:
        sys.path.insert(0, str_path)

from logger import get_logger
from models import RankingRecord
from sources.arwu import ARWUCrawler
from sources.qs import QSCrawler
from sources.the import THECrawler


class RankingCrawlerEngine:
    """Coordinates source-specific ranking crawlers."""

    def __init__(self) -> None:
        self.logger = get_logger("crawlernest.ranking.engine")
        self.sources = {
            "qs": QSCrawler(),
            "the": THECrawler(),
            "arwu": ARWUCrawler(),
        }

    def crawl_source(
        self,
        source_name: str,
        *,
        ranking_year: int,
        universe_type: str = "global",
        universe_key: str = "global",
    ) -> list[RankingRecord]:
        source_key = source_name.lower()
        if source_key not in self.sources:
            raise ValueError(f"Unsupported ranking source: {source_name}")

        self.logger.info("Starting ranking crawl for source=%s", source_key)
        records = self.sources[source_key].crawl(
            ranking_year=ranking_year,
            universe_type=universe_type,
            universe_key=universe_key,
        )
        self.logger.info("Produced %s ranking records", len(records))
        return records


def main() -> None:
    engine = RankingCrawlerEngine()
    records = engine.crawl_source(
        "qs",
        ranking_year=2026,
        universe_type="global",
        universe_key="global",
    )
    for record in records:
        print(record)


if __name__ == "__main__":
    main()
