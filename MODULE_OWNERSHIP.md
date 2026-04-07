# MODULE_OWNERSHIP

## Purpose

This document defines ownership boundaries for the CrawlerNest engineering system.

Its goals are:

- keep cross-layer responsibilities explicit
- prevent architectural drift as the codebase grows
- reduce accidental coupling between data, API, and product layers
- give human developers and AI agents a shared operating model

This document is normative. When it conflicts with convenience, the document wins.

---

## System Layers

CrawlerNest is organized as a layered system:

1. Data Production Layer
2. Canonical Layer
3. Aggregation Layer
4. Decision Layer
5. Product Layer

The layers are implemented across multiple runtimes, but ownership is defined by responsibility, not language.

---

## Ownership Principles

### Single Responsibility by Layer

Each module must have a primary responsibility.

- Crawlers produce raw data.
- Canonical logic resolves identity and normalization truth.
- Aggregation logic produces ranking truth.
- Decision logic computes recommendation, trust, and comparison outputs.
- API and frontend serve already-produced data.

No module may silently absorb responsibilities from another layer.

### Single Source of Truth

For every important domain concern, one module owns authoritative truth.

- Raw crawl payload structure: Data Production Layer
- Canonical university identity: Canonical Layer
- Ranking truth and aggregated results: Aggregation Layer
- Recommendation policy and trust scoring formulas: Decision Layer
- Public response contract: API layer
- UI state and presentation: Frontend

If the same rule exists in two places, one of them is technical debt unless explicitly documented as a read-only mirror.

### Read Down, Write Through the Owner

Lower layers may be read by upper layers.

Upper layers must not write around an owning layer’s rules.

Examples:

- Frontend may read API responses, but must not recreate aggregation rules.
- API may read aggregated rankings, but must not crawl source websites.
- Pipeline may write canonical seeds only through canonical workflows, not by bypassing identity rules in ad hoc SQL.

---

## Module Ownership

### 1. Crawler / Pipeline

Primary code area:

- `crawlernest/run_pipeline.py`
- `crawlernest/pipeline/**`
- crawler, fetcher, extractor, job modules

Responsibilities:

- source crawling and ingestion orchestration
- checkpointing, resume, repair, and safe re-run behavior
- raw-to-structured extraction
- controlled writes into the warehouse through pipeline-owned write paths
- job execution for QS, THE, ARWU, and future sources

Can change:

- crawl scheduling and retry policies
- snapshot/checkpoint behavior
- source-specific extraction logic
- ingestion batching and job orchestration
- pipeline logging and progress reporting

Must not touch:

- frontend UI behavior
- public API response design
- recommendation policy semantics
- direct redefinition of canonical identity rules owned by the canonical layer
- ad hoc database mutations outside pipeline-owned ingest/write flows

Depends on:

- normalization helpers
- canonical resolution services
- PostgreSQL warehouse schemas

Single source of truth owned here:

- crawl execution state
- source payload handling
- pipeline recovery behavior

---

### 2. Normalization

Primary code area:

- Python normalization helpers
- C normalization engine
- normalization utilities used by ingestion/canonical flows

Responsibilities:

- text cleanup
- safe rank/score/country normalization
- alias cleanup before canonical matching
- high-performance normalization primitives

Can change:

- parsing and normalization rules
- canonical cleanup mappings
- performance optimizations in C or Python

Must not touch:

- recommendation scoring
- API presentation copy
- frontend display formatting
- ranking aggregation formulas

Depends on:

- source data contracts from the pipeline
- canonical rules when normalization feeds entity resolution

Single source of truth owned here:

- normalization rules for raw values before canonical resolution

Important note:

- if the frontend needs normalized labels, it should consume backend-provided canonical metadata rather than maintain an independent normalization rule set

---

### 3. Canonical Layer

Primary code area:

- entity resolution
- alias mapping
- canonical seed/backfill paths
- country alias / institution identity logic

Responsibilities:

- canonical university identity
- alias management
- linking source-specific institutions to canonical entities
- country and institution variant reconciliation

Can change:

- alias tables and resolution heuristics
- canonical seeding flows
- confidence thresholds and deterministic matching rules

Must not touch:

- UI state
- API-only filtering behavior that does not belong to identity resolution
- recommendation grouping policy
- crawl scheduling

Depends on:

- normalized source data
- warehouse canonical tables

Single source of truth owned here:

- `canonical_university`
- alias mapping rules
- source-to-canonical linking

Critical rule:

- canonical identity must never be reimplemented independently in the frontend

---

### 4. Aggregation / Database Layer

Primary code area:

- PostgreSQL warehouse schemas
- analytics views
- ranking aggregation refresh paths
- aggregation repositories

Responsibilities:

- ranking truth storage
- materialized or computed aggregated ranking outputs
- persistent source evidence
- scope/universe-aware ranking storage
- country and metadata joins used by read queries

Can change:

- schema evolution through controlled migration
- aggregation queries and view refresh logic
- indexes, storage structure, and warehouse optimization

Must not touch:

- crawling logic
- frontend filtering logic
- API presentation formatting
- recommendation UX semantics

Depends on:

- canonical identity tables
- source ranking records

Single source of truth owned here:

- warehouse truth
- aggregated ranking records
- persisted source evidence fields

