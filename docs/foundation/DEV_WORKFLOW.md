# DEV_WORKFLOW

## Purpose

This document defines the expected engineering workflow for CrawlerNest feature delivery.

The project must scale across:

- data engineering
- backend/API engineering
- frontend/product engineering
- AI-assisted implementation

This document is intentionally strict. It exists to prevent accidental coupling, unstable releases, and architecture drift.

---

## Core Delivery Flow

Every non-trivial feature should follow this sequence:

1. Spec
2. API Contract
3. Mock
4. Implementation
5. Integration
6. Validation
7. Release

Do not start from UI code or database code without knowing where the feature belongs in this sequence.

---

## 1. Spec

### Required Before Implementation

Every feature must define:

- user-facing goal
- owner layer
- required data inputs
- expected outputs
- failure and empty-state behavior
- non-goals

### Spec Questions

Before work begins, answer these:

- Is this a data production feature, read feature, or product feature?
- Which layer owns the truth?
- Does this require new persistent data?
- Does this change public API semantics?
- Does this depend on canonical identity or aggregation truth?

If the spec cannot answer these, the task is not ready.

---

## 2. API Contract

The API contract must be defined before frontend implementation depends on live backend behavior.

### Required Contract Elements

- endpoint
- request params
- response shape
- success semantics
- empty-result semantics
- error semantics

### Rules

- frontend may build against a contract, not against guessed backend behavior
- backend must not ship undocumented response fields as if they were stable
- if a field is experimental, mark it explicitly

### Contract Change Rule

Any contract change must state:

- backward compatibility impact
- frontend impact
- migration path

---

## 3. Mock

Frontend and product work must not block on backend completion when the contract is already defined.

### Mock Usage Rules

- use contract-shaped mock payloads
- place mock data behind an explicit mock boundary
- keep mock logic temporary and removable
- do not let mocks become a hidden second backend

### Good Uses of Mock Data

- page layout
- loading states
- empty states
- filter interactions
- compare/recommendation interaction scaffolding

### Bad Uses of Mock Data

- inventing canonical identity behavior
- inventing aggregation outputs
- inventing trust semantics that backend does not define

---

## 4. Implementation

Implementation begins only after spec and contract are stable enough to code against.

### Expected Order

#### Data-layer feature

1. source ingestion change
2. normalization/canonical update
3. warehouse persistence
4. validation query
5. API mapping
6. frontend wiring

#### Read/API feature

1. warehouse/read-path design
2. API DTO/contract
3. integration query
4. frontend consumption

#### Frontend-only feature

1. route/component design
2. mock state
3. API wiring
4. empty/error/loading states

---

## 5. Integration

Integration is the point where independent module work is joined.

### Required Integration Checks

- request params flow correctly from frontend to API
- API validation does not reject valid inputs
- warehouse/read queries return expected rows
- empty state is not confused with error state
- backend truth is rendered correctly in the UI

### Integration Rule

Never treat “UI changed” as proof that the feature works.

Integration is only complete when:

- the input reaches the owning layer
- the owning layer changes the output
- the rendered result matches the updated truth

---

## Parallel Team Workflow

### Frontend Team

Can work in parallel when:

- the contract is defined
- mock payloads are available

Frontend should focus on:

- page structure
- state handling
- user interaction
- empty/error/loading behavior

### Backend/API Team

Can work in parallel when:

- required warehouse inputs are known
- DTO contract is defined

Backend should focus on:

- validation
- read path
- mapping
- deterministic response behavior

### Data Team

Owns:

- source ingestion
- canonical truth
- aggregation truth
- reproducibility and pipeline correctness

Data work should not be blocked by frontend layout concerns.

---

## Database Change Workflow

Database-related logic is high risk and must be changed conservatively.

### Required Steps

1. define the truth owner
2. inspect current schema and live read/write path
3. design migration or query change
4. validate against real data
5. update dependent repositories/services
6. run focused regression checks

### Rules

- no ad hoc manual schema edits without documented intent
- no silent warehouse truth changes
- no frontend assumptions about schema internals
- no API workaround that hides broken warehouse truth

### Safe DB Change Pattern

- add field or query capability
- wire repository
- wire service
- wire controller
- wire frontend only after API response is stable

---

## Testing Strategy

Testing is layered. Do not rely on one test type to prove system correctness.

### Unit Tests

Use for:

- parsers
- mappers
- normalization helpers
- trust/recommendation formulas
- small UI utilities/hooks

### Integration Tests

Use for:

- controller/service/repository flow
- API contract behavior
- filter propagation
- aggregation read-path correctness

### Pipeline Validation

Use for:

- crawl output sanity
- canonical linking
- aggregation refresh correctness
- backfill/recovery flows

### UI Validation

Use for:

- loading state
- empty state
- error state
- filter state in URL
- compare/recommendation interaction

### Minimum Rule

Every feature should have at least one test or validation artifact at the owning layer.

---

## Debugging Flow

When something is broken, debug from the owning layer outward.

### General Order

1. verify the input
2. identify the owner of the truth
3. inspect the live path
4. verify the output at the owner
5. only then inspect downstream rendering

### If the UI looks wrong

Check in this order:

1. URL state
2. API request
3. API response
4. frontend mapping
5. component rendering

### If API output looks wrong

Check in this order:

1. controller params
2. service logic
3. repository/query
4. warehouse truth

### If data is wrong in the warehouse

Check in this order:

1. ingestion payload
2. normalization
3. canonical linking
4. aggregation refresh
5. downstream consumers

---

## Release Checklist

Before release, confirm:

- spec is still accurate
- API contract is documented
- no mock path is leaking into production
- empty state and error state are distinct
- logs are useful but not noisy
- feature flags or compatibility paths are understood
- database or aggregation changes were validated on real data
- frontend/backend remain contract-aligned
- README/docs updates are included when the behavior changed materially

---

## DO

- define the owner before coding
- implement against a contract
- use mock data only as a temporary development boundary
- keep heavy computation out of request paths
- keep frontend focused on state and presentation
- add focused tests where the logic lives
- validate with real API and real database paths before calling a feature complete
- refactor by extraction, not by uncontrolled rewrite

---

## DON'T

- do not let frontend touch the database
- do not let API handlers crawl websites
- do not hide broken warehouse truth behind frontend hacks
- do not mix canonical identity rules into UI code
- do not compute ranking truth in the frontend
- do not change schema casually to solve a presentation problem
- do not start implementation from whichever layer is easiest to edit
- do not treat empty results as errors unless the contract says they are errors
- do not leave parallel legacy and new paths without marking the live one clearly

---

## AI-Assisted Development Rules

AI tools may accelerate implementation, but they must operate inside the same workflow.

### Allowed AI Usage

- generate boilerplate under a defined contract
- extract helpers/modules without semantic change
- add tests and defensive guards
- trace live code paths
- draft migration-safe refactors

### Disallowed AI Usage Without Explicit Human Approval

- schema redesign
- ownership changes across layers
- public contract redesign
- recommendation/trust formula changes
- canonical rule changes

### Review Rule

Any AI-generated patch that touches:

- warehouse truth
- canonical logic
- aggregation logic
- public API contracts
- release behavior

must be reviewed by a human owner before merge.

---

## Enforcement Rule

If a task skips:

- spec
- contract
- ownership identification

then the task is not ready for implementation, regardless of urgency.
