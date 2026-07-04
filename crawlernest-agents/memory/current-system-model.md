# CrawlerNest Current System Model

Source basis:
- `README.md`
- `agents/crawlernest-data-pipeline-engineer.md`
- `agents/crawlernest-workflow-architect.md`
- `agents/crawlernest-debug-reliability-engineer.md`
- `agents/crawlernest-postgres-optimizer.md`
- Existing `memory/*.md`

Inspection limit:
- This repository is `crawlernest-agents`, an AI-assisted development system for CrawlerNest.
- It does not contain the full CrawlerNest application implementation.
- Treat this model as the current agent-side engineering memory, not proof that every runtime module is complete or production-stable.

## 1. Current System Model

CrawlerNest is a structured data infrastructure system for university intelligence.

Core pipeline:

```text
crawler -> extractor -> normalization -> db_writer -> analytics -> recommendation
```

Confirmed project characteristics:
- Evolving MVP, not fully production-stable.
- Data-first, I/O-bound, pipeline-oriented system.
- PostgreSQL is the primary target database.
- `run_pipeline.py` is the main orchestration entry point.
- Common components include `extractor`, `db_writer`, `exporter`, and `recommendation_engine`.
- Named modules include `crawlernest-core`, `crawlernest-api`, `crawlernest-analytics`, `crawlernest-autoeval`, and `crawlernest-cli`.

Stage model:
- `crawler`: collects upstream university/ranking/admission data from external sources.
- `extractor`: parses source content into structured fields; must handle missing or changed fields.
- `normalization`: turns extracted data into consistent internal representations; rules must be explicit and traceable.
- `db_writer`: persists raw/staging/canonical data into PostgreSQL; must protect idempotency and avoid partial-write ambiguity.
- `analytics`: reads persisted data to produce derived views, summaries, or warehouse-ready outputs.
- `recommendation`: consumes trusted persisted/derived data for filtering, scoring, or recommendation output.
- `pipeline orchestration`: `run_pipeline.py` coordinates stage order, reruns, backfills, and failure boundaries.

## 2. Data Flow

Primary flow:

```text
crawler
  -> extractor
  -> normalization
  -> db_writer
  -> analytics
  -> recommendation
```

Expected behavior:
- Data should remain traceable from source input to normalized and persisted output.
- Each stage should have explicit inputs, outputs, and failure handling.
- Pipeline outputs must be trustworthy before analytics or recommendations use them.
- Recommendation quality depends on upstream extraction, normalization, and database correctness.

Fallback:
- Fallback behavior is a known concern, especially for 403/degraded-source cases.
- Fallback must not silently hide bad or incomplete data.
- If fallback produces degraded output, downstream stages should expose confidence gaps or missing fields.

Deferred enrichment:
- Deferred enrichment is a recognized pattern for later-stage completion.
- Deferred work must preserve enough source/context to be replayed or completed later.
- Deferred items should not be mistaken for fully complete records.

Pipeline failure behavior:
- Partial runs and partial writes are known reliability risks.
- Checkpoints, transactions, or replay-safe writes are preferred where data could be duplicated or corrupted.
- Failures should identify the stage boundary: source, parser, normalizer, database, API, analytics, or recommendation.
- Debugging should collect concrete evidence before claiming readiness.

## 3. Module Responsibilities

### `crawlernest-core`

Should do:
- Own core pipeline logic and shared domain contracts.
- Contain crawler, extractor, normalization, persistence-facing logic, or shared interfaces used by those stages.
- Keep source-to-output behavior traceable.

Should not do:
- Hide source-specific parsing rules as undocumented magic.
- Mix API presentation concerns with low-level pipeline correctness.
- Assume upstream data fields are always present.

### `crawlernest-api`

Should do:
- Expose application/service interfaces over trusted persisted or derived data.
- Keep request/response behavior separate from batch pipeline execution.
- Surface errors or incomplete data truthfully.

Should not do:
- Own crawler/extractor implementation details.
- Mask pipeline failures as successful API responses.
- Perform expensive batch backfills synchronously unless explicitly designed.

