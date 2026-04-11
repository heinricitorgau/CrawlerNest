# Markdown Index

This file is a curated index of the project-owned Markdown documents under `/Users/test/Desktop/crawlernest`.

## Scope

Included:
- Root docs
- `docs/`
- Module `README.md` and design docs under `crawlernest/`
- `mini_agent/README.md`
- `lobster-01/README_NODE.md`

Excluded from this index:
- `.venv/`, `.venv-1/`
- `node_modules/`
- `.claude/worktrees/`
- mirrored module docs under `lobster-01/crawlernest/`

## Reading Order

If someone is new to the repo, this is the fastest path:

1. `README.md`
2. `README.zh-TW.md`
3. `docs/REPO_STRUCTURE.md`
4. `docs/foundation/MASTER_PROJECT_PLAN.md`
5. `docs/foundation/Whitepaper.md`
6. `crawlernest/crawlernest-docs/SYSTEM_ARCHITECTURE.md`
7. `docs/foundation/TESTING_GUIDE.md`

## 1. Root Entry Docs

| File | Purpose |
| --- | --- |
| `README.md` | Main English project entrypoint and overall repo introduction. |
| `README.zh-TW.md` | Traditional Chinese version of the main project overview. |

## 2. Foundation And Repo Governance

| File | Purpose |
| --- | --- |
| `docs/REPO_STRUCTURE.md` | Explains the repo's two-level workspace layout and where major systems live. |
| `docs/foundation/MASTER_PROJECT_PLAN.md` | Master plan covering scope, phases, and project-level priorities. |
| `docs/foundation/Whitepaper.md` | High-level architecture whitepaper in Traditional Chinese. |
| `docs/foundation/DEV_WORKFLOW.md` | Expected engineering workflow for implementation and delivery. |
| `docs/foundation/MODULE_OWNERSHIP.md` | Ownership boundaries across the system. |
| `docs/foundation/TESTING_GUIDE.md` | Testing, validation, and maintenance guidance. |

## 3. Architecture And Platform Design

| File | Purpose |
| --- | --- |
| `crawlernest/crawlernest-docs/SYSTEM_ARCHITECTURE.md` | System-level architecture for the CrawlerNest platform. |
| `crawlernest/crawlernest-docs/architecture.md` | Broader platform architecture narrative and processing model. |
| `docs/frontend_api_mapping.md` | Maps frontend pages to backend API endpoints for the website MVP. |

## 4. Deployment And Operations

| File | Purpose |
| --- | --- |
| `docs/deployment/Lobster_01_Deployment_Guide.md` | Production node deployment and runbook for Lobster-01. |
| `lobster-01/README_NODE.md` | Operational notes for the Lobster-01 crawler node environment. |

## 5. Core Product Modules

| File | Purpose |
| --- | --- |
| `crawlernest/crawlernest-core/README.md` | Shared config, models, logging, and common utilities. |
| `crawlernest/crawlernest-core/entity_resolution/README.md` | Entity resolution logic for university identity cleanup and matching. |
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
| `crawlernest/crawlernest-extractors/README.md` | Source-specific crawling, fetching, and parsing components. |
| `crawlernest/crawlernest-jobs/README.md` | Orchestration for job-based crawling pipelines. |
| `crawlernest/crawlernest-kb/README.md` | Knowledge-base scripts and snapshot storage. |
| `crawlernest/crawlernest-samples/README.md` | Sample HTML, JSON, and CSV files for testing and parser work. |
| `crawlernest/crawlernest-autoeval/README.md` | Auto-evaluation layer for experiments and optimization loops. |
| `crawlernest/crawlernest-autoeval/eval_spec.md` | Scoring metrics and decision rules for auto-evaluation. |
| `crawlernest/crawlernest-autoeval/program.md` | How AutoEval experiments are run operationally. |

## 7. Interfaces And Delivery Surfaces

| File | Purpose |
| --- | --- |
| `crawlernest/crawlernest-api/README.md` | Interactive API/TUI layer and validation entrypoints. |
| `crawlernest/crawlernest-cli/README.md` | Command-line interface and interactive tooling. |
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

## 10. Generated, Repeated, Or Lower-Priority Docs

These files are useful, but they are not top-level reference docs:

| File | Note |
| --- | --- |
| `crawlernest/crawlernest-web/CLAUDE.md` | Redirect-style file kept as a tool-facing entrypoint to `AGENTS.md`. |

## Suggested Cleanup

If you want to reduce doc sprawl further, these are the easiest wins:

1. Decide one canonical architecture doc between `crawlernest/crawlernest-docs/SYSTEM_ARCHITECTURE.md` and `crawlernest/crawlernest-docs/architecture.md`, then cross-link them clearly.
2. Keep `docs/MARKDOWN_INDEX.md` updated whenever a new top-level module doc is added.
