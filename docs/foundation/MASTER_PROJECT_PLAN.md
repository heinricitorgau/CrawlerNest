# CrawlerNest Master Project Plan

## Executive Summary
CrawlerNest is an end-to-end university data infrastructure and web platform. It transforms fragmented global education data into structured knowledge, powering a deterministic decision engine for students and advisors.

Our core evolution path:
**Data Acquisition → Data Platform → Analytical Capability → AI Recommendation → Productization**

---

## 1. Current System Status

### 1.1 Module Completion Map (As of March 2026)

| Module | Description | Status | Completion |
| :--- | :--- | :---: | :---: |
| End-to-End Pipeline | `run_pipeline.py` (crawl → normalize → store → query) | Operational | ~90% |
| Continuous Crawler | Infinite loop, graceful shutdown, resilient fetching | Operational | 100% |
| Crawler / Network | Async requests, endpoint detection, conservative throttling | Operational | ~85% |
| Extraction Layer | Admission requirements, deadlines, scoring rules | Operational | ~80% |
| Python Normalization | Country standardization, safe value conversion | Operational | ~75% |
| C Normalization Engine | High-performance parsing for names/rankings | In Dev | ~25% |
| Identity Resolution | Alias mapping, fuzzy matching baseline | Operational | ~40% |
| Storage / Warehouse | PostgreSQL schema, DB writer, Spring Data JPA | Operational | ~95% |
| API Layer | Spring Boot endpoints (`/universities`, `/recommendations`, etc.) | Operational | ~92% |
| Website MVP | Next.js frontend, University Detail, Recommendation UI | Operational | ~88% |
| Quality & Validation | Transaction safety, JUnit, AutoEval baseline | Operational | ~90% |
| Low-Spec Runtime | `lobster-01` optimized workspace and scripts | Completed | 100% |

---

## 2. Platform Architecture & Strategy

### 2.1 Five-Layer Architecture
CrawlerNest is built on a decoupled 5-layer system to ensure scalability:
1.  **Data Layer (Acquisition):** Async crawlers for rankings and admission requirements.
2.  **Canonical Layer (Processing):** Field cleaning, normalization, and Identity Resolution.
3.  **Aggregation Layer (Storage):** PostgreSQL single source of truth for all structured data.
4.  **Decision Layer (Analytics):** Ranking aggregation and the Explainable Decision Engine (Reach/Target/Safety).
5.  **API & Product Layer:** Spring Boot APIs serving the Next.js Consumer Website.

### 2.2 Core Engineering Concepts
- **Continuous Resilience:** The engine runs in an infinite loop with `KeyboardInterrupt` handling to prevent data loss.
- **Explainable Recommendation (v3):** Uses a hybrid deterministic scoring model with calibrated categories.
- **Entity Resolution:** Maps multiple data sources (QS, THE, future ARWU) to a single `canonical_university` entity.
- **Production-Safe Pipeline:** Conservative throttling (`request_delay ≈ 30s`) and automatic 403 degradation.

---

## 3. Product Roadmap

### Milestone 1: Foundation & Infrastructure (Completed)
- Async pipeline development and PostgreSQL migration.
- Implementation of the `lobster-01` production-safe runtime.
- Establishment of the `Data-first` design principle.

### Milestone 2: Intelligence & Decision Support (Current)
- Refinement of the Recommendation Engine (v3) and explainable comparisons.
- Launch of the Website MVP (Rankings Browser, University Details) with live polling.
- Implementation of Continuous Crawler Resilience and Expanded Regional Coverage (v1.0).
- Implementation of AutoEval for automated data quality assurance.

### Milestone 3: Platform Expansion (Next 6-18 Months)
- Integration of THE and ARWU data sources.
- Deepening of Program-level and Degree-level analytics.
- Enhanced Identity Resolution using fuzzy matching and embeddings.

### Milestone 4: Commercialization & AI (Future)
- LLM-assisted admission requirement verification.
- Public API platform launch.
- Full-scale AI-driven education consulting insights.

---

## 4. Maintenance & Operations
- **Node Management:** Using `systemd` timers for background jobs.
- **Resilience:** Automatic checkpoint/resume and incremental journal writing.
- **Regional Data:** Ensuring global coverage through manual geographic mapping backfills.
