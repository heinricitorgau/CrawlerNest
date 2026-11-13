# CrawlerNest Documentation Hub

Every document under `docs/` is listed here once, by folder. New to the project? Set it up with
[GETTING_STARTED.md](GETTING_STARTED.md), then read the five docs below.

## Start Here

1. [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md)
2. [REPOSITORY_MAP.md](REPOSITORY_MAP.md)
3. [DATA_FLOW.md](DATA_FLOW.md)
4. [OPERATIONAL_RUNBOOK.md](operational/OPERATIONAL_RUNBOOK.md)
5. [API_SURFACE.md](API_SURFACE.md)

These five are the current source of truth for architecture, repository layout, data movement, operations and endpoint coverage.

## Catalog

### Top level

The current reference docs. Five of them are linked from `index.html` (the GitHub Pages landing page) and several are named by code, scripts or `CLAUDE.md`, so they stay here.

| File | Purpose |
| --- | --- |
| [API_SURFACE.md](API_SURFACE.md) | Product, diagnostics, health, freshness, and explainability endpoint catalog. |
| [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md) | Current high-level system architecture and rendered diagrams. |
| [AUTH_LIMITATIONS.md](AUTH_LIMITATIONS.md) | Auth model, non-goals, localhost assumptions, scaling risks, and future requirements. |
| [DATA_FLOW.md](DATA_FLOW.md) | Ranking and subject ranking flow from source to frontend. |
| [GETTING_STARTED.md](GETTING_STARTED.md) | Canonical setup from scratch: prerequisites, database bootstrap, first data load, troubleshooting. |
| [LOCAL_TROUBLESHOOTING.md](LOCAL_TROUBLESHOOTING.md) | Local environment issues and fixes. |
| [PROJECT_STATE_REVIEW.md](PROJECT_STATE_REVIEW.md) | Current maturity, inventory, risks, readiness, and next-phase priorities. |
| [PYTHON_ENVIRONMENT.md](PYTHON_ENVIRONMENT.md) | Python venv, psycopg2, PEP 668, and runtime consistency notes. |
| [REPOSITORY_MAP.md](REPOSITORY_MAP.md) | Current repository and major directory map. |
| [USER_DATA_SAFETY_REVIEW.md](USER_DATA_SAFETY_REVIEW.md) | User data safety review: isolation guarantees, validation hardening, session model, operational limits. |
| [UX_STABILIZATION_NOTES.md](UX_STABILIZATION_NOTES.md) | UX stabilization pass: loading/error/session-expired states, save button consistency, shared auth messages, known limits. |
| `COMMIT_LOG.md` | Generated commit history. Local only (gitignored): `python3 scripts/generate_commit_log.py` writes it. |

### `agent/` Agent and model providers

`/agent`, Tassel, provider bridges and the demo material for them.

| File | Purpose |
| --- | --- |
| [AGENTS_PIPELINE_ANALYSIS.md](agent/AGENTS_PIPELINE_ANALYSIS.md) | How CrawlerNest optionally calls the sibling `crawlernest-agents` repository. |
| [AGENT_COMPETITION_VALUE.md](agent/AGENT_COMPETITION_VALUE.md) | Phase 4 rehearsal: honest evaluation of the agent's competition value, strengths and weaknesses. |
| [AGENT_CONTEXT_FLOW.md](agent/AGENT_CONTEXT_FLOW.md) | The readonly repository context snapshot sent with agent prompts. |
| [AGENT_DEMO_EVALUATION.md](agent/AGENT_DEMO_EVALUATION.md) | Rubric for whether `/agent` responses are demo-ready. |
| [AGENT_DEMO_FALLBACK.md](agent/AGENT_DEMO_FALLBACK.md) | Keeping the `/agent` demo going when a model provider is unavailable. |
| [AGENT_DEMO_PROMPTS.md](agent/AGENT_DEMO_PROMPTS.md) | Prompt library and expected answers for consistent `/agent` demos. |
| [AGENT_MODEL_INTEGRATION.md](agent/AGENT_MODEL_INTEGRATION.md) | Readonly `/agent` model provider bridge, env vars, fallback behavior, and safety boundaries. |
| [AGENT_PROVIDER_MATRIX.md](agent/AGENT_PROVIDER_MATRIX.md) | Model provider choices for `/agent` demo use, compared. |
| [AI_DEV_WORKFLOW.md](agent/AI_DEV_WORKFLOW.md) | AI-assisted development workflow and crawlernest-agents integration notes. |
| [TASSEL_ASSISTANT.md](agent/TASSEL_ASSISTANT.md) | Tassel, the `/desk` application counselor: live tool loop in the Spring Boot API. |

