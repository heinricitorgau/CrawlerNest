# CrawlerNest Automation System

This document defines the automation layer for `crawlernest-agents`.

The goal is to integrate AI-assisted workflows into real engineering operations
without introducing unnecessary complexity.

---

## 🎯 Goals

Automation should:

- Reduce obvious mistakes
- Standardize repetitive checks
- Provide structured debugging entry points
- Keep the human engineer in control

---

## 🚫 Non-Goals

This system is NOT:

- Fully autonomous development
- Silent code modification
- Multi-agent orchestration without explicit intent
- A replacement for engineering judgment

---

## 🧠 Design Philosophy

- Minimal > complex
- Deterministic > magical
- Explicit triggers > hidden behavior
- Assistive > autonomous

---

## ⚙️ Automation Components

### 1. Pre-Commit Gate

**Trigger:** `git commit`

**Script:**  
`scripts/git-hooks/pre-commit`

**Responsibilities:**

- Run agent lint (`lint-agents.sh`)
- Validate shell scripts (`bash -n`)
- Ensure required documentation exists
- Detect agent file modifications
- Warn about documentation drift

**Purpose:**
Prevent broken or inconsistent state from entering the repository.

---

### 2. Test Failure Debug Helper

**Trigger:** manual test run

**Script:**
```bash
./scripts/run-tests-with-debug.sh
```

**Behavior:**

- Runs test suite
- Captures failure logs
- Generates structured debug prompt

**Output:**

```text
tmp/latest-debug-prompt.md
```

**Agent Used:**
- `crawlernest-debug-reliability-engineer`

**Purpose:**
Convert raw test failures into actionable debugging context.

---

### 3. Pipeline Log Analyzer

**Trigger:** manual invocation

**Script:**
```bash
./scripts/analyze-pipeline-log.sh <log_file>
```

**Behavior:**

- Reads pipeline logs
- Generates structured analysis prompt

**Output:**

```text
tmp/pipeline-analysis-prompt.md
```

**Agents Used:**
- `crawlernest-debug-reliability-engineer`
- `crawlernest-data-pipeline-engineer`

**Purpose:**
Turn pipeline execution logs into structured analysis tasks.

---

### 4. Documentation Drift Check

**Trigger:** pre-commit

**Script:**
`scripts/check-doc-drift.sh`

**Behavior:**

- Detects code/system changes
- Detects documentation changes
- Warns if they are out of sync

**Purpose:**
Prevent divergence between implementation and documentation.

---

## Operational Heuristics Injection

Automation-generated prompts automatically include:

- `docs/OPERATIONAL_HEURISTICS.md`

This ensures debug and pipeline analysis follow the same decision rules.

The heuristics do not make decisions automatically.
They only guide the generated prompt.

---

## Memory Injection

Automation-generated prompts include:

- `docs/OPERATIONAL_HEURISTICS.md`
- `memory/known-issues.md`
- `memory/pipeline-pitfalls.md`
- `memory/extractor-edge-cases.md`
- `memory/db-decisions.md`

Memory is truncated to avoid prompt overflow.

Memory is used to guide reasoning, not to override log evidence.

---

## 📁 Directory Structure

```text
scripts/
├── git-hooks/
│   └── pre-commit
├── install-hooks.sh
├── lint-agents.sh
├── check-doc-drift.sh
├── run-tests-with-debug.sh
├── generate-debug-prompt.py
├── analyze-pipeline-log.sh
└── generate-pipeline-analysis.py
```

---

## 🚀 Setup

Install git hooks:

```bash
./scripts/install-hooks.sh
```

---

## 🧪 Typical Workflow

### Commit Flow

```bash
git add .
git commit -m "update agent prompts"
```

Triggers:
- agent lint
- shell validation
- doc drift check

---

### Test + Debug Flow

```bash
./scripts/run-tests-with-debug.sh
```

If tests fail:
- debug prompt generated
- pass to debug agent

---

### Pipeline Analysis Flow

```bash
./scripts/analyze-pipeline-log.sh tmp/pipeline.log
```

---

## 🔄 Escalation Logic

When something fails:

1. Generate structured context (automation)
2. Use correct agent:
   - Debug → root cause
   - Data Pipeline → design fix
3. Re-run system
4. Review before commit

---

## 🧠 Human-in-the-Loop Principle

Automation never:

- Commits code
- Fixes bugs automatically
- Modifies system state silently

Automation always:

- Surfaces information
- Structures problems
- Assists decision-making

---

## 📌 Summary

This automation system transforms:

- raw logs → structured prompts
- failures → reproducible debugging tasks
- commits → controlled checkpoints

It is intentionally simple and focused.

It exists to support a single engineer building a complex system — not to simulate a team.
