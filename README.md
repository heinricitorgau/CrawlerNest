# CrawlerNest: University Data Infrastructure + Web Platform

Traditional Chinese version: [README.zh-TW.md](README.zh-TW.md)

**CrawlerNest** has evolved from an infrastructure-focused data pipeline into a comprehensive **University Data Infrastructure and Web Platform**. It bridges the gap between raw, scattered global education data and actionable, consumer-facing insights.

## What is this system?
CrawlerNest is an end-to-end data platform that transforms fragmented web data (university rankings, admission requirements, tuition) into structured knowledge. It powers a deterministic decision engine that algorithmically guides students, replacing black-box manual consulting with transparent, data-driven "reach/target/safety" recommendations.

## Why it exists
While APIs and CLIs validate the data, students and advisors need a visual, comparative interface to make life-altering decisions. Raw data is overwhelming; by layering a deterministic decision engine and a clean UX over our data infrastructure, we provide clarity instead of just volume.

## Current Capabilities
*   **Data Pipeline:** Asynchronous, compliance-aware crawlers fetching global rankings (1500+ universities scaled).
*   **Multi-Universe Ingestion:** QS global / region / subject / special universes can be ingested through one unified runner.
*   **Ingestion Traceability:** Every ingest run now writes `run_id` / `updated_at` trace fields into PostgreSQL ranking records.
*   **Canonical Recovery Path:** Unlinked crawled universities can now be promoted into `canonical_university` and backfilled into `warehouse.ranking_record` without changing crawler behavior.
*   **Aggregation Truth:** Aggregation now supports multi-universe truth, and the visible aggregated ranking count has expanded from 221 to 2736 after canonical seeding, ranking backfill, and THE missing-entity recovery.
*   **Decision Engine:** An explainable recommendation engine providing deterministic groupings (reach/target/safety).
*   **API Platform:** Repaired Java Spring Boot APIs (API v1) serving normalized analytical data with support for scoped/regional filtering.
*   **Database Reliability:** Robust PostgreSQL transaction handling with automatic rollbacks on batch failures.
*   **Frontend Freshness:** The Next.js rankings browser uses same-origin proxying, `no-store` fetches, periodic polling, and focus/visibility refresh to keep the UI close to live database state.

## High-Level Architecture
CrawlerNest is built on a strict, decoupled 5-layer architecture:
1.  **Data Layer:** Web crawlers fetching from global sources.
2.  **Canonical (Processing) Layer:** Entity resolution and normalization.
3.  **Aggregation (Storage) Layer:** PostgreSQL data warehouse.
4.  **Decision Layer:** Recommendation engine and comparison logic.
5.  **API (Product) Layer:** Java Spring Boot APIs and the Consumer Website.

For a deep dive into the engineering principles, see the [Whitepaper](docs/foundation/Whitepaper.md).

## Python Environment Setup

CrawlerNest's Python pipeline should run inside the project virtual environment.

### 1. Create the virtual environment
```bash
python3 -m venv .venv
```

### 2. Activate it
```bash
source .venv/bin/activate
```

### 3. Install Python dependencies
```bash
pip install -r requirements.txt
```

The production-safe runner already prefers:

```bash
/Users/test/Desktop/crawlernest/.venv/bin/python
```

So keeping `.venv` healthy is the safest way to run the crawler, validation scripts, and PostgreSQL ingestion pipeline.

## Data Visibility Model

CrawlerNest now has a clear database visibility chain:

1. crawler writes raw university / ranking facts into PostgreSQL
2. canonical identity layer links raw universities to `canonical_university`
3. `warehouse.ranking_record` stores universe-aware ranking truth
4. aggregation refreshes `analytics.v_aggregated_rankings_latest`
5. Spring Boot API reads aggregated truth
6. Next.js frontend reads through `/api/rankings`

This matters because universities stored only in `warehouse.universities` are not automatically visible in the API.  
They become visible only after canonical linking and ranking-record backfill are complete.

## How to Run the Web Platform (Website MVP)

To start the full stack (Backend API + Frontend UI), follow these steps in two separate terminals:

### 1. Start the Java Backend API
The backend serves normalized university and ranking data.
```bash
cd crawlernest/servise_for_java
./mvnw spring-boot:run
```

### 2. Start the Next.js Frontend
The frontend provides the Rankings Browser and Recommendation UI.
```bash
cd crawlernest/crawlernest-web
npm run dev
```

The application will be available at `http://localhost:3000`.

The frontend rankings browser is designed to stay close to the database state:
- same-origin API proxy at `/api/rankings`
- `no-store` fetches through the proxy
- periodic polling
- immediate refresh on focus / visibility / reconnect

---

## How to Run the Data Pipeline (Crawler)

Use the pipeline commands according to the job you want to perform:

- **daily safe operation**: use the production-safe runner
- **manual crawl / targeted reruns**: use the QS / THE commands directly
- **verification**: use validation and diagnostic commands
- **visibility repair**: use canonical / backfill recovery commands