### `analytics/` Analytics

What analytics show and the honesty contract they follow.

| File | Purpose |
| --- | --- |
| [ANALYTICS_EXPLAINABILITY.md](analytics/ANALYTICS_EXPLAINABILITY.md) | The caveats honesty contract every analytics response follows; `test_caveat_contract.py` holds code to it. |
| [ANALYTICS_SURFACE_PLAN.md](analytics/ANALYTICS_SURFACE_PLAN.md) | Which analytics capabilities are worth demonstrating, and why. |
| [ANALYTICS_VISUALIZATION_PLAN.md](analytics/ANALYTICS_VISUALIZATION_PLAN.md) | Phase 3 visualization decisions: which analytics views to build, why, and operational honesty considerations. |
| [RECOMMENDATION_EVIDENCE_MODEL.md](analytics/RECOMMENDATION_EVIDENCE_MODEL.md) | Phase 2: the evidence model behind recommendations. |

### `architecture/` Architecture

Desk design, plus compatibility entrypoints for older links.

| File | Purpose |
| --- | --- |
| [DESK_SCHEMA_AND_API.md](architecture/DESK_SCHEMA_AND_API.md) | "Your desk": schema and API design (live since 2026-10-18). |
| [REPO_STRUCTURE.md](architecture/REPO_STRUCTURE.md) | Compatibility entrypoint for older repository-structure links. |
| [SYSTEM_ENGINE_ARCHITECTURE.md](architecture/SYSTEM_ENGINE_ARCHITECTURE.md) | Compatibility entrypoint for older system-architecture links. |

### `competition/` Competition track

Competition positioning and the Phase 4 rehearsal reviews.

| File | Purpose |
| --- | --- |
| [COMPETITION_DEMO_NARRATIVE.md](competition/COMPETITION_DEMO_NARRATIVE.md) | Live demo flow, talking points and required caveats. |
| [COMPETITION_READINESS_REVIEW.md](competition/COMPETITION_READINESS_REVIEW.md) | Phase 4 rehearsal: final competition-readiness assessment of v0.1. |
| [COMPETITION_STORYTELLING.md](competition/COMPETITION_STORYTELLING.md) | Competition demo storytelling framework: what to say, what to avoid, required caveats. |
| [COMPETITION_TRACK.md](competition/COMPETITION_TRACK.md) | Positioning for competition and Dispatch-style reviews. |
| [DEMO_NARRATIVE_AUDIT.md](competition/DEMO_NARRATIVE_AUDIT.md) | Phase 4 rehearsal: does the narrative answer what a judge needs answered. |
| [JUDGE_ATTENTION_STRATEGY.md](competition/JUDGE_ATTENTION_STRATEGY.md) | Phase 4 judge strategy: high-impact screens, misunderstanding risks, framing guidance. |
| [JUDGE_QUESTION_BANK.md](competition/JUDGE_QUESTION_BANK.md) | Phase 4 rehearsal: judge questions from four reviewer perspectives. |

### `data/` Data, entities and source health

Entity repairs, the QS archive, source health and report models.

