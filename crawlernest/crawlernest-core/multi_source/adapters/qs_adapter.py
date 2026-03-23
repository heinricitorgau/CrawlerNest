from __future__ import annotations

from typing import Iterable

from models import University

from ..types import StandardizedRankingRecord
from .base_adapter import BaseSourceAdapter


class QSAdapter(BaseSourceAdapter):
    source_code = "QS"

    def __init__(self, ranking_year: int, ranking_type: str = "world", source_version: str | None = None):
        self.ranking_year = int(ranking_year)
        self.ranking_type = ranking_type
        self.source_version = source_version

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
                    rank=_safe_int(uni.rank),
                    score=_safe_float((uni.table_metrics or {}).get("Overall Score")),
                    source_url=uni.qs_profile_path or uni.path or None,
                    source_version=self.source_version,
                    metadata={"table_metrics": dict(uni.table_metrics or {})},
                )
            )
        return out


def _safe_int(v: object) -> int | None:
    try:
        if v is None or str(v).strip() == "":
            return None
        return int(str(v).strip())
    except Exception:
        return None


def _safe_float(v: object) -> float | None:
    try:
        if v is None or str(v).strip() == "":
            return None
        return float(str(v).strip())
    except Exception:
        return None
