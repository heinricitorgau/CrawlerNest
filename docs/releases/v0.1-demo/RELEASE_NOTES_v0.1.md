# CrawlerNest v0.1 — Demo Release Notes

**Release Date:** 2026-05-16
**Release Type:** Engineering Milestone / Demo Release
**Maturity:** Operational MVP — local development environment

---

## Executive Summary

CrawlerNest v0.1 is the first formally scoped engineering milestone of an end-to-end university data infrastructure platform. The system ingests global university ranking data from QS (and THE), resolves canonical university identities, aggregates multi-source scores, and serves rankings, subject rankings, diagnostics, and explainability through a Spring Boot API and Next.js web frontend.

This release is not a public or production deployment. It is a **reproducible, demonstrable, operational MVP** running on a local development environment, intended to represent a defined engineering baseline with observable system behavior, CI coverage, and operational automation.

The system currently holds **1,499 aggregated universities** (QS 2026), with diagnostics, explainability, and subject ranking support operational.

---

## Current Capabilities

### Data Pipeline

- QS global ranking ingestion (1,503 raw records → 1,499 matched canonical universities, 4 unresolved)
- THE ranking ingestion with full entity match after `seed-canonical-from-missing`
- ARWU adapter infrastructure present; active ingestion requires source data
- Raw → normalized → staging → validate → ingest → warehouse preview → warehouse landing workflow
- Deterministic canonical university resolution with alias seeding and refresh loop
- Unresolved entity reporting and manual curation path

### Rankings Product

- Global rankings browser at `/rankings` with pagination, search, country/region filter
- Aggregated composite score across QS and THE sources
- `display_rank`, `composite_score`, `coverage_ratio`, `source_ranks_json` exposed per university
- `analytics.v_aggregated_rankings_latest` view as product truth source

### Subject Rankings (MVP)

- QS subject rankings ingestion for selected subjects (e.g., Computer Science, Electrical Engineering)
- Subject rankings page at `/subject-rankings` with subject selector
- `warehouse.subject_ranking_record` → `analytics.v_subject_rankings_latest` path
- Subject ranking diagnostic endpoint at `/api/v1/diagnostics/subjects`
- Subject ranking does **not** feed the global aggregation formula

### Diagnostics

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/health` | PostgreSQL connectivity and key record counts |
| `GET /api/v1/freshness` | Per-source and aggregation freshness status |
| `GET /api/v1/diagnostics/rankings` | Ranking pipeline readiness and row counts |
| `GET /api/v1/diagnostics/subjects` | Subject ranking readiness and row counts |
| `GET /api/v1/diagnostics/data-quality` | Unresolved entities, drift warnings, regression summary |
| `GET /api/v1/diagnostics/source-agreement` | QS/THE rank difference, outliers, source overlap |
| `GET /api/v1/diagnostics/operational-status` | System-status UI data feed |

### Explainability

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/universities/{id}/source-comparison` | Per-university QS/THE/ARWU evidence comparison |
| `GET /api/v1/rankings/{id}/explain` | Aggregation inputs: weights, normalized scores, formula note |

The explainability layer reads stored aggregation output. It does not recalculate or modify ranking scores.

### Recommendation (Limited)

- Rule-based recommendation groups (Reach / Target / Safety) at `/recommendations`
- Reads from `analytics.v_aggregated_rankings_latest`
- Intentionally limited and optional until upstream data completeness improves

### Operational Automation

| Script | Purpose |
|--------|---------|
| `scripts/run_daily_pipeline.sh` | Orchestrates daily crawl, subject run, snapshot, bundle, smoke |
| `scripts/export_system_snapshot.py` | Writes `snapshots/system_snapshot_*.json` and `snapshots/latest_status.json` |
| `scripts/export_metadata_bundle.sh` | Creates compressed backup bundle in `backups/` |
| `scripts/build_failure_summary.py` | Generates `reports/latest_failure_summary.md` from snapshot |
| `scripts/check_pipeline_health.py` | Readonly diagnostic health check |
| `scripts/compare_snapshots.py` | Diff two snapshot files for drift detection |
| `scripts/smoke_local_stack.sh` | Validates all live services are up and responding |
| `scripts/smoke_release.sh` | CI-ready build smoke test (no live services required) |

