# Ranking Aggregation (Deterministic, Explainable)

## Objective

Combine source-specific rankings (QS/THE/ARWU) into one explainable comparison layer.

This is **not ML**. It is deterministic analytics.

## Pipeline Position

```
crawler -> extractor -> normalize -> entity resolution
-> multi-source integration -> ranking aggregation -> analytics/API
```

## Deterministic Stages

1. Per-source normalization
- if raw score exists: convert to 0-100 using source scale
- if rank exists: convert to 0-100 by rank percentile against source max rank
- if both exist: blended by `score_rank_blend` (default 0.7)

2. Source weighting
- configurable per source
- default:
  - QS: 0.40
  - THE: 0.35
  - ARWU: 0.25

3. Composite score
- weighted average over **available** sources only
- no unfair penalty for missing source rows

4. Display rank
- sort by composite score desc
- dense rank assignment (ties share rank)

## Explainability Output

Per university output includes:

- `canonical_university_id`
- `source_ranks`
- `source_normalized_scores`
- `source_weights_used`
- `composite_score`
- `display_rank`
- `aggregation_method_version`
- `coverage_ratio`

## Edge Case Handling

- Missing source data: weighted average renormalizes by used weights
- Tied scores: dense rank
- Rank ranges (`201-250`): midpoint
- Conflicting score scales: source-specific scale config + safe fallback
- Partial year coverage: aggregate per year independently
- Single-source universities: still aggregated, lower `coverage_ratio`

## Core Interface

```python
from ranking_aggregation import aggregate_rankings, default_aggregation_config

outputs = aggregate_rankings(records, config=default_aggregation_config())
```

## Storage

Use `ranking_aggregation_postgresql.sql` tables:

- `analytics.aggregation_runs`
- `analytics.source_weight_config`
- `analytics.aggregated_rankings`

and view:

- `analytics.v_aggregated_rankings_latest`
