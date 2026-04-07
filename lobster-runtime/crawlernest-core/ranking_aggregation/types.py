from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class RankingRecordInput:
    canonical_university_id: int
    source: str  # QS/THE/ARWU
    year: int
    universe_type: str = "global"
    universe_key: str = "global"
    rank: Optional[Any] = None  # supports int, str range ("201-250"), etc.
    score: Optional[float] = None
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AggregatedRankingOutput:
    canonical_university_id: int
    year: int
    universe_type: str
    universe_key: str
    source_ranks: dict[str, Optional[float]]
    source_normalized_scores: dict[str, Optional[float]]
    source_weights_used: dict[str, float]
    composite_score: Optional[float]
    display_rank: Optional[int]
    coverage_ratio: float
    aggregation_method_version: str
    metadata: dict[str, Any] = field(default_factory=dict)
