# Operational Index

This index consolidates CrawlerNest operational artifacts into a single
hierarchy. It is a documentation layer only: it does not change runtime
diagnostics, ranking aggregation, scoring, auth, frontend behavior, CI
semantics, or agent autonomy.

---

## Operational Hierarchy

1. Runtime state is held in PostgreSQL and local services.
2. Snapshots capture point-in-time operational evidence.
3. Reports summarize snapshots, diagnostics, validation output, and bundle state.
4. Release bundles copy selected docs, snapshots, reports, and validation output.
5. Agent context wrappers package readonly evidence for sibling-agent analysis.

---

## Snapshots

| Artifact | Purpose | Producer Script | Readonly Status | Expected Frequency | Consumed By | Operational Importance |
| --- | --- | --- | --- | --- | --- | --- |
| `snapshots/system_snapshot_*.json` | Dated historical snapshot of health, freshness, unresolved counts, drift warnings, regression summary, and last ingestion. | `scripts/export_system_snapshot.py` | Writes files only; reads PostgreSQL; does not mutate DB. | After pipeline runs, release validation, or handoff checkpoints. | timeline, drift, freshness, compare, release bundle. | High: primary historical evidence. |
| `snapshots/latest_status.json` | Compact pointer to the latest exported state. | `scripts/export_system_snapshot.py` | File write only; no runtime mutation. | Overwritten with each export. | frontend snapshot info route, reports, release bundle. | High: latest evidence pointer. |

Retention expectation: append dated snapshots for release and handoff windows;
clean manually with operational approval. `latest_status.json` is replaceable.

---

## Reports

| Artifact | Purpose | Producer Script | Readonly Status | Expected Frequency | Consumed By | Operational Importance |
| --- | --- | --- | --- | --- | --- | --- |
| `reports/latest_failure_summary.md` | Human summary of freshness, drift, regression, unresolved, and source coverage. | `scripts/build_failure_summary.py` | Reads snapshots and optional readonly checks. | Release validation and demos. | release bundle, agent context. | High. |
| `reports/snapshot_timeline.md` / `.json` | Timeline of aggregation count, unresolved trend, source coverage, freshness, and warnings. | `scripts/build_snapshot_timeline.py` | Reads `snapshots/*.json`; writes report files only. | After snapshot export or before demos. | operational summary, reviewers. | High. |
| `reports/operational_summary.md` | Demo-friendly latest state summary with source health. | `scripts/build_operational_summary.py` | Reads snapshots/reports/docs only. | Before demos or handoff. | release bundle, operational index summary. | High. |
| `reports/operational_index_summary.md` | Single-entry consolidated operational status. | `scripts/build_operational_index_summary.py` | Reads reports/snapshots/docs/bundle outputs only. | Before release bundle creation or handoff. | release bundle, humans. | High. |
| `reports/maintenance_readiness_summary.md` | Maintenance-oriented freshness, source, unresolved, and release/demo caveat summary. | `scripts/inspect_source_freshness.py --summary-output ...` | Reads snapshot JSON only; writes report file only. | Before maintenance windows, demos, or source recovery. | release checklist, release bundle, humans. | High. |
| `reports/demo_caveats.md` | Presenter-facing caveats derived from freshness, operational, maintenance, and snapshot evidence. | `scripts/build_demo_caveats.py` | Reads reports and snapshot JSON only; writes report file only. | Before demos and bundle rebuilds. | release bundle, presenters. | High. |
| `reports/operational_trust_summary.md` | Conservative confidence rollup across freshness, source completeness, release, demo, maintenance, and operational trust. | `scripts/build_operational_trust_summary.py` | Reads reports and snapshot JSON only; writes report file only. | Before demos, release review, and maintenance handoff. | release bundle, overview, humans. | High. |

Retention expectation: generated reports are reproducible and can be refreshed;
keep latest reports for release evidence, do not treat them as runtime truth.

---

## Diagnostics

| Artifact | Purpose | Producer Script | Readonly Status | Expected Frequency | Consumed By | Operational Importance |
| --- | --- | --- | --- | --- | --- | --- |
| API diagnostics `/api/v1/diagnostics/*` | Live readonly operational and data-quality checks. | Spring Boot diagnostics controllers. | GET-only; no runtime mutation. | While stack is running. | demos, smoke checks, operator curl checks. | High. |
| `scripts/check_pipeline_health.py` output | Readonly database health/freshness check. | `scripts/check_pipeline_health.py` | Reads PostgreSQL only. | Smoke, bundle diagnostics, handoff. | smoke, bundle diagnostics. | High. |

Retention expectation: live diagnostics are not retained unless captured into
bundle/report output.

---

## Release Validation

| Artifact | Purpose | Producer Script | Readonly Status | Expected Frequency | Consumed By | Operational Importance |
| --- | --- | --- | --- | --- | --- | --- |
| `docs/RC1_VALIDATION_RESULTS.md` | Recorded release-candidate validation evidence and accepted limitations. | Manual validation pass. | Documentation only. | RC/handoff milestones. | operational index summary, docs readers. | High. |
| `releases/v0.1-demo/smoke_release_output.txt` | Captured bundle-time smoke run. | `scripts/build_demo_bundle.sh` | Runs readonly/build checks; no pipeline mutation. | Each bundle build. | operational index summary, release reviewers. | High. |

Retention expectation: keep with release bundle for reproducibility evidence.

---

## Drift Intelligence

