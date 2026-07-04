# Contributing

This repository is intentionally narrow. Contributions should make the CrawlerNest AI dev system more useful for real engineering work, not broader for its own sake.

## What Belongs Here

- improvements to the curated CrawlerNest agents
- better README, runbooks, ADRs, and workflow templates
- small tooling that supports prompt quality or local maintenance
- docs and templates tied to actual CrawlerNest development workflows

## What Does Not Belong Here

- generic business agents
- marketing, sales, finance, support, or game-dev prompts
- role proliferation without a repeated real workflow
- showcase-oriented additions that increase maintenance cost

## Agent Authoring Rules

Each agent file in `agents/` should:

- have YAML frontmatter with `name`, `description`, and `color`
- stay tightly scoped to a real CrawlerNest workflow
- explain concrete responsibilities and limits
- avoid hype, unnecessary roleplay, and redundant overlap

## Contribution Standard

When proposing a new agent or major rewrite, explain:

1. which repeated CrawlerNest workflow it supports
2. why an existing agent is insufficient
3. how the new prompt stays distinct and maintainable

## Validation

Run:

```bash
./scripts/lint-agents.sh
```

before opening a PR.

For local workflow safety, also install the repository hook:

```bash
./scripts/install-hooks.sh
```
