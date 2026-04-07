# CrawlerNest Entity Resolution

## Pipeline Position

```
crawler -> extractor -> normalization -> entity_resolution -> db_writer
```

Entity resolution takes normalized source records and returns canonical IDs plus matching metadata.

## Staged Matching Strategy

1. `exact`
- lookup by exact alias text (O(1) hash lookup)
- highest precision, lowest latency

2. `normalized`
- normalize case/punctuation/abbreviations and compare exact normalized key
- high precision, robust to formatting differences

3. `fuzzy`
- candidate blocking by token and optional country
- scoring: `0.75 * SequenceMatcher + 0.25 * token_jaccard`
- accepts only over configurable threshold

4. `embedding` (optional plugin)
- pluggable function for semantic similarity
- suitable for multilingual/noisy aliases, but slower and costlier

## Threshold Design

Default thresholds (`ResolverThresholds`):

- `fuzzy_accept = 0.93`
- `fuzzy_review = 0.88`
- `embedding_accept = 0.90`
- `embedding_review = 0.84`

Guideline:

- Above `*_accept`: auto-accept
- Between `*_review` and `*_accept`: mark for manual review
- Below `*_review`: unresolved

## Performance Notes

- No full pairwise O(N^2) comparisons
- Blocking by normalized tokens (and country when provided)
- Candidate cap (`max_fuzzy_candidates`) to bound worst-case latency
- Recommended DB indexes:
  - `alias_normalized` btree
  - trigram GIN on alias text/normalized alias
  - `(source_name, source_entity_id)` unique mapping index

## Function Interfaces

Core interfaces:

- `EntityResolver.resolve_one(record: EntityRecord) -> ResolutionResult`
- `EntityResolver.resolve_batch(records: list[EntityRecord]) -> list[ResolutionResult]`
- `EntityResolutionRepository.load_canonical_profiles() -> list[CanonicalProfile]`
- `EntityResolutionRepository.upsert_source_mapping(result, threshold_used)`
- `EntityResolutionRepository.log_resolution_event(...)`

## Integration Example

```python
from entity_resolution import EntityRecord, EntityResolver

records = [
    EntityRecord(source_name="QS", source_entity_id="nid:123", university_name="MIT", country_hint="united states"),
]

results = resolver.resolve_batch(records)
for r in results:
    # write mapping and event logs
    repo.upsert_source_mapping(r, threshold_used=0.93)
    repo.log_resolution_event(
        source_name=r.source_name,
        source_entity_id=r.source_entity_id,
        raw_name=records[0].university_name,
        country_hint=records[0].country_hint,
        result=r,
    )
```
