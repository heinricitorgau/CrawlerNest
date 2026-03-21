# CrawlerNest

**CrawlerNest** is a research‑driven platform for building infrastructure around **web crawling**, **data intelligence**, and **knowledge systems**.

The project focuses on transforming large amounts of scattered web information into **structured, queryable knowledge** that can support analytics platforms and intelligent applications.

Currently, CrawlerNest focuses on **global education data**, including university rankings, admission requirements, and related academic information.

---

## Vision

Build a **global education data intelligence platform** capable of collecting, structuring, and analyzing university information worldwide.

CrawlerNest aims to provide the technical foundation for:

- education analytics
- university comparison tools
- admission intelligence
- future AI‑driven recommendation systems

---

## Current System Status (Reality Layer)

CrawlerNest is currently transitioning from a crawler tool into a structured data platform (V1 → V1.5).

### Current (V1.5): What is working now

- ✅ QS ranking crawler (stable)
- ✅ Asynchronous crawling pipeline (AsyncIO-based)
- ✅ SQLite-based knowledge base (original warehouse baseline)
- ✅ PostgreSQL schema initialization baseline (validated)
- ✅ Extraction and parsing modules for rankings and admission data
- ✅ Python data ingestion pipeline (crawler → DB)
- ✅ Minimal end-to-end runner (`crawlernest/run_pipeline.py`: crawl → normalize → store → query)
- ✅ C normalization engine (prototype for high-performance parsing)
- ✅ Modular architecture (crawler / extractor / db_writer separation)
- ✅ Initial Java Spring Boot service integration (validated startup against PostgreSQL baseline)
- ✅ Read-only internal API endpoints: `/universities`, `/rankings`, `/admissions`

### Next (V2): In progress

- Entity resolution (university aliases / fuzzy matching)
- Data consistency and normalization refinement
- Ranking aggregation logic
- Knowledge base expansion (programs, degrees, metadata)
- PostgreSQL-backed service and analytics expansion

### Future (V3): Planned (not yet implemented)

- AI-driven recommendation system
- Public API platform
- Web-based analytics interface

This section reflects the **actual engineering maturity** of the system and distinguishes it from long-term architectural goals.

---

## Minimal End-to-End Usage (Current)

The commands below describe the current, testable path for QS data.

### 1) Run crawler → extract → normalize → store (SQLite)

From repository root:

```bash
python3 crawlernest/run_pipeline.py run --limit 30
```

Expected console shape:

```text
[1/4] Crawling QS data...
[2/4] Normalizing fields (Python baseline)...
[3/4] Writing 30 rows to sqlite...
[4/4] Done.
Inserted rows: 30
```

### 2) Query stored rankings (SQLite query mode)

```bash
python3 crawlernest/run_pipeline.py query MIT --limit 20
```

Expected output shape:

```text
rank | university | country | score | ranking_type
1 | Massachusetts Institute of Technology (MIT) | United States | 100.0 | world
```

### 3) Read-only API paths (Spring Boot service)

Once `servise_for_java` is running:

- `GET /universities`
- `GET /rankings`
- `GET /admissions`

Example requests:

```bash
curl http://localhost:8080/universities
curl http://localhost:8080/rankings
curl http://localhost:8080/admissions
```

Note: public/external API hardening is still part of future roadmap work.

---

## What This Repository Contains

This repository hosts the **core CrawlerNest platform codebase**, organized as a modular data‑platform architecture.


Major components include:

- **crawlernest-core** – shared utilities and core platform logic
- **crawlernest-extractors** – data extraction and parsing modules
- **crawlernest-jobs** – crawler pipelines and data ingestion workflows
- **crawlernest-db-writer** – database writing and persistence layer
- **crawlernest-kb** – university knowledge base structures
- **crawlernest-analytics** – analytical modules built on collected data
- **crawlernest-cli** – command‑line interface for exploring the platform
- **crawlernest-schema** – database schema definitions
- **crawlernest-tests** – automated tests
- **servise_for_java** – Java Spring Boot backend providing REST APIs and recommendation logic

---
## Platform Architecture

The high‑level architecture of CrawlerNest follows a layered data‑platform pipeline:

```
                ┌──────────────────┐
                │   Web Sources    │
                │ Rankings / Sites │
                └─────────┬────────┘
                          │
                          ▼
               ┌─────────────────────┐
               │  Crawler Pipelines  │
               │  Async Fetch Jobs   │
               └─────────┬───────────┘
                         │
                         ▼
             ┌─────────────────────────┐
             │ Extraction & Parsers    │
             │ HTML / JSON processing  │
             └─────────┬───────────────┘
                       │
                       ▼
       ┌──────────────────────────────────┐
       │ C Normalization Engine           │
       │ (Name / Country / Score parsing) │
       └─────────┬────────────────────────┘
                 │
                 ▼
        ┌──────────────────────────────┐
        │ University Knowledge Base    │
        │ SQLite / PostgreSQL Warehouse│
        └─────────┬────────────────────┘
                  │
                  ▼
           ┌──────────────────────┐
           │ Analytics Layer      │
           │ Ranking / Insights   │
           └─────────┬────────────┘
                     │
                     ▼
           ┌──────────────────────┐
           │ API & Platform Layer │
           │ Spring Boot Services │
           └──────────────────────┘
```

## Future Platform Architecture

CrawlerNest is evolving beyond a crawler into a full **education data infrastructure and decision-support platform**.

```
Crawler → Knowledge Base → Analytics → AI → Product
```

### What This Means

In the future, the system will include:

- **Global University Knowledge Base**
  - Rankings (QS / THE / ARWU)
  - Admission requirements
  - Programs / degrees
  - Tuition and future outcome signals

