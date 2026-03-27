# CrawlerNest: University Data Infrastructure + Web Platform

**CrawlerNest** has evolved from an infrastructure-focused data pipeline into a comprehensive **University Data Infrastructure and Web Platform**. It bridges the gap between raw, scattered global education data and actionable, consumer-facing insights.

## What is this system?
CrawlerNest is an end-to-end data platform that transforms fragmented web data (university rankings, admission requirements, tuition) into structured knowledge. It powers a deterministic decision engine that algorithmically guides students, replacing black-box manual consulting with transparent, data-driven "reach/target/safety" recommendations.

## Why it exists
While APIs and CLIs validate the data, students and advisors need a visual, comparative interface to make life-altering decisions. Raw data is overwhelming; by layering a deterministic decision engine and a clean UX over our data infrastructure, we provide clarity instead of just volume.

## Current Capabilities
*   **Data Pipeline:** Asynchronous, compliance-aware crawlers fetching global rankings (1500+ universities scaled).
*   **Decision Engine:** An explainable recommendation engine providing deterministic groupings (reach/target/safety).
*   **API Platform:** Repaired Java Spring Boot APIs (API v1) serving normalized analytical data with support for scoped/regional filtering.
*   **Database Reliability:** Robust PostgreSQL transaction handling with automatic rollbacks on batch failures.

## High-Level Architecture
CrawlerNest is built on a strict, decoupled 5-layer architecture:
1.  **Data Layer:** Web crawlers fetching from global sources.
2.  **Canonical (Processing) Layer:** Entity resolution and normalization.
3.  **Aggregation (Storage) Layer:** PostgreSQL data warehouse.
4.  **Decision Layer:** Recommendation engine and comparison logic.
5.  **API (Product) Layer:** Java Spring Boot APIs and the Consumer Website.

For a deep dive into the engineering principles, see the [Whitepaper](docs/foundation/Whitepaper.md).
For engineering operations, API invariants, and testing logic, see the [Engineering Validation & Maintenance Guide](docs/foundation/TESTING_GUIDE.md).
For the current repository map and working paths, see [Repository Structure](docs/REPO_STRUCTURE.md).

## Current System Status
This reflects our actual engineering maturity:
*   ✅ **production-safe pipeline:** DONE (scaled to 1500+ universities)
*   ✅ **PostgreSQL integration:** DONE (transaction-safe with rollback)
*   ✅ **recommendation engine (v3 decision system):** DONE
*   ✅ **API v1 readiness:** DONE (repaired & pagination-aligned)
*   ✅ **node deployment (Lobster-01):** DONE (dedicated `lobster-01/` runtime)
*   🟡 **multi-source (QS only currently):** PARTIAL
*   🔄 **website layer:** IN PROGRESS

## Milestones & Development History
CrawlerNest's engineering depth is built on a history of rigorous milestones:

### Completed (Foundation & Infrastructure)
*   **Crawler Development:** Asynchronous pipeline, local parse parallelism, compliance-safe request pacing.
*   **Normalization:** Python baseline and C-prototype for high-performance string parsing.
*   **PostgreSQL Switch:** Transitioned to a robust PostgreSQL warehouse (the sole datastore).
*   **Production-Safe Pipeline:** Established Lobster-01 (node-ready deployment) with systemd scheduling, avoiding 403 blocks with decoupled cooldowns.
*   **Recommendation Engine:** Evolved from rule-based filters (v1) to grouped categories (v2), up to calibrated hybrid deterministic scoring (v3).

### In Progress (Platform Expansion)
*   Web product user interface development.
*   Deepening the canonical university entity resolution.

### Future
*   Public API platform commercialization.
*   AI-driven insights overlaying the deterministic engine.

## Repository Map

The repo currently has two layers:

- outer workspace: docs, deployment assets, editor config, top-level project material
- inner platform workspace: [`crawlernest/`](crawlernest) containing the runnable pipeline, backend, schema, and frontend

Most day-to-day engineering work happens in:

- [`crawlernest/run_pipeline.py`](crawlernest/run_pipeline.py)
- [`crawlernest/crawlernest-core/`](crawlernest/crawlernest-core)
- [`crawlernest/crawlernest-schema/`](crawlernest/crawlernest-schema)
- [`crawlernest/servise_for_java/`](crawlernest/servise_for_java)
- [`crawlernest/crawlernest-web/`](crawlernest/crawlernest-web)