| File | Purpose |
| --- | --- |
| [CONFIDENCE_CONSISTENCY_REVIEW.md](data/CONFIDENCE_CONSISTENCY_REVIEW.md) | Confidence consistency and intentional divergence across reports. |
| [DUPLICATE_MERGE_2026-10-12.md](data/DUPLICATE_MERGE_2026-10-12.md) | The 112 merges of one university carried as two records: evidence, rehearsal, what was not merged. |
| [ENTITY_REVIEW_QUEUE.md](data/ENTITY_REVIEW_QUEUE.md) | The read-only review queue for duplicate records and false merges (`entity_review_candidates.py`). |
| [ENTITY_SPLIT_2026-10-03.md](data/ENTITY_SPLIT_2026-10-03.md) | Seven source entities taken off another university's canonical (the Miami split). |
| [FRESHNESS_CONSISTENCY_REVIEW.md](data/FRESHNESS_CONSISTENCY_REVIEW.md) | Freshness semantics consistency review across health checks, reports, summaries, and snapshots. |
| [PIPELINE_HEALTH_MODEL.md](data/PIPELINE_HEALTH_MODEL.md) | Health states, thresholds, freshness expectations, and source coverage model. |
| [QS_ARCHIVE_DISCLOSURE_DESIGN.md](data/QS_ARCHIVE_DISCLOSURE_DESIGN.md) | (zh-TW) How archived QS and THE editions are disclosed; option A adopted 2026-10-03. |
| [QS_ARCHIVE_LOADER_DESIGN.md](data/QS_ARCHIVE_LOADER_DESIGN.md) | (zh-TW) Design of the QS Internet Archive loader, implemented 2026-10-03 as `crawlernest-jobs/qs_archive_loader.py`. |
| [REPORT_CRITICALITY.md](data/REPORT_CRITICALITY.md) | Critical / important / reference classification for all generated reports and release artifacts. |
| [REPORT_LIFECYCLE.md](data/REPORT_LIFECYCLE.md) | Producer, consumer, freshness expectation, lifecycle category, and archival expectation per report. |
| [REPORT_RELATIONSHIPS.md](data/REPORT_RELATIONSHIPS.md) | Relationship map for reports, snapshots, diagnostics, release bundles, and demo summaries. |
| [SIGNAL_TO_NOISE_REVIEW.md](data/SIGNAL_TO_NOISE_REVIEW.md) | High-value vs secondary signal classification; recommended reading hierarchy by operator role. |
| [SNAPSHOT_COMPARISON.md](data/SNAPSHOT_COMPARISON.md) | Compare operational snapshots for drift and coverage changes. |
| [SNAPSHOT_LINEAGE.md](data/SNAPSHOT_LINEAGE.md) | Snapshot lifecycle, timeline derivation, comparison, freshness, and drift relationships. |
| [SOURCE_COMPLETENESS_REVIEW.md](data/SOURCE_COMPLETENESS_REVIEW.md) | Source completeness analysis for QS, THE, ARWU, and subject rankings. |
| [SOURCE_FRESHNESS_RECOVERY.md](data/SOURCE_FRESHNESS_RECOVERY.md) | Human-led source freshness recovery plan for stale QS and unavailable THE/ARWU. |
| [SOURCE_HEALTH_MODEL.md](data/SOURCE_HEALTH_MODEL.md) | Source health states, signals, severity interpretation, and no-failover boundary. |
| [SOURCE_STATE_EXPLAINABILITY.md](data/SOURCE_STATE_EXPLAINABILITY.md) | Human-readable source-state explanations, maintainer responses, and demo/release caveats. |
| [STABLE_DEGRADED_CONTINUITY.md](data/STABLE_DEGRADED_CONTINUITY.md) | Long-term stable degraded posture guidance: calm maintenance, false urgency avoidance, desensitization risks. |
| [STABLE_DEGRADED_STATE.md](data/STABLE_DEGRADED_STATE.md) | Current RC-1 stable degraded posture: accepted conditions, what is stable, escalation triggers, communication guidance. |

### `demo/` Demo production

Scripts, routes, screenshots and recovery for live demos.

