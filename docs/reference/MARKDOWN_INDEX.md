# Markdown Index

This file is a curated index of the project-owned Markdown documents in this
repository.

## Scope

Included:
- Root docs
- `docs/`
- Module `README.md` and design docs under `crawlernest/`
- `legacy/mini_agent/README.md`

Excluded from this index:
- `.venv/`, `.venv-1/`
- `node_modules/`
- `.claude/worktrees/`
- `deployment-support/` — build output of
  `crawlernest/scripts/build_lobster_runtime.sh`, no longer tracked

## Reading Order

If someone is new to the repo, this is the fastest path:

1. `README.md`
2. `README.zh-TW.md`
3. `docs/README.md`
4. `docs/ARCHITECTURE_OVERVIEW.md`
5. `docs/REPOSITORY_MAP.md`
6. `docs/DATA_FLOW.md`
7. `docs/operational/OPERATIONAL_RUNBOOK.md`
8. `docs/API_SURFACE.md`
9. `docs/PROJECT_STATE_REVIEW.md`
10. `docs/release/CI_PIPELINES.md`
11. `docs/foundation/TESTING_GUIDE.md`

## 1. Root Entry Docs

| File | Purpose |
| --- | --- |
| `README.md` | Main English project entrypoint and overall repo introduction. |
| `README.zh-TW.md` | Traditional Chinese version of the main project overview. |
| `MARKDOWN_INDEX.md` | Root-level pointer to the canonical Markdown inventory under `docs/reference/`. |
| `docs/README.md` | Documentation hub, canonical reading order, and duplicate-content policy. |

## 2. Foundation And Repo Governance

| File | Purpose |
| --- | --- |
| `docs/foundation/MASTER_PROJECT_PLAN.md` | Historical and planning context for scope, phases, and project-level priorities. |
| `docs/foundation/Whitepaper.md` | Long-form architecture and product vision in Traditional Chinese. |
| `docs/foundation/ARCHITECTURE_SCOPE.md` | Scope guardrails and architectural boundaries. |
| `docs/foundation/DATA_CONTRACTS.md` | Data-layer contract definitions. |
| `docs/foundation/DEV_WORKFLOW.md` | Expected engineering workflow for implementation and delivery. |
| `docs/foundation/MODULE_OWNERSHIP.md` | Ownership boundaries across the system. |
| `docs/foundation/DO_NOT_AUTO_MODIFY.md` | Areas that agents and automated patch loops must not rewrite. |
| `docs/foundation/TESTING_GUIDE.md` | Testing, validation, and maintenance guidance. |
| `docs/agent/AI_DEV_WORKFLOW.md` | AI-assisted development workflow and crawlernest-agents integration notes. |
| `docs/agent/AGENT_MODEL_INTEGRATION.md` | Readonly agent model provider bridge architecture, supported providers, env vars, fallback behavior, and safety boundaries. |

## 3. Architecture And Platform Design