### CI/CD

- `release-smoke.yml`: Spring Boot compile + Next.js build + Python syntax on every push/PR
- `data-quality.yml`: Fixture-mode ranking regression, golden dataset validation, failure summary upload
- Both workflows run without a live database
- CI artifacts: `regression_result.json`, `ci_failure_summary.md` (14-day retention)

### Readonly Agent Integration

- `scripts/agent_pipeline_analysis.sh` wraps optional sibling `crawlernest-agents` repository
- Agents operate in development-support mode only: readonly pipeline log analysis
- Agent boundary is enforced: agents are **not** in the production data path
- Agent runtime at `localhost:8090` is optional and does not affect API or data results

---

## System Architecture Summary

```
External sources (QS, THE, ARWU)
        ↓
Python crawlers + normalization adapters
        ↓
Canonical university resolution (deterministic, alias-seeded)
        ↓
PostgreSQL warehouse schema (warehouse.ranking_record, warehouse.subject_ranking_record)
        ↓
Analytics aggregation (analytics.aggregated_rankings, analytics.v_aggregated_rankings_latest)
        ↓
Spring Boot API (:8080) ← diagnostics, explainability, health, freshness
        ↓
Next.js frontend (:3000) ← rankings, subject rankings, recommendations, system status
```

Runtime split:

- **Python**: crawling, normalization, canonical resolution, ingestion, aggregation writes, snapshots, scripts
- **PostgreSQL**: warehouse records, analytics views, canonical truth
- **Spring Boot**: product API reads, diagnostics, explainability
- **Next.js**: web UI, same-origin proxy routes, live freshness polling
- **GitHub Actions + scripts**: repeatable CI verification

---

## Included Components

| Component | Path | Status |
|-----------|------|--------|
| Python pipeline core | `crawlernest/run_pipeline.py`, `crawlernest/pipeline/` | Operational |
| Ranking crawlers (QS, THE) | `crawlernest/crawlernest-jobs/` | Operational |
| Multi-source aggregation | `crawlernest/crawlernest-core/ranking_aggregation/` | Operational |
| Canonical resolution | `crawlernest/crawlernest-core/multi_source/` | Operational |
| Spring Boot API | `crawlernest/servise_for_java/` | Operational |
| Next.js frontend | `crawlernest/crawlernest-web/` | Operational |
| Subject rankings | Crawler + API + UI path | MVP Operational |
| Diagnostics | API endpoints + system-status page | Operational |
| Explainability | API endpoints | Operational |
| AutoEval / CI fixtures | `crawlernest/crawlernest-autoeval/` | Operational |
| Operational scripts | `scripts/` | Operational |
| CI workflows | `.github/workflows/` | Operational |
| Readonly agent integration | `scripts/agent_pipeline_analysis.sh` | Development Support |

---

## Operational Capabilities

- Full pipeline run reproducible from scratch with `bootstrap-postgres` + `run_pipeline run`
- Snapshot and bundle export produce durable evidence without modifying runtime state
- Failure summary generation from committed fixtures (no live DB required)
- CI regression and golden dataset checks run offline
- `smoke_release.sh` validates build artifacts without live services
- System status page (`/system-status`) aggregates health, freshness, diagnostics, and subject coverage in one view

---

## Diagnostics and Explainability Support

The v0.1 system provides **read-only observability** at every layer:

- **Health**: PostgreSQL connectivity, record counts, service readiness
- **Freshness**: Per-source timestamp tracking, stale detection
- **Ranking diagnostics**: Ingestion run IDs, batch history, API readiness
- **Subject diagnostics**: Subject coverage, source/year state
- **Data quality**: Unresolved entities (currently 4), drift warnings, regression summary
- **Source agreement**: QS/THE rank difference, overlap, confidence buckets, outliers
- **Explainability per university**: Source comparison, aggregation weights, formula note
- **System status page**: Unified dashboard at `/system-status`

