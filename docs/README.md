# CrawlerNest Documentation Hub

This folder is organized around a small set of current canonical docs, with
older architecture narratives preserved under `docs/legacy/` for historical
context.

## Start Here

Read these documents first when onboarding or debugging the current system:

1. [Architecture Overview](ARCHITECTURE_OVERVIEW.md)
2. [Repository Map](REPOSITORY_MAP.md)
3. [Data Flow](DATA_FLOW.md)
4. [Operational Runbook](OPERATIONAL_RUNBOOK.md)
5. [API Surface](API_SURFACE.md)

These five files are the current source of truth for architecture, repository
layout, data movement, operations, and endpoint coverage.

## Current Reference Docs

| File | Purpose |
| --- | --- |
| [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md) | Current high-level system architecture and ASCII maps. |
| [REPOSITORY_MAP.md](REPOSITORY_MAP.md) | Current repository and major directory map. |
| [DATA_FLOW.md](DATA_FLOW.md) | Ranking and subject ranking flow from source to frontend. |
| [OPERATIONAL_RUNBOOK.md](OPERATIONAL_RUNBOOK.md) | Startup, smoke checks, daily jobs, snapshots, diagnostics, rollback. |
| [API_SURFACE.md](API_SURFACE.md) | Product, diagnostics, health, freshness, and explainability endpoint catalog. |
| [PROJECT_STATE_REVIEW.md](PROJECT_STATE_REVIEW.md) | Current maturity, inventory, risks, readiness, and next-phase priorities. |
| [CI_PIPELINES.md](CI_PIPELINES.md) | GitHub Actions workflow summary and troubleshooting notes. |
| [SCHEDULED_OPERATIONS.md](SCHEDULED_OPERATIONS.md) | Cron and scheduled pipeline automation details. |
| [DEMO_CHECKLIST.md](DEMO_CHECKLIST.md) | Pre-demo and handover checklist. |
| [LOCAL_TROUBLESHOOTING.md](LOCAL_TROUBLESHOOTING.md) | Local environment issues and fixes. |
| [AI_DEV_WORKFLOW.md](AI_DEV_WORKFLOW.md) | AI-assisted development workflow and crawlernest-agents integration notes. |

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