| File | Purpose |
| --- | --- |
| `docs/ARCHITECTURE_OVERVIEW.md` | Current high-level architecture, system maps, and rendered diagrams. |
| `docs/REPOSITORY_MAP.md` | Current repository structure map and onboarding guide. |
| `docs/DATA_FLOW.md` | QS/THE/ARWU and subject ranking data flow from source to frontend. |
| `docs/operational/OPERATIONAL_RUNBOOK.md` | Startup, smoke checks, daily pipeline, snapshots, diagnostics, CI troubleshooting, and rollback guidance. |
| `docs/API_SURFACE.md` | Current API endpoint catalog for rankings, subjects, diagnostics, explainability, health, and freshness. |
| `docs/PROJECT_STATE_REVIEW.md` | Current project maturity, inventory, operational risks, technical debt, scaling risks, and next-phase priorities. |
| `docs/AUTH_LIMITATIONS.md` | Auth model, non-goals, localhost assumptions, future scaling risks, and deployment requirements. |
| `docs/USER_DATA_SAFETY_REVIEW.md` | User data safety review: isolation guarantees, session model, validation hardening, health endpoint fix, operational limits. |
| `docs/UX_STABILIZATION_NOTES.md` | UX stabilization pass notes: stabilized states, session expiry behavior, shared auth messages, intentionally avoided complexity, known limits. |
| `docs/release/RC1_ENVIRONMENT_FREEZE.md` | RC-1 environment freeze, verified versions, localhost assumptions, unsupported environments, and setup notes. |
| `docs/release/RC1_DEPENDENCY_REVIEW.md` | RC-1 dependency review across frontend, backend, and Python runtimes. |
| `docs/release/RC1_RELEASE_HYGIENE.md` | RC-1 source-control hygiene for build outputs, generated evidence, and temporary artifacts. |
| `docs/release/RC1_STABILITY_REVIEW.md` | RC-1 long-run stability review for sessions, persistence, diagnostics, storage, and restart behavior. |
| `docs/release/RC1_FREEZE_SCOPE.md` | RC-1 frozen areas, allowed changes, blocked changes, and re-validation rules. |
| `docs/release/RC1_VALIDATION_RESULTS.md` | RC-1 operational validation outcomes, warnings, and accepted limitations. |
| `docs/operational/OPERATIONAL_INTELLIGENCE_AUTOMATION.md` | Readonly operational intelligence automation philosophy, boundaries, non-goals, and escalation semantics. |
| `docs/data/SOURCE_HEALTH_MODEL.md` | Source health states and signals used by operational intelligence reports. |
| `docs/operational/OPERATIONAL_INDEX.md` | Unified operational hierarchy for snapshots, reports, diagnostics, validation, bundles, smoke checks, CI, and agent context artifacts. |
| `docs/operational/OPERATIONAL_VOCABULARY.md` | Consolidated operational vocabulary for stale, degraded, critical, drift, freshness, source coverage, and validation surfaces. |
| `docs/data/REPORT_RELATIONSHIPS.md` | Report dependency and consumption map across snapshots, diagnostics, reports, bundles, and demo summaries. |
| `docs/data/SNAPSHOT_LINEAGE.md` | Snapshot source, lifecycle, timeline derivation, comparison, freshness, and drift relationships. |
| `docs/operational/OPERATIONAL_SURFACE_REVIEW.md` | Operational surface review covering overlap, terminology risks, and consolidation recommendations. |
| `docs/operational/MAINTENANCE_PRIORITY_MATRIX.md` | Maintenance priority matrix with response guidance and freeze interaction rules. |
| `docs/data/SOURCE_FRESHNESS_RECOVERY.md` | Source freshness recovery plan for stale QS and unavailable THE/ARWU. |
| `docs/operational/MAINTENANCE_RUNBOOK.md` | Copy-paste friendly maintenance runbook for freshness, drift, snapshots, release checks, and bundles. |
| `docs/release/RELEASE_STATE_CHECKLIST.md` | Checklist for demo/release readiness and operational caveat coverage. |
| `docs/operational/OPERATIONAL_CLEANUP_GUIDE.md` | Cleanup and retention guidance for operational artifacts. |
| `docs/data/SOURCE_STATE_EXPLAINABILITY.md` | Source-state explanations for maintainers, demos, reviewers, and caveat handling. |
| `docs/data/FRESHNESS_CONSISTENCY_REVIEW.md` | Freshness consistency and divergence review across health checks, reports, and compact snapshots. |
| `docs/operational/MAINTENANCE_ERGONOMICS_REVIEW.md` | Maintenance ergonomics review covering entrypoints, cognitive load, discoverability, and cleanup opportunities. |
| `docs/operational/OPERATIONAL_CONFIDENCE_MODEL.md` | Operational confidence dimensions, levels, examples, escalation implications, and maintainer behavior. |
| `docs/data/SOURCE_COMPLETENESS_REVIEW.md` | Current source completeness review for QS, THE, ARWU, and subject rankings. |
| `docs/demo/DEMO_HONESTY_GUIDELINES.md` | Demo honesty rules, required caveats, acceptable phrasing, and unacceptable phrasing. |
| `docs/data/CONFIDENCE_CONSISTENCY_REVIEW.md` | Confidence consistency review across operational, maintenance, freshness, drift, caveat, and trust reports. |
| `docs/operational/MAINTENANCE_SIGNAL_CLARITY.md` | Maintenance signal hierarchy and recommended maintainer/release reading order. |
| `docs/agent/AGENT_MODEL_INTEGRATION.md` | Agent model provider integration for `/agent` with mock, Ollama, and OpenAI boundaries. |
| `docs/operational/OPERATIONAL_RESTRAINT_GUIDELINES.md` | When NOT to add automation, diagnostics, reports, or scripts; saturation signals; safe addition criteria. |
| `docs/operational/MAINTENANCE_SUSTAINABILITY_REVIEW.md` | Sustainable vs complexifying maintenance areas; debt risks; highest-value future cleanup targets. |
| `docs/data/SIGNAL_TO_NOISE_REVIEW.md` | Signal value classification and recommended reading hierarchy by operator role. |
| `docs/operational/OPERATIONAL_BOUNDARY_REINFORCEMENT.md` | Capabilities intentionally NOT implemented at RC-1 and the rationale for each. |
| `docs/data/REPORT_CRITICALITY.md` | Critical / important / reference classification for all generated reports and release artifacts. |
| `docs/release/RELEASE_BUNDLE_SIMPLIFICATION_REVIEW.md` | Must-exist vs supporting vs optional classification of v0.1-demo bundle artifacts. |
| `docs/operational/OPERATIONAL_CALMNESS_REVIEW.md` | Calm vs noisy surface analysis; false urgency risks; calmness preservation and wording discipline guidelines. |
| `docs/data/REPORT_LIFECYCLE.md` | Producer, consumer, freshness expectation, lifecycle category, and archival expectation for every report. |
| `docs/operational/MAINTENANCE_FATIGUE_REVIEW.md` | Attention hotspots, repeated warning exposure, cognitive overload risks, and fatigue reduction workflows. |
| `docs/operational/OPERATIONAL_COHERENCE_REVIEW.md` | Coherence strengths, terminology risks, relationship stability, and future cleanup opportunities. |
| `docs/operational/MAINTENANCE_READING_MODES.md` | Structured reading modes for quick status, release/demo prep, freshness investigation, incident, audit, and onboarding. |
| `docs/operational/MAINTENANCE_CADENCE_REVIEW.md` | Appropriate cadence for each maintenance activity: daily, weekly, release-demo, incident-only, archival. |
| `docs/operational/OPERATIONAL_MEMORY_PRESERVATION.md` | What operational knowledge must be preserved long-term vs temporary; bundle archival semantics; handoff requirements. |
| `docs/data/STABLE_DEGRADED_STATE.md` | Current RC-1 stable degraded posture: accepted conditions, what is stable, escalation triggers, communication guidance. |
| `docs/operational/MAINTENANCE_DISCIPLINE.md` | Behavioral discipline for maintenance: healthy and unhealthy patterns, discipline under pressure, boundaries. |
| `docs/operational/OPERATIONAL_CONTINUITY_REVIEW.md` | Continuity strengths, risks, vulnerable operational assumptions, and report relationships requiring attention. |
| `docs/operational/MAINTENANCE_CONTINUITY_MODEL.md` | Continuity concept definitions: stable degraded, report, snapshot, confidence, honesty, vocabulary continuity. |
| `docs/operational/OPERATIONAL_MEMORY_DURABILITY.md` | Artifact durability tiers (durable/semi-durable/ephemeral); bundle and snapshot durability semantics. |
| `docs/data/STABLE_DEGRADED_CONTINUITY.md` | Long-term stable degraded posture guidance: calm maintenance, false urgency, desensitization, remediation churn. |
| `docs/architecture/REPO_STRUCTURE.md` | Compatibility wrapper that points to `docs/REPOSITORY_MAP.md`. |
| `docs/architecture/SYSTEM_ENGINE_ARCHITECTURE.md` | Compatibility wrapper that points to current architecture docs. |
| `crawlernest/crawlernest-docs/SYSTEM_ARCHITECTURE.md` | Legacy mirror that now redirects readers to the canonical architecture docs in `docs/`. |
| `crawlernest/crawlernest-docs/architecture.md` | Compatibility architecture note kept to avoid stale inner-workspace links. |

