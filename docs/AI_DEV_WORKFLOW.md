# CrawlerNest AI Development Workflow

This document explains how the `crawlernest-agents` system is used with the main CrawlerNest repository.

This is an integration layer, not a copy of the full agent repo.

---

## Purpose

The goal is to support daily engineering work with a small, structured AI-assisted workflow.

This system is used for:

- codebase understanding
- workflow design
- code review
- debugging
- pipeline analysis
- documentation updates

This system is not used for:

- fully autonomous coding
- silent modifications
- replacing engineering judgment

---

## External Dependency

The full agent definitions live in a separate repository:

- `crawlernest-agents`

This repository only contains the minimal integration layer required for daily use.

---

## Core Agents

Use these agents from `crawlernest-agents`:

- `crawlernest-repo-onboarding`
- `crawlernest-workflow-architect`
- `crawlernest-data-pipeline-engineer`
- `crawlernest-postgres-optimizer`
- `crawlernest-debug-reliability-engineer`
- `crawlernest-code-reviewer`
- `crawlernest-technical-writer`

---

## Recommended Development Flow

### 1. Understand

Use `crawlernest-repo-onboarding`.

When:

- entering an unfamiliar module
- tracing data flow
- locating entry points

### 2. Design

Use `crawlernest-workflow-architect`.

When:

- adding a new feature
- changing module boundaries
- changing pipeline flow

### 3. Implement

Write code normally.

Use `crawlernest-data-pipeline-engineer` if the change affects:

- crawler
- extractor
- normalization
- db_writer
- analytics
- recommendation flow

If the change targets `crawlernest/crawlernest-crawler-core/`, first verify that the work is truly shared runtime logic rather than ranking-specific or admission-specific behavior. Treat `crawlernest-crawler-core/` as a thin shared subproject boundary, not a mixed business-logic zone.

### 4. Review

Use `crawlernest-code-reviewer`.

Mandatory before:

- important commits
- merging
- major refactors

### 5. Debug

Use `crawlernest-debug-reliability-engineer`.

When:

- tests fail
- logs are unclear
- output is wrong
- pipeline behavior degrades unexpectedly

### 6. Database

Use `crawlernest-postgres-optimizer`.

When:

- changing schema
- writing queries
- debugging performance
- reviewing data consistency risks

### 7. Documentation

Use `crawlernest-technical-writer`.

When:

- updating README
- updating whitepaper
- writing usage guides
- explaining current system state

---

## Automation Entry Points

The following helper scripts are available in this repo:

- `scripts/ai-dev/run-tests-with-debug.sh`
- `scripts/ai-dev/analyze-pipeline-log.sh`

These scripts do not fix issues automatically.

They generate structured prompts and analysis input for the correct agent workflow.

---

## Configuration

Local integration defaults live in `.ai-dev.config`.

Use this file to set:

- the external `crawlernest-agents` repo path
- the local temp output directory
- the default test command

The scripts are designed to work even if the external repo is absent, but the prompts they generate assume the `crawlernest-agents` roles are available in your normal tooling.

---

## Human-in-the-Loop Rule

AI assists.

The engineer decides.

This integration layer is intentionally conservative.
