# Phase 2 Expansion

This repo should stay small until real usage proves a repeated need. Add a new agent only if at least one of these is true:

- the current agents are overloaded in a repeated, identifiable way
- a workflow keeps requiring the same framing or checklist
- the new role has clear boundaries and does not duplicate an existing agent

## Good Next Candidates

### CrawlerNest Recommendation Analyst

Use if recommendation tuning becomes its own repeated workflow with ranking logic, scoring interpretation, and evaluation criteria that deserve a dedicated prompt.

### CrawlerNest Data Quality Auditor

Use if validation, anomaly review, and normalization quality checks become frequent enough to deserve their own role.

### CrawlerNest Migration Planner

Use if schema evolution, backfills, and rollout planning become a recurring source of risk.

### CrawlerNest Operations Runbook Agent

Use if the project accumulates enough scheduled jobs, operational commands, and manual recovery procedures to justify a dedicated operations-focused prompt.

## Expansion Rules

- add at most one or two agents per phase
- prefer renaming or extending an existing agent before introducing a new one
- each new agent must explain why an existing agent is insufficient
- every new agent should map to a repeated real workflow inside CrawlerNest
