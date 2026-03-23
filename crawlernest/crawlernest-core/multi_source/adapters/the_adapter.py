from __future__ import annotations

from typing import Any, Iterable

from ..types import StandardizedRankingRecord
from .base_adapter import BaseSourceAdapter


class THEAdapter(BaseSourceAdapter):
    """
    Stub adapter for THE.
    Expected payload item shape (dict):
    {
      "id": "...",
      "name": "...",
      "country": "...",
      "year": 2026,
      "rank": 25,
      "score": 91.2,
      "url": "..."
    }
    """

    source_code = "THE"

    def __init__(self, default_year: int, ranking_type: str = "world", source_version: str | None = None):
        self.default_year = int(default_year)
        self.ranking_type = ranking_type
        self.source_version = source_version

    def adapt(self, payload: Iterable[Any]) -> list[StandardizedRankingRecord]:
        out: list[StandardizedRankingRecord] = []
        for row in payload:
            if not isinstance(row, dict):
                continue
            out.append(
                StandardizedRankingRecord(
                    source=self.source_code,
                    source_entity_id=str(row.get("id") or row.get("url") or row.get("name") or "").strip(),
                    university_name=str(row.get("name") or "").strip(),
                    country_hint=_to_opt_str(row.get("country")),
                    ranking_year=int(row.get("year") or self.default_year),
                    ranking_type=str(row.get("ranking_type") or self.ranking_type),
                    rank=_safe_int(row.get("rank")),
                    score=_safe_float(row.get("score")),
                    source_url=_to_opt_str(row.get("url")),
                    source_version=self.source_version,
                    metadata={"raw_source": "THE"},
                )
            )
        return [r for r in out if r.source_entity_id and r.university_name]


def _to_opt_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _safe_int(v: Any) -> int | None:
    try:
        if v is None or str(v).strip() == "":
            return None
        return int(str(v).strip())
    except Exception:
        return None


def _safe_float(v: Any) -> float | None:
    try:
        if v is None or str(v).strip() == "":
            return None
        return float(str(v).strip())
    except Exception:
        return None
