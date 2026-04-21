# CrawlerNest

Traditional Chinese version: [README.zh-TW.md](README.zh-TW.md)

**CrawlerNest** is a **University Data Intelligence Infrastructure** enhanced by a **controlled, evaluation-driven AI-assisted development layer**. It bridges fragmented global education data with structured analytics, explainable recommendation, and production-minded system design.

## What is this system?
CrawlerNest is an end-to-end data platform that transforms fragmented web data into structured, queryable university intelligence. It aggregates ranking sources such as QS, THE, and ARWU, exposes ranking evidence and trust signals, and powers explainable recommendation and comparison workflows for students, counselors, and product teams.

It is now also evolving with a **Mini-Agent Development Layer** and an early **Web Agent path**: a lightweight, controlled workflow for development acceleration, system refinement, and web-facing agent interaction on top of CrawlerNest data. This layer remains deeply tied to evaluation, provider visibility, safe fallback behavior, and human oversight. It is not a standalone autonomous agent system.

## Why it exists
Students and advisors do not just need more ranking rows. They need transparent evidence, comparable signals, and decision support they can trust. CrawlerNest exists to make ranking aggregation understandable rather than opaque, and useful rather than merely searchable.

## Current Capabilities
*   **Multi-Source Ranking Ingestion:** QS, THE, and ARWU can now feed the same ranking storage and aggregation path. THE world rankings prefer **structured JSON** (CDN blobs when published, else Next.js `__NEXT_DATA__`) rather than brittle HTML-first scraping.
*   **Split Crawler Foundation:** The crawling stack now has an explicit shared crawler core plus two independent engines: a **Ranking Crawler Engine** for ranking sources and an **Admission Crawler Engine** for university-site admissions data.
*   **Standalone Shared Crawler Subproject:** `crawlernest-crawler-core/` is now treated as a separately developable runtime subproject for shared transport, retry, rate limiting, logging, and snapshot primitives. Ranking and admission crawlers may depend on it, but business-specific extraction or recommendation logic must stay outside this boundary.
*   **Ranking Production Workflow:** The ranking path now runs through a controlled production-oriented chain: raw artifact, normalized artifact, staging output, validation gate, controlled ingest, warehouse preview, warehouse landing, deterministic entity resolution, unresolved reporting, alias seeding, and refresh orchestration.
*   **Admission Production Workflow:** The admission path now has its own controlled chain from crawl through staging, validation, warehouse preview, warehouse landing, deterministic entity resolution, unresolved reporting, and alias-driven refresh.
*   **Correctness-First Hardening:** The admission path now includes host allowlisting, extractor input budgets, field-range validation, anomaly breakdowns, and richer suspicious-resolution visibility before broader scale-up.
*   **Universe-Aware Aggregation:** Rankings are handled as distinct universes such as `global`, `region`, `subject`, and `special`, with aggregation isolated per universe.
*   **Rank-Based Aggregation Truth:** Aggregated rank order is now driven by source ranks, not composite score sorting. Composite score remains a display signal only.
*   **Ranking Evidence:** Product rows and university detail pages expose QS / THE / ARWU source ranks directly, including disagreement across sources.
*   **Trust Layer:** Each aggregated ranking can include a conservative trust score and trust explanation based on source coverage and source agreement.
*   **Explainable Recommendation:** Recommendations include fit dimensions, reasons, and warnings instead of opaque match scores only.
*   **Compare Workflow:** Shortlisted universities can be compared side by side using aggregated rank, source evidence, trust, and admissions context.
*   **Canonical Country Filtering:** Rankings country filters now flow through a centralized canonical country normalization layer. Variants such as `China`, `China (mainland)`, `USA`, and `UK` are normalized before validation, SQL filtering, and metadata generation.
*   **Canonical Recovery Path:** Unlinked crawled universities can be promoted into `canonical_university` and backfilled into `warehouse.ranking_record` without changing crawler behavior.
*   **Convergence Preview Layer:** Ranking and admission preview rows can now be joined through shared canonical identity, producing convergence preview and canonical university detail preview objects before product read-model hardening.
*   **Ingestion Traceability:** Every ingest run writes `run_id` / `updated_at` trace fields into PostgreSQL ranking records.
*   **API Platform:** Java Spring Boot APIs expose rankings, university detail, recommendations, comparison data, and a thin preview endpoint for canonical university detail preview.
*   **Split Agent Runtime:** Web Agent and Dev Agent now have explicit execution boundaries, separate tool scopes, and separate response contracts, while still sharing lower-level planner / validation / memory capabilities.
*   **Web Agent Generation Layer:** The web-facing `/agent` path now includes a provider-aware generation layer with task-specific context building, task-specific prompt routing, OpenAI-compatible / local-model support, and deterministic fallback when no model is available.
*   **Agent Observability:** Debug mode now exposes generation source, provider status, memory summaries, and recent-entity carry-over signals without leaking those details into normal user mode.
*   **Database Reliability:** PostgreSQL transaction handling, canonical repair paths, and operational snapshot fallback keep the product usable even when upstream sources are unstable.

