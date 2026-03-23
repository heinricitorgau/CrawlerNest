# Rule-Based Recommendation Engine

## Objective

Recommend universities from canonical entities using deterministic, explainable rules.

This is **not ML**.

## Pipeline Position

```text
aggregated_rankings + admission_requirements -> recommendation_engine -> analytics/API
```

## Stages

1. Hard filters
- country match
- IELTS score must satisfy minimum requirement
- rank must be within target rank

2. Deterministic scoring
- `ranking_score`: better rank => higher score
- `ielts_fit_score`: closer to the required IELTS => higher score
- `completeness_score`: rewards rows with stable ranking/admission coverage

3. Sorting
- sort by `matching_score` descending
- tie-break by better aggregated rank, then canonical id

## Explainability Output

Each result returns:
- `canonical_university_id`
- `university_name`
- `country`
- `aggregated_rank`
- `ielts_min`
- `matching_score`
- `explanation`
- `score_breakdown`

## Design Notes

- Missing IELTS requirement is excluded by default when the user supplies an IELTS score.
- If `preferred_ranking_source` is present and that source rank exists, it is used for the rank constraint and rank-score component.
- If the preferred source rank is missing, the engine falls back to `aggregated_rank`.
- Missing sub-scores do not zero-out the final score; weights are renormalized over available components.

## Recommended Storage

Use `recommendation_postgresql.sql` to create:
- `warehouse.canonical_university_link`
- `analytics.recommendation_runs`
- `analytics.recommendation_results`
- `analytics.v_recommendation_candidates_latest`

## Core Interface

```python
from recommendation_engine import (
    RecommendationQuery,
    default_recommendation_config,
    recommend_universities,
)

results = recommend_universities(candidates, RecommendationQuery(country="UK", ielts_score=6.5, target_rank=100))
```
