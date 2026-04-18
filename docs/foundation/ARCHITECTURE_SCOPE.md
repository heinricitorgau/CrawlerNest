# CrawlerNest Architecture Scope

## Purpose

This document defines the current mainline development scope for CrawlerNest.
It exists to prevent layer mixing, premature automation, and roadmap drift.

Core rule:

- Stabilize the data pipeline first.
- Productize the warehouse second.
- Build recommendation on top of trusted data.
- Let agents assist only after the upstream system is stable.

## Mainline System

CrawlerNest mainline architecture is the following data path:

1. `crawl`
2. `extract`
3. `normalize`
4. `canonicalize`
5. `write`
6. `query`

This path is the primary delivery path for:

- admission data
- ranking data
- university detail data
- downstream recommendation inputs

Everything else is a support layer, not the mainline.

## Current Mainline Priorities

The current development priority order is:

1. Admission crawl engine can reliably capture a small controlled school set.
2. Admission normalization and canonical mapping are stable.
3. Admission and ranking warehouse tables are formalized.
4. Formal APIs are warehouse-backed and contract-stable.
5. Admission-aware recommendation becomes explainable and usable.
6. Crawl scale-up happens only after metrics and failure taxonomy exist.
7. AutoEval operates as judge-only infrastructure.
8. Dev Agent can assist in low-risk, review-gated areas.
9. Closed-loop agent improvement only starts after the data/product path is stable.

## Scope Boundaries

### In Scope Now

- controlled admission crawling
- extractor robustness for admission pages
- normalization rules
- canonical university resolution
- warehouse schema stabilization
- formal API semantics
- explainable recommendation based on ranking + admission fit

### Advanced Layers, Not Current Mainline

The following layers may exist in the repository and may continue to be maintained,
but they are not allowed to displace the mainline priorities above:

- Web Agent conversational generation
- Dev Agent autonomous refinement
- orchestration between Web and Dev agents
- self-improvement and meta-strategy systems
- self-rewrite / patch sandbox systems

These are considered advanced support layers.
They must not dictate the order of core data-platform work.

## Phase Order

### Phase 0: Freeze Scope and Boundaries

Deliver:

- architecture boundary documents
- data contracts
- do-not-auto-modify guardrails

Rules:

- no major new platform modules
- no agent-led structural rewrites

### Phase 1: Admission Crawl Engine Stability

Deliver:

- controlled crawl for 5 to 10 schools
- raw HTML, raw text, extracted JSON retained for each crawl
- stable reruns on core admission pages

Rules:

- no recommendation integration yet
- no automatic extractor rewriting

### Phase 2: Normalization and Canonical Layer

Deliver:

- admission normalization rules
- canonical university mapping
- country / region / source normalization
- explicit distinction between raw, normalized, and canonical records

Rules:

- do not scale crawl volume before canonical resolution is healthy

### Phase 3: Formal Warehouse and API

Deliver:

- formal warehouse tables for admission and ranking
- stable API contracts for rankings, admissions, and university detail
- formal query semantics for pagination, metadata, and filtering

Rules:

- preview data must not back product pages

### Phase 4: Admission-Aware Recommendation

Deliver:

- explainable rule-based recommendation
- ranking + admission fit + completeness + source coverage factors

Rules:

- transparent scoring only
- no opaque ML ranking as the first implementation

### Phase 5: Crawl Scale-Up

Deliver:

- queueing, retry, rate limiting
- crawl metrics
- extraction failure taxonomy

Rules:

- no scale-up without visibility into failure and fill-rate metrics

### Phase 6: AutoEval as Judge

Deliver:

- extractor eval datasets
- admission eval datasets
- regression comparison reports

Rules:

- evaluator only
- no automatic overwrite of production path

### Phase 7: Dev Agent Partial Takeover

Deliver:

- review-gated patch proposals
- low-risk engineering assistance

Rules:

- agent is a co-developer, not the owner of the core system

### Phase 8: Agent Improvement Closed Loop

Deliver:

- sandbox candidate evaluation
- rollback
- allowlist / denylist
- audit trail

Rules:

- only after pipeline, warehouse, and recommendation are stable

## No-Skip Rules

1. Before the admission crawler is stable, agent closed-loop improvement must not become the mainline.
2. Before normalization and canonical resolution are stable, large-scale crawl expansion must not proceed.
3. Before the formal warehouse is stable, product frontend pages must not depend on preview data.
4. Before recommendation is admission-aware, the system must not claim complete admission assessment.
5. Before AutoEval is mature, agents may propose changes but must not directly own the main branch path.

## Decision Rule

When roadmap tradeoffs appear, the tie-breaker is:

- prefer data integrity over automation
- prefer explainability over complexity
- prefer review-gated change over autonomous change
- prefer warehouse truth over preview convenience