## High-Level Architecture

CrawlerNest now has two explicit architecture views:

- `docs/architecture/SYSTEM_ENGINE_ARCHITECTURE.md`
  canonical system / engine architecture covering both current execution reality and longer-term vision

For current engineering reality, the safest summary is:

1. **Active Data Pipeline:** crawl, extract, normalize, write, warehouse, API, web
2. **Controlled Expansion:** limited admission enrichment and basic rule-based recommendation
3. **Development Support Only:** mini-agent, autoeval, and broader agent systems are not part of the production data path

Inside the data-production path, the crawler system is now intentionally split into three code boundaries:

- **`crawlernest-crawler-core/`**: shared transport/runtime concerns such as HTTP, retry, rate limiting, logging, and snapshot stubs
- **`crawlernest-ranking-crawler/`**: ranking-source crawling for QS, THE, ARWU, ranking universes, and structured ranking rows
- **`crawlernest-admission-crawler/`**: university-site crawling, admission-page discovery, and extraction of semi-structured admission requirements

`crawlernest-crawler-core/` should be read as a thin shared runtime dependency that can evolve on a different cadence from crawler engines, as long as it preserves its non-business, reusable boundary.

`run_pipeline.py` remains the top-level orchestration entrypoint for the active path.

The Mini-Agent Layer follows a constrained loop:

`Task -> Generate -> Evaluate -> Refine`

It is integrated with AutoEval and designed to improve development speed without weakening system reliability, but it is not part of the production data path.

The ranking-specific data-production loop now follows this controlled path:

`crawl -> raw -> normalized -> staging -> validate -> ingest -> warehouse preview -> warehouse landing -> resolve -> report -> seed -> refresh`

This path is intentionally isolated from the final production read model. Ranking facts are first stabilized in staging and warehouse landing layers, then enriched through deterministic entity resolution and manual curation before they are allowed to influence broader downstream truth.

Current downgrade assumptions:

- recommendation is still acceptable as a basic / optional rule-based capability
- multi-source integration and ranking aggregation remain broader expansion areas rather than the minimum executable core
- agent systems remain development-support capabilities, not production truth generators

For a deep dive into the engineering principles, see the [Whitepaper](docs/foundation/Whitepaper.md).

The current mainline development guardrails are defined here:

- [Architecture Scope](docs/foundation/ARCHITECTURE_SCOPE.md)
- [Data Contracts](docs/foundation/DATA_CONTRACTS.md)
- [Do Not Auto Modify](docs/foundation/DO_NOT_AUTO_MODIFY.md)

These documents define the no-skip order for CrawlerNest:

1. stabilize crawl and extraction
2. stabilize normalization and canonical mapping
3. formalize warehouse and API contracts
4. build admission-aware recommendation
5. only then expand agent autonomy

## AI-Assisted Development (Mini-Agent)

- **Controlled by design:** the Mini-Agent layer is a bounded workflow, not a fully autonomous system
- **Evaluation-driven:** generated outputs are expected to pass evaluation before broader adoption
- **Human-in-the-loop:** oversight is required for important changes, refinements, and integration decisions
- **Integrated with AutoEval:** evaluation is used to reinforce reliability rather than automate blindly
- **Focused on system refinement:** useful for extractor iteration, workflow improvement, and development acceleration

## Design Philosophy

- reliability over autonomy
- evaluation-first development
- controlled automation over unrestricted generation
- system clarity over opaque intelligence

## Dual-System Architecture

CrawlerNest is designed as a dual-layer system combining a data intelligence core with an evaluation-driven agent capability layer.

### Core Intelligence Layer

The Core Intelligence Layer is responsible for the platform's primary data and decision workflow. In the current execution stage, that mostly means crawl, extract, normalize, controlled write, warehouse, and product-serving API paths. This layer remains deterministic, queryable, and production-oriented.

### Agent Capability Layer

The Agent Capability Layer sits above the operational core as a controlled improvement and assistance system. It is intentionally outside the production data path and now has two explicit modes:

- a **Dev Agent** path for extractor hardening, parser refinement, evaluation loops, and engineering-facing validation
- a **Web Agent** path for conversational ranking explanation, university lookup, recommendation guidance, and web-facing agent interaction

Both modes share bounded lower-level capabilities, but they do not share the same execution policy. The Dev Agent remains engineering-facing and validation-heavy, while the Web Agent is formatter-driven, provider-aware, fallback-safe, and designed to produce user-facing responses without exposing development-only behavior.