| File | Purpose |
| --- | --- |
| [DEMO_BROWSER_STATE.md](demo/DEMO_BROWSER_STATE.md) | Demo Production Phase 1: browser tabs, zoom, light mode, session state, avoid-during-demo actions. |
| [DEMO_CHECKLIST.md](demo/DEMO_CHECKLIST.md) | Pre-demo and handover checklist. |
| [DEMO_DATA_FREEZE.md](demo/DEMO_DATA_FREEZE.md) | Demo Production Phase 1: which data to freeze before demo, why stable degraded beats unstable freshness. |
| [DEMO_EVIDENCE_SEQUENCING.md](demo/DEMO_EVIDENCE_SEQUENCING.md) | Phase 4 evidence sequencing: revelation order from problem to data to explainability to caveats. |
| [DEMO_FAILURE_RECOVERY.md](demo/DEMO_FAILURE_RECOVERY.md) | Demo Production Phase 1: per-failure recovery steps for backend, session, analytics, browser, environment. |
| [DEMO_FLOW_ARCHITECTURE.md](demo/DEMO_FLOW_ARCHITECTURE.md) | Phase 4 demo flow: timing, screens, core messages, and condensed flows for 30s / 90s / 4-min formats. |
| [DEMO_HONESTY_GUIDELINES.md](demo/DEMO_HONESTY_GUIDELINES.md) | Required caveats, warnings not to soften, acceptable phrasing, and unacceptable phrasing. |
| [DEMO_HONESTY_STRATEGY.md](demo/DEMO_HONESTY_STRATEGY.md) | Phase 4 honesty strategy: which caveats to state aloud, framing without alarm inflation. |
| [DEMO_PRODUCTION_RUNBOOK.md](demo/DEMO_PRODUCTION_RUNBOOK.md) | Demo Production Phase 1: environment startup, browser prep, session verification, pre-demo checklist. |
| [DEMO_RECORDING_PREP.md](demo/DEMO_RECORDING_PREP.md) | Demo Production Phase 1: screen resolution, narration pacing, offline-safe operation, recovery guidance. |
| [DEMO_ROUTE.md](demo/DEMO_ROUTE.md) | Phase 4 demo route: step-by-step click sequence with dwell times and core sentences. |
| [DEMO_SCREENSHOT_PLAN.md](demo/DEMO_SCREENSHOT_PLAN.md) | Phase 4 screenshot plan: which screens to capture, what must be visible, what to crop out. |
| [DEMO_SCRIPT_v0.1.md](demo/DEMO_SCRIPT_v0.1.md) | v0.1 demo script. A frozen copy lives in `releases/v0.1-demo/`; the two have diverged. |
| [DEMO_TIMING_REVIEW.md](demo/DEMO_TIMING_REVIEW.md) | Phase 4 rehearsal: 90-second, 3-minute and 5-minute flows timed. |
| [SCREENSHOT_CAPTURE_WORKFLOW.md](demo/SCREENSHOT_CAPTURE_WORKFLOW.md) | Demo Production Phase 1: priority screenshots, required visible elements, crop guidance, fallback use. |
| [SCREENSHOT_CHECKLIST_v0.1.md](demo/SCREENSHOT_CHECKLIST_v0.1.md) | v0.1 screenshot checklist. A frozen copy lives in `releases/v0.1-demo/`; the two have diverged. |
| [SCREENSHOT_VALUE_REVIEW.md](demo/SCREENSHOT_VALUE_REVIEW.md) | Phase 4 rehearsal: which pages and states are worth capturing. |

### `deployment/` Deployment

Production node runbooks.

| File | Purpose |
| --- | --- |
| [Lobster_01_Deployment_Guide.md](deployment/Lobster_01_Deployment_Guide.md) | Production node deployment and runbook for Lobster-01. |

### `foundation/` Foundation and governance

Plans, contracts, ownership and testing guidance.

| File | Purpose |
| --- | --- |
| [ARCHITECTURE_SCOPE.md](foundation/ARCHITECTURE_SCOPE.md) | Scope guardrails and architectural boundaries. |
| [DATA_CONTRACTS.md](foundation/DATA_CONTRACTS.md) | Data-layer contract definitions. |
| [DEV_WORKFLOW.md](foundation/DEV_WORKFLOW.md) | Expected engineering workflow for implementation and delivery. |
| [DO_NOT_AUTO_MODIFY.md](foundation/DO_NOT_AUTO_MODIFY.md) | Areas that agents and automated patch loops must not rewrite. |
| [MASTER_PROJECT_PLAN.md](foundation/MASTER_PROJECT_PLAN.md) | Historical and planning context for scope, phases, and project-level priorities. |
| [MODULE_OWNERSHIP.md](foundation/MODULE_OWNERSHIP.md) | Ownership boundaries across the system. |
| [TESTING_GUIDE.md](foundation/TESTING_GUIDE.md) | Testing, validation, and maintenance guidance. |
| [Whitepaper.md](foundation/Whitepaper.md) | Long-form architecture and product vision in Traditional Chinese. |

### `history/` Repository history

The 2026-11-11 history rewrite.

| File | Purpose |
| --- | --- |
| [README.md](history/README.md) | The 2026-11-11 history rewrite (`git filter-repo`) and the old-to-new commit map beside it. |

### `legacy/` Legacy

Older architecture narratives, no longer canonical.

| File | Purpose |
| --- | --- |
| [REPO_STRUCTURE_legacy.md](legacy/REPO_STRUCTURE_legacy.md) | Previous long-form repository structure narrative. Current entrypoint: `docs/REPOSITORY_MAP.md`. |
| [SYSTEM_ENGINE_ARCHITECTURE_legacy.md](legacy/SYSTEM_ENGINE_ARCHITECTURE_legacy.md) | Previous long-form system/engine architecture narrative. Current entrypoint: `docs/ARCHITECTURE_OVERVIEW.md`. |

