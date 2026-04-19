# Multi-Source Integration (QS / THE / ARWU)

## Architecture

```
crawler -> extractor -> normalize -> entity_resolution -> multi_source_merge -> db
```

### Source abstraction

- `adapters/base_adapter.py`: base interface
- `adapters/qs_adapter.py`: refactored QS adapter
- `adapters/the_adapter.py`: THE adapter stub
- `adapters/arwu_adapter.py`: ARWU adapter stub

All adapters output `StandardizedRankingRecord`.

## Standardized Output

`StandardizedRankingRecord` fields:

- `source`
- `source_entity_id`
- `university_name`
- `country_hint`
- `ranking_year`
- `ranking_type`
- `rank`
- `score`
- `source_url`
- `source_version`

## Merge behavior

- No cross-source overwrite
- QS/THE/ARWU rows are stored independently
- unified link is through `canonical_university_id`

`UnifiedRankingRecord` output contains:

- `canonical_university_id`
- `source`
- `rank`
- `score`
- `year`
- `matching_method`
- `confidence_score`

## Conflict handling

If QS rank != THE rank:

- keep both rows in `ranking_record`
- no overwrite between sources
- future aggregation can consume those rows

## Performance strategy

- De-duplicate resolution keys by `(normalized_name, country_hint)`
- Single batch ER call per unique key
- Candidate-blocked fuzzy matching inside ER module
- DB-side indexes in `multi_source_postgresql.sql`

## Observability

Use analytics tables:

- `analytics.source_ingestion_log`
- `analytics.missing_entity_log`
- `analytics.merge_diagnostics`

## Entry interface

```python
from multi_source import integrate_sources

unified_rows, diagnostics = integrate_sources(records, resolver)
```
