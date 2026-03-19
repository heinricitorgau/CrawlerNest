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
- ✅ SQLite-based knowledge base (data warehouse baseline)
- ✅ Extraction and parsing modules for rankings and admission data
- ✅ Python data ingestion pipeline (crawler → DB)
- ✅ C normalization engine (prototype for high-performance parsing)
- ✅ Modular architecture (crawler / extractor / db_writer separation)
- ✅ Initial Java Spring Boot service integration (basic data connection)

### Next (V2): In progress

- Entity resolution (university aliases / fuzzy matching)
- Data consistency and normalization refinement
- Ranking aggregation logic
- Knowledge base expansion (programs, degrees, metadata)

### Future (V3): Planned (not yet implemented)

- AI-driven recommendation system
- Public API platform
- Web-based analytics interface

This section reflects the **actual engineering maturity** of the system and distinguishes it from long-term architectural goals.

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
        │ SQLite Data Warehouse        │
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

This pipeline transforms **unstructured web information** into a **structured knowledge system** that can power analytics tools, university intelligence platforms, and future AI‑driven recommendation systems.

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
- **SQLite** – local analytical knowledge base
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

CrawlerNest is currently evolving from a crawler-centric system into a modular data platform with:

- a structured data ingestion pipeline
- a normalization engine (C-based prototype)
- a knowledge base (SQLite warehouse)
- an emerging service layer (Java backend)

The project is in a **platform-building phase**, focusing on stability, data quality, and architectural scalability.

---

## Access

CrawlerNest repositories are currently **private** and maintained under the CrawlerNest organization.

---

## License

This project is licensed under the Apache License 2.0.

© 2026 CrawlerNest Organization