Critical rule:

- API code must not invent ranking truth outside the warehouse

---

### 5. API Layer

Primary code area:

- Spring Boot controllers, services, repositories

Responsibilities:

- public read contracts
- request validation
- read-time filtering
- assembling frontend-consumable payloads from warehouse truth
- exposing decision-layer outputs

Can change:

- endpoint structure
- DTOs and read contracts
- request validation
- mapping logic from warehouse rows to API payloads

Must not touch:

- source crawling
- heavy batch processing
- pipeline scheduling
- ownership of canonical identity or aggregation truth

Depends on:

- warehouse
- canonical layer outputs
- decision-layer services

Single source of truth owned here:

- public response contract
- API-level validation behavior

Critical rule:

- the API is a read-serving layer, not a crawler, not a pipeline runner, and not a data correction tool

---

### 6. Frontend

Primary code area:

- Next.js app
- React hooks
- UI components

Responsibilities:

- query-state and URL-state management
- presentation of rankings, evidence, trust, compare, and recommendation output
- user interactions
- empty/loading/error state handling

Can change:

- page structure
- component composition
- local interaction patterns
- client-side display logic

Must not touch:

- database access
- aggregation formulas
- canonical identity resolution
- recommendation core logic
- crawler or pipeline execution

Depends on:

- API contracts only

Single source of truth owned here:

- client-side UI state
- rendering logic

Critical rule:

- the frontend may cache and derive display state, but it must not become a second business logic engine

---

### 7. Recommendation Engine

Primary code area:

- recommendation services
- comparison logic
- trust scoring
- fit and risk-profile logic

Responsibilities:

- deterministic recommendation policy
- reach/target/safety grouping
- trust scoring and explainability
- comparison summaries

Can change:

- score formulas
- recommendation grouping rules
- explanation notes
- trust heuristics

Must not touch:

- crawl orchestration
- canonical linking rules
- UI display-only formatting
- warehouse schema without aggregation/data review

Depends on:

- canonical identity
- aggregated ranking truth
- admissions or structured metadata from the warehouse

Single source of truth owned here:

- recommendation semantics
- trust score semantics
- comparison decision logic

---

## Single Source of Truth Rules

### Rule 1. Canonical Country Logic

Canonical country normalization must be owned by the backend/canonical side.

- frontend may display normalized labels
- frontend must not become the authoritative owner of country alias rules

### Rule 2. Ranking Truth

Aggregated rank, scope rank, evidence availability, and source count must come from the warehouse/read layer.

- frontend must not recompute ranking truth from raw source fragments

### Rule 3. Trust and Evidence

Trust score and explainability semantics belong to the decision/API side.

- frontend may render badges and explanatory copy
- frontend must not create alternate trust formulas

### Rule 4. Public Contract

Only the API defines the public contract consumed by the frontend.

- frontend must not reach around the API to infer hidden data model details

---

## Forbidden Cross-Layer Access

The following are forbidden unless a documented exception is approved.

### Frontend Forbidden Actions

- direct database access
- reimplementing canonical matching
- reimplementing ranking aggregation
- hardcoding data-layer correction rules

### API Forbidden Actions

- crawling websites
- doing long-running heavy batch computation in request handlers
- mutating warehouse truth outside explicit service-owned write paths

### Pipeline Forbidden Actions

- introducing frontend-only response formatting
- embedding UI assumptions in data models
- bypassing canonical ownership with ad hoc identity writes

### Recommendation Layer Forbidden Actions

- editing canonical tables directly
- inventing missing evidence
- silently correcting inconsistent warehouse truth inside recommendation code

### Database / Aggregation Forbidden Actions

- embedding product copy
- embedding UI-specific filtering semantics
- allowing application code to bypass aggregation ownership with uncontrolled manual writes

---

## AI Agent Participation Rules

AI agents are allowed contributors, but they do not own architecture by default.

### Approved Roles for AI Agents

- extract/refactor code inside an owned module
- implement scoped features against a defined contract
- add tests, guards, logging, and documentation
- help generate migration-safe patches

### AI Agents Must Not Do Without Explicit Approval

- rewrite ownership boundaries
- change public API contracts across modules
- introduce a second source of truth
- alter schema or aggregation semantics casually
- move business logic across layers because it “feels cleaner”

### Required AI Working Pattern

- inspect the live path first
- identify the owning layer
- modify the owner, not a downstream symptom
- preserve contract compatibility when possible
- document assumptions and validation steps

### Human Review Requirement

Any AI-authored change that affects one of the following requires human review before merge:

- schema or migration logic
- canonical matching rules
- aggregation formulas
- trust/recommendation formulas
- API contract changes
- cross-layer refactors

---

## Change Approval Matrix

### Safe to Change Within Module Ownership

- logging
- defensive guards
- internal refactors
- tests
- isolated parser/mapper/component extraction

### Requires Cross-Module Review

- public API contract changes
- warehouse schema changes
- canonical alias logic changes
- aggregation logic changes
- trust/recommendation semantics changes

---

## Enforcement Rule

When a change request touches multiple layers, the team must first answer:

1. Which layer owns the truth?
2. Which layer is only presenting the truth?
3. Which layer is allowed to validate but not redefine?

If those three answers are unclear, implementation must pause until ownership is clarified.
