# CrawlerNest Repository Map

This document explains the major directories in the repository and what to inspect first when onboarding or debugging.

## Top-Level Map

```text
.
+-- crawlernest/
+-- crawlernest-samples/
+-- docs/
+-- scripts/
+-- snapshots/
+-- reports/
+-- backups/
+-- .github/workflows/
+-- deployment-support/
+-- legacy/
```

## Core Directories

### `crawlernest/`

Main application and data platform workspace. It contains Python pipeline code, Java API service, Next.js web app, schemas, autoeval datasets, and operational helpers.

Important subdirectories:

- `crawlernest/run_pipeline.py`: primary Python CLI for bootstrap, ingestion, aggregation, subject ranking, and maintenance tasks.
- `crawlernest/crawlernest-core/`: core Python packages for multi-source ingestion, ranking aggregation, entity resolution, comparison, and recommendation logic.
- `crawlernest/crawlernest-ranking-crawler/`: ranking crawler components and source-specific extractors.
- `crawlernest/crawlernest-admission-crawler/`: admission crawler and extraction support.
- `crawlernest/crawlernest-schema/`: PostgreSQL schema definitions for warehouse, analytics, recommendation, and ranking support.
- `crawlernest/db/`: analytics bridge helpers used to sync and backfill database outputs.
- `crawlernest/scripts/`: CrawlerNest-specific utility scripts.

### `crawlernest/crawlernest-web/`

Next.js frontend. It contains user-facing pages, API proxy routes, React components, hooks, and frontend types.

Key paths:

- `src/app/rankings/`: global rankings UI.
- `src/app/subject-rankings/`: subject rankings UI.
- `src/app/universities/[slug]/`: university detail pages.
- `src/app/universities/[slug]/sources/`: source comparison and explainability page.
- `src/app/data-quality/`: data quality and source agreement dashboard.
- `src/app/system-status/`: operational status UI.
- `src/app/api/`: Next.js proxy routes to the Spring Boot API.

### `crawlernest/servise_for_java/`

Spring Boot API service. The directory name is historical. It is the main product API read layer.

Key paths:

- `src/main/java/clawer/api/`: controllers and endpoint surface.
- `src/main/java/clawer/service/`: business and diagnostic services.
- `src/main/java/clawer/repository/`: JDBC/JPA read adapters.
- `src/test/java/clawer/`: API, service, and integration tests.
- `src/test/resources/sql/`: integration-test database fixtures.
- `src/main/resources/application.properties`: local datasource configuration.

### `crawlernest/crawlernest-autoeval/`

Evaluation and diagnostics workspace. It supports fixture-mode CI, local regression checks, canonical diagnostics, source drift analysis, and report generation.

Key paths:

- `datasets/`: golden data and CI fixtures.
- `runners/`: Python runners for ranking regression, subject evaluation, canonical diagnostics, and source drift.
- `reports/`: generated autoeval outputs.
- `sandbox/`: isolated experimentation and auto-loop assets.

### `scripts/`

Repository-level operational scripts. These are the preferred entry points for local service startup, smoke checks, daily operations, snapshots, and failure summaries.

Important scripts:

- `scripts/start_localhost.sh`
- `scripts/smoke_local_stack.sh`
- `scripts/smoke_release.sh`
- `scripts/run_daily_pipeline.sh`
- `scripts/export_system_snapshot.py`
- `scripts/export_metadata_bundle.sh`
- `scripts/build_failure_summary.py`
- `scripts/run_ci_locally.sh`

### `snapshots/`

Operational snapshot output directory. Typical files include:

- `latest_status.json`
- `system_snapshot_YYYYMMDD_HHMMSS.json`

Snapshots summarize health, freshness, drift warnings, regression status, and table counts for handoff or incident review.

### `reports/`

Generated human-readable reports. This directory is used by diagnostics and CI support scripts, including failure summaries and autoeval artifacts.

### `backups/`

Local backup output area. Use this for manual database exports or operational backup files. Do not treat it as a source-of-truth schema location.

## Supporting Directories

### `docs/`

Project documentation. New architecture, data flow, runbook, repository map, and API surface docs live here.

### `.github/workflows/`

CI definitions:

- `release-smoke.yml`: compile/build/syntax smoke workflow.
- `data-quality.yml`: fixture-mode data quality workflow.

### `crawlernest-samples/`

Sample data used for local development, previews, and crawler/export demonstrations.

### `deployment-support/`

Deployment notes and node-specific operational files, including Lobster host support.

### `legacy/`

Historical code retained for reference. Prefer current paths under `crawlernest/`, `scripts/`, and `docs/` for active development.

## Where To Start

```text
Need to ingest data?       -> crawlernest/run_pipeline.py
Need API behavior?         -> crawlernest/servise_for_java/src/main/java/clawer/api/
Need web behavior?         -> crawlernest/crawlernest-web/src/app/
Need ranking formula?      -> crawlernest/crawlernest-core/ranking_aggregation/
Need schema/view details?  -> crawlernest/crawlernest-schema/
Need diagnostics?          -> scripts/ and crawlernest/crawlernest-autoeval/
Need CI status?            -> .github/workflows/
```

## Related Documents

- [Architecture Overview](ARCHITECTURE_OVERVIEW.md)
- [Data Flow](DATA_FLOW.md)
- [Operational Runbook](OPERATIONAL_RUNBOOK.md)
- [API Surface](API_SURFACE.md)
