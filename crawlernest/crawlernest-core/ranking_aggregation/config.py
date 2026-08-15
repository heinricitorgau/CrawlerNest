from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AggregationConfig:
    """
    Deterministic aggregation config:
    - source_weights: configurable source importance for rank aggregation
    - source_score_scales: optional explicit raw score max (e.g. 100)
    - source_rank_fallback_max: fallback max rank when observed max unavailable
    - composite_score is the weighted normalized rank score and drives rank order
    """

    aggregation_method_version: str = "multi_source_weighted_v1"
    source_weights: dict[str, float] = field(default_factory=dict)
    source_score_scales: dict[str, float] = field(default_factory=dict)
    source_rank_fallback_max: dict[str, int] = field(default_factory=dict)
    tie_epsilon: float = 1e-9


def default_aggregation_config() -> AggregationConfig:
    return AggregationConfig(
        aggregation_method_version="multi_source_weighted_v1",
        # Mirrored by db.analytics_bridge.WEIGHTS, which serves the legacy
        # bridge path; test_analytics_bridge_weights asserts the two agree.
        source_weights={
            "QS": 0.222,
            "THE": 0.654,
            "ARWU": 0.124,
        },
        source_score_scales={},
        source_rank_fallback_max={},
        tie_epsilon=1e-9,
    )