### 1. Production-Safe Run (Recommended Daily Entry)

Use this when you want the safest default command for regular operation.

```bash
bash crawlernest/scripts/run_production_safe.sh
```

To resume after an interruption:

```bash
bash crawlernest/scripts/run_production_safe.sh 2500 --resume
```

The production-safe script currently runs:

- **Step 1**: QS global rankings crawl
- **Step 2**: deferred detail enrichment if pending items exist
- **Step 3**: THE world rankings ingestion
- **Step 4**: QS major region universes, one pass each
  - europe
  - asia
  - latin-america
  - arab-region
  - oceania
  - africa
  - north-america

Operational behavior:

- prefers the project `.venv` automatically
- keeps the crawler progress to a single live progress line
- supports resume mode for interrupted runs
- continues writing each completed pass into PostgreSQL
- warns and continues if non-critical stages fail

### 2. Manual Crawl / Ingest Commands

Use these commands when you need direct control over scope, resume behavior, or testing.

#### 2.1 Run all QS universes

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-qs-universes --ranking-year 2026 --limit 2500 --pg-user test --pg-database clawer
```

To resume an interrupted QS multi-universe run:

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-qs-universes --ranking-year 2026 --limit 2500 --resume --pg-user test --pg-database clawer
```

#### 2.2 Run a single QS region universe

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-qs-region --region europe --ranking-year 2026 --limit 2500 --pg-user test --pg-database clawer
```

To resume the same region:

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-qs-region --region europe --ranking-year 2026 --limit 2500 --resume --pg-user test --pg-database clawer
```

#### 2.3 Run THE world rankings

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-the-rankings --pg-user test --pg-database clawer
```

If you only want THE ingest without extra seed/backfill recovery:

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-the-rankings --skip-seed --pg-user test --pg-database clawer
```

Important runtime behavior for QS universe commands:

- `run-qs-*` and `run-qs-universes` are continuous commands and keep running until `Ctrl+C`
- each completed pass is written to PostgreSQL before the next pass starts
- if interrupted, rerun with `--resume` to continue from the last saved universe snapshot instead of starting from scratch

### 3. Validation and Diagnostics

Use these commands after crawl/ingest when you want to confirm data correctness or identify missing universes.

#### 3.1 Validate aggregation output

```bash
./.venv/bin/python crawlernest/scripts/validate_aggregation.py --year 2026 --universe-type region --universe-key europe
```

The validator reports:

- row count
- distinct university count
- duplicate count
- null rank count
- missing ranks
- top countries
- top 20 preview

#### 3.2 Diagnose missing QS universes

```bash
./.venv/bin/python crawlernest/run_pipeline.py rebuild-universe-records --ranking-year 2026 --pg-user test --pg-database clawer
```

This command:

- checks all configured QS universes
- reports which universe/year pairs currently have `0` rows in `warehouse.ranking_record`
- does **not** re-crawl by itself

### 4. Visibility Recovery Commands

Use these only when data exists in PostgreSQL but is still missing from the API or frontend.

#### 4.1 Recover universities already present in `warehouse.universities`

If universities have already been crawled into `warehouse.universities` but do not appear in the API or frontend, the usual cause is missing canonical/link/backfill steps.

Run these two commands in order:

```bash
./.venv/bin/python crawlernest/run_pipeline.py seed-canonical --pg-user test --pg-database clawer
./.venv/bin/python crawlernest/run_pipeline.py backfill-ranking-records --pg-user test --pg-database clawer
```

These commands:

- create missing `canonical_university` rows
- create missing `canonical_university_link` rows
- backfill legacy `warehouse.rankings` into `warehouse.ranking_record`
- refresh aggregation so the API/frontend can see the new rows immediately

Observed result from the current environment:

- visible global aggregated rows increased from `221` to `1323`
- `/api/v1/rankings` reported `metadata.totalCount = 1323`

#### 4.2 Recover THE-only universities from `analytics.missing_entity_log`

THE universities do not come from `warehouse.universities`, so `seed-canonical` alone cannot recover them.

```bash
./.venv/bin/python crawlernest/run_pipeline.py seed-canonical-from-missing --pg-user test --pg-database clawer
```

This command:

- reads unresolved rows from `analytics.missing_entity_log` (default source: `THE`)
- seeds new `canonical_university` entities from `(raw_name, country_hint)`
- re-runs THE ingestion so the newly seeded entities can be matched immediately

Observed result from the current environment:

- `seeded=1283`
- THE re-ingest reached `matched=2191`
- THE `unresolved=0`
- aggregated visible rows expanded to `2736`

---

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

### 3. All-in-One Major Rankings Run
This single command runs the World ranking and all 5 major regional rankings (Europe, Asia, Latin America, Oceania, Africa) sequentially in a continuous loop.
```bash
./.venv/bin/python crawlernest/run_pipeline.py run-qs-major --ranking-year 2026
```

---

For engineering operations, API invariants, and testing logic, see the [Engineering Validation & Maintenance Guide](docs/foundation/TESTING_GUIDE.md).
