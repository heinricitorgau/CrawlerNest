# Operational Vocabulary

This document consolidates operational language used by CrawlerNest reports,
diagnostics, release docs, and agent context artifacts. It does not redefine
runtime API semantics or change any diagnostic behavior.

---

## Terms

| Term | Definition | Notes |
| --- | --- | --- |
| `stale` | Data or evidence is older than the freshness threshold used by the relevant report or diagnostic. | Stale does not imply broken runtime behavior; cached data may still serve. |
| `degraded` | The system remains usable, but one or more quality, coverage, or freshness signals should be explained. | Common for incomplete source coverage or non-blocking warnings. |
| `critical` | A severe operational signal that can block release/demo claims, such as missing aggregation, very old data, major source gaps, or count collapse. | Advisory in reports; no automatic repair is triggered. |
| `unresolved` | Source rows or entities that could not be confidently mapped to canonical university records. | Used for trend and quality visibility, not automatic mutation. |
| `drift` | A material change across snapshots or source evidence, such as count drops, source disappearance, unresolved growth, or warning increases. | Drift can be benign, warning-level, or critical. |
| `freshness` | Age and currency of ingestion, aggregation, source, subject, and snapshot evidence. | Freshness is separate from correctness. |
| `source coverage` | Which expected ranking sources are represented and how many records they contribute. | Baseline expected sources are QS, THE, and ARWU unless a report states otherwise. |
| `aggregation collapse` | Aggregated ranking count drops to zero or falls sharply compared with earlier snapshots. | Critical drift signal; reports observe it only. |
| `snapshot lineage` | The relationship between dated snapshots, `latest_status.json`, derived timeline reports, and release bundle copies. | Lineage is historical evidence, not runtime authority. |
| `release-ready` | Build/test/smoke evidence passes and known data limitations are documented honestly. | Does not require perfect freshness if the demo claim is scoped correctly. |
| `readonly-safe` | A script or report reads evidence and writes generated files only; it does not mutate runtime data or behavior. | File outputs under `reports/`, `snapshots/`, `tmp/`, or `releases/` are allowed when documented. |
| `operational intelligence` | Derived summaries and classifications that help humans understand operational evidence. | Not autonomous repair or decision-making. |
| `validation surface` | The set of scripts, docs, reports, snapshots, and bundle files used to judge release/demo health. | Larger surfaces need indexes and relationship docs to avoid fragmentation. |

---

## Consistency Rules

- Use `stale` for age/freshness problems, not for all failures.
- Use `degraded` when the system is usable but needs a caveat.
- Use `critical` for severe evidence that should block or re-scope a release
  claim.
- Use `drift` only for change over time or change relative to prior evidence.
- Use `unresolved` only for entity/canonical matching gaps.
- Use `readonly-safe` for observation or generated evidence, not for scripts
  that mutate PostgreSQL or pipeline state.

---

## Explicit Boundary

Operational vocabulary is descriptive. It does not authorize:

- automatic pipeline reruns
- source retries
- selector repair
- scoring changes
- recommendation mutation
- autonomous operational decisions
- agent self-modification