## 4. Deployment And Operations

| File | Purpose |
| --- | --- |
| `docs/release/CI_PIPELINES.md` | GitHub Actions workflow summary and troubleshooting notes. |
| `docs/operational/SCHEDULED_OPERATIONS.md` | Cron and scheduled pipeline automation details. |
| `docs/demo/DEMO_CHECKLIST.md` | Pre-demo and handover checklist. |
| `docs/LOCAL_TROUBLESHOOTING.md` | Local environment issues and fixes. |
| `docs/operational/OPERATIONAL_RECOVERY.md` | Recovery guidance for PostgreSQL, analytics views, datasource issues, snapshots, and rollback. |
| `docs/data/PIPELINE_HEALTH_MODEL.md` | Health states, thresholds, freshness expectations, and source coverage model. |
| `docs/PYTHON_ENVIRONMENT.md` | Python venv, psycopg2, PEP 668, and runtime consistency notes. |
| `docs/operational/BACKUP_RESTORE_DRILL.md` | Readonly-safe backup, restore, rollback, and disaster-recovery drill guidance. |
| `docs/data/SNAPSHOT_COMPARISON.md` | Snapshot comparison workflow for coverage, freshness, drift, and failure-state fixtures. |
| `docs/data/SOURCE_HEALTH_MODEL.md` | Source health states and readonly observability signals for source coverage, freshness, and drift. |
| `docs/operational/OPERATIONAL_INTELLIGENCE_AUTOMATION.md` | Operational intelligence automation philosophy, readonly guarantees, non-goals, and escalation semantics. |
| `docs/deployment/Lobster_01_Deployment_Guide.md` | Production node deployment and runbook for Lobster-01. |