---

## Subject Ranking Support

Subject rankings are a v0.1 MVP capability:

- Ingested via `run-qs-subject` pipeline command
- Stored in `warehouse.subject_ranking_record`
- Served from `analytics.v_subject_rankings_latest`
- UI at `/subject-rankings` with subject selector
- Subject rankings are **independent** of the global composite score formula
- Diagnostic coverage at `/api/v1/diagnostics/subjects`

---

## Readonly Agent Integration

Agent systems are present in development-support mode:

- `scripts/agent_pipeline_analysis.sh` — wraps sibling `crawlernest-agents` repo
- `scripts/agent_context_snapshot.sh` — exports system state for agent context
- `scripts/agent_debug.sh` — local agent debug support
- Agents are **not** runtime dependencies, not submodules, not CI dependencies
- No agent writes to production data; all agent interactions are readonly analysis

---

## Known Limitations

1. **4 unresolved canonical entities** from the QS 2026 ingestion — require manual alias curation to resolve
2. **Low composite score coverage**: all 1,499 aggregated universities have `composite_score < 0.5` — this reflects QS-only single-source coverage, not a scoring defect; THE integration expands dual-source coverage
3. **Subject rankings MVP**: limited to manually triggered subjects; no automated full-subject sweep
4. **ARWU ingestion inactive**: adapter infrastructure exists but requires source data file to activate
5. **Admission data limited**: admission requirement extraction is partial; not surfaced as primary product
6. **C normalization engine incomplete**: ~65% complete; Python normalization is the production path
7. **Recommendation engine limited**: rule-based only; not suitable as a primary product decision layer
8. **No production cloud deployment**: the system runs on a local development environment
9. **No live THE ingestion**: THE data was seeded manually; automated THE crawl cadence is not scheduled
10. **Agent capabilities are development-support only**: no autonomous repair, no production data writes

---

## Explicit Non-Goals for v0.1

- Autonomous agent repair or production data modification
- Cloud deployment or production infrastructure
- Live THE re-ingestion or automated THE crawl scheduling
- Distributed pipeline execution
- Full admission requirement extraction and product surfacing
- ARWU live ingestion
- Program-level or degree-level analytics
- LLM-assisted requirement verification
- Public API platform
- Automated full-subject ranking sweeps

---

## Current Maturity Assessment

| Dimension | Assessment |
|-----------|-----------|
| Pipeline reproducibility | High — `bootstrap-postgres` + `run_pipeline` is deterministic |
| Data coverage | Moderate — QS 2026 full, THE seeded, ARWU not active |
| API stability | High — product endpoints stable, schema frozen for v0.1 |
| CI coverage | High — offline fixture-mode CI for regression and build smoke |
| Observability | High — health, freshness, diagnostics, explainability all operational |
| Frontend stability | High — rankings, subject rankings, recommendations, system status all functional |
| Operational automation | High — daily pipeline, snapshot, bundle, failure summary all scripted |
| Agent integration | Low — development-support only, no production coupling |
| Production readiness | Not applicable — local development milestone only |

---

## Recommended Future Directions

1. **Automate THE crawl scheduling** — integrate THE into the daily pipeline cron cadence
2. **Activate ARWU ingestion** — validate adapter against real ARWU source data
3. **Expand subject ranking coverage** — automate full-subject sweep instead of per-subject CLI runs
4. **Resolve 4 unresolved entities** — add alias seeds for the 4 remaining unmatched QS records
5. **Deepen admission data** — surface admission requirements as a product feature alongside rankings
6. **Expand identity resolution** — broader alias coverage and batch curation workflow tooling
7. **Program-level analytics** — degree/field granularity as the next data layer above subject rankings
8. **Agent read capabilities** — structured readonly query tools for the agent layer once data quality stabilizes
9. **Cloud deployment** — define production infra after local operational patterns are proven

---

*This release notes document is frozen at v0.1. Future releases should create a new `RELEASE_NOTES_vX.Y.md`.*