CrawlerNest Platform
│
├── Core Intelligence Layer
├── Agent Capability Layer
└── Interface Layer

This separation exists to preserve clarity of responsibility inside the architecture. The core platform can scale as a stable intelligence and analytics system, while the agent layer can evolve independently as a controlled, self-improving capability. The result is a cleaner separation of concerns, a more scalable system boundary, and a foundation for iterative improvement without weakening trust in the production data path.

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
5. Spring Boot API joins canonical university metadata on top of aggregated truth for product fields such as `universityName`, `slug`, and `country`
6. Next.js frontend reads through `/api/rankings`

This matters because universities stored only in `warehouse.universities` are not automatically visible in the API.  
They become visible only after canonical linking and ranking-record backfill are complete.

## How to Run the Web Platform (Website Product Layer)

To start the full stack (Backend API + Frontend UI), follow these steps in two separate terminals:

### 1. Start the Java Backend API
The backend serves normalized university and ranking data.

Before you start the Java backend for a fresh verification run, do this first:

1. stop any old Spring Boot process so you do not keep querying stale code
2. recompile the backend after changing ranking / trust / country-filter logic
3. if you changed normalization or rankings read-path logic, run the focused test before boot

Recommended preflight:

```bash
pkill -f "spring-boot:run"
cd crawlernest/servise_for_java
./mvnw -q -DskipTests compile
./mvnw -q -Dtest=CountryNormalizationTest test
```

Then start the API:

```bash
./mvnw clean
./mvnw spring-boot:run
```

### 2. Start the Next.js Frontend
The frontend provides the Rankings Browser and Recommendation UI.
```bash
cd crawlernest/crawlernest-web
npm run dev
```

The application will be available at `http://localhost:3000`.

The frontend currently includes:
- rankings browser
- university detail pages
- recommendation flow
- compare page

The rankings browser uses same-origin API proxying at `/api/rankings` and `no-store` fetches, but it now refreshes only on initial load, filter changes, or manual browser refresh.

Country filtering is applied in the final rankings read query rather than the aggregation layer:

- aggregated rank order is preserved
- product rows are filtered by canonical university country metadata
- global scope allows any supported country
- region scope remains region-consistent
- country aliases are normalized to canonical names before validation and SQL filtering
- `metadata.countryOptions` is deduplicated to canonical country names

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
- **Step 3.5**: ARWU world rankings ingestion
- **Step 4**: QS major region universes, one pass each
  - europe
  - asia
  - latin-america
  - arab-region
  - oceania
  - africa
  - north-america
- **Step 5**: seed canonical entities from missing THE entities

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

#### 2.4 Chain the main `run` command with THE (optional)

After QS crawl → normalize → DB write → QS multi-source sync, you can ingest THE in the same invocation (does not change default behavior unless you pass the flag):

```bash
./.venv/bin/python crawlernest/run_pipeline.py run --limit 2500 --ranking-year 2026 \
  --with-the-rankings --the-ranking-year 2026 \
  --pg-user test --pg-database clawer
```

Useful flags:

- `--the-ranking-year` — THE edition (default: `2026`)
- `--the-output-dir` — where `the_rankings_<year>.json` is written (defaults to `crawlernest/crawlernest-kb/databases`)
- `--the-skip-seed` — skip canonical seed / legacy backfill after THE ingest (faster, less recovery)

Pipeline logs include `[THE_CRAWL]` during the THE crawl; THE rows use `run_id` batch style `the-<year>` in the multi-source ingest path.

#### 2.5 All-in-one QS major regions (continuous loop)

This single command runs the World ranking and all five major regional rankings (Europe, Asia, Latin America, Oceania, Africa) sequentially in a continuous loop:

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-qs-major --ranking-year 2026
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

#### 3.3 Count THE rows in `warehouse.ranking_record`

`ranking_record` stores `ranking_source_id`, not a plain `source` text column. Join the registry:

```sql
SELECT COUNT(*)
FROM warehouse.ranking_record rr
JOIN warehouse.ranking_source rs ON rs.ranking_source_id = rr.ranking_source_id
WHERE rs.source_code = 'THE';
```

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
For the current repository map and working paths, see [Repository Structure](docs/architecture/REPO_STRUCTURE.md).

## Current System Status
This reflects our actual engineering maturity:
*   ✅ **production-safe pipeline:** DONE (2,767 global universities visible through the current rankings API query)
*   ✅ **PostgreSQL integration:** DONE (transaction-safe with rollback)
*   ✅ **recommendation engine (v3 decision system):** DONE
*   ✅ **API v1 readiness:** DONE (repaired, pagination-aligned, scope-aware, country-aware)
*   ✅ **node deployment (Lobster-01):** DONE (single canonical `deployment-support/lobster-01/` runtime directory)
*   ✅ **multi-source (QS + THE):** OPERATIONAL (2,191 THE universities matched)
*   ✅ **website product layer:** OPERATIONAL (rankings, detail, recommendation, compare, evidence, trust, country-aware filters, preview university page, `/agent`)

