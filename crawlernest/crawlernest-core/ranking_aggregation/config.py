from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AggregationConfig:
    """
    Deterministic aggregation config:
    - source_weights: configurable source importance
    - source_score_scales: optional explicit raw score max (e.g. 100)
    - source_rank_fallback_max: fallback max rank when observed max unavailable
    - score_rank_blend: if both score+rank exist -> blended normalized score
    """

    aggregation_method_version: str = "rank_agg_v1"
    source_weights: dict[str, float] = field(default_factory=dict)
    source_score_scales: dict[str, float] = field(default_factory=dict)
    source_rank_fallback_max: dict[str, int] = field(default_factory=dict)
    score_rank_blend: float = 0.7
    tie_epsilon: float = 1e-9


def default_aggregation_config() -> AggregationConfig:
    return AggregationConfig(
        aggregation_method_version="rank_agg_v1",
        source_weights={
            "QS": 0.40,
            "THE": 0.35,
            "ARWU": 0.25,
        },
        source_score_scales={
            "QS": 100.0,
            "THE": 100.0,
            # ARWU often lacks direct comparable score in some feeds; keep optional.
        },
        source_rank_fallback_max={
            "QS": 1500,
            "THE": 2000,
            "ARWU": 1000,
        },
        score_rank_blend=0.7,
        tie_epsilon=1e-9,
    )
