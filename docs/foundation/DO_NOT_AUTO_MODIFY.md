# Do Not Auto Modify

## Purpose

This document defines which parts of CrawlerNest must not be autonomously
modified by agents, patch loops, or self-rewrite systems.

The goal is simple:

- protect core system integrity
- preserve explainability
- keep rollback manageable

Agents may analyze these areas.
Agents may suggest changes to these areas.
Agents must not autonomously rewrite these areas.

## Hard-Protected Areas

The following are hard-protected by policy and process.

### 1. Core Routing and Execution Boundaries

Do not auto-modify:

- `agent/service/agent_service.py`
- `agent/orchestration/*`
- core routing logic between `WebAgentEngine` and `DevAgentEngine`

Reason:

- these files define system execution boundaries
- accidental drift here can break the entire agent topology

### 2. Memory Selection Core

Do not auto-modify:

- short-term memory selection policy
- relevance scoring core
- ambiguity heuristics
- memory safety boundaries between short-term and long-term memory

Examples:

- `memory_policy.py`
- any module that decides memory eligibility or selection weights

Reason:

- memory drift is hard to observe and easy to misdiagnose
- silent regression here contaminates all downstream behavior

### 3. Evaluator Core

Do not auto-modify:

- autonomous evaluator logic
- evaluation score interpretation
- regression comparison core

Examples:

- `agent/autonomous/evaluator.py`
- core eval comparison logic used by AutoEval

Reason:

- if the judge changes itself, the system loses trustworthiness

### 4. Canonical Schema and Resolution Rules

Do not auto-modify:

- canonical schema definitions
- canonical identifier semantics
- entity resolution rules that affect admission/ranking alignment

Reason:

- these rules define warehouse truth
- mistakes here corrupt downstream joins and recommendation quality

### 5. Production Crawl Policy

Do not auto-modify:

- crawl allowlist / denylist
- rate limit policy
- retry strategy for production-scale crawling
- source access rules

Reason:

- these have external operational consequences

## Review-Gated Areas

The following areas may receive agent-generated patch suggestions,
but only under human review and evaluation gates:

- extractor candidate patch
- parser robustness patch
- formatter improvement
- low-risk UI copy or mapping fixes
- SQL explanation / query diagnostics
- documentation and reporting

These are allowed only when:

- the patch is sandboxed
- validation passes
- rollback remains simple

## Allowed Autonomous Suggestion Scope

The current acceptable scope for autonomous proposal is:

- function-level local changes
- local module improvements
- extractor / parser / formatter modules

The current unacceptable scope is:

- schema migrations
- canonical identity semantics
- routing topology
- memory policy internals
- evaluator authority
- production crawler governance

## Safety Rules

1. No agent may directly overwrite protected files.
2. Any change affecting canonical truth requires explicit human review.
3. Any change affecting scoring or evaluation authority requires explicit human review.
4. Any change affecting production crawl policy requires explicit human review.
5. Preview or experimental success does not grant permission to modify protected modules.

## Operational Rule

If there is any ambiguity about whether a file belongs to a protected area:

- treat it as protected
- require human review
- do not auto-apply changes

## Relationship to Roadmap

This document is intentionally conservative.

CrawlerNest is still in a stage where:

- admission crawling must stabilize
- normalization and canonical mapping must mature
- formal warehouse semantics must remain trustworthy

Until those layers are stable, agent autonomy must remain bounded and review-gated.

