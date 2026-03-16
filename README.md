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
        │ SQLite Data Warehouse       │
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
├── clawer_c_data_normalization_engine/
│   High‑performance data normalization engine written in C
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
- **C** – high‑performance normalization engine
- **Java / Spring Boot** – backend API services and recommendation engine
- **AsyncIO** – asynchronous crawling
- **PyTest** – automated testing

---

## Platform Concept

```
Web Crawling → Data Platform → Knowledge Base → Analytics → AI
```

---

## Project Status

Active development.

CrawlerNest is an evolving research and engineering project exploring scalable education data systems.

---

## Access

CrawlerNest repositories are currently **private** and maintained under the CrawlerNest organization.

---

## License

This project is licensed under the Apache License 2.0.

© 2026 CrawlerNest Organization