- **Analytics Layer (Next)**
  - Cross-ranking aggregation
  - Admission probability estimation
  - ROI / trend analysis

- **Recommendation Engine (Future)**
  - Rule-based filtering (constraints)
  - Weighted scoring (explainable)
  - ML-based refinement (long-term)

- **API Platform (Future)**
  - Public/externalized API hardening and product-facing contracts
  - `/recommendations`

- **End-user Products (Future)**
  - AI university selection assistant
  - School comparison tools
  - Education data explorer

### Positioning

CrawlerNest is not just a crawler.

It is being designed as a **data infrastructure layer for global education intelligence**, with a long-term goal of becoming an **AI-powered decision support system**.

---

## Roadmap Visualization

CrawlerNest development is organized into clearly defined stages to distinguish **current capabilities** from **near-term engineering goals** and **long-term vision**.

```
V1.5 (Current) → V2 (Next) → V3+ (Future)
```

### V1.5 — Data Platform Foundation (Current)
- Stable QS ranking crawler
- Async crawling pipeline (AsyncIO)
- SQLite knowledge base (baseline)
- PostgreSQL schema initialized (validated)
- Python ingestion pipeline (crawler → DB)
- Minimal end-to-end flow via `crawlernest/run_pipeline.py`
- C normalization engine (prototype)
- Modular architecture (crawler / extractor / db_writer)
- Java service layer (boot-tested with PostgreSQL)
- Read-only internal API endpoints (`/universities`, `/rankings`, `/admissions`)

### V2 — Data Intelligence Layer (Next)
- Entity resolution (alias / fuzzy matching)
- Data consistency & normalization improvements
- Multi-source ranking integration (QS / THE / ARWU)
- Ranking aggregation logic
- Expanded knowledge base (programs / degrees / metadata)
- PostgreSQL-backed analytics expansion

### V3+ — Intelligence & Product Layer (Future)
- AI-driven recommendation engine
- Public API platform
- Web-based analytics interface
- University/program recommendation system
- B2C (student tools) + B2B (data/API services)

### Key Principle

CrawlerNest is built with a staged evolution model:

- **Current = implemented and testable**
- **Next = actively being engineered**
- **Future = clearly defined but not yet built**

This ensures clarity, credibility, and a realistic development trajectory.
---

## Repository Structure Map

The CrawlerNest codebase is organized as a layered data‑platform architecture.  
Below is a simplified map of the current repository structure.

```
crawlernest/
│
├── crawlernest-core/
│   Shared utilities, configuration, and core platform logic
│
├── crawlernest-extractors/
│   Data extraction modules
│   HTML parsers, ranking parsers, and admission requirement extractors
│
├── crawlernest-jobs/
│   Crawling pipelines and scheduled ingestion workflows
│   Ranking crawlers, admission crawlers, and ingestion orchestration
│
├── crawlernest-db-writer/
│   Persistence layer
│   Handles validated records and writes them into the knowledge base
│
├── crawlernest-kb/
│   Knowledge base layer
│   Database models and domain objects such as:
│   universities, rankings, admission requirements, programs, degrees
│
├── crawlernest-schema/
│   SQL schema definitions
│   Data warehouse structure and relational schema
│
├── crawlernest-analytics/
│   Analytical modules
│   Ranking aggregation, statistics, and future recommendation features
│
├── crawlernest-cli/
│   Command‑line interface
│   Tools for exploring and querying the knowledge base
│
├── crawlernest-tests/
│   Automated tests using PyTest
│   Ensures reliability of crawlers, extractors, and database logic
│
├── crawlernest_c_data_normalization_engine/
│   High‑performance data normalization engine written in C (prototype)
│   Responsible for tasks such as:
│   • university name normalization
│   • country standardization
│   • ranking score parsing
│   • admission requirement parsing
│
├── servise_for_java/
│   Java Spring Boot backend
│   Provides REST APIs and future recommendation system services
│
└── docs /
    Project documentation, architecture descriptions, and design notes
```

This layered structure separates **data acquisition**, **data processing**, **knowledge storage**, and **analytics**, allowing the platform to evolve from a crawler system into a full **education data intelligence platform**.

---

---

## Technology

CrawlerNest uses a lightweight and portable stack designed for research and data engineering:

- **Python** – crawler pipelines and data processing
- **SQLite** – original local analytical knowledge base baseline
- **PostgreSQL** – validated next-stage operational database baseline
- **C** – high‑performance normalization engine (prototype)
- **Java / Spring Boot** – backend API services and recommendation engine
- **AsyncIO** – asynchronous crawling
- **PyTest** – automated testing

---

## Platform Concept

```
Web Crawling → Data Ingestion → Normalization → Knowledge Base → Analytics → AI Systems
```

---

## Project Status

Active development (V1.5 – Data Platform Transition Stage).

CrawlerNest is currently evolving from a crawler-centric system into a modular data platform with a validated PostgreSQL migration baseline and:

- a structured data ingestion pipeline
- a minimal runnable flow (`crawlernest/run_pipeline.py`) for QS crawl/store/query
- a normalization engine (C-based prototype)
- a knowledge base (SQLite warehouse baseline + PostgreSQL initialization baseline)
- an emerging service layer (Java backend with read-only endpoints for universities/rankings/admissions)

The project is in a **platform-building phase**, focusing on stability, data quality, and architectural scalability.

---

## Access

CrawlerNest repositories are currently **private** and maintained under the CrawlerNest organization.

---

## License

This project is protected by a custom proprietary license.
See the [LICENSE](./LICENSE) file for full terms and restrictions.