## 5. Core Product Modules

| File | Purpose |
| --- | --- |
| `crawlernest/crawlernest-crawler-core/README.md` | Shared crawler runtime primitives for HTTP, retry, rate limiting, logging, and snapshot hooks; treated as a thin standalone shared crawler subproject boundary. |
| `crawlernest/crawlernest-admission-crawler/README.md` | Admission-specific crawler engine entry doc. |
| `crawlernest/crawlernest-core/README.md` | Shared config, models, logging, and common utilities. |
| `crawlernest/crawlernest-core/entity_resolution/README.md` | Deterministic ranking-entity resolution, alias curation loop, and future resolution direction. |
| `crawlernest/crawlernest-core/multi_source/README.md` | Integration strategy for multiple ranking sources like QS, THE, and ARWU. |
| `crawlernest/crawlernest-core/ranking_aggregation/README.md` | Deterministic ranking aggregation layer. |
| `crawlernest/crawlernest-core/recommendation_engine/README.md` | Deterministic university recommendation engine design. |
| `crawlernest/crawlernest-schema/README.md` | Source of truth for the database schema. |
| `crawlernest/crawlernest-db-writer/README.md` | Database ingestion and write path. |
| `crawlernest/crawlernest-analytics/README.md` | Aggregation, ranking analysis, and export utilities. |
| `crawlernest/crawlernest-tests/README.md` | Integration and regression testing module. |

## 6. Data Ingestion, Jobs, And Samples