| Artifact | Purpose | Producer Script | Readonly Status | Expected Frequency | Consumed By | Operational Importance |
| --- | --- | --- | --- | --- | --- | --- |
| `reports/drift_timeline.md` | Classifies unresolved growth, source disappearance, stale transitions, aggregation drops, and drift warnings. | `scripts/build_drift_timeline.py` | Reads snapshots only. | Before demos and release handoffs. | operational summary, bundle. | Medium-high. |
| `scripts/compare_snapshots.py` output | Compares two selected snapshots for count, coverage, stale, and drift differences. | `scripts/compare_snapshots.py` | Reads JSON files only. | Ad hoc drift review or smoke fixture validation. | smoke, humans. | Medium-high. |

Retention expectation: latest generated drift timeline is enough for most
demos; compare outputs may remain ad hoc unless captured.

---

## Freshness Intelligence

| Artifact | Purpose | Producer Script | Readonly Status | Expected Frequency | Consumed By | Operational Importance |
| --- | --- | --- | --- | --- | --- | --- |
| `reports/freshness_escalation.md` | Classifies latest freshness as healthy/degraded/stale/critical. | `scripts/build_freshness_escalation.py` | Reads snapshots only. | Before demos and handoff. | operational summary, bundle. | High. |
| `scripts/inspect_source_freshness.py` output | Summarizes latest source state, aggregation age, source coverage, unresolved trend, and subject freshness. | `scripts/inspect_source_freshness.py` | Reads snapshot JSON only. | Maintenance inspection and source recovery planning. | maintenance readiness summary, humans. | High. |
| `scripts/maintenance_overview.sh` output | Single-entry maintenance overview combining source freshness, operational summary, latest snapshot comparison hint, and smoke summary. | `scripts/maintenance_overview.sh` | Reads reports/snapshots and runs readonly file-based helpers. | Operator first look. | humans. | High. |
| Freshness API `/api/v1/freshness` | Live freshness surface. | Spring Boot API. | GET-only. | While stack is running. | demos, smoke checks. | High. |

Retention expectation: report output is refreshable; API output is live and not
retained unless copied into bundle/logs.

---

## Agent Context Artifacts

| Artifact | Purpose | Producer Script | Readonly Status | Expected Frequency | Consumed By | Operational Importance |
| --- | --- | --- | --- | --- | --- | --- |
| `tmp/agent-context/context_snapshot.md` | Bounded repo and operational evidence snapshot for sibling agents. | `scripts/agent_context_snapshot.sh` | Reads repo and reports; writes `tmp/` only. | Per debugging or review session. | `agent_repo_prompt.sh`. | Medium. |
| `tmp/agent-context/repo-aware-prompt.md` | Prompt-ready context package. | `scripts/agent_repo_prompt.sh` | Writes `tmp/` only; no source mutation. | Per prompt generation. | sibling `crawlernest-agents`. | Medium. |

Agent wrappers may consume latest smoke summaries, failure summaries,
diagnostic snapshots, freshness snapshots, and regression summaries. They do
not consume live runtime authority, mutate DB state, make commits, open PRs, or
make `crawlernest-agents` a runtime dependency.

---

## Release Bundles

| Artifact | Purpose | Producer Script | Readonly Status | Expected Frequency | Consumed By | Operational Importance |
| --- | --- | --- | --- | --- | --- | --- |
| `releases/v0.1-demo/` | Demo/release evidence package. | `scripts/build_demo_bundle.sh` | Copies docs/reports/snapshots and runs smoke; no pipeline mutation. | Before demos, releases, or handoff. | humans, demo reviewers. | High. |
| `releases/v0.1-demo/OPERATIONAL_ARTIFACTS.md` | Bundle-local relationship map for included operational artifacts. | `scripts/build_demo_bundle.sh` | File write only in bundle. | Each bundle build. | bundle readers. | High. |

Retention expectation: release bundles are historical evidence and should be
kept per release milestone.

---

## Smoke Validation

| Artifact | Purpose | Producer Script | Readonly Status | Expected Frequency | Consumed By | Operational Importance |
| --- | --- | --- | --- | --- | --- | --- |
| `scripts/smoke_release.sh` output | Build, syntax, fixture, and diagnostics smoke. No services, no endpoints. | `scripts/smoke_release.sh` | Build/read checks only; no pipeline mutation. | Before release or bundle build. | bundle, CI, humans. | High. |
| `scripts/smoke_api_endpoints.sh` output | Endpoint liveness and `postgres_connected`, against a running API. | `scripts/smoke_api_endpoints.sh` | Read-only HTTP checks. | In CI's `Analytics bridge smoke` job; locally with Spring Boot up. | CI, humans. | High. |
| `scripts/smoke_local_stack.sh` output | Local stack reachability and UI/API smoke. | `scripts/smoke_local_stack.sh` | GET checks only. | While running local services. | operators. | Medium-high. |

Retention expectation: capture release smoke in bundle; local stack smoke is
usually transient.

---

## CI Validation

| Artifact | Purpose | Producer Script | Readonly Status | Expected Frequency | Consumed By | Operational Importance |
| --- | --- | --- | --- | --- | --- | --- |
| `.github/workflows/release-smoke.yml` | CI release smoke fixture/build validation. | GitHub Actions. | CI reads/builds; no runtime mutation. | On configured workflow triggers. | maintainers. | High. |
| `.github/workflows/data-quality.yml` | Fixture-mode data quality checks. | GitHub Actions. | Fixture based. | On configured workflow triggers. | maintainers. | High. |

Retention expectation: CI history lives in GitHub Actions; bundle screenshots
may capture representative green runs.
