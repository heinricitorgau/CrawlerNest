# CrawlerNest Documentation Hub

This folder is organized around a small set of current canonical docs, with
older architecture narratives preserved under `docs/legacy/` for historical
context.

## Start Here

Read these documents first when onboarding or debugging the current system:

1. [Architecture Overview](ARCHITECTURE_OVERVIEW.md)
2. [Repository Map](REPOSITORY_MAP.md)
3. [Data Flow](DATA_FLOW.md)
4. [Operational Runbook](operational/OPERATIONAL_RUNBOOK.md)
5. [API Surface](API_SURFACE.md)

These five files are the current source of truth for architecture, repository
layout, data movement, operations, and endpoint coverage.

## Current Reference Docs

| File | Purpose |
| --- | --- |
| [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md) | Current high-level system architecture and rendered diagrams. |
| [REPOSITORY_MAP.md](REPOSITORY_MAP.md) | Current repository and major directory map. |
| [DATA_FLOW.md](DATA_FLOW.md) | Ranking and subject ranking flow from source to frontend. |
| [OPERATIONAL_RUNBOOK.md](operational/OPERATIONAL_RUNBOOK.md) | Startup, smoke checks, daily jobs, snapshots, diagnostics, rollback. |
| [API_SURFACE.md](API_SURFACE.md) | Product, diagnostics, health, freshness, and explainability endpoint catalog. |
| [PROJECT_STATE_REVIEW.md](PROJECT_STATE_REVIEW.md) | Current maturity, inventory, risks, readiness, and next-phase priorities. |
| [CI_PIPELINES.md](release/CI_PIPELINES.md) | GitHub Actions workflow summary and troubleshooting notes. |
| [SCHEDULED_OPERATIONS.md](operational/SCHEDULED_OPERATIONS.md) | Cron and scheduled pipeline automation details. |
| [PYTHON_ENVIRONMENT.md](PYTHON_ENVIRONMENT.md) | Python venv, psycopg2, PEP 668, and runtime consistency notes. |
| [BACKUP_RESTORE_DRILL.md](operational/BACKUP_RESTORE_DRILL.md) | Readonly-safe backup and restore drill procedure. |
| [SNAPSHOT_COMPARISON.md](data/SNAPSHOT_COMPARISON.md) | Compare operational snapshots for drift and coverage changes. |
| [SOURCE_HEALTH_MODEL.md](data/SOURCE_HEALTH_MODEL.md) | Source health states and readonly observability signals. |
| [OPERATIONAL_INTELLIGENCE_AUTOMATION.md](operational/OPERATIONAL_INTELLIGENCE_AUTOMATION.md) | Readonly operational intelligence automation philosophy, boundaries, and escalation semantics. |
| [DEMO_CHECKLIST.md](demo/DEMO_CHECKLIST.md) | Pre-demo and handover checklist. |
| [LOCAL_TROUBLESHOOTING.md](LOCAL_TROUBLESHOOTING.md) | Local environment issues and fixes. |
| [AI_DEV_WORKFLOW.md](agent/AI_DEV_WORKFLOW.md) | AI-assisted development workflow and crawlernest-agents integration notes. |
| [AGENT_MODEL_INTEGRATION.md](agent/AGENT_MODEL_INTEGRATION.md) | Readonly `/agent` model provider bridge, env vars, fallback behavior, and safety boundaries. |
| [AUTH_LIMITATIONS.md](AUTH_LIMITATIONS.md) | Auth model, non-goals, localhost assumptions, scaling risks, and future requirements. |
| [USER_DATA_SAFETY_REVIEW.md](USER_DATA_SAFETY_REVIEW.md) | User data safety review: isolation guarantees, validation hardening, session model, operational limits. |
| [UX_STABILIZATION_NOTES.md](UX_STABILIZATION_NOTES.md) | UX stabilization pass: loading/error/session-expired states, save button consistency, shared auth messages, known limits. |
| [RC1_ENVIRONMENT_FREEZE.md](release/RC1_ENVIRONMENT_FREEZE.md) | RC-1 environment bounds, verified runtime versions, localhost assumptions, and setup notes. |
| [RC1_DEPENDENCY_REVIEW.md](release/RC1_DEPENDENCY_REVIEW.md) | RC-1 dependency inventory, pinning concerns, and drift risks. |
| [RC1_RELEASE_HYGIENE.md](release/RC1_RELEASE_HYGIENE.md) | RC-1 artifact, ignore, snapshot, backup, and temporary-output policy. |
| [RC1_STABILITY_REVIEW.md](release/RC1_STABILITY_REVIEW.md) | RC-1 long-run stability review and restart / persistence bounds. |
| [RC1_FREEZE_SCOPE.md](release/RC1_FREEZE_SCOPE.md) | RC-1 frozen surfaces, allowed changes, and blocked expansion areas. |
| [RC1_VALIDATION_RESULTS.md](release/RC1_VALIDATION_RESULTS.md) | RC-1 operational validation summary and accepted limitations. |
| [OPERATIONAL_INTELLIGENCE_AUTOMATION.md](operational/OPERATIONAL_INTELLIGENCE_AUTOMATION.md) | Readonly operational intelligence automation philosophy, boundaries, and non-goals. |
| [SOURCE_HEALTH_MODEL.md](data/SOURCE_HEALTH_MODEL.md) | Source health states, signals, severity interpretation, and no-failover boundary. |
| [OPERATIONAL_INDEX.md](operational/OPERATIONAL_INDEX.md) | Unified hierarchy of snapshots, reports, diagnostics, validation, bundles, and agent context artifacts. |
| [OPERATIONAL_VOCABULARY.md](operational/OPERATIONAL_VOCABULARY.md) | Consolidated operational terminology for stale, degraded, critical, drift, freshness, and validation surfaces. |
| [REPORT_RELATIONSHIPS.md](data/REPORT_RELATIONSHIPS.md) | Relationship map for reports, snapshots, diagnostics, release bundles, and demo summaries. |
| [SNAPSHOT_LINEAGE.md](data/SNAPSHOT_LINEAGE.md) | Snapshot lifecycle, timeline derivation, comparison, freshness, and drift relationships. |
| [OPERATIONAL_SURFACE_REVIEW.md](operational/OPERATIONAL_SURFACE_REVIEW.md) | Review of overlapping reports, terminology risks, and surface-reduction recommendations. |
| [MAINTENANCE_PRIORITY_MATRIX.md](operational/MAINTENANCE_PRIORITY_MATRIX.md) | Maintenance priority levels, escalation guidance, response times, and freeze interaction rules. |
| [SOURCE_FRESHNESS_RECOVERY.md](data/SOURCE_FRESHNESS_RECOVERY.md) | Human-led source freshness recovery plan for stale QS and unavailable THE/ARWU. |
| [MAINTENANCE_RUNBOOK.md](operational/MAINTENANCE_RUNBOOK.md) | Copy-paste friendly maintenance commands for freshness, drift, snapshots, smoke, and bundles. |
| [RELEASE_STATE_CHECKLIST.md](release/RELEASE_STATE_CHECKLIST.md) | Demo/release readiness checklist for smoke, snapshots, reports, freshness, drift, and caveats. |
| [OPERATIONAL_CLEANUP_GUIDE.md](operational/OPERATIONAL_CLEANUP_GUIDE.md) | Retention and cleanup guidance for snapshots, reports, bundles, tmp artifacts, and backups. |
| [SOURCE_STATE_EXPLAINABILITY.md](data/SOURCE_STATE_EXPLAINABILITY.md) | Human-readable source-state explanations, maintainer responses, and demo/release caveats. |
| [FRESHNESS_CONSISTENCY_REVIEW.md](data/FRESHNESS_CONSISTENCY_REVIEW.md) | Freshness semantics consistency review across health checks, reports, summaries, and snapshots. |
| [MAINTENANCE_ERGONOMICS_REVIEW.md](operational/MAINTENANCE_ERGONOMICS_REVIEW.md) | Maintenance entrypoint, cognitive load, report discoverability, and workflow friction review. |
| [OPERATIONAL_CONFIDENCE_MODEL.md](operational/OPERATIONAL_CONFIDENCE_MODEL.md) | Confidence dimensions, levels, examples, escalation implications, and maintainer behavior. |
| [SOURCE_COMPLETENESS_REVIEW.md](data/SOURCE_COMPLETENESS_REVIEW.md) | Source completeness analysis for QS, THE, ARWU, and subject rankings. |
| [DEMO_HONESTY_GUIDELINES.md](demo/DEMO_HONESTY_GUIDELINES.md) | Required caveats, warnings not to soften, acceptable phrasing, and unacceptable phrasing. |
| [CONFIDENCE_CONSISTENCY_REVIEW.md](data/CONFIDENCE_CONSISTENCY_REVIEW.md) | Confidence consistency and intentional divergence across reports. |
| [MAINTENANCE_SIGNAL_CLARITY.md](operational/MAINTENANCE_SIGNAL_CLARITY.md) | Signal hierarchy, authoritative vs derived signals, and recommended reading order. |
| [OPERATIONAL_RESTRAINT_GUIDELINES.md](operational/OPERATIONAL_RESTRAINT_GUIDELINES.md) | When NOT to add automation, diagnostics, reports, wrappers, or scripts; saturation signals; safe addition criteria. |
| [MAINTENANCE_SUSTAINABILITY_REVIEW.md](operational/MAINTENANCE_SUSTAINABILITY_REVIEW.md) | Sustainable vs complexifying areas; maintenance debt risks; highest-value future cleanup targets. |
| [SIGNAL_TO_NOISE_REVIEW.md](data/SIGNAL_TO_NOISE_REVIEW.md) | High-value vs secondary signal classification; recommended reading hierarchy by operator role. |
| [OPERATIONAL_BOUNDARY_REINFORCEMENT.md](operational/OPERATIONAL_BOUNDARY_REINFORCEMENT.md) | Capabilities intentionally NOT implemented at RC-1 and the reasons for each boundary. |
| [REPORT_CRITICALITY.md](data/REPORT_CRITICALITY.md) | Critical / important / reference classification for all generated reports and release artifacts. |
| [RELEASE_BUNDLE_SIMPLIFICATION_REVIEW.md](release/RELEASE_BUNDLE_SIMPLIFICATION_REVIEW.md) | Must-exist vs supporting vs optional artifact classification for the v0.1-demo release bundle. |
| [OPERATIONAL_CALMNESS_REVIEW.md](operational/OPERATIONAL_CALMNESS_REVIEW.md) | Calm vs noisy maintenance surface analysis; false urgency risks; calmness preservation guidelines. |
| [REPORT_LIFECYCLE.md](data/REPORT_LIFECYCLE.md) | Producer, consumer, freshness expectation, lifecycle category, and archival expectation per report. |
| [MAINTENANCE_FATIGUE_REVIEW.md](operational/MAINTENANCE_FATIGUE_REVIEW.md) | Attention hotspots, repeated warning exposure, cognitive overload risks, and fatigue reduction guidance. |
| [OPERATIONAL_COHERENCE_REVIEW.md](operational/OPERATIONAL_COHERENCE_REVIEW.md) | Coherence strengths, terminology risks, relationship stability, and cleanup opportunities. |
| [MAINTENANCE_READING_MODES.md](operational/MAINTENANCE_READING_MODES.md) | Structured reading paths for quick status, release prep, freshness investigation, incident, audit, and onboarding. |
| [MAINTENANCE_CADENCE_REVIEW.md](operational/MAINTENANCE_CADENCE_REVIEW.md) | Appropriate cadence for each maintenance activity: daily, weekly, release-demo, incident-only, archival. |
| [OPERATIONAL_MEMORY_PRESERVATION.md](operational/OPERATIONAL_MEMORY_PRESERVATION.md) | What operational knowledge must be preserved long-term vs temporary; bundle archival semantics; handoff requirements. |
| [STABLE_DEGRADED_STATE.md](data/STABLE_DEGRADED_STATE.md) | Current RC-1 stable degraded posture: accepted conditions, what is stable, escalation triggers, communication guidance. |
| [MAINTENANCE_DISCIPLINE.md](operational/MAINTENANCE_DISCIPLINE.md) | Behavioral discipline for maintenance: healthy and unhealthy patterns, discipline under pressure, boundaries. |
| [OPERATIONAL_CONTINUITY_REVIEW.md](operational/OPERATIONAL_CONTINUITY_REVIEW.md) | Continuity strengths, risks, vulnerable assumptions, and report relationships requiring continuity attention. |
| [MAINTENANCE_CONTINUITY_MODEL.md](operational/MAINTENANCE_CONTINUITY_MODEL.md) | Continuity concept definitions: stable degraded, report, snapshot, confidence, honesty, vocabulary continuity. |
| [OPERATIONAL_MEMORY_DURABILITY.md](operational/OPERATIONAL_MEMORY_DURABILITY.md) | Artifact durability tiers (durable/semi-durable/ephemeral); bundle and snapshot durability semantics. |
| [STABLE_DEGRADED_CONTINUITY.md](data/STABLE_DEGRADED_CONTINUITY.md) | Long-term stable degraded posture guidance: calm maintenance, false urgency avoidance, desensitization risks. |
| [ANALYTICS_VISUALIZATION_PLAN.md](analytics/ANALYTICS_VISUALIZATION_PLAN.md) | Phase 3 visualization decisions: which analytics views to build, why, and operational honesty considerations. |
| [COMPETITION_STORYTELLING.md](competition/COMPETITION_STORYTELLING.md) | Competition demo storytelling framework: what to say, what to avoid, required caveats. |
| [DEMO_FLOW_ARCHITECTURE.md](demo/DEMO_FLOW_ARCHITECTURE.md) | Phase 4 demo flow: timing, screens, core messages, and condensed flows for 30s / 90s / 4-min formats. |
| [JUDGE_ATTENTION_STRATEGY.md](competition/JUDGE_ATTENTION_STRATEGY.md) | Phase 4 judge strategy: high-impact screens, misunderstanding risks, framing guidance. |
| [DEMO_ROUTE.md](demo/DEMO_ROUTE.md) | Phase 4 demo route: step-by-step click sequence with dwell times and core sentences. |
| [DEMO_SCREENSHOT_PLAN.md](demo/DEMO_SCREENSHOT_PLAN.md) | Phase 4 screenshot plan: which screens to capture, what must be visible, what to crop out. |
| [DEMO_EVIDENCE_SEQUENCING.md](demo/DEMO_EVIDENCE_SEQUENCING.md) | Phase 4 evidence sequencing: revelation order from problem to data to explainability to caveats. |
| [DEMO_HONESTY_STRATEGY.md](demo/DEMO_HONESTY_STRATEGY.md) | Phase 4 honesty strategy: which caveats to state aloud, framing without alarm inflation. |
| [DEMO_PRODUCTION_RUNBOOK.md](demo/DEMO_PRODUCTION_RUNBOOK.md) | Demo Production Phase 1: environment startup, browser prep, session verification, pre-demo checklist. |
| [DEMO_BROWSER_STATE.md](demo/DEMO_BROWSER_STATE.md) | Demo Production Phase 1: browser tabs, zoom, light mode, session state, avoid-during-demo actions. |
| [SCREENSHOT_CAPTURE_WORKFLOW.md](demo/SCREENSHOT_CAPTURE_WORKFLOW.md) | Demo Production Phase 1: priority screenshots, required visible elements, crop guidance, fallback use. |
| [DEMO_RECORDING_PREP.md](demo/DEMO_RECORDING_PREP.md) | Demo Production Phase 1: screen resolution, narration pacing, offline-safe operation, recovery guidance. |
| [DEMO_DATA_FREEZE.md](demo/DEMO_DATA_FREEZE.md) | Demo Production Phase 1: which data to freeze before demo, why stable degraded beats unstable freshness. |
| [DEMO_FAILURE_RECOVERY.md](demo/DEMO_FAILURE_RECOVERY.md) | Demo Production Phase 1: per-failure recovery steps for backend, session, analytics, browser, environment. |

## Subfolders

| Folder | Purpose |
| --- | --- |
| `architecture/` | Compatibility entrypoints for older architecture links. |
| `foundation/` | Governance, ownership, contracts, testing, and long-form project planning. |
| `deployment/` | Production node deployment runbooks. |
| `reference/` | Indexes, OpenAPI reference, frontend/API mapping. |
| `legacy/` | Preserved older architecture narratives that are no longer canonical. |
| `assets/` | Images, robots samples, and source data samples used by docs or tests. |

## Duplicate-Content Policy

- Keep current operational truth in the five "Start Here" docs.
- Keep governance and long-term vision in `foundation/`.
- Keep historical architecture material in `legacy/`.
- Use compatibility wrappers instead of duplicating long architecture content.
- When adding a new doc, update [reference/MARKDOWN_INDEX.md](reference/MARKDOWN_INDEX.md).

## Legacy Notes

The previous long-form architecture files were preserved here:

- [legacy/REPO_STRUCTURE_legacy.md](legacy/REPO_STRUCTURE_legacy.md)
- [legacy/SYSTEM_ENGINE_ARCHITECTURE_legacy.md](legacy/SYSTEM_ENGINE_ARCHITECTURE_legacy.md)
