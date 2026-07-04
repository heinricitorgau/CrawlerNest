# CrawlerNest Agent Repo Audit

## 1. Current State Audit

The original fork was a broad "AI agency" style repository with many domain divisions. Top-level folders included:

- `engineering/`
- `design/`
- `marketing/`
- `sales/`
- `finance/`
- `product/`
- `project-management/`
- `testing/`
- `support/`
- `strategy/`
- `specialized/`
- `game-development/`
- `spatial-computing/`
- `academic/`
- `integrations/`
- `examples/`

The strongest reusable content lived in engineering-oriented prompts such as:

- codebase onboarding
- code review
- data engineering
- database optimization
- technical writing
- software architecture
- workflow design
- reality checking / testing skepticism

The noisiest content for CrawlerNest included:

- marketing and paid media
- sales and revenue operations
- finance roles
- game development and XR
- academic personas
- customer support and hospitality
- highly niche or unrelated specialized roles

## 2. Keep / Remove Decision

### Keep or Rewrite

- `engineering-codebase-onboarding-engineer` -> rewritten as `crawlernest-repo-onboarding`
- `engineering-code-reviewer` -> rewritten as `crawlernest-code-reviewer`
- `engineering-data-engineer` -> rewritten as `crawlernest-data-pipeline-engineer`
- `engineering-database-optimizer` -> rewritten as `crawlernest-postgres-optimizer`
- `engineering-technical-writer` -> rewritten as `crawlernest-technical-writer`
- `specialized-workflow-architect` -> rewritten as `crawlernest-workflow-architect`
- `testing-reality-checker` plus SRE ideas -> merged into `crawlernest-debug-reliability-engineer`

### Remove

- all non-engineering business functions
- most showcase-oriented divisions and niche specialists
- large multi-tool integration surface area that was only useful for the original broad catalog
- example scenarios unrelated to CrawlerNest development

## 3. New Repository Structure

```text
.
├── agents/
│   ├── crawlernest-code-reviewer.md
│   ├── crawlernest-data-pipeline-engineer.md
│   ├── crawlernest-debug-reliability-engineer.md
│   ├── crawlernest-postgres-optimizer.md
│   ├── crawlernest-repo-onboarding.md
│   ├── crawlernest-technical-writer.md
│   └── crawlernest-workflow-architect.md
├── docs/
│   ├── phase-2-expansion.md
│   └── repo-audit.md
├── templates/
│   ├── adr-template.md
│   └── workflow-spec.md
├── scripts/
│   ├── install.sh
│   └── lint-agents.sh
├── README.md
└── CONTRIBUTING.md
```

## 4. MVP Agent Set

The MVP keeps seven agents. This is intentionally below the original scale and within the target range of 4-8 core roles.

1. Repo onboarding
2. Code review
3. Data pipeline engineering
4. PostgreSQL optimization
5. Workflow architecture
6. Debugging and reliability
7. Technical writing

Why this set works:

- it covers the full CrawlerNest lifecycle from understanding to implementation support to review and docs
- it matches actual project needs instead of imaginary future departments
- it leaves architecture and reliability covered without introducing unnecessary role overlap

## 5. Positioning Rewrite

### Recommended Repo Name

`crawlernest-ai-dev-system`

### Suggested Repository Description

Focused AI-assisted development system for CrawlerNest, built around a small set of engineering agents for onboarding, review, data pipelines, PostgreSQL, workflow design, debugging, and documentation.

### README Opening Direction

Describe the repo as a focused internal development system, not a broad marketplace of specialists. Emphasize maintainability, real engineering workflows, and single-operator practicality.

## 6. Concrete File Adjustment Plan

### Deleted Directories

- `academic/`
- `design/`
- `engineering/`
- `examples/`
- `finance/`
- `game-development/`
- `integrations/`
- `marketing/`
- `paid-media/`
- `product/`
- `project-management/`
- `sales/`
- `spatial-computing/`
- `specialized/`
- `strategy/`
- `support/`
- `testing/`

### Deleted or Simplified Files

- `scripts/convert.sh`
- `scripts/i18n/*`
- original large-scale integration READMEs
- workflow files referencing the old category layout

### Rewritten Files

- `README.md`
- `CONTRIBUTING.md`
- `scripts/install.sh`
- `scripts/lint-agents.sh`
- `.github/workflows/lint-agents.yml`
- `.github/ISSUE_TEMPLATE/new-agent-request.yml`
- `.github/PULL_REQUEST_TEMPLATE.md`

### New Files

- `docs/repo-audit.md`
- `docs/phase-2-expansion.md`
- `templates/adr-template.md`
- `templates/workflow-spec.md`
- curated CrawlerNest agents in `agents/`

## 7. Phase 2 Expansion Suggestions

Only expand after the MVP is used in real work. The next additions should be demand-driven, not category-driven.

Good candidates:

- `crawlernest-recommendation-analyst`
- `crawlernest-schema-migration-planner`
- `crawlernest-data-quality-auditor`
- `crawlernest-runbook-operator`

Bad expansion pattern:

- recreating divisions for every possible engineering or business role
- adding agents before a repeated workflow actually exists
- splitting one responsibility into multiple near-duplicate personas
