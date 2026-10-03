from __future__ import annotations

from datetime import datetime, timezone

from crawlernest_ranking_crawler.models import RankingRecord


class QSCrawler:
    def crawl(self) -> list[RankingRecord]:
        extracted_at = datetime.now(timezone.utc)
        return [
            RankingRecord(
                university_name="MIT",
                source="QS",
                rank=1,
                year=2026,
                source_url=None,
                extracted_at=extracted_at,
                raw_payload={
                    "university": "MIT",
                    "rank": 1,
                    "source": "QS",
                    "year": 2026,
                },
            ),
            RankingRecord(
                university_name="Oxford",
                source="QS",
                rank=2,
                year=2026,
                source_url=None,
                extracted_at=extracted_at,
                raw_payload={
                    "university": "Oxford",
                    "rank": 2,
                    "source": "QS",
                    "year": 2026,
                },
            ),
        ]
