"""QS ranking source stub."""

from __future__ import annotations

import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
ENGINE_DIR = CURRENT_DIR.parent
CORE_DIR = ENGINE_DIR.parent / "crawlernest-crawler-core"
for path in (ENGINE_DIR, CORE_DIR):
    str_path = str(path)
    if str_path not in sys.path:
        sys.path.insert(0, str_path)

from base import BaseCrawler
from extractors.ranking_rows import to_ranking_records
from models import RankingRecord


class QSCrawler(BaseCrawler):
    """Minimal QS crawler returning mock ranking rows."""

    def __init__(self) -> None:
        super().__init__(name="crawlernest.ranking.qs")

    def crawl(self, *, ranking_year: int, universe_type: str, universe_key: str) -> list[RankingRecord]:
        self.logger.info(
            "Running QS crawl stub for year=%s universe=%s/%s",
            ranking_year,
            universe_type,
            universe_key,
        )
        mock_rows = [
            {
                "source": "QS",
                "ranking_year": ranking_year,
                "universe_type": universe_type,
                "universe_key": universe_key,
                "institution_name": "Massachusetts Institute of Technology",
                "country": "United States",
                "rank": 1,
                "score": 99.8,
            },
            {
                "source": "QS",
                "ranking_year": ranking_year,
                "universe_type": universe_type,
                "universe_key": universe_key,
                "institution_name": "Imperial College London",
                "country": "United Kingdom",
                "rank": 2,
                "score": 98.5,
            },
        ]
        return to_ranking_records(mock_rows)
