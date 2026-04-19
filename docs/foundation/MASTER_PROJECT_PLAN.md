# CrawlerNest Master Project Plan

## Executive Summary
CrawlerNest is an end-to-end university data infrastructure and web platform. It transforms fragmented global education data into structured knowledge, powering a deterministic decision engine for students and advisors.

Our core evolution path:
**Data Acquisition → Data Platform → Analytical Capability → AI Recommendation → Productization**

Execution note:

- `docs/architecture/SYSTEM_ENGINE_ARCHITECTURE.md`
  canonical system / engine architecture, combining current executable architecture with the longer-term target

This project plan should be read with the execution architecture as the current mainline and the vision architecture as the target horizon.

---

## 1. Current System Status

### 1.1 Module Completion Map (As of March 2026)

| Module | Description | Status | Completion |
| :--- | :--- | :---: | :---: |
| End-to-End Pipeline | `run_pipeline.py` (crawl → normalize → write → warehouse → query) | Operational | ~90% |
| Continuous Crawler | Infinite loop, graceful shutdown, resilient fetching | Operational | 100% |
| Crawler / Network | Async requests, endpoint detection, conservative throttling | Operational | ~85% |
| Extraction Layer | Admission requirements, deadlines, scoring rules | Operational | ~80% |
| Python Normalization | Country standardization, safe value conversion | Operational | ~75% |
| C Normalization Engine | High-performance parsing for names/rankings | In Progress | ~65% |
| Identity Resolution | Deterministic exact match, alias seeding, unresolved reporting, refresh loop | Operational | ~65% |
| Ranking Production Workflow | Raw → normalized → staging → validate → ingest → warehouse preview → landing | Operational | ~80% |
| Multi-Universe Aggregation | Global / region / subject scoped aggregation truth | Controlled Expansion | ~95% |
| THE Integration | Times Higher Education crawler + full entity ingestion | Operational | 100% |
| Storage / Warehouse | PostgreSQL schema, DB writer, Spring Data JPA, ingest traceability | Operational | ~95% |
| API Layer | Spring Boot endpoints (`/universities`, `/recommendations`, `/rankings`) | Operational | ~92% |
| Website MVP | Next.js frontend, University Detail, Recommendation UI, live freshness refresh | Operational | ~92% |
| Quality & Validation | Transaction safety, JUnit, AutoEval baseline | Operational | ~90% |
| Recommendation Engine | Basic / rule-based / optional recommendation path | Limited | ~70% |
| Agent Runtime | `crawlernest/agent/`, mini-agent, AutoEval-assisted loop | Development Support Only | ~70% |
| Low-Spec Runtime | `lobster-01` optimized workspace and scripts | Completed | 100% |

---

## 2. Platform Architecture & Strategy

### 2.1 Current Execution Architecture
CrawlerNest is currently best understood as a controlled 3-zone system:
1.  **Active Data Pipeline:** crawl, extract, normalize, write, warehouse, API, web.
2.  **Controlled Expansion:** limited admission enrichment and basic rule-based recommendation.
3.  **Development Support:** agent, mini-agent, and AutoEval systems outside the production data path.

The broader layered architecture still matters as a long-term design target, but it should not be mistaken for the current executable mainline.

### 2.2 Core Engineering Concepts
- **Continuous Resilience:** The engine runs in an infinite loop with `KeyboardInterrupt` handling to prevent data loss.
- **Explainable Recommendation (limited):** Keep recommendation basic, rule-based, and optional until upstream data and admission completeness are more stable.
- **Entity Resolution:** Maps multiple data sources (QS, THE, future ARWU) to a single `canonical_university` entity.
- **Controlled Ranking Production Path:** Ranking records now move through raw, normalized, staging, validation, warehouse preview, warehouse landing, and deterministic resolution before any stronger downstream truth coupling.
- **Production-Safe Pipeline:** Conservative throttling (`request_delay ≈ 30s`) and automatic 403 degradation.
- **Visibility Recovery Path:** If crawled universities are stuck in `warehouse.universities`, `seed-canonical` and `backfill-ranking-records` now provide an explicit recovery path into visible aggregated truth.
- **Frontend Freshness:** The website reads through a same-origin proxy with `no-store`, periodic polling, and focus/visibility refresh so DB-side updates surface quickly in the UI.
- **Agent Boundary:** Agent systems assist development and experimentation, but are intentionally outside the production data path.

---

## 3. Product Roadmap

### Milestone 1: Foundation & Infrastructure (Completed)
- Async pipeline development and PostgreSQL migration.
- Implementation of the `lobster-01` production-safe runtime.
- Establishment of the `Data-first` design principle.

### Milestone 2: Controlled Productization (Current)
- Stabilize the active data pipeline and warehouse-backed product path.
- Keep recommendation explainable, limited, and operationally optional.
- Launch of the Website MVP (Rankings Browser, University Details) with live polling.
- Implementation of Continuous Crawler Resilience and Expanded Regional Coverage (v1.0).
- Implementation of AutoEval for evaluation support without production ownership.
- Keep multi-universe aggregation available as a broader expansion path rather than the minimum execution core.
- Canonical recovery + ranking-record backfill expanded visible global aggregated rows from `221` to `1323`.
- THE crawler and full integration (2,191 universities, 100% match rate after seed-canonical-from-missing).
- `seed-canonical-from-missing` command: THE-only universities now visible in API and frontend.
- Ranking-specific deterministic resolution workflow, unresolved reporting, alias seeding, and refresh loop now support incremental manual curation.
- `production_safe.sh` 5-step automation (QS global → deferred enrichment → THE → QS regions).
- About page and premium NavBar with dark mode toggle.
- Aggregated visible rows expanded to 2,736 (QS + THE dual source).

### Milestone 3: Platform Expansion (Next 6-18 Months)
- Integration of ARWU and additional data sources (THE already complete).
- Deepening of Program-level and Degree-level analytics.
- Expanded identity resolution through broader alias coverage and batch curation workflows.

### Milestone 4: Commercialization & AI (Future)
- LLM-assisted admission requirement verification.
- Public API platform launch.
- Full-scale AI-driven education consulting insights.
- Production-grade agent capabilities only after data correctness and product stability remain strong.

---

## 4. Maintenance & Operations
- **Node Management:** Using `systemd` timers for background jobs.
- **Resilience:** Automatic checkpoint/resume and incremental journal writing.
- **Regional Data:** Ensuring global coverage through manual geographic mapping backfills.
- **Visibility Repair:** When crawler data exists but API-visible rows remain too low, run `seed-canonical` followed by `backfill-ranking-records`.
