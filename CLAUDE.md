# CLAUDE.md

CrawlerNest — a university ranking data platform. Python crawlers ingest ranking
sources (currently QS only) into a PostgreSQL warehouse, a Spring Boot API serves
read-only aggregated data, and a Next.js frontend displays it.

Development happens on Linux/WSL. All commands below assume a POSIX shell at the
repo root.

## Naming traps (read first)

These names are historical and misspelled. They are load-bearing — do not "fix"
them without a coordinated rename, and remember them when searching:

- `crawlernest/servise_for_java/` — the main Spring Boot API service ("servise" is a typo, kept).
- Java root package is `clawer` (not `crawler`). Grepping for "crawler" will miss all Java code.
- The PostgreSQL database is named `clawer` (user `test`, password `test`, localhost:5432).

## Live code vs. stale duplicates

- **`crawlernest_ranking_crawler/` at the repo root (underscores) is the live
  ranking pipeline package.** It is what `crawlernest/run_pipeline.py` imports.
- `crawlernest/crawlernest-ranking-crawler/` (hyphens) is a diverged copy that no
  Python code imports. Do not edit it expecting runtime effect, even though
  `docs/REPOSITORY_MAP.md` points there.
- Same pattern applies to root `crawlernest_admission_crawler/` and
  `crawlernest_crawler_core/` — verify imports before choosing where to edit.
- Build artifacts are unfortunately tracked in git (`__pycache__/`, `*.pyc`,
  `crawlernest/clawer.db`, `*.db.bak`). Never edit or read these as source.
- Some docs exist in two copies (e.g. `docs/demo/DEMO_SCRIPT_v0.1.md` and
  `releases/v0.1-demo/DEMO_SCRIPT_v0.1.md`). Update both or note the divergence.

## Architecture

```
Python pipeline (crawlernest/run_pipeline.py + crawlernest_ranking_crawler/)
  → PostgreSQL: staging → warehouse.canonical_university → analytics.aggregated_rankings
    (one row per university per year per aggregation_run; source_ranks_json holds
     {"QS": rank, "THE": null, "ARWU": null} — missing sources are null-valued keys)
  → Spring Boot read API  crawlernest/servise_for_java/   (port 8080, package clawer.*)
  → Next.js web           crawlernest/crawlernest-web/    (port 3000, proxies /api/* to 8080)
  → Agent API                                             (port 8090)
```

Core aggregation logic lives in `crawlernest/crawlernest-core/ranking_aggregation/`
(weights, composite score, coverage ratio). Schema DDL is in
`crawlernest/crawlernest-schema/`.

## Commands

```bash
# One-time setup
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python3 -m crawlernest.run_pipeline bootstrap-postgres --pg-user test --pg-password test --pg-database clawer

# Load ranking data
./.venv/bin/python -m crawlernest.run_pipeline run --limit 20 --ranking-year 2026 \
  --pg-user test --pg-password test --pg-database clawer

# Start everything (PostgreSQL + API + web)
./scripts/start_localhost.sh

# Individual services
cd crawlernest/servise_for_java && ./mvnw -Dmaven.test.skip=true spring-boot:run
cd crawlernest/crawlernest-web && npm run dev

# Verify a Java change compiles
cd crawlernest/servise_for_java && ./mvnw -q compile

# Python tests (adds crawlernest/crawlernest-* module dirs to sys.path)
python3 crawlernest/crawlernest-tests/run_tests.py

# Smoke check the running stack
./scripts/smoke_local_stack.sh
```

CI: `.github/workflows/release-smoke.yml` (full-stack smoke, includes Java build)
and `data-quality.yml` (fixture-mode checks, Python syntax). The full Python test
suite in `crawlernest/crawlernest-tests/` does not run in CI — run it locally.

## Behavioral policies that constrain changes

- **Analytics endpoints are strictly read-only.** No mutations, no pipeline
  triggers from the API layer.
- **Every analytics response must include a `caveats` array** disclosing data
  limitations. This is an explicit honesty contract — see
  `docs/analytics/ANALYTICS_EXPLAINABILITY.md`. Never remove or soften caveats
  to make output look better.
- **No black-box scores.** Confidence is derived mechanically from source count
  (3 sources = high, 2 = medium, 1 = low). Do not set confidence manually.
- Caveat strings are currently hardcoded in two places —
  `clawer/service/AnalyticsService.java` and `clawer/api/AnalyticsController.java` —
  and mirrored in the explainability doc. A change to one usually requires
  changing all three.
- Only the QS source is implemented (`crawlernest_ranking_crawler/sources/qs.py`).
  THE and ARWU appear throughout schemas and configs as planned sources with
  null data; code must handle their absence.

## Key docs

- `docs/GETTING_STARTED.md` — canonical setup steps and troubleshooting
- `docs/ARCHITECTURE_OVERVIEW.md`, `docs/DATA_FLOW.md`, `docs/API_SURFACE.md`
- `docs/REPOSITORY_MAP.md` — directory guide (but see the stale-duplicate warning above)
- `crawlernest/crawlernest-web/CLAUDE.md` and
  `crawlernest/crawlernest-mini-agent/CLAUDE.md` — subproject-specific guidance

## Debugging order

Data problems are almost always upstream of the UI. When something looks wrong
on a page, check in this order: warehouse/analytics tables → Java API response
(`curl localhost:8080/api/v1/...`) → Next.js proxy route → React component.
