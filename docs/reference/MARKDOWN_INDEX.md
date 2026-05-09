# Markdown Index

This file is a curated index of the project-owned Markdown documents in this
repository.

## Scope

Included:
- Root docs
- `docs/`
- Module `README.md` and design docs under `crawlernest/`
- `mini_agent/README.md`
- `deployment-support/lobster-01/README_NODE.md`

Excluded from this index:
- `.venv/`, `.venv-1/`
- `node_modules/`
- `.claude/worktrees/`
- mirrored module docs under `deployment-support/lobster-01/crawlernest/`

## Reading Order

If someone is new to the repo, this is the fastest path:

1. `README.md`
2. `README.zh-TW.md`
3. `docs/README.md`
4. `docs/ARCHITECTURE_OVERVIEW.md`
5. `docs/REPOSITORY_MAP.md`
6. `docs/DATA_FLOW.md`
7. `docs/OPERATIONAL_RUNBOOK.md`
8. `docs/API_SURFACE.md`
9. `docs/PROJECT_STATE_REVIEW.md`
10. `docs/CI_PIPELINES.md`
11. `docs/foundation/TESTING_GUIDE.md`

## 1. Root Entry Docs

| File | Purpose |
| --- | --- |
| `README.md` | Main English project entrypoint and overall repo introduction. |
| `README.zh-TW.md` | Traditional Chinese version of the main project overview. |
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
| `docs/AI_DEV_WORKFLOW.md` | AI-assisted development workflow and crawlernest-agents integration notes. |

## 3. Architecture And Platform Design

| File | Purpose |
| --- | --- |
| `docs/ARCHITECTURE_OVERVIEW.md` | Current high-level architecture, system maps, and rendered diagrams. |
| `docs/REPOSITORY_MAP.md` | Current repository structure map and onboarding guide. |
| `docs/DATA_FLOW.md` | QS/THE/ARWU and subject ranking data flow from source to frontend. |
| `docs/OPERATIONAL_RUNBOOK.md` | Startup, smoke checks, daily pipeline, snapshots, diagnostics, CI troubleshooting, and rollback guidance. |
| `docs/API_SURFACE.md` | Current API endpoint catalog for rankings, subjects, diagnostics, explainability, health, and freshness. |
| `docs/PROJECT_STATE_REVIEW.md` | Current project maturity, inventory, operational risks, technical debt, scaling risks, and next-phase priorities. |
| `docs/architecture/REPO_STRUCTURE.md` | Compatibility wrapper that points to `docs/REPOSITORY_MAP.md`. |
| `docs/architecture/SYSTEM_ENGINE_ARCHITECTURE.md` | Compatibility wrapper that points to current architecture docs. |
| `crawlernest/crawlernest-docs/SYSTEM_ARCHITECTURE.md` | Legacy mirror that now redirects readers to the canonical architecture docs in `docs/`. |
| `crawlernest/crawlernest-docs/architecture.md` | Compatibility architecture note kept to avoid stale inner-workspace links. |

## 4. Deployment And Operations

| File | Purpose |
| --- | --- |
| `docs/CI_PIPELINES.md` | GitHub Actions workflow summary and troubleshooting notes. |
| `docs/SCHEDULED_OPERATIONS.md` | Cron and scheduled pipeline automation details. |
| `docs/DEMO_CHECKLIST.md` | Pre-demo and handover checklist. |
| `docs/LOCAL_TROUBLESHOOTING.md` | Local environment issues and fixes. |
| `docs/OPERATIONAL_RECOVERY.md` | Recovery guidance for PostgreSQL, analytics views, datasource issues, snapshots, and rollback. |
| `docs/PIPELINE_HEALTH_MODEL.md` | Health states, thresholds, freshness expectations, and source coverage model. |
| `docs/PYTHON_ENVIRONMENT.md` | Python venv, psycopg2, PEP 668, and runtime consistency notes. |
| `docs/BACKUP_RESTORE_DRILL.md` | Readonly-safe backup, restore, rollback, and disaster-recovery drill guidance. |
| `docs/SNAPSHOT_COMPARISON.md` | Snapshot comparison workflow for coverage, freshness, drift, and failure-state fixtures. |
| `docs/deployment/Lobster_01_Deployment_Guide.md` | Production node deployment and runbook for Lobster-01. |
| `deployment-support/lobster-01/README_NODE.md` | Operational notes for the Lobster-01 crawler node environment. |

## 5. Core Product Modules

| File | Purpose |
| --- | --- |
| `crawlernest/crawlernest-crawler-core/README.md` | Shared crawler runtime primitives for HTTP, retry, rate limiting, logging, and snapshot hooks; treated as a thin standalone shared crawler subproject boundary. |
| `crawlernest/crawlernest-ranking-crawler/README.md` | Ranking-specific crawler engine entry doc. |
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
| `crawlernest/crawlernest-normalization/README.md` | Main normalization module overview. |
| `crawlernest/crawlernest-normalization/c_engine/docs/architecture.md` | Detailed architecture for the C-based normalization engine. |
| `crawlernest/crawlernest-normalization-py/README.md` | Python-side normalization constants and mappings. |
| `crawlernest/crawlernest-recommendation/README.md` | Recommendation module overview and future direction. |

## 9. Mini-Agent Track

There are two mini-agent areas in this repo:
- `mini_agent/` at the repo root: lightweight Python mini-agent project
- `crawlernest/crawlernest-mini-agent/`: broader Claw Code system docs, including Rust parity work

| File | Purpose |
| --- | --- |
| `mini_agent/README.md` | Entry doc for the lightweight mini-agent project at repo root. |
| `crawlernest/crawlernest-mini-agent/README.md` | Main overview of the full mini-agent system. |
| `crawlernest/crawlernest-mini-agent/PHILOSOPHY.md` | Design philosophy and intended abstraction layer. |
| `crawlernest/crawlernest-mini-agent/USAGE.md` | Canonical usage guide for the mini-agent workflow. |
| `crawlernest/crawlernest-mini-agent/ROADMAP.md` | Planned milestones and future direction. |
| `crawlernest/crawlernest-mini-agent/CLAUDE.md` | Contributor guidance for Claude Code usage in this subproject. |
| `crawlernest/crawlernest-mini-agent/docs/container.md` | Container-first workflow guidance. |
| `crawlernest/crawlernest-mini-agent/rust/README.md` | Rust implementation overview. |
| `crawlernest/crawlernest-mini-agent/PARITY.md` | Canonical parity status for the mini-agent Rust port. |
| `crawlernest/crawlernest-mini-agent/rust/MOCK_PARITY_HARNESS.md` | Deterministic mock LLM parity harness notes. |
| `crawlernest/crawlernest-mini-agent/rust/TUI-ENHANCEMENT-PLAN.md` | TUI enhancement plan for the Rust implementation. |

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