### `migrations/` Migrations

Schema migration guides.

| File | Purpose |
| --- | --- |
| [ADMISSION_SCHEMA_CONVERGENCE.md](migrations/ADMISSION_SCHEMA_CONVERGENCE.md) | Folding the admission pipeline into the entity-resolution schema; cited by the schema DDL. |

### `operational/` Operations and maintenance

Runbooks, scheduled jobs, and the RC-1 maintenance reviews.

| File | Purpose |
| --- | --- |
| [BACKUP_RESTORE_DRILL.md](operational/BACKUP_RESTORE_DRILL.md) | Readonly-safe backup and restore drill procedure. |
| [MAINTENANCE_CADENCE_REVIEW.md](operational/MAINTENANCE_CADENCE_REVIEW.md) | Appropriate cadence for each maintenance activity: daily, weekly, release-demo, incident-only, archival. |
| [MAINTENANCE_CONTINUITY_MODEL.md](operational/MAINTENANCE_CONTINUITY_MODEL.md) | Continuity concept definitions: stable degraded, report, snapshot, confidence, honesty, vocabulary continuity. |
| [MAINTENANCE_DISCIPLINE.md](operational/MAINTENANCE_DISCIPLINE.md) | Behavioral discipline for maintenance: healthy and unhealthy patterns, discipline under pressure, boundaries. |
| [MAINTENANCE_ERGONOMICS_REVIEW.md](operational/MAINTENANCE_ERGONOMICS_REVIEW.md) | Maintenance entrypoint, cognitive load, report discoverability, and workflow friction review. |
| [MAINTENANCE_FATIGUE_REVIEW.md](operational/MAINTENANCE_FATIGUE_REVIEW.md) | Attention hotspots, repeated warning exposure, cognitive overload risks, and fatigue reduction guidance. |
| [MAINTENANCE_PRIORITY_MATRIX.md](operational/MAINTENANCE_PRIORITY_MATRIX.md) | Maintenance priority levels, escalation guidance, response times, and freeze interaction rules. |
| [MAINTENANCE_READING_MODES.md](operational/MAINTENANCE_READING_MODES.md) | Structured reading paths for quick status, release prep, freshness investigation, incident, audit, and onboarding. |
| [MAINTENANCE_RUNBOOK.md](operational/MAINTENANCE_RUNBOOK.md) | Copy-paste friendly maintenance commands for freshness, drift, snapshots, smoke, and bundles. |
| [MAINTENANCE_SIGNAL_CLARITY.md](operational/MAINTENANCE_SIGNAL_CLARITY.md) | Signal hierarchy, authoritative vs derived signals, and recommended reading order. |
| [MAINTENANCE_SUSTAINABILITY_REVIEW.md](operational/MAINTENANCE_SUSTAINABILITY_REVIEW.md) | Sustainable vs complexifying areas; maintenance debt risks; highest-value future cleanup targets. |
| [OPERATIONAL_BOUNDARY_REINFORCEMENT.md](operational/OPERATIONAL_BOUNDARY_REINFORCEMENT.md) | Capabilities intentionally NOT implemented at RC-1 and the reasons for each boundary. |
| [OPERATIONAL_CALMNESS_REVIEW.md](operational/OPERATIONAL_CALMNESS_REVIEW.md) | Calm vs noisy maintenance surface analysis; false urgency risks; calmness preservation guidelines. |
| [OPERATIONAL_CLEANUP_GUIDE.md](operational/OPERATIONAL_CLEANUP_GUIDE.md) | Retention and cleanup guidance for snapshots, reports, bundles, tmp artifacts, and backups. |
| [OPERATIONAL_COHERENCE_REVIEW.md](operational/OPERATIONAL_COHERENCE_REVIEW.md) | Coherence strengths, terminology risks, relationship stability, and cleanup opportunities. |
| [OPERATIONAL_CONFIDENCE_MODEL.md](operational/OPERATIONAL_CONFIDENCE_MODEL.md) | Confidence dimensions, levels, examples, escalation implications, and maintainer behavior. |
| [OPERATIONAL_CONTINUITY_REVIEW.md](operational/OPERATIONAL_CONTINUITY_REVIEW.md) | Continuity strengths, risks, vulnerable assumptions, and report relationships requiring continuity attention. |
| [OPERATIONAL_INDEX.md](operational/OPERATIONAL_INDEX.md) | Unified hierarchy of snapshots, reports, diagnostics, validation, bundles, and agent context artifacts. |
| [OPERATIONAL_INTELLIGENCE_AUTOMATION.md](operational/OPERATIONAL_INTELLIGENCE_AUTOMATION.md) | Readonly operational intelligence automation philosophy, boundaries, and non-goals. |
| [OPERATIONAL_MEMORY_DURABILITY.md](operational/OPERATIONAL_MEMORY_DURABILITY.md) | Artifact durability tiers (durable/semi-durable/ephemeral); bundle and snapshot durability semantics. |
| [OPERATIONAL_MEMORY_PRESERVATION.md](operational/OPERATIONAL_MEMORY_PRESERVATION.md) | What operational knowledge must be preserved long-term vs temporary; bundle archival semantics; handoff requirements. |
| [OPERATIONAL_RECOVERY.md](operational/OPERATIONAL_RECOVERY.md) | Recovery guidance for PostgreSQL, analytics views, datasource issues, snapshots, and rollback. |
| [OPERATIONAL_RESTRAINT_GUIDELINES.md](operational/OPERATIONAL_RESTRAINT_GUIDELINES.md) | When NOT to add automation, diagnostics, reports, wrappers, or scripts; saturation signals; safe addition criteria. |
| [OPERATIONAL_RUNBOOK.md](operational/OPERATIONAL_RUNBOOK.md) | Startup, smoke checks, daily jobs, snapshots, diagnostics, rollback. |
| [OPERATIONAL_SURFACE_REVIEW.md](operational/OPERATIONAL_SURFACE_REVIEW.md) | Review of overlapping reports, terminology risks, and surface-reduction recommendations. |
| [OPERATIONAL_VOCABULARY.md](operational/OPERATIONAL_VOCABULARY.md) | Consolidated operational terminology for stale, degraded, critical, drift, freshness, and validation surfaces. |
| [SCHEDULED_OPERATIONS.md](operational/SCHEDULED_OPERATIONS.md) | Cron and scheduled pipeline automation details. |

