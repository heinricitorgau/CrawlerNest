from __future__ import annotations

from typing import Any, Iterable

from ..types import StandardizedRankingRecord
from .base_adapter import BaseSourceAdapter


class THEAdapter(BaseSourceAdapter):
    """Adapter for normalized THE ranking rows."""

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
            metadata = dict(row.get("metadata") or {})
            score = self._extract_score(row)
            source_entity_id = self._to_optional_str(
                row.get("id")
                or row.get("source_entity_id")
                or row.get("url")
                or row.get("profile_url")
                or row.get("slug")
                or row.get("name")
                or row.get("university_name")
            )
            university_name = self._to_optional_str(
                row.get("name") or row.get("university_name") or row.get("institution") or row.get("school")
            )
            out.append(
                StandardizedRankingRecord(
                    source=self.source_code,
                    source_entity_id=source_entity_id or "",
                    university_name=university_name or "",
                    country_hint=self._to_optional_str(row.get("country") or row.get("location")),
                    ranking_year=int(row.get("year") or self.default_year),
                    ranking_type=str(row.get("ranking_type") or self.ranking_type),
                    rank=self._safe_int(row.get("rank") or row.get("rank_position") or row.get("overall_rank")),
                    score=score,
                    source_url=self._to_optional_str(row.get("url") or row.get("profile_url")),
                    source_version=self.source_version,
                    metadata={
                        "raw_source": "THE",
                        **metadata,
                    },
                )
            )
        return [r for r in out if r.source_entity_id and r.university_name]

    def _extract_score(self, row: dict[str, Any]) -> float | None:
        direct = row.get("score") or row.get("overall_score") or row.get("scores_overall")
        if direct is not None:
            return self._safe_float(direct)
        scores = row.get("scores")
        if isinstance(scores, dict):
            return self._safe_float(scores.get("overall") or scores.get("overall_score") or scores.get("total"))
        return None
