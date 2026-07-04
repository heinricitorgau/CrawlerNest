# CrawlerNest Agent Selection Guide

This document defines how to choose the correct agent for a task.

The goal is:
- Avoid random agent usage
- Avoid overlapping responsibilities
- Ensure consistent workflow

---

## 🧠 Core Principle

Each agent has a **non-overlapping responsibility**.

If two agents can do the same task → you're using the system wrong.

---

## 🚀 Standard Development Flow

### 1. Understanding code
👉 Use: `crawlernest-repo-onboarding`

When:
- You don't understand a module
- You need architecture overview
- You want to trace data flow

---

### 2. Designing or modifying system flow
👉 Use: `crawlernest-workflow-architect`

When:
- Adding new feature
- Changing pipeline structure
- Defining module responsibilities

---

### 3. Implementing or improving pipeline logic
👉 Use: `crawlernest-data-pipeline-engineer`

When:
- Working on crawler / extractor / db_writer
- Handling retries / fallback
- Fixing pipeline reliability

---

### 4. Database-related work
👉 Use: `crawlernest-postgres-optimizer`

When:
- Writing queries
- Changing schema
- Debugging performance
- Handling large data

---

### 5. Debugging issues
👉 Use: `crawlernest-debug-reliability-engineer`

When:
- Something fails
- Output is wrong
- Tests fail
- Logs unclear

---

### 6. Reviewing code (MANDATORY before important commits)
👉 Use: `crawlernest-code-reviewer`

When:
- Before merging
- Before major changes
- When unsure about correctness

---

### 7. Writing documentation
👉 Use: `crawlernest-technical-writer`

When:
- Updating README
- Writing whitepaper
- Explaining system

---

## 🔄 Escalation Rules

If stuck:

1. ❌ Don't retry blindly
2. ✅ Switch agent

Example:

- Pipeline fails → Debug Engineer
- Still unclear → Repo Onboarding
- Root cause found → Data Pipeline Engineer

---

## ⚠️ Anti-Patterns

### ❌ Using Code Reviewer to design systems
→ Wrong agent

### ❌ Using Data Engineer to debug logs
→ Wrong agent

### ❌ Using Technical Writer to invent features
→ Forbidden

---

## 🧱 Agent Boundaries (Strict)

| Agent | Does | Does NOT |
|------|------|---------|
| Onboarding | Explain system | Modify design |
| Workflow Architect | Define structure | Write full code |
| Data Pipeline Engineer | Pipeline logic | DB tuning |
| Postgres Optimizer | DB logic | Pipeline flow |
| Debug Engineer | Find root cause | Redesign system |
| Code Reviewer | Find issues | Implement features |
| Technical Writer | Documentation | Change system behavior |

---

## 🧭 Golden Rule

If you are unsure which agent to use:

👉 Start with `crawlernest-repo-onboarding`

---

## 🧠 Philosophy

This is not a multi-agent simulation.

This is a **tooling system to support a single engineer (you)**.

- Agents assist
- You decide
- System stays simple