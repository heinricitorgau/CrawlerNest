# CrawlerNest v0.1 — Version Scope

This document defines the precise scope of the v0.1 milestone. Everything listed under "Included" was present and operational at the time of the milestone freeze. Everything listed under "Not Included" or "Explicitly Avoided" was a deliberate out-of-scope decision, not an oversight.

---

## Included in v0.1

### Data Pipeline

| Capability | Notes |
|-----------|-------|
| QS global rankings ingestion | 1,503 raw records → 1,499 matched, 4 unresolved |
| THE rankings ingestion | Seeded via `seed-canonical-from-missing`; 100% match rate |
| ARWU adapter infrastructure | Adapter exists; live ingestion requires source data file |
| Raw → staging → validate → warehouse landing workflow | Deterministic, traceable |
| Canonical university resolution | Deterministic exact match, alias seeding, refresh loop |
| Unresolved entity reporting | 4 unresolved entities tracked, manual curation path available |
| Multi-source aggregation | QS + THE aggregated into `analytics.aggregated_rankings` |
| Analytics views | `analytics.v_aggregated_rankings_latest`, `analytics.v_subject_rankings_latest` |

### Product Layer

| Capability | Notes |
|-----------|-------|
| Global rankings browser | `/rankings` — pagination, search, country/region filter |
| University detail page | `/universities/{slug}` — composite score, source breakdown |
| Subject rankings page | `/subject-rankings` — QS subject data, subject selector |
| Recommendations page | `/recommendations` — Reach/Target/Safety groups, rule-based |
| System status page | `/system-status` — health, freshness, diagnostics, subject coverage |

### API Layer

| Endpoint group | Included |
|---------------|---------|
| Rankings API | `/api/v1/rankings`, `/api/v1/rankings/{source}` |
| Subject Rankings API | `/api/v1/subject-rankings`, `/api/v1/subject-rankings/{subjectKey}`, `/api/v1/universities/{id}/subject-rankings`, `/api/v1/subject-rankings/subjects` |
| University API | `/api/v1/universities`, `/api/v1/universities/{id}`, `/api/v1/universities/by-slug/{slug}`, `/api/v1/preview/universities` |
| Recommendation/Compare API | `/api/v1/recommendations`, `/api/v1/compare` |
| Diagnostics API | `/api/v1/diagnostics/rankings`, `/api/v1/diagnostics/subjects`, `/api/v1/diagnostics/data-quality`, `/api/v1/diagnostics/source-agreement`, `/api/v1/diagnostics/operational-status` |
| Explainability API | `/api/v1/universities/{id}/source-comparison`, `/api/v1/rankings/{id}/explain` |
| Health and Freshness API | `/api/v1/health`, `/api/v1/freshness` |

### Subject Rankings (MVP)

| Capability | Notes |
|-----------|-------|
| QS subject ranking ingestion | `run-qs-subject` pipeline command |
| `warehouse.subject_ranking_record` table | Per-subject, per-source, per-year records |
| `analytics.v_subject_rankings_latest` view | Subject rankings product truth source |
| Subject ranking API | Queryable by subject, source, year, country, search |
| Subject ranking diagnostics | `/api/v1/diagnostics/subjects` |
| Subject ranking UI | `/subject-rankings` with selector |

Subject rankings are a **parallel read path** and do not feed the global composite score formula.

### Diagnostics (Full Coverage)

| Capability | Notes |
|-----------|-------|
| Health diagnostics | PostgreSQL connectivity, key counts |
| Freshness diagnostics | Per-source timestamps, stale detection |
| Ranking diagnostics | Pipeline readiness, ingestion run history |
| Subject diagnostics | Subject coverage, source/year state |
| Data quality diagnostics | Unresolved entities, drift warnings, regression summary |
| Source agreement diagnostics | QS/THE rank difference, outliers, confidence buckets |
| Operational status | Unified status for system-status UI |
| System status dashboard | `/system-status` frontend page |

### Explainability (Read-Only)

| Capability | Notes |
|-----------|-------|
| Per-university source comparison | QS/THE/ARWU evidence side-by-side |
| Per-ranking aggregation explanation | Weights, normalized scores, formula note, missing-source penalties |

Explainability reads stored aggregation output only. It does not recalculate or modify scores.

### Operational Automation

