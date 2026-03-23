from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class StandardizedRankingRecord:
    source: str  # QS/THE/ARWU
    source_entity_id: str
    university_name: str
    country_hint: Optional[str]
    ranking_year: int
    ranking_type: str
    rank: Optional[int]
    score: Optional[float]
    source_url: Optional[str] = None
    source_version: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UnifiedRankingRecord:
    canonical_university_id: Optional[int]
    source: str
    source_entity_id: str
    rank: Optional[int]
    score: Optional[float]
    year: int
    ranking_type: str
    matched_alias: Optional[str]
    confidence_score: float
    matching_method: str
    source_url: Optional[str] = None
    source_version: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
