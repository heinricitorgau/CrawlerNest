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

---

# High-Level Architecture

```
External Data Sources
        │
        │ HTTP requests
        ▼
Crawler Layer
(crawlernest-jobs)
        │
        ▼
Fetcher / Extractor
(crawlernest-extractors)
        │
        ▼
Normalization Engine
(crawlernest-normalization)
(crawlernest-normalization-py)
        │
        ▼
Database Writer
(crawlernest-db-writer)
        │
        ▼
SQLite Knowledge Base
(crawlernest.db)
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
crawlernest-jobs
```

Responsibilities:

- orchestrate crawling workflows
- control crawling scope and pagination
- schedule ranking collection jobs
- coordinate data collection tasks

Example crawling targets:

- QS World University Rankings
- QS Subject Rankings
- Regional University Rankings
- Sustainability Rankings

Primary entry point:

```
run_crawler()
```

---

## 2. Fetcher and Extractor Layer

Repository:

```
crawlernest-extractors
```

Responsibilities:

- send HTTP requests
- retrieve HTML pages
- parse website content
- extract structured information

Typical extracted fields include:

- university names
- ranking positions
- program information
- admission requirements

Technologies used:

- requests
- BeautifulSoup
- lxml

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

- persist normalized data
- insert ranking records
- maintain crawl metadata
- manage crawl sessions

Important tables include:

- universities
- rankings
- admission_requirements
- crawl_runs

Database engine:

```
SQLite
```

Primary database file:

```
crawlernest.db
```

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
7 SQLite knowledge base
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