| File | Purpose |
| --- | --- |
| `crawlernest/crawlernest-extractors/README.md` | Shared fetch/parse helpers used by ranking and admission crawler engines. |
| `crawlernest/crawlernest-jobs/README.md` | Orchestration for job-based crawling pipelines. |
| `crawlernest/crawlernest-kb/README.md` | Knowledge-base scripts and snapshot storage. |
| `crawlernest/crawlernest-samples/README.md` | Sample HTML, JSON, and CSV files for testing and parser work. |
| `crawlernest/crawlernest-autoeval/README.md` | Auto-evaluation layer for experiments and optimization loops. |
| `crawlernest/crawlernest-autoeval/eval_spec.md` | Scoring metrics and decision rules for auto-evaluation. |
| `crawlernest/crawlernest-autoeval/program.md` | How AutoEval experiments are run operationally. |

## 7. Interfaces And Delivery Surfaces

| File | Purpose |
| --- | --- |
| `crawlernest/crawlernest-api/README.md` | Legacy / transitional API-side material. |
| `crawlernest/crawlernest-cli/README.md` | Legacy CLI-side material. |
| `crawlernest/crawlernest-web/README.md` | Official Next.js website MVP entry document. |
| `crawlernest/crawlernest-web/AGENTS.md` | Frontend-specific working conventions for agents and contributors. |
| `crawlernest/crawlernest-web/CLAUDE.md` | Thin redirect doc that points back to `AGENTS.md`. |
| `crawlernest/servise_for_java/readmeforjava.md` | Java backend service notes for the Clawer platform. |
| `crawlernest/crawlernest-infra/README.md` | Infrastructure-level project config and compliance notes. |

## 8. Normalization And Recommendation Track

| File | Purpose |
| --- | --- |
| `crawlernest/crawlernest-normalization/README.md` | Main normalization module overview (C engine). |
| `crawlernest/crawlernest-normalization/c_engine/docs/architecture.md` | Detailed architecture for the C-based normalization engine. |
| `crawlernest/crawlernest-normalization-py/README.md` | Python-side normalization constants and mappings. |
| `crawlernest/crawlernest-recommendation/README.md` | Recommendation module overview and future direction. |

## 9. Mini-Agent Track

`legacy/mini_agent/` is the lightweight Python mini-agent project. The former
`crawlernest/crawlernest-mini-agent/` tree was a vendored third-party "Claw Code"
checkout (Python + Rust) that no CrawlerNest code imported and that shipped
without its own LICENSE; it has been removed from the repository along with its
docs.

| File | Purpose |
| --- | --- |
| `legacy/mini_agent/README.md` | Entry doc for the lightweight Python mini-agent project. |

## 10. Legacy And Compatibility Docs

These files preserve older narratives or compatibility paths. They are useful
for archaeology, but they are not the current source of truth.

| File | Note |
| --- | --- |
| `docs/legacy/REPO_STRUCTURE_legacy.md` | Previous long-form repository structure narrative. Current entrypoint: `docs/REPOSITORY_MAP.md`. |
| `docs/legacy/SYSTEM_ENGINE_ARCHITECTURE_legacy.md` | Previous long-form system/engine architecture narrative. Current entrypoint: `docs/ARCHITECTURE_OVERVIEW.md`. |
| `crawlernest/crawlernest-web/CLAUDE.md` | Redirect-style file kept as a tool-facing entrypoint to `AGENTS.md`. |

## Suggested Cleanup

To keep doc sprawl under control:

1. Keep `docs/README.md` as the human-facing docs hub.
2. Keep the five current docs in `docs/` as the canonical operational truth.
3. Keep older long-form architecture material in `docs/legacy/`.
4. Keep compatibility wrappers short.
5. Update this index whenever a new top-level module doc is added.

## Recently Updated Narrative Areas

The following docs were recently synchronized to reflect the current ranking workflow:

- root project overviews
- repo structure and system-engine docs
- execution-vs-vision architecture split
- ranking crawler module overview
- system architecture narratives
- entity resolution overview
- whitepaper chapter for ranking production and resolution workflow