### `reference/` Reference

Inventories, the OpenAPI file and the frontend/API map.

| File | Purpose |
| --- | --- |
| [MARKDOWN_INDEX.md](reference/MARKDOWN_INDEX.md) | Repository-wide Markdown inventory, including module docs under `crawlernest/`. |
| [frontend_api_mapping.md](reference/frontend_api_mapping.md) | Frontend surfaces mapped to the backend API groups they call. |

### `release/` Release process

RC-1 reviews, CI and release notes. Data releases themselves are in `releases/`.

| File | Purpose |
| --- | --- |
| [CI_PIPELINES.md](release/CI_PIPELINES.md) | GitHub Actions workflow summary and troubleshooting notes. |
| [RC1_DEPENDENCY_REVIEW.md](release/RC1_DEPENDENCY_REVIEW.md) | RC-1 dependency inventory, pinning concerns, and drift risks. |
| [RC1_ENVIRONMENT_FREEZE.md](release/RC1_ENVIRONMENT_FREEZE.md) | RC-1 environment bounds, verified runtime versions, localhost assumptions, and setup notes. |
| [RC1_FREEZE_SCOPE.md](release/RC1_FREEZE_SCOPE.md) | RC-1 frozen surfaces, allowed changes, and blocked expansion areas. |
| [RC1_RELEASE_HYGIENE.md](release/RC1_RELEASE_HYGIENE.md) | RC-1 artifact, ignore, snapshot, backup, and temporary-output policy. |
| [RC1_STABILITY_REVIEW.md](release/RC1_STABILITY_REVIEW.md) | RC-1 long-run stability review and restart / persistence bounds. |
| [RC1_VALIDATION_RESULTS.md](release/RC1_VALIDATION_RESULTS.md) | RC-1 operational validation summary and accepted limitations. |
| [RELEASE_BUNDLE_SIMPLIFICATION_REVIEW.md](release/RELEASE_BUNDLE_SIMPLIFICATION_REVIEW.md) | Must-exist vs supporting vs optional artifact classification for the v0.1-demo release bundle. |
| [RELEASE_NOTES_v0.1.md](release/RELEASE_NOTES_v0.1.md) | v0.1 demo release notes. A frozen copy lives in `releases/v0.1-demo/`; the two have diverged. |
| [RELEASE_NOTES_v0.2-2026-snapshot.md](release/RELEASE_NOTES_v0.2-2026-snapshot.md) | v0.2 2026 data release freeze notes (the release itself is `releases/v0.2-2026-snapshot/`). |
| [RELEASE_STATE_CHECKLIST.md](release/RELEASE_STATE_CHECKLIST.md) | Demo/release readiness checklist for smoke, snapshots, reports, freshness, drift, and caveats. |
| [RELEASE_STRUCTURE.md](release/RELEASE_STRUCTURE.md) | What the `releases/v0.1-demo/` bundle holds. A frozen copy lives in the bundle; the two have diverged. |
| [VERSION_SCOPE_v0.1.md](release/VERSION_SCOPE_v0.1.md) | Exact scope of the v0.1 milestone. A frozen copy lives in `releases/v0.1-demo/`; the two have diverged. |

