# CrawlerNest

Traditional Chinese version: [README.zh-TW.md](README.zh-TW.md)

CrawlerNest is an end-to-end university data infrastructure and web platform. It turns fragmented ranking and admissions data into structured warehouse records, canonical university identity, explainable ranking evidence, and product-facing decision support.

The current mainline is correctness-first:

```text
crawl -> extract -> normalize -> write -> warehouse -> API -> web
```

Agent and AutoEval capabilities exist, but they are development-support systems. They do not own production truth.

## Current Status

As of April 2026, CrawlerNest is best understood as a three-zone system:

- **Active data pipeline:** QS / THE / ARWU ranking ingestion, admission pilot ingestion, normalization, warehouse writes, deterministic entity resolution, API, and web product.
- **Controlled expansion:** admission enrichment, multi-universe aggregation, comparison, and basic explainable recommendation.
- **Development support:** Python agent runtime, Web Agent / Dev Agent split, mini-agent runtime, and AutoEval-assisted extractor improvement.

CrawlerNest is also expected to evolve alongside a sibling development-support repository:

```text
../crawlernest-agents
```

That repository contains a small CrawlerNest-specific AI-assisted development system: repo onboarding, code review, data pipeline engineering, PostgreSQL tuning, workflow architecture, debugging/reliability, and technical writing agents. It is a companion engineering workflow repo, not a production runtime and not a source of production truth.

The engineering order is intentionally strict:

1. stabilize crawl and extraction
2. stabilize normalization and canonical mapping
3. formalize warehouse and API contracts
4. build admission-aware recommendation
5. expand agent autonomy only after the data path is reliable

## Product Surfaces

The website currently includes:

- rankings browser
- university detail pages
- recommendation flow
- compare page
- preview university page
- web-facing `/agent` page with deterministic fallback behavior

The backend API currently serves:

- rankings and ranking evidence
- university detail
- admissions context
- recommendations
- comparison data
- canonical university preview data

## Decision Product Layer

CrawlerNest's recommendation surface is now a decision product rather than a raw score list. The recommendation engine still keeps scoring, filtering, and ranking deterministic, but the product layer adds concise explanation surfaces around the decision:

- `decisionOutput` explains the recommended action for an individual university.
- `applicationPlans` compare balanced, conservative, and aggressive application strategies.
- `decisionSummary` exports a structured decision record.
- `decisionSummaryCompact` provides a one-line product snapshot for UI, assistant reply, and text export.
- `admissionResolved` exposes admission requirement trust metadata without changing recommendation logic.

Admission data is intentionally treated as signals, not absolute facts. The current trust path is:

```text
raw extraction
  -> AdmissionSignal
  -> validation
  -> resolved admission field
  -> recommendation metadata
  -> decision messaging / UI / export
```

This layer is conservative by design:

- conflicting requirement signals stay visible
- low-confidence requirement signals are called out in decision messaging
- consistent high-confidence signals improve explanation clarity
- no admission trust metadata changes scoring, ranking, or filtering

In the web product, this appears as compact admission signal badges, a decision summary banner, assistant summary text, and exportable decision snapshots.

## Repository Layout

CrawlerNest uses an outer repository plus an inner product workspace.

```text
repo-root/
├── README.md / README.zh-TW.md
├── docs/
├── crawlernest/                       # canonical product workspace
├── crawlernest-samples/               # outer sample artifacts
├── deployment-support/
├── legacy/
└── docker-compose.postgres.yml
```

Important paths inside `crawlernest/`:

```text
crawlernest/run_pipeline.py            # main Python pipeline entrypoint
crawlernest/run_platform.py            # modular platform bootstrap
crawlernest/pipeline/                  # command routing and pipeline stages
crawlernest/crawlernest-ranking-crawler/
crawlernest/crawlernest-admission-crawler/
crawlernest/crawlernest-crawler-core/  # shared crawler runtime primitives
crawlernest/crawlernest-core/          # domain engines
crawlernest/crawlernest-schema/        # PostgreSQL / SQLite schema assets
crawlernest/servise_for_java/          # Spring Boot API; historical spelling
crawlernest/crawlernest-web/           # Next.js frontend
crawlernest/agent/                     # development-support agent runtime
crawlernest/crawlernest-mini-agent/    # standalone mini-agent runtime
crawlernest/crawlernest-autoeval/      # extractor evaluation workflow
```

