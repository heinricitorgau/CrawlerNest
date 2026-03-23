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
- ✅ PostgreSQL-only knowledge base and operational warehouse
- ✅ PostgreSQL schema initialization baseline (validated)
- ✅ Extraction and parsing modules for rankings and admission data
- ✅ Python data ingestion pipeline (crawler → DB)
- ✅ Minimal end-to-end runner (`crawlernest/run_pipeline.py`: crawl → normalize → store → query)
- ✅ Multi-source ranking integration path (QS / THE / ARWU → entity resolution → `warehouse.ranking_record`)
- ✅ Deterministic aggregation refresh from PostgreSQL ranking facts
- ✅ C normalization engine (prototype for high-performance parsing)
- ✅ Modular architecture (crawler / extractor / db_writer separation)
- ✅ Initial Java Spring Boot service integration (validated startup against PostgreSQL baseline)
- ✅ Read-only internal API endpoints: `/universities`, `/rankings`, `/admissions`
- ✅ Deterministic comparison engine with explainable side-by-side reasoning
- ✅ Recommendation engine v1 / v2 / v3:
  - `recommend`: hard-filtered rule-based shortlist
  - `recommend-v2`: grouped reach / target / safety decisions
  - `recommend-v3`: hybrid deterministic scoring with preference weights and risk adjustments
- ✅ Recommendation and comparison API endpoints: `/recommendations`, `/compare`
- ✅ Rankings-only mode (`--rankings-only`) for faster collection when detail pages are not required
- ✅ Local parse parallelism (`--local-parse-workers`) that speeds parsing without increasing web-request concurrency
- ✅ Batch DB writes (`executemany` path in writer) to reduce per-row write overhead
- ✅ Incremental checkpoint journal (`*.journal`) + compaction to speed resume reliability
- ✅ Partial update strategy: compare `school_slug + ranking_type + year` and skip unchanged rows
- ✅ Request-parameter failure blacklist (TTL) to avoid repeatedly retrying known-bad API parameter pairs

V1.5 completion snapshot (as of 2026-03-23):

- **End-to-end pipeline maturity**: ~88% (crawl -> normalize -> write -> query is stable)
- **Performance optimization maturity**: ~85% (batch write / incremental checkpoint / partial update in production path)
- **Operational resilience maturity**: ~82% (403 auto-degrade + deferred enrichment flow established)
- **Decision-support maturity**: ~72% (aggregated rankings + explainable comparison + grouped and hybrid recommendations are operational)

### Next (V2): In progress

- Data consistency and normalization refinement
- Canonical / ranking year quality backfill
- Knowledge base expansion (programs, degrees, metadata)
- PostgreSQL-backed service and analytics expansion
- Program-level recommendation refinement

### Future (V3): Planned (not yet implemented)

- AI-driven recommendation system
- Public API platform
- Web-based analytics interface

This section reflects the **actual engineering maturity** of the system and distinguishes it from long-term architectural goals.

---

## Minimal End-to-End Usage (Current)

The commands below describe the current, testable path for QS data and the active multi-source ranking pipeline.

### 1) Run crawler → extract → normalize → store (PostgreSQL)

From repository root:

```bash
python3 crawlernest/run_pipeline.py run --limit 30 --ranking-year 2026
```

Compliance-safe baseline (recommended for QS):

```bash
python3 crawlernest/run_pipeline.py run \
  --limit 200 \
  --ranking-year 2026 \
  --workers 1 \
  --request-delay 10 \
  --local-parse-workers 4 \
  --write-batch-size 200
```

Pinned production-safe command (recommended for daily runs):

```bash
bash crawlernest/scripts/run_production_safe.sh
```

Fast ranking-only mode (skip per-school detail requirements pages):

```bash
python3 crawlernest/run_pipeline.py run \
  --limit 200 \
  --ranking-year 2026 \
  --rankings-only \
  --workers 1 \
  --request-delay 10
```

Deferred detail enrichment in small batches (recommended after 403 degrade):

```bash
python3 crawlernest/run_pipeline.py enrich-details \
  --limit 30 \
  --request-delay 10
```

Expected console shape:

```text
[1/4] Crawling QS data...
[2/4] Normalizing fields (Python baseline)...
[3/4] Writing 30 rows to postgres...
[4/4] Done.
[multi-source] rows=30 matched=30 unresolved=0 duplicates=0 aggregated_years=[2026]
```