## Milestones & Development History
CrawlerNest's engineering depth is built on a history of rigorous milestones:

### Completed (Foundation & Infrastructure)
*   **Crawler Development:** Asynchronous pipeline, local parse parallelism, compliance-safe request pacing.
*   **Normalization:** Python baseline and C-prototype for high-performance string parsing.
*   **PostgreSQL Switch:** Transitioned to a robust PostgreSQL warehouse (the sole datastore).
*   **Production-Safe Pipeline:** Established Lobster-01 (node-ready deployment) with systemd scheduling, avoiding 403 blocks with decoupled cooldowns.
*   **Recommendation Engine:** Evolved from rule-based filters (v1) to grouped categories (v2), up to calibrated hybrid deterministic scoring (v3).

### In Progress (Platform Expansion)
*   Deepening the canonical university entity resolution.
*   Subject / special universe expansion.

### Future
*   Public API platform commercialization.
*   AI-driven insights overlaying the deterministic engine.

### Recent Product & Data Milestones
*   **2026-04-02:** Hardened QS production crawl with stable global entry resolution and snapshot fallback under upstream blocking.
*   **2026-04-03:** Switched aggregation ordering from score-led ranking to weighted rank-based aggregation truth.
*   **2026-04-04:** Added aggregation explainability, strict trust layer, explainable recommendation, and richer university detail evidence.
*   **2026-04-05:** Completed hydration-safe rankings refactor, compare page MVP, and end-to-end country filtering wired through the final Java rankings read query.
*   **2026-04-05:** Added a centralized canonical country normalization layer so alias inputs and metadata variants resolve to stable product-facing country filters.
*   **2026-04-14:** Completed the admission production workflow, deterministic admission entity resolution, and shared alias seeding / refresh loop.
*   **2026-04-15:** Completed ranking + admission convergence preview, canonical university detail preview, Java preview API, and the preview university page.
*   **2026-04-16:** Switched the rankings main API from demo-grade preview rows to the full ranking warehouse and aligned the frontend rankings browser semantics around total matches vs rows on the current page.
*   **2026-04-17:** Completed the explicit Web / Dev Agent split, Web Agent formatter boundary, generation layer (context / prompt / response generator), `/agent` normal/debug mode split, and memory debug upgrades including summary reporting and recent-entity carry-over.
*   **2026-04-18:** Formalized the mainline development order through architecture scope, data contracts, and do-not-auto-modify guardrails, recentering the project on admission crawl, normalization, canonical identity, warehouse, and recommendation correctness.
*   **2026-04-19:** Added correctness-first hardening across the prototype path: admission crawler host guards, extractor truncation and field validation, agent prompt untrusted-source guardrails, API request size caps, and anomaly visibility in resolution summaries / unresolved reports.

## AutoEval Extractor Milestone

CrawlerNest's extractor loop is now backed by a repeatable AutoEval workflow that can score a candidate extractor, surface concrete failure cases, and validate whether a refinement actually improves the output before it is kept.

### Improvement (Before -> After)

| Metric            | Before | After |
|------------------|--------|-------|
| score            | 0.13   | 0.95  |
| error_count      | 50+    | 0     |
| exact_match_rate | 0.05   | 1.00  |
| field_coverage   | 0.22   | 0.98  |
| retry_needed     | frequent | rare |

These figures are representative of the milestone outcome: the baseline extractor failed on most golden samples, while the refined version consistently matched the structured target output with near-complete field coverage.

### What This Means (Engineering Perspective)

This milestone is not just a parser tweak. It demonstrates a controlled optimization loop where the system can evaluate a candidate, modify the implementation, re-evaluate the result, and then keep or revert the change based on measurable output quality.

In practice, this makes data quality observable instead of subjective. Regression becomes detectable, improvement becomes testable, and the extractor path starts to behave like a self-improving engineering system rather than a one-off scraping script.

### How to Reproduce

Run the extractor evaluation directly:

```bash
python crawlernest/crawlernest-autoeval/runners/run_extractor_eval.py --no-log
```

If you are using the project virtual environment, the equivalent command is:

```bash
./.venv/bin/python crawlernest/crawlernest-autoeval/runners/run_extractor_eval.py --no-log
```

## Repository Map

The repo currently has two layers:

- outer workspace: docs, deployment assets, editor config, top-level project material
- inner platform workspace: [`crawlernest/`](crawlernest) containing the runnable pipeline, backend, schema, and frontend
