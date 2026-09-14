from __future__ import annotations

from typing import Iterable

from models import University

from ..types import StandardizedRankingRecord
from .base_adapter import BaseSourceAdapter


class QSAdapter(BaseSourceAdapter):
    source_code = "QS"

    def __init__(
        self,
        ranking_year: int,
        ranking_type: str = "world",
        source_version: str | None = None,
        universe_type: str = "global",
        universe_key: str = "global",
    ):
        self.ranking_year = int(ranking_year)
        self.ranking_type = ranking_type
        self.source_version = source_version
        self.universe_type = str(universe_type or "global").strip().lower()
        self.universe_key = str(universe_key or "global").strip().lower()

    def adapt(self, payload: Iterable[University]) -> list[StandardizedRankingRecord]:
        out: list[StandardizedRankingRecord] = []
        for uni in payload:
            source_entity_id = (uni.qs_profile_path or uni.path or uni.name).strip()
            out.append(
                StandardizedRankingRecord(
                    source=self.source_code,
                    source_entity_id=source_entity_id,
                    university_name=uni.name,
                    country_hint=uni.country or None,
                    ranking_year=self.ranking_year,
                    ranking_type=self.ranking_type,
                    rank=self._safe_int(uni.rank),
                    score=self._safe_float((uni.table_metrics or {}).get("Overall Score")),
                    source_url=uni.qs_profile_path or uni.path or None,
                    source_version=self.source_version,
                    universe_type=self.universe_type,
                    universe_key=self.universe_key,
                    metadata={
                        "table_metrics": dict(uni.table_metrics or {}),
                        "universe_type": self.universe_type,
                        "universe_key": self.universe_key,
                        # The printed rank ("=17", "601-610"). rank_position holds
                        # the sort ordinal; a year-over-year delta must read the
                        # band from here or claim precision QS never published.
                        "rank_display": str(getattr(uni, "rank_display", "") or "") or None,
                    },
                )
            )
        return out