### `roadmap/` Roadmap

| File | Purpose |
| --- | --- |
| [v0.3-roadmap.md](roadmap/v0.3-roadmap.md) | v0.3 roadmap, kept for its status record; superseded by v0.4. |
| [v0.4-roadmap.md](roadmap/v0.4-roadmap.md) | The working roadmap since 2026-11-11. |

### `superpowers/` Design specs and plans

Specs and implementation plans written before a change.

| File | Purpose |
| --- | --- |
| [plans/2026-11-09-transient-network-retry.md](superpowers/plans/2026-11-09-transient-network-retry.md) | Implementation plan for retrying transient network failures. |
| [specs/2026-11-09-transient-network-retry-design.md](superpowers/specs/2026-11-09-transient-network-retry-design.md) | Design: transient network failures recover on their own (approved, implemented). |

### `releases/` Data releases

Each release is a self-checking artifact (`manifest.json`, a database dump, notes). CI restores the newest one nightly (`warehouse-validation.yml`) and checks it on change (`release-snapshot.yml`); `scripts/release_snapshot.py build` cuts a new one. Files inside a release are frozen.

| Release | Notes |
| --- | --- |
| [v0.1-demo](releases/v0.1-demo/RELEASE_NOTES_v0.1.md) | The v0.1 demo bundle (`scripts/build_demo_bundle.sh`): report copies, snapshots, screenshots. Its copies of release/demo docs are frozen at bundle time. |
| [v0.2-2026-snapshot](releases/v0.2-2026-snapshot/README.md) | 2026 data freeze (frozen 2026-09-05, ingested 2026-09-04). |
| [v0.3-multi-year-snapshot](releases/v0.3-multi-year-snapshot/README.md) | Multi-year snapshot: THE/ARWU 2015-2024 and the QS archive editions (frozen 2026-11-11). |
| [v0.3.1-qs-2017-relabel](releases/v0.3.1-qs-2017-relabel/README.md) | QS 2016 relabelled as QS 2017 (frozen 2026-11-11). This is the newest release. |

### `assets/`

| Folder | Holds |
| --- | --- |
| `assets/images/` | The banners the two top-level READMEs show. |
| `assets/screenshots/` | README screenshots, written by `scripts/capture_readme_screenshots.sh`. |
| `assets/robots/` | Saved `robots.txt` of QS and THE. |
| `assets/samples/` | Small THE and ARWU source samples. |

## Keeping This Folder Tidy

- **Do not move or rename a file here without updating what names it.** Code comments (Java, TypeScript, nginx), scripts under `scripts/` (many build paths like `docs/<NAME>.md`), `CLAUDE.md`, the GitHub Pages page `index.html` and links from outside the repository all use these paths.
- **A new doc gets a row in this catalog.** `crawlernest-tests/test_docs_catalog.py` fails when a doc is missing here or a link here is broken.
- **Frozen copies stay frozen.** `releases/v0.1-demo/` holds bundle-time copies of `release/` and `demo/` docs; they differ from the live ones on purpose. Update the live doc, not the copy.
- **Current truth lives in the Start Here docs**, governance in `foundation/`, superseded narratives in `legacy/`. Prefer a short compatibility page (as in `architecture/`) to a second copy of long content.
- [reference/MARKDOWN_INDEX.md](reference/MARKDOWN_INDEX.md) inventories Markdown across the whole repository; this page is the complete list for `docs/`.