| Script | Included |
|--------|---------|
| `scripts/run_daily_pipeline.sh` | Daily orchestration |
| `scripts/export_system_snapshot.py` | Snapshot generation |
| `scripts/export_metadata_bundle.sh` | Compressed backup bundle |
| `scripts/build_failure_summary.py` | Failure summary report |
| `scripts/check_pipeline_health.py` | Readonly health check |
| `scripts/compare_snapshots.py` | Snapshot diff/drift detection |
| `scripts/smoke_local_stack.sh` | Live stack smoke test |
| `scripts/smoke_release.sh` | Build artifact smoke test |
| `scripts/verify_local_environment.sh` | Environment verification |
| `scripts/start_localhost.sh` | Service startup helper |
| `scripts/run_ci_locally.sh` | Local CI reproduction |
| `scripts/build_demo_bundle.sh` | Demo release bundle builder |

### CI/CD

| Workflow | Included |
|---------|---------|
| `release-smoke.yml` | Spring Boot compile, Next.js build, Python syntax |
| `data-quality.yml` | Fixture-mode ranking regression, golden dataset, failure summary |
| Fixture-mode CI | Both CI workflows run without a live database |
| Regression golden dataset | `crawlernest/crawlernest-autoeval/datasets/ranking_regression/golden.json` |
| CI fixtures | `crawlernest/crawlernest-autoeval/datasets/ci_fixtures/` |

### Readonly Agent Integration

| Capability | Notes |
|-----------|-------|
| `scripts/agent_pipeline_analysis.sh` | Wraps optional sibling `crawlernest-agents` repo |
| `scripts/agent_context_snapshot.sh` | Exports system state for agent context |
| Agent boundary enforcement | Agents are not in the production data path |

---

## Not Included in v0.1

These capabilities were considered but not activated or completed in this milestone.

| Capability | Reason |
|-----------|--------|
| Automated THE re-ingestion (cron) | THE data seeded manually; no scheduled crawl cadence |
| Live ARWU ingestion | Adapter exists; no active source data pipeline |
| Full-subject sweep automation | Subject runs triggered manually per subject |
| C normalization engine (production) | ~65% complete; Python normalization is the production path |
| Admission requirements as product feature | Extraction partial; not surfaced in product UI |
| Agent autonomous actions | Agent layer is development-support only |
| Agent write capabilities | All agent interactions are readonly analysis |
| Program-level analytics | Planned for post-v0.1 |
| Degree-level analytics | Planned for post-v0.1 |
| Broader alias curation tooling | Manual alias seeding only; no batch curation UI |
| LLM-assisted requirement verification | Future milestone only |
| Public API platform | Future milestone only |

---

## Future Work

These are accepted directions for post-v0.1 development.

| Direction | Priority |
|-----------|---------|
| Automate THE crawl in daily pipeline | High |
| Activate ARWU live ingestion | High |
| Full-subject sweep automation | Medium |
| Resolve 4 remaining unresolved canonical entities | Medium |
| Deepen admission requirements as product feature | Medium |
| Expand alias coverage and batch curation workflow | Medium |
| Program-level and degree-level analytics | Medium |
| Agent structured readonly query tools | Low (after data quality stabilizes) |
| Cloud/production deployment | Low (after local operational patterns proven) |

---

## Explicitly Avoided in v0.1

These were intentionally excluded as out-of-scope for this milestone to maintain operational stability and focused scope.

| Avoided | Reason |
|---------|--------|
| Autonomous agent repair | Would introduce agents into production data path; not safe at this maturity |
| Agents writing to database | Hard boundary: agents are readonly development-support tools |
| Production cloud deployment | Not the goal of this milestone; local operational MVP first |
| Distributed pipeline execution | No distributed infrastructure; single-node local only |
| Auto-fixing agents | Would violate the agent boundary and production data integrity |
| Ranking aggregation formula changes | Formula frozen for v0.1; changes tracked separately |
| Schema changes | Schema frozen for v0.1 |
| API behavior changes | API surface frozen for v0.1 |
| Frontend UX changes | Product behavior frozen for v0.1 |
| Scoring changes | Scoring logic frozen for v0.1 |
| Canonical matching changes | Matching logic frozen for v0.1 |

---

## Milestone Freeze Statement

v0.1 was frozen with the following known state:

- **1,499** universities aggregated (QS 2026 full ingestion)
- **4** unresolved canonical entities (known, tracked, not blocking)
- **0** drift warnings
- Subject rankings MVP operational for Computer Science and Electrical Engineering
- All diagnostics and explainability endpoints operational
- Readonly agent integration present but non-production
- CI passing (release-smoke + data-quality) without live database
- Snapshot: `snapshots/system_snapshot_20260508_072113.json`
- Last aggregation run: 2026-05-08T06:24:35 (UTC+8)

This document is frozen at v0.1. Do not update it for post-v0.1 changes — create a new `VERSION_SCOPE_vX.Y.md`.