The `run` command keeps the existing QS crawler path, then syncs normalized QS rows into the active multi-source flow:

```text
crawler -> extractor -> normalize -> entity resolution
-> source adapter -> warehouse.ranking_record -> aggregation -> recommendation
```

### 2) Ingest THE / ARWU payloads into the same multi-source pipeline

THE:

```bash
python3 crawlernest/run_pipeline.py ingest-rankings \
  --source THE \
  --input-file ./the_sample.json \
  --ranking-year 2026
```

ARWU:

```bash
python3 crawlernest/run_pipeline.py ingest-rankings \
  --source ARWU \
  --input-file ./arwu_sample.json \
  --ranking-year 2026
```

Expected payload shape:

```json
[
  {
    "id": "the:oxford",
    "institution": "University of Oxford",
    "country": "United Kingdom",
    "year": 2026,
    "rank_position": 1,
    "scores": { "overall": 98.5 },
    "profile_url": "https://example.test/the/oxford"
  }
]
```

Source rows are stored independently. QS, THE, and ARWU are not overwritten across sources; they are combined later by aggregation.

### 3) Query stored rankings (PostgreSQL query mode)

```bash
python3 crawlernest/run_pipeline.py query MIT --limit 20
```

Expected output shape:

```text
rank | university | country | score | ranking_type
1 | Massachusetts Institute of Technology (MIT) | United States | 100.0 | world
```

### 4) Spring Boot API paths

Once `servise_for_java` is running:

- `GET /universities`
- `GET /rankings`
- `GET /admissions`
- `GET /recommendations`
- `GET /compare`

Example requests:

```bash
curl http://localhost:8080/universities
curl http://localhost:8080/rankings
curl http://localhost:8080/admissions
curl "http://localhost:8080/recommendations?country=United%20Kingdom&ielts=6.5&targetRank=100&preferredRankingSource=QS&limit=3"
curl "http://localhost:8080/recommendations?version=v3&targetRank=100&ielts=6.5&country=United%20Kingdom&riskProfile=aggressive"
curl "http://localhost:8080/compare?u1=Oxford&u2=LSE"
```

Note: public/external API hardening is still part of future roadmap work.

### 5) Recommendation and Comparison (current)

CLI:

```bash
python3 crawlernest/run_pipeline.py recommend \
  --country "United Kingdom" \
  --ielts-score 6.5 \
  --target-rank 100 \
  --preferred-ranking-source QS \
  --limit 5
```

Without `--preferred-ranking-source`, the recommender uses the aggregated multi-source rank by default.

Grouped strategy recommendation:

```bash
python3 crawlernest/run_pipeline.py recommend-v2 \
  --target-rank 100 \
  --ielts 6.5 \
  --risk-profile balanced \
  --country "United Kingdom" \
  --limit 5
```

Hybrid deterministic recommendation:

```bash
python3 crawlernest/run_pipeline.py recommend-v3 \
  --target-rank 100 \
  --ielts 6.5 \
  --risk-profile aggressive \
  --country "United Kingdom" \
  --preference-weights '{"ranking":0.5,"ielts":0.2,"confidence":0.2,"country_match":0.1}' \
  --limit 5
```

University comparison:

```bash
python3 crawlernest/run_pipeline.py compare --a "Oxford" --b "LSE"
```

API smoke test:

```bash
python3 crawlernest/scripts/smoke_test_recommendations_api.py --base-url http://localhost:8080
```

Expected v3 response shape:

```json
{
  "reach": [
    {
      "university_name": "University of Oxford",
      "score": 94.2,
      "category": "reach",
      "preference_alignment": "strong",
      "explanation": "..."
    }
  ],
  "target": [],
  "safety": [],
  "metadata": {
    "version": "v3",
    "risk_profile": "aggressive",
    "preference_weights": {
      "ranking": 0.5,
      "ielts": 0.2,
      "confidence": 0.2,
      "country_match": 0.1
    }
  }
}
```

### 6) Multi-source validation queries

Check that source rows were persisted independently:

```sql
SELECT
  cu.display_name,
  rs.source_code,
  rr.ranking_year,
  rr.rank_position,
  rr.score
FROM warehouse.ranking_record rr
JOIN warehouse.ranking_source rs
  ON rs.ranking_source_id = rr.ranking_source_id
JOIN warehouse.canonical_university cu
  ON cu.canonical_university_id = rr.canonical_university_id
WHERE cu.display_name ILIKE '%Oxford%'
ORDER BY rs.source_code;
```

Check that aggregation has been refreshed:

```sql
SELECT
  canonical_university_id,
  ranking_year,
  display_rank,
  composite_score,
  source_ranks_json,
  source_normalized_scores_json
FROM analytics.v_aggregated_rankings_latest
WHERE ranking_year = 2026
ORDER BY display_rank
LIMIT 20;
```

---

## Performance Updates (2026-03)

The following acceleration items are already implemented and active in current pipeline:

- **Network compliance first**: QS requests remain conservative (`workers=1`, `request_delay≈10s`) to reduce legal/rate-limit risk.
- **Two-stage crawl mode**: support ranking-only runs, then optional detail enrichment later.
- **Local CPU acceleration**: detail-page parsing can use local workers without violating web-side request pacing.
- **Write-path batching**: raw records / aliases / rankings / admissions support batched insert calls.
- **Checkpoint incrementalization**: append-only journal during run, then compact at finish.
- **Partial update write-avoidance**: unchanged schools are skipped by key state comparison, reducing unnecessary DB writes.
- **Bad-parameter suppression**: failed request parameter combinations are temporarily blacklisted (TTL) to avoid repeated slow failures.

### Known Field Issue: QS Detail 403

Observed behavior:

- Ranking list fetch may succeed, while detail pages (`/universities/...`) return `403 Forbidden`.
- This is more likely under async HTTP client fingerprints and repeated detail-page access patterns.

Operational handling (current project standard):

- Keep compliance-safe pacing: `workers=1`, `request_delay=10`.
- Prefer non-async mode for full detail crawl when 403 appears repeatedly.
- Use `--rankings-only` first for stable main dataset, then run detail enrichment in smaller batches.

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
        │ PostgreSQL Warehouse         │
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
- PostgreSQL knowledge base and schema initialized
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
- **PostgreSQL** – single operational database and source of truth
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
- a PostgreSQL knowledge base and service data layer
- an emerging service layer (Java backend with read-only endpoints for universities/rankings/admissions)

The project is in a **platform-building phase**, focusing on stability, data quality, and architectural scalability.

---

## Access

CrawlerNest repositories are currently **private** and maintained under the CrawlerNest organization.

---

## License

This project is protected by a custom proprietary license.
See the [LICENSE](./LICENSE) file for full terms and restrictions.

---

## AutoEval Extractor Milestone

CrawlerNest has successfully completed its first full **AutoEval optimization loop** for the extractor system, achieving production‑grade extraction accuracy on a hard, adversarial dataset.

### Final Evaluation Result

- Required fill rate: 1.0 (100%)
- Exact match rate: 1.0 (100%)
- Error count: 0
- Adjusted score: ~0.95 (runtime adjusted)

| Metric                | Value      |
|----------------------|------------|
| required_fill_rate   | 1.000000   |
| exact_match_rate     | 1.000000   |
| error_count          | 0          |
| score (runtime adj.) | ~0.95      |

### Significance

This milestone demonstrates the extractor's capability to achieve near-perfect accuracy and robustness on challenging data sets, validating the effectiveness of the AutoEval loop.

### Reproduce

Run the evaluation locally to reproduce the results:

```bash
python crawlernest/crawlernest-autoeval/runners/run_extractor_eval.py --no-log
```

You should observe zero errors and near‑perfect score (runtime-adjusted).

---

## Technology

CrawlerNest uses a lightweight and portable stack designed for research and data engineering:

- **Python** – crawler pipelines and data processing
- **PostgreSQL** – single operational database and source of truth
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
- a PostgreSQL knowledge base and service data layer
- an emerging service layer (Java backend with read-only endpoints for universities/rankings/admissions)

The project is in a **platform-building phase**, focusing on stability, data quality, and architectural scalability.

---

## Access

CrawlerNest repositories are currently **private** and maintained under the CrawlerNest organization.

---

## License

This project is protected by a custom proprietary license.
See the [LICENSE](./LICENSE) file for full terms and restrictions.
