# CrawlerNest Master Technical Architecture Whitepaper

CrawlerNest is a scalable, traceable, analytical, and productized **University Data Infrastructure + Web Platform**.

Its core evolution path is:
**Data Acquisition → Data Platform → Analytics → Decision Engine → Web Product**

---

## 1. Document Positioning

This whitepaper serves to:
*   Act as the primary reference for mid-to-long-term technical architecture and product decisions.
*   Unify the design language across the Data, Canonical, Aggregation, Decision, and API layers.
*   Articulate the product vision, current system status, and historical milestones.

For operational testing, validation queries, and regression checks, see the [Engineering Validation & Maintenance Guide](TESTING_GUIDE.md).

---

## 2. Product Vision

We are building a holistic ecosystem where **data, decision logic, and UX** converge. By combining robust **data infrastructure** with an explainable **decision engine** (calculating reach/target/safety probabilities) and an intuitive **UX**, we guide users through complex educational choices.

### Product Positioning
*   **Against static ranking publishers (e.g., QS, THE, ARWU):** We offer aggregated rankings across multiple sources combined with personalized, profile-based recommendations.
*   **Against traditional human agencies:** We provide transparent, algorithmically deterministic, and explainable recommendations, eliminating black-box bias.

---

## 3. The 5-Layer System Architecture

The system is strictly decoupled into five functional layers:

### Layer 1: Data Layer (Acquisition)
*   **Scope:** Crawlers, Fetchers, Source Adapters.
*   **Details:** Acquires global rankings, admission requirements, and tuition data. Operates asynchronously, respecting compliance and pacing rules (e.g., handling HTTP 403 blocks with deferred retry queues).

### Layer 2: Canonical Layer (Processing & Resolution)
*   **Scope:** Extraction, Normalization, Entity Resolution.
*   **Details:** Transforms unstructured data into typed entities. Maps raw source names to a **canonical university** identity via alias and fuzzy matching.

### Layer 3: Aggregation Layer (Storage)
*   **Scope:** PostgreSQL Data Warehouse (`warehouse` and `analytics` schemas).
*   **Details:** The single, unified source of truth. Stores raw records for traceability, normalized entities, aggregated rankings, and logging via batch insertions.

### Layer 4: Decision Layer (Analytics & Recommendation)
*   **Scope:** Recommendation Engine, Comparison Logic, Confidence Model.
*   **Details:** Powers the explainable recommendation system. Applies rule-based filtering, weighted hybrid scoring (v3), and deterministic policies to categorize universities into **Reach**, **Target**, and **Safety** groups.

### Layer 5: API Layer (Product)
*   **Scope:** Java Spring Boot APIs, Consumer Web Product.
*   **Details:** Exposes the Decision Layer to end-users via a strictly typed JSON envelope contract, translating engineering depth into a fluid interactive web experience.

---

## 4. Key Engineering Concepts

### Entity Resolution & The Multi-Source Future
CrawlerNest handles data from disparate publishers (QS, THE, ARWU) by resolving them into a single `canonical_university`. Overlapping ranks are not overwritten but retained as distinct `ranking_record` rows tied to the canonical entity.

### Ranking Aggregation
Data from multiple sources is mathematically combined into an `aggregated_rank`. The composite score reflects a unified representation of global standing, gracefully handling partial missing data.

### Recommendation Decision System (v3) & Confidence Model
Our latest recommender strictly categorizes schools into Reach, Target, and Safety groups using a multi-factor hybrid scoring algorithm. It features a Confidence Model that dynamically adjusts baseline predictions based on the underlying data quality (e.g., downgrading confidence if a university lacks explicit admission requirements for the targeted program).

### Lobster-01 Infrastructure Node
CrawlerNest utilizes a dedicated low-spec control node (Lobster-01) for rigorous, long-duration background pipeline jobs.
*   **Role:** Runs the production-safe pipeline via systemd timers, leveraging batch DB writes and incremental checkpoints for high resilience on constrained hardware.

---

## 5. Development History & Milestones

| Phase | Milestone | Description |
| :--- | :--- | :--- |
| **Foundation** | **Crawler Development** | Initial asynchronous pipeline, parse parallelism, compliance-safe pacing. |
| **Data Platform** | **Entity Resolution** | Python baseline and C-prototype normalization; mapping scattered views to canonical entities. |
| **Data Platform** | **PostgreSQL Switch** | Transitioned from legacy SQLite to a robust PostgreSQL warehouse as the absolute source of truth. |
| **Aggregation Layer** | **Multi-Source Aggregated Rankings** | Introduced canonical-university aggregation outputs, deterministic `aggregated_rank`, and explainable composite score views for downstream products. |
| **Infrastructure** | **Production-Safe Flow** | Established the Lobster-01 node deployment strategy for WAF/403 block circumvention. |
| **Decision Engine** | **Recommendation Engine v3**| Progressed from CLI rule-based matching to calibrated hybrid deterministic scoring with preference weights. |
| **Web Product** | **API Services** | Standardized Java backend supplying frontend-ready UI contracts with success envelopes. |
| **Web Product** | **Website MVP** | Delivered the official Next.js frontend with a rankings homepage, university detail pages, and a recommendation workflow connected to the backend API. |
| **Web Product** | **Rankings Browser Upgrade** | Expanded the homepage from a static rankings preview into a browsable rankings product with pagination, filtering, and stable same-origin API proxying. |
| **Web Product** | **Decision-Support UX Layer** | Added quick insight labels, recommendation buckets, source-trust cues, and decision-oriented navigation so the product supports browsing and shortlist evaluation rather than passive viewing. |

---

> [!IMPORTANT]
> This document governs the architectural direction of CrawlerNest. Any major changes to the data model, web product interface, or recommendation systems must align with the 5-layer model defined herein.
