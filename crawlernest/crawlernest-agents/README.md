# CrawlerNest AI Dev System

> A focused, repo-native agent collection for AI-assisted CrawlerNest development.

This repository is a trimmed-down fork of a much larger general-purpose agent collection. It is now a small, maintainable system aimed at one real use case: helping a solo builder ship and maintain **CrawlerNest**.

CrawlerNest's core working areas are:

- crawling and ingestion
- extraction and normalization
- PostgreSQL and schema design
- analytics and recommendations
- debugging and reliability
- technical documentation
- workflow and architecture thinking
- code review and repo understanding

This repo intentionally does **not** try to cover marketing, sales, finance, game development, XR, or customer support. The goal is utility, not breadth.

## Project Context

CrawlerNest is a structured data infrastructure system for university intelligence.

Core pipeline: `crawler -> extractor -> normalization -> db_writer -> analytics -> recommendation`

Current characteristics:
- Evolving MVP (not fully production-stable)
- Data-first system (I/O-bound, pipeline-oriented)
- Uses PostgreSQL as primary target database
- Contains modules such as `crawlernest-core`, `crawlernest-api`, `crawlernest-analytics`, `crawlernest-autoeval`, and `crawlernest-cli`
- Uses `run_pipeline.py` as a main orchestration entry point
- Common components include `extractor`, `db_writer`, `exporter`, and `recommendation_engine`

Working principles:
- Conservative (no overclaiming features)
- Truthful (reflect real system state)
- Practical (optimize for working pipeline, not theory)

## Positioning

Repository type: CrawlerNest-specific AI-assisted development system

Design principles:

- Keep the agent set small and high-signal
- Prefer practical engineering work over persona sprawl
- Make structure obvious enough to maintain over time
- Optimize for a single operator with AI assistance
- Preserve room for future expansion without rebuilding the foundation

## Automation Principles

Automation goals:

- reduce obvious mistakes
- standardize repetitive checks
- trigger the correct agent workflow at the correct time
- keep the human engineer in control

Automation non-goals:

- fully autonomous coding
- silent code modification
- multi-agent orchestration without explicit review

## MVP Agents

The first version keeps seven core agents:

| Agent | Purpose | Best for |
|---|---|---|
| [`crawlernest-repo-onboarding`](agents/crawlernest-repo-onboarding.md) | factual repo understanding | onboarding, tracing entry points, mapping data flow |
| [`crawlernest-code-reviewer`](agents/crawlernest-code-reviewer.md) | correctness-focused review | PR review, regression risk, missing tests |
| [`crawlernest-data-pipeline-engineer`](agents/crawlernest-data-pipeline-engineer.md) | data pipeline design and quality | crawler pipelines, normalization, warehouse prep |
| [`crawlernest-postgres-optimizer`](agents/crawlernest-postgres-optimizer.md) | PostgreSQL design and tuning | schema review, query plans, indexes, migrations |
| [`crawlernest-workflow-architect`](agents/crawlernest-workflow-architect.md) | workflow and architecture mapping | ingestion flow design, failure paths, handoffs |
| [`crawlernest-debug-reliability-engineer`](agents/crawlernest-debug-reliability-engineer.md) | debugging and production realism | incident triage, failure analysis, evidence checks |
| [`crawlernest-technical-writer`](agents/crawlernest-technical-writer.md) | technical docs and decision records | README, runbooks, architecture docs, process docs |

## Repo Structure

```text
.
├── agents/         # Curated CrawlerNest-specific agent prompts
├── docs/           # Audit, restructuring rationale, roadmap
├── templates/      # ADR and workflow-spec templates
├── scripts/        # Minimal install and lint helpers
└── .github/        # Lightweight repo automation and templates
```

## Quick Start

Read the agents directly in this repo, or copy them into your preferred tool:

```bash
./scripts/install.sh --target ~/.claude/agents
```

Lint the curated prompts:

```bash
./scripts/lint-agents.sh
```

Install the local git hook:

```bash
./scripts/install-hooks.sh
```

Run tests and generate a debug prompt on failure:

```bash
./scripts/run-tests-with-debug.sh
```

Analyze a pipeline log into an agent-ready prompt:

```bash
./scripts/analyze-pipeline-log.sh tmp/pipeline.log
```

## Naming Recommendation

Recommended rename options:

1. `crawlernest-ai-dev-system`
2. `crawlernest-agents`
3. `crawlernest-dev-agents`

Preferred option: `crawlernest-ai-dev-system`

## Suggested Description

Focused AI-assisted development system for CrawlerNest, with a small set of engineering agents for onboarding, review, data pipelines, PostgreSQL, workflow design, debugging, and technical documentation.

## Supporting Docs

- Agent routing guide: [AGENT_SELECTION.md](AGENT_SELECTION.md)
- Daily development workflow: [DEV_PLAYBOOK.md](DEV_PLAYBOOK.md)
- Prompt templates: [AGENT_PROMPT_LIBRARY.md](AGENT_PROMPT_LIBRARY.md)
- OpenClaw integration skeleton: [openclaw/README.md](openclaw/README.md)
- Antigravity integration skeleton: [antigravity/README.md](antigravity/README.md)
- Audit and restructuring rationale: [docs/repo-audit.md](docs/repo-audit.md)
- Expansion roadmap: [docs/phase-2-expansion.md](docs/phase-2-expansion.md)
- Workflow template: [templates/workflow-spec.md](templates/workflow-spec.md)
- ADR template: [templates/adr-template.md](templates/adr-template.md)

## Timeline

- `2026-04-22`: We designed and implemented a minimal, structured AI-assisted engineering system for CrawlerNest, including curated agents, workflows, automation, and a clean integration into the main repository.

## Non-Goals

- Large agent catalogs
- showcase-style divisions and branding
- non-CrawlerNest business roles
- keeping agents "just in case"
- complex multi-tool integration machinery before it is needed

## License

MIT