### `crawlernest-analytics`

Should do:
- Produce analytics-ready outputs from persisted data.
- Make data quality, counts, and aggregation assumptions visible.
- Depend on clear raw/staging/canonical boundaries.

Should not do:
- Correct upstream extraction bugs silently.
- Treat partial or deferred records as complete without marking them.
- Become the place where normalization rules are invented ad hoc.

### `crawlernest-autoeval`

Should do:
- Evaluate pipeline, extraction, recommendation, or data-quality behavior.
- Provide repeatable checks that catch regressions and silent correctness failures.

Should not do:
- Be treated as proof of production readiness without meaningful coverage.
- Replace manual investigation when logs or evidence are incomplete.

### `crawlernest-cli`

Should do:
- Provide operator entry points for pipeline runs, backfills, diagnostics, and local workflows.
- Make commands explicit about which stage or workflow they trigger.

Should not do:
- Hide complex multi-stage side effects behind unclear commands.
- Bypass validation, checkpoints, or idempotency protections.

## 4. Known Constraints

- This is an evolving MVP.
- Do not claim the system is production-ready unless current evidence proves it.
- Do not assume every module is stable or complete.
- Pipeline behavior may be unstable, partial, or under-instrumented.
- Data correctness is more important than architecture elegance.
- Practical working pipeline fixes beat speculative redesign.
- PostgreSQL schema, constraints, query patterns, and migrations must be treated as correctness and reliability concerns.

## 5. Correction of Previous Assumptions

Wrong assumptions to avoid:
- "The system is production-ready." Wrong: current docs explicitly say evolving MVP and not fully production-stable.
- "All modules are implemented and stable." Wrong: this repo documents agent-side understanding, not full application implementation.
- "The happy path is enough." Wrong: workflow docs require fallback, retries, checkpoints, handoffs, and failure paths.
- "Recommendations can be debugged independently." Wrong: recommendation behavior depends on crawler, extractor, normalization, and database correctness.
- "Fallback success means data is correct." Wrong: fallback can be degraded and must expose quality gaps.
- "Analytics can fix upstream data." Wrong: analytics should consume trustworthy data and reveal quality issues, not hide extraction or normalization bugs.
- "Elegant architecture is the priority." Wrong: data correctness and practical operability come first.

## 6. Updated Behavior Rules

Future CrawlerNest agent behavior:
- Start by checking existing memory and docs before proposing fixes.
- Do not assume the system is complete, stable, or production-ready.
- Prefer debug and evidence collection over design speculation.
- Keep recommendations scoped to the smallest working correction.
- Trace failures through the actual data path: crawler, extractor, normalization, db_writer, analytics, recommendation.
- Name the boundary where evidence stops.
- Treat missing fields, partial writes, fallback, deferred enrichment, and idempotency as first-class risks.
- Do not over-architect; improve the working pipeline first.
- When new incidents reveal reusable lessons, record them in memory with context, root cause, fix, verification, and prevention rules.

## 7. Operational Debug Heuristics

These are action rules, not descriptions.

### Rule 1 — Missing or empty fields
- Likely cause: extractor
- Do NOT fix in analytics or recommendation
- First check: selector / parsing logic

---

### Rule 2 — Record count mismatch
- Likely cause: db_writer partial write
- First check:
  - transaction usage
  - batch insert boundary
  - checkpoint logic

---

### Rule 3 — Pipeline crash after partial success
- Risk: duplicated or inconsistent data
- First check:
  - rerun safety
  - idempotency
  - upsert logic

---

### Rule 4 — Recommendation looks wrong
- Do NOT debug recommendation first
- First check:
  - analytics output
  - upstream data completeness

---

### Rule 5 — Data inconsistency across modules
- Trace backwards:
  recommendation → analytics → db_writer → extractor → crawler

---

### Rule 6 — Unexpected null / missing optional fields
- Treat as valid case, not error
- Fix should be in normalization or schema design

---

### Rule 7 — Upstream source change (site layout / API)
- Likely impact:
  - extractor break
  - schema drift
- Do NOT assume system bug before verifying source change