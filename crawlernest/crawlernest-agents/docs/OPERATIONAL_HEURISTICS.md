# CrawlerNest Operational Debug Heuristics

These are action rules used by automation-generated prompts.

## Debug Priority Order

1. extractor
2. db_writer
3. pipeline orchestration
4. analytics
5. recommendation

Do not reverse this order unless the log provides strong evidence.

## Rules

### Missing or empty fields

- Likely cause: extractor
- Do not fix in analytics or recommendation first
- First check: selector / parsing logic

### Record count mismatch

- Likely cause: db_writer partial write
- First check:
  - transaction usage
  - batch insert boundary
  - checkpoint logic

### Pipeline crash after partial success

- Risk: duplicated or inconsistent data
- First check:
  - rerun safety
  - idempotency
  - upsert logic

### Wrong recommendation result

- Do not debug recommendation first
- First check:
  - analytics output
  - upstream data completeness

### Data inconsistency across modules

- Trace backwards:
  recommendation -> analytics -> db_writer -> normalization -> extractor -> crawler

### Unexpected null / missing optional fields

- Treat as valid case unless required by contract
- Fix should be in normalization or schema design, not hidden downstream

### Upstream source change

- Likely impact:
  - extractor break
  - schema drift
- Verify source change before assuming internal logic bug