For the full map, see [Repository Structure](docs/architecture/REPO_STRUCTURE.md).

## Architecture

The canonical architecture document is:

- [System And Engine Architecture](docs/architecture/SYSTEM_ENGINE_ARCHITECTURE.md)

The current production-oriented path is:

```text
External Sources
  -> ranking / admission crawlers
  -> extraction
  -> normalization
  -> staging validation
  -> warehouse landing
  -> deterministic entity resolution
  -> aggregation / read models
  -> Spring Boot API
  -> Next.js web product
```

Crawler boundaries are intentional:

- `crawlernest-crawler-core/` contains reusable runtime primitives such as HTTP, retry, rate limiting, logging, and snapshot helpers.
- `crawlernest-ranking-crawler/` owns QS / THE / ARWU ranking-source extraction and ranking-specific crawl policy.
- `crawlernest-admission-crawler/` owns university-site discovery, admission extraction, site profiles, and admission-specific crawl policy.

## Data Visibility Model

API-visible ranking rows come through the warehouse and canonical identity chain:

1. crawlers collect raw university, ranking, and admission facts
2. normalization prepares source records
3. staging validators reject invalid or suspicious rows
4. `warehouse.ranking_record` stores universe-aware ranking truth
5. canonical identity links raw entities to `canonical_university`
6. aggregation runs produce product read models such as `analytics.v_aggregated_rankings_latest`
7. Spring Boot joins ranking truth with canonical metadata
8. Next.js reads through same-origin API routes

Data that exists only in raw or staging tables is not automatically product-visible. Missing API rows usually require canonical linking, backfill, or aggregation refresh.

For the QS legacy path, `run_pipeline.py run` still writes the backward-compatible `warehouse.rankings` table first. After that write commits, the pipeline automatically runs the native analytics bridge:

```text
warehouse.rankings
  -> warehouse.ranking_source
  -> warehouse.canonical_university
  -> warehouse.canonical_university_link
  -> warehouse.ranking_record
  -> analytics.aggregation_runs
  -> analytics.aggregated_rankings
  -> analytics.v_aggregated_rankings_latest
```

The bridge is idempotent and safe to rerun. A QS live HTTP 403 is not treated as a pipeline failure when the fallback snapshot succeeds; the fallback rows continue through the same legacy write and analytics sync path.

## Setup

### Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Most pipeline commands should be run in module mode:

```bash
./.venv/bin/python -m crawlernest.run_pipeline <command>
```

This ensures the Python package import path is correct.

### PostgreSQL

The default local database expected by the pipeline and Java API is:

```text
database: clawer
user: test
host: localhost
port: 5432
```

If needed, start the local helper service:

```bash
docker compose -f docker-compose.postgres.yml up -d
```

## Run The Web Platform

Use two terminals.

### 1. Start The Spring Boot API

```bash
cd crawlernest/servise_for_java
./mvnw -q -DskipTests compile
./mvnw spring-boot:run
```

The API runs on:

```text
http://localhost:8080
```

Useful focused backend tests:

```bash
cd crawlernest/servise_for_java
./mvnw -q -Dtest=CountryNormalizationTest test
./mvnw -q -Dtest=RankingApiIntegrationTest test
./mvnw -q -Dtest=RecommendationControllerTest test
```

### 2. Start The Next.js Frontend

```bash
cd crawlernest/crawlernest-web
npm install
npm run dev
```

The app runs on:

```text
http://localhost:3000
```

The frontend proxies product API calls through same-origin Next.js routes such as `/api/rankings`, `/api/recommendations`, `/api/compare`, and `/api/university-preview`.

## Run The Data Pipeline

### Production-Safe Daily Run

```bash
bash crawlernest/scripts/run_production_safe.sh
```

Resume after an interruption:

```bash
bash crawlernest/scripts/run_production_safe.sh 2500 --resume
```

The production-safe runner prefers `.venv`, uses conservative request pacing, writes completed passes to PostgreSQL, and continues through non-critical stage failures where safe.

### Common Manual Commands

Run QS global crawl and write:

```bash
./.venv/bin/python crawlernest/run_pipeline.py run --limit 2500 --ranking-year 2026 --pg-user test --pg-database clawer
```

This command writes legacy `warehouse.rankings`, syncs analytics-native ranking tables, verifies `analytics.v_aggregated_rankings_latest`, and only prints `Done` after the product rankings view has rows.

