# CrawlerNest System Architecture

## Overview

CrawlerNest is a modular **education data intelligence platform** designed to collect, normalize, store, and analyze global university information.

The platform converts scattered web data into **structured knowledge** that can power analytics, decision systems, and future AI-driven recommendation services.

Primary data domains include:

- university rankings
- admission requirements
- academic programs
- geographic and institutional metadata

CrawlerNest is organized as a **data pipeline architecture**, where each subsystem transforms raw web data into progressively more structured and useful information.

The ranking pipeline now has an explicit safe-production path before any final read-model integration:

```text
crawl -> raw -> normalized -> staging -> validate -> ingest -> warehouse preview -> warehouse landing -> resolve -> report -> seed -> refresh
```

This path exists to keep ranking ingestion, warehouse landing, and entity resolution observable and rerunnable before data is promoted into broader product truth.

---

# High-Level Architecture

```
External Data Sources
        │
        │ HTTP requests
        ▼
Shared Crawler Core
(crawlernest-crawler-core)
        │
        ▼
Ranking Crawler Engine / Admission Crawler Engine
(crawlernest-ranking-crawler / crawlernest-admission-crawler)
        │
        ▼
Fetcher / Extractor Reuse
(crawlernest-extractors)
        │
        ▼
Pipeline / Jobs Orchestration
(run_pipeline.py / crawlernest-jobs)
        │
        ▼
Normalization Engine
(crawlernest-normalization)
(crawlernest-normalization-py)
        │
        ▼
Validation / Controlled Ingest / Warehouse Landing
(pipeline + staging/warehouse writers)
        │
        ▼
PostgreSQL Warehouse / Knowledge Artifacts
(PostgreSQL / crawlernest-kb)
        │
        ▼
Analytics Layer
(crawlernest-analytics)
        │
        ▼
Interfaces
├ CLI Platform (crawlernest-cli)
├ API Services (crawlernest-api)
└ Web UI (crawlernest-web)
```

---

# Core Architecture Layers

## 1. Data Acquisition (Crawler Layer)

Repository:

```
crawlernest-crawler-core
crawlernest-ranking-crawler
crawlernest-admission-crawler
crawlernest-jobs
```

Responsibilities:

- shared crawler runtime primitives such as HTTP, retry, rate limiting, logging, and snapshot hooks
- ranking-specific crawling for QS / THE / ARWU and ranking universes
- admission-specific crawling for university websites and semi-structured requirements
- orchestration of crawl scope, pagination, resume, and batch execution from pipeline entrypoints
- safe handoff from crawler output into downstream normalization and staging boundaries

Example crawling targets:

- QS World University Rankings
- QS Subject Rankings
- Regional University Rankings
- Sustainability Rankings
- University admissions and language-requirement pages

Primary entry point:

```
run_pipeline.py
```

---

## 2. Fetcher and Extractor Layer

Repository:

```
crawlernest-extractors
```

Responsibilities:

- provide reusable fetch / parse helpers for crawler engines
- retrieve HTML or structured payloads
- parse source content into candidate structured fields
- support engine-specific extraction without owning job orchestration or transport runtime

Typical extracted fields include:

- university names
- ranking positions
- program information
- admission requirements

Important design rule:

- `crawlernest-crawler-core` owns transport concerns
- ranking and admission engines own business-specific crawling behavior
- `crawlernest-extractors` remains a helper layer rather than the top-level crawler runtime

---

## 3. Data Normalization Layer

Repositories:

```
crawlernest-normalization
crawlernest-normalization-py
```

Responsibilities:

Convert raw scraped data into **standardized structured formats**.

Examples of normalization tasks:

- GPA scale normalization
- IELTS score parsing
- GRE / GMAT extraction
- country and region standardization

CrawlerNest supports two normalization implementations:

- Python-based normalization pipeline
- High-performance **C normalization engine**

This hybrid approach provides both flexibility and performance.

---

## 4. Database Writing Layer

Repository:

```
crawlernest-db-writer
```

Responsibilities:

- persist validated data into controlled staging and warehouse-oriented targets
- keep ingest and write targets isolated from final production read models
- maintain crawl metadata
- manage rerunnable persistence boundaries

Important tables include:

- staging and warehouse landing tables
- universities
- rankings
- admission_requirements
- crawl_runs

Database engine:

```
PostgreSQL
```

For the ranking path, persistence is intentionally split:

- staging persistence for validated normalized rows
- warehouse landing persistence for warehouse-ready rows
- deterministic entity-resolution updates after warehouse landing

This avoids coupling crawler output directly to final product-serving tables.

---

## 5. Knowledge Base Layer

Repository:

```
crawlernest-schema
```

Defines the canonical **database schema** used across the platform.

Important files:

- schema.sql
- schema_min.sql

The schema models relationships between:

- universities
- rankings
- programs
- admission metrics

This forms the **University Knowledge Base**.

For ranking-specific production flow, warehouse-oriented landing rows and canonical resolution metadata now act as a controlled intermediate contract before downstream aggregation and recommendation layers.

---

## 6. Analytics Layer

Repository:

```
crawlernest-analytics
```

Responsibilities:

- ranking comparison analysis
- admission metric statistics
- cross-region comparisons
- aggregated data queries

Planned future features:

- ranking trend analysis
- historical ranking movement
- admission difficulty modeling

---

## 7. Interface Layer

The platform exposes multiple user interfaces.

### CLI Platform

Repository:

```
crawlernest-cli
```

Features:

- interactive ranking explorer
- country and region filters
- sorting by admission metrics
- local data exploration

Example command:

```
python run_platform.py
```

---

### API Services

Repository:

```
crawlernest-api
```

Planned capabilities:

- REST API for ranking queries
- university search endpoints
- admission requirement APIs

Example endpoints:

```
/api/universities
/api/rankings
/api/admissions
```

---

### Web Interface

Repository:

```
crawlernest-web
```

Future capabilities:

- interactive ranking visualization
- university search interface
- admission dashboards

---

# Data Flow Example

Example pipeline for **QS World University Rankings**:

```
1 crawlernest-jobs
        ↓
2 fetch ranking pages
        ↓
3 crawlernest-extractors
        ↓
4 extract university data
        ↓
5 normalization engine
        ↓
6 crawlernest-db-writer
        ↓
7 PostgreSQL warehouse / knowledge artifacts
        ↓
8 CLI / analytics queries
```

---

# Testing Infrastructure

Repository:

```
crawlernest-tests
```

Testing framework:

```
pytest
```

Current tests cover:

- database operations
- extractor logic
- crawler utilities
- ranking parsing

---

# System Design Principles

CrawlerNest follows several engineering principles.

### Modular Architecture

Each subsystem exists in a dedicated repository to allow independent development and scaling.

### Pipeline-Based Processing

Data flows through clearly defined transformation stages.

### Separation of Concerns

Different responsibilities are isolated into dedicated modules:

- crawling
- parsing
- normalization
- storage
- analytics

### Local-First Deployment

SQLite and lightweight dependencies allow the platform to run locally for research and experimentation.

### Research-Oriented Platform

CrawlerNest is designed both as:

- a practical data platform
- a research environment for education intelligence.

---

# Future Architecture Roadmap

Planned expansion areas include:

## Knowledge Graph

Construct a graph linking:

- universities
- rankings
- programs
- admission requirements

## Recommendation Engine

Provide personalized university suggestions based on:

- GPA
- IELTS
- GRE / GMAT
- geographic preferences

## Distributed Crawling

Introduce parallel crawling infrastructure for large-scale data ingestion.

## Data Intelligence Platform

Long-term platform direction:

```
Crawler → Knowledge Base → Analytics → AI Recommendation
```

---

# Project Vision

CrawlerNest aims to evolve into a **global education data intelligence platform** that enables students, researchers, and institutions to explore structured knowledge about universities worldwide.
