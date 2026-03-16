# CrawlerNest Roadmap

CrawlerNest is evolving from a crawler prototype into a full **education data intelligence platform**.  
This roadmap outlines the planned development phases of the project.

---

# Phase 1 — Core Crawler Platform (Current)

Goal: Build a stable and modular crawler infrastructure.

Key components:

- Modular crawler architecture
- Async web crawling pipelines
- Data extraction and validation
- SQLite-based data storage
- Command-line data explorer
- Automated tests with PyTest

Repositories involved:

- crawlernest-core
- crawlernest-jobs
- crawlernest-extractors
- crawlernest-db-writer
- crawlernest-schema
- crawlernest-cli

Status: **Active development**

---

# Phase 2 — Knowledge Base Construction

Goal: Transform crawled data into a structured **University Knowledge Base**.

Planned work:

- entity normalization
- university identity resolution
- ranking dataset consolidation
- admission requirement datasets
- regional and country metadata

Repositories involved:

- crawlernest-normalization
- crawlernest-kb
- crawlernest-schema

Expected result:

A structured and queryable education data warehouse.

---

# Phase 3 — Data Analytics Layer

Goal: Provide analytical capabilities on top of the knowledge base.

Planned features:

- ranking comparison tools
- cross-region university statistics
- admission requirement analysis
- ranking trend tracking

Repositories involved:

- crawlernest-analytics

Potential outputs:

- analytical datasets
- reports
- statistical summaries

---

# Phase 4 — Recommendation Engine

Goal: Build intelligent systems that help users discover suitable universities.

Possible features:

- university recommendation system
- admission probability estimation
- program similarity matching
- country and region recommendation

Technologies under exploration:

- machine learning models
- similarity search
- ranking algorithms

---

# Phase 5 — Data Platform Expansion

Goal: Expand the platform beyond a crawler into a full data intelligence system.

Possible directions:

- REST API services
- web-based data explorer
- education analytics dashboards
- large-scale dataset releases

Potential new repositories:

- crawlernest-api
- crawlernest-web

---

# Long-Term Vision

CrawlerNest aims to evolve into a **global education data intelligence platform** capable of:

- collecting large-scale university data
- building structured knowledge bases
- powering analytics and decision systems
- supporting AI-driven recommendation tools

---

# Estimated Project Scale

Current scale:

- ~7.7k lines of code and documentation
- Python crawler pipelines
- C-based normalization engine
- SQLite knowledge base
- modular multi-repository architecture

The platform will continue expanding as additional data sources and analytical capabilities are integrated.