Run all QS configured universes:

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-qs-universes --ranking-year 2026 --limit 2500 --pg-user test --pg-database clawer
```

Run one QS region:

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-qs-region --region europe --ranking-year 2026 --limit 2500 --pg-user test --pg-database clawer
```

Run THE rankings:

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-the-rankings --pg-user test --pg-database clawer
```

Run ARWU rankings:

```bash
./.venv/bin/python crawlernest/run_pipeline.py run-arwu-rankings --pg-user test --pg-database clawer
```

Generate recommendation output from the v3 engine:

```bash
./.venv/bin/python crawlernest/run_pipeline.py recommend-v3 --country "United Kingdom" --ielts 6.5 --target-rank 100
```

Compare universities:

```bash
./.venv/bin/python crawlernest/run_pipeline.py compare --a "University of Oxford" --b "University of Cambridge"
```

To inspect the complete command list:

```bash
./.venv/bin/python crawlernest/run_pipeline.py --help
```

## Validation And Repair

Validate aggregation output:

```bash
./.venv/bin/python crawlernest/scripts/validate_aggregation.py --year 2026 --universe-type global --universe-key global
```

Smoke test the legacy-to-analytics bridge and product API:

```bash
./.venv/bin/python crawlernest/scripts/smoke_analytics_bridge.py --year 2026
```

The smoke test reruns the bridge twice, verifies `warehouse.ranking_record`, verifies `analytics.v_aggregated_rankings_latest`, and checks `/api/v1/rankings` returns items. Start the Spring Boot API first if you want the API check to pass.

Recover canonical universities from existing warehouse universities:

```bash
./.venv/bin/python crawlernest/run_pipeline.py seed-canonical --pg-user test --pg-database clawer
./.venv/bin/python crawlernest/run_pipeline.py backfill-ranking-records --pg-user test --pg-database clawer
```

Recover source-only unresolved entities, such as THE rows:

```bash
./.venv/bin/python crawlernest/run_pipeline.py seed-canonical-from-missing --pg-user test --pg-database clawer
```

Refresh ranking resolution:

```bash
./.venv/bin/python crawlernest/run_pipeline.py refresh-ranking-resolution --pg-user test --pg-database clawer
```

Refresh admission resolution:

```bash
./.venv/bin/python crawlernest/run_pipeline.py refresh-admission-resolution --pg-user test --pg-database clawer
```

Legacy/dev SQL fallback for the old manual bridge flow:

```bash
psql -U test -d clawer -f scripts/bridge_legacy_rankings_to_analytics.sql
psql -U test -d clawer -f scripts/ai-dev/bridge_legacy_rankings_to_analytics.sql
```

## Testing

Python focused tests:

```bash
python -m pytest crawlernest/crawlernest-tests
```

Admission trust and decision-product focused tests:

```bash
python -m pytest test_admission_signals.py test_admission_resolver.py crawlernest/crawlernest-tests/test_recommendation_engine.py
```

Frontend tests:

```bash
cd crawlernest/crawlernest-web
npm test
```

Recommendation UI / export focused tests:

```bash
cd crawlernest/crawlernest-web
npm test -- AdmissionSignalBadge.test.tsx RecommendationPageExport.test.tsx
```

Frontend build:

```bash
cd crawlernest/crawlernest-web
npm run build
```

AutoEval extractor evaluation:

```bash
./.venv/bin/python crawlernest/crawlernest-autoeval/runners/run_extractor_eval.py --no-log
```

## Engineering Guardrails

Read these before changing mainline behavior:

- [Architecture Scope](docs/foundation/ARCHITECTURE_SCOPE.md)
- [Data Contracts](docs/foundation/DATA_CONTRACTS.md)
- [Module Ownership](docs/foundation/MODULE_OWNERSHIP.md)
- [Development Workflow](docs/foundation/DEV_WORKFLOW.md)
- [Do Not Auto Modify](docs/foundation/DO_NOT_AUTO_MODIFY.md)
- [Testing Guide](docs/foundation/TESTING_GUIDE.md)
- [Whitepaper](docs/foundation/Whitepaper.md)

The short version:

- keep production truth deterministic
- make contracts explicit before wiring frontend behavior
- do not put business logic into `crawlernest-crawler-core/`
- treat agent output as assistance, not authority
- validate ingestion before product visibility
- avoid skipping canonical identity and warehouse contracts
