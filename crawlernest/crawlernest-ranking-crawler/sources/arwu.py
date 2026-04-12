"""ARWU ranking source stub."""

from __future__ import annotations

from models import RankingRecord


class ARWUCrawler:
    """Placeholder crawler for ARWU."""

    source_name = "ARWU"

    def crawl(self, *, ranking_year: int, universe_type: str, universe_key: str) -> list[RankingRecord]:
        _ = (ranking_year, universe_type, universe_key)
        return []
