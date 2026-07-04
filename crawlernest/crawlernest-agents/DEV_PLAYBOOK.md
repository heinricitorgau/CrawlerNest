# CrawlerNest Dev Playbook

This is the standard workflow for developing CrawlerNest using the agent system.

---

## Core Rule

Do not jump into coding immediately.

Always:

Understand -> Design -> Implement -> Review -> Validate -> Document

---

## Standard Flow

### Step 1 - Understand

Use: [`crawlernest-repo-onboarding`](agents/crawlernest-repo-onboarding.md)

Prompt:

```text
Analyze this module and explain data flow, key components, and risk areas.
```

### Step 2 - Design

Use: [`crawlernest-workflow-architect`](agents/crawlernest-workflow-architect.md)

Prompt:

```text
Design how this feature integrates into the existing pipeline. Define module boundaries and data flow.
```

### Step 3 - Implement

Use: no agent by default, or [`crawlernest-data-pipeline-engineer`](agents/crawlernest-data-pipeline-engineer.md) when pipeline logic changes are central.

### Step 4 - Review

Use: [`crawlernest-code-reviewer`](agents/crawlernest-code-reviewer.md)

Prompt:

```text
Review this code. Find bugs, edge cases, and risks.
```

This step is mandatory before important commits.

### Step 5 - Debug

Use: [`crawlernest-debug-reliability-engineer`](agents/crawlernest-debug-reliability-engineer.md)

Prompt:

```text
Analyze this failure. Reproduce, identify root cause, and suggest fix.
```

Use this only when needed.

### Step 6 - DB Optimization

Use: [`crawlernest-postgres-optimizer`](agents/crawlernest-postgres-optimizer.md)

Use this when schema, query behavior, indexing, or scale is part of the task.

### Step 7 - Documentation

Use: [`crawlernest-technical-writer`](agents/crawlernest-technical-writer.md)

Use this after behavior is stable enough to document accurately.

---

## Incident Flow

When things break:

1. [`crawlernest-debug-reliability-engineer`](agents/crawlernest-debug-reliability-engineer.md) -> find root cause
2. [`crawlernest-repo-onboarding`](agents/crawlernest-repo-onboarding.md) -> understand system context
3. [`crawlernest-data-pipeline-engineer`](agents/crawlernest-data-pipeline-engineer.md) -> fix design or logic
4. [`crawlernest-code-reviewer`](agents/crawlernest-code-reviewer.md) -> verify the fix

---

## Anti-Patterns

- skipping review
- designing while coding
- guessing bugs
- writing docs before the system is stable

---

## Philosophy

This system is:

- minimal
- deterministic
- engineer-controlled

Not:

- autonomous
- over-engineered
- multi-agent chaos
