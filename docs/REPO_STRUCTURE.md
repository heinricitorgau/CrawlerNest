# Repository Structure

CrawlerNest currently uses a two-level workspace:

- outer workspace: repo root for docs, deployment assets, editor settings
- inner product workspace: `crawlernest/` for the runnable data platform and backend code

This document is the low-risk structure map for the current repo. It does not rename or move core modules.

## Top Level

- `README.md`
  Project overview and current status.
- `docs/`
  Product and API documentation.
- `docs/foundation/`
  Core planning and architecture documents.
- `docs/assets/`
  Non-runtime reference assets such as sample payloads, robots snapshots, and images.
- `logs/`
  Local run logs.
- `lobster-01/`
  Node/runtime deployment assets.
- `.vscode/`
  Workspace editor settings.
- `crawlernest/`
  Main executable platform workspace.

## Main Platform Workspace

All active code paths currently live under `crawlernest/`.

### Runtime Entrypoints

- `crawlernest/run_pipeline.py`
  Main Python data pipeline entrypoint.
- `crawlernest/run_platform.py`
  Platform orchestration entrypoint.
- `crawlernest/verify_db.py`
  DB verification helper.

### Python Platform Modules

- `crawlernest/crawlernest-core/`
  Shared Python domain logic:
  normalization, entity resolution, recommendation engine, multi-source ingestion, aggregation.
- `crawlernest/crawlernest-extractors/`
  Crawling and fetch/extract adapters.
- `crawlernest/crawlernest-jobs/`
  Crawl job orchestration and QS universe runners.
- `crawlernest/crawlernest-db-writer/`
  Database write adapters.
- `crawlernest/crawlernest-analytics/`
  Analytics/export utilities.
- `crawlernest/crawlernest-schema/`
  SQL schema and read-model definitions.
- `crawlernest/crawlernest-tests/`
  Python tests for pipeline and ingestion invariants.

### Product / API Layers

- `crawlernest/servise_for_java/`
  Spring Boot API layer.
  Note: directory name is legacy-spelled and should be renamed only in a dedicated migration.
- `crawlernest/crawlernest-web/`
  Next.js frontend product.

### Knowledge / Data Artifacts

- `crawlernest/crawlernest-kb/`
  Snapshots, universe artifacts, resolution cache, local knowledge outputs.

### Supporting / Legacy / Secondary Areas

- `crawlernest/scripts/`
  Maintenance, migration, smoke-test, and bootstrap scripts.
- `crawlernest/crawlernest-api/`
  Older API-side material not used as the primary product backend.
- `crawlernest/crawlernest-recommendation/`
  Legacy or sidecar recommendation material.
- `crawlernest/crawlernest-normalization/`
  Older normalization implementation and experiments.
- `crawlernest/crawlernest-normalization-py/`
  Python normalization-side material.
- `crawlernest/crawlernest-cli/`
  CLI-side UX utilities.
- `crawlernest/crawlernest-docs/`
  Legacy internal documentation mirror.
- `crawlernest/crawlernest-samples/`
  Example/sample datasets.
- `crawlernest/crawlernest-infra/`
  Infrastructure-side notes and assets.
- `crawlernest/crawlernest-autoeval/`
  Evaluation harness and reports.

## Current Canonical Working Paths

When working on the active product, these are the most important paths:

- Data pipeline: `crawlernest/run_pipeline.py`
- Python core: `crawlernest/crawlernest-core/`
- SQL schema: `crawlernest/crawlernest-schema/`
- Java API: `crawlernest/servise_for_java/`
- Frontend: `crawlernest/crawlernest-web/`

## Known Structural Debt

- The repo has an outer workspace and an inner executable workspace, which is functional but visually confusing.
- `servise_for_java/` is misspelled but should only be renamed with a controlled migration.
- Some legacy/secondary directories still live beside active platform modules.
- Local build/cache directories exist inside the repo and should be ignored rather than moved ad hoc.

## Recommended Future Cleanup Order

1. Keep current paths stable while platform behavior is still changing quickly.
2. Consolidate legacy/secondary directories only after confirming they are not on active runtime paths.
3. Rename `servise_for_java/` only with a dedicated path migration.
4. Consider flattening the outer/inner workspace split only as a separate structural project.
