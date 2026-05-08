# CrawlerNest Architecture Overview

This document maps the current CrawlerNest system as implemented in the repository. It focuses on how ranking data moves from crawlers into PostgreSQL, how analytics views feed APIs, and how operations and CI keep the platform observable.

## High-Level Architecture

```text
              +---------------------+
              | External sources    |
              | QS, THE, ARWU       |
              +----------+----------+
                         |
                         v
              +---------------------+
              | Python ingestion    |
              | crawlers + adapters |
              +----------+----------+
                         |
                         v
              +---------------------+
              | Normalization and   |
              | canonical matching  |
              +----------+----------+
                         |
                         v
              +---------------------+
              | PostgreSQL          |
              | warehouse schema    |
              +----------+----------+
                         |
                         v
              +---------------------+
              | Analytics schema    |
              | aggregations/views  |
              +----------+----------+
                         |
            +------------+-------------+
            |                          |
            v                          v
+----------------------+     +----------------------+
| Spring Boot API      |     | Autoeval/diagnostics |
| servise_for_java     |     | scripts + reports    |
+----------+-----------+     +----------+-----------+
           |                            |
           v                            v
+----------------------+     +----------------------+
| Next.js frontend     |     | snapshots/bundles    |
| crawlernest-web      |     | operations evidence  |
+----------------------+     +----------------------+
```

Core runtime split:

- Python owns crawling, normalization, canonical resolution, ingestion, aggregation writes, snapshots, and operational scripts.
- PostgreSQL owns durable warehouse records and analytics views.
- Spring Boot owns product API reads and operational API diagnostics.
- Next.js owns the web UI and server-side proxy routes.
- GitHub Actions and scripts own repeatable verification.

## Ingestion Pipeline

```text
QS/THE/ARWU crawler
      |
      v
source adapter
      |
      v
standardized ranking records
      |
      v
canonical university resolution
      |
      v
warehouse.ranking_record
      |
      v
analytics.aggregated_rankings
      |
      v
analytics.v_aggregated_rankings_latest
```

Main code paths:

- `crawlernest/run_pipeline.py`
- `crawlernest/crawlernest-core/multi_source/`
- `crawlernest/crawlernest-core/ranking_aggregation/`
- `crawlernest/db/analytics_bridge.py`
- `crawlernest/servise_for_java/src/main/java/clawer/api/RankingController.java`

The aggregation formula is owned by the ranking aggregation layer. API explainability reads existing stored aggregation output and does not recalculate or change ranking scores.

## Analytics Flow

```text
warehouse.ranking_record
      |
      v
RankingAggregator
      |
      v
analytics.aggregated_rankings
      |
      v
analytics.v_aggregated_rankings_latest
      |
      +--> rankings API
      +--> recommendation candidates
      +--> data quality diagnostics
      +--> cross-source explainability
```

Important analytics fields include:

- `display_rank`
- `composite_score`
- `coverage_ratio`
- `source_ranks_json`
- `source_normalized_scores_json`
- `source_weights_used_json`
- `aggregation_method_version`

These support rankings, confidence visibility, source comparison, and explainability without modifying the aggregation output.

## Subject Ranking Flow

```text
QS subject source
      |
      v
subject crawler
      |
      v
subject normalization
      |
      v
canonical university resolution
      |
      v
warehouse.subject_ranking_record
      |
      v
analytics.v_subject_rankings_latest
      |
      v
subject ranking API and UI
```

Subject rankings are a parallel read path. They do not feed the global ranking aggregation formula.

Key entry points:

- `python3 -m crawlernest.run_pipeline run-qs-subject`
- `crawlernest/servise_for_java/src/main/java/clawer/api/SubjectRankingController.java`
- `crawlernest/crawlernest-web/src/app/subject-rankings/page.tsx`

## Diagnostics Flow

```text
warehouse + analytics tables
        |
        v
Spring Boot diagnostic services
        |
        +--> /api/v1/health
        +--> /api/v1/freshness
        +--> /api/v1/diagnostics/rankings
        +--> /api/v1/diagnostics/subjects
        +--> /api/v1/diagnostics/data-quality
        +--> /api/v1/diagnostics/source-agreement
        |
        v
Next.js status/data-quality pages
```

Diagnostics cover:

- PostgreSQL connectivity and counts
- freshness and stale source detection
- ranking and subject API readiness
- unresolved canonical entities
- source drift and low-confidence matches
- source agreement, overlap, and disagreement outliers

## Operational Automation Flow

```text
operator or cron
      |
      v
scripts/run_daily_pipeline.sh
      |
      +--> ranking pipeline
      +--> subject ranking pipeline
      +--> smoke checks
      +--> autoeval diagnostics
      +--> scripts/export_system_snapshot.py
      +--> scripts/export_metadata_bundle.sh
      |
      v
logs/ + snapshots/ + reports/
```

The operational scripts create evidence that can be inspected without rerunning the full system:

- `snapshots/latest_status.json`
- `snapshots/system_snapshot_*.json`
- `reports/`
- `logs/daily_pipeline_*.log`

## CI/CD Flow

```text
push or pull request
      |
      +---------------------------+
      |                           |
      v                           v
release-smoke.yml          data-quality.yml
      |                           |
      v                           v
scripts/smoke_release.sh   fixture-mode data quality
      |                           |
      +--> Spring compile         +--> golden dataset checks
      +--> Next.js build          +--> ranking regression
      +--> Python syntax          +--> failure summary artifact
      +--> optional API curl
```

CI is intentionally split:

- Release smoke confirms the platform can compile/build and that Python entry points are syntactically valid.
- Data quality CI runs fixture-mode checks without requiring a live database.

## Related Documents

- [Repository Map](REPOSITORY_MAP.md)
- [Data Flow](DATA_FLOW.md)
- [Operational Runbook](OPERATIONAL_RUNBOOK.md)
- [API Surface](API_SURFACE.md)
- [CI Pipelines](CI_PIPELINES.md)
