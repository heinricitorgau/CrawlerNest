# CrawlerNest Data Flow

This document traces global ranking and subject ranking data from source acquisition to frontend rendering.

## Global Ranking Flow

```text
QS/THE/ARWU source
      |
      v
crawler
      |
      v
source adapter
      |
      v
normalization
      |
      v
canonical resolution
      |
      v
warehouse.ranking_record
      |
      v
aggregation
      |
      v
analytics.aggregated_rankings
      |
      v
analytics.v_aggregated_rankings_latest
      |
      v
Spring Boot API
      |
      v
Next.js frontend
```

### 1. Source Acquisition

Ranking acquisition starts with source-specific crawlers and adapters.

- QS global and universe crawls are handled by the ranking crawler and `run` command.
- THE world ranking ingestion is available through `run-the-rankings`.
- ARWU ingestion support is available through `run-arwu-rankings` when source data exists.

Main entry points:

- `crawlernest/run_pipeline.py`
- `crawlernest_ranking_crawler/sources/qs.py`
- `crawlernest/crawlernest-core/multi_source/adapters/qs_adapter.py`
- `crawlernest/crawlernest-core/multi_source/adapters/the_adapter.py`
- `crawlernest/crawlernest-core/multi_source/adapters/arwu_adapter.py`

### 2. Normalization

Raw source rows are normalized into stable records before persistence. Normalization standardizes names, ranks, years, source identifiers, countries, and source-specific metadata.

Relevant paths:

- `crawlernest/pipeline/utils/normalization.py`
- `crawlernest/crawlernest-core/multi_source/types.py`
- `crawlernest/crawlernest-core/multi_source/integrator.py`

### 3. Canonical Resolution

Canonical resolution connects source university names to `warehouse.canonical_university` records. This keeps ranking, admission, subject, and recommendation data on the same canonical identity.

Resolution outputs and diagnostics can include:

- canonical links
- source mappings
- university aliases
- missing entity logs
- low-confidence matches

Relevant paths:

- `crawlernest/crawlernest-core/entity_resolution/`
- `crawlernest_ranking_crawler/entity_resolver.py`
- `crawlernest_admission_crawler/entity_resolver.py`

### 4. Ranking Records

Resolved ranking rows are written into:

```text
warehouse.ranking_record
warehouse.ranking_source
```

These tables preserve source-level evidence. They are the input evidence for aggregation, source comparison, and explainability.

### 5. Aggregation

Aggregation reads source ranking records and writes stored outputs.

```text
warehouse.ranking_record
      |
      v
RankingAggregator
      |
      v
analytics.aggregated_rankings
```

Stored aggregation output includes:

- source ranks
- normalized scores
- weights used
- composite score
- display rank
- coverage ratio
- aggregation method version

The explainability API reads these stored fields. It does not change the formula.

### 6. Analytics Views

The product read path uses:

```text
analytics.v_aggregated_rankings_latest
```

This view selects latest aggregated ranking rows by canonical university, year, universe, and method. It feeds rankings, recommendations, diagnostics, and source intelligence.

### 7. API

Spring Boot reads from warehouse and analytics tables.

Primary global ranking endpoints:

- `GET /api/v1/rankings`
- `GET /api/v1/rankings/{source}`
- `GET /api/v1/rankings/{id}/explain`
- `GET /api/v1/universities/{id}/source-comparison`

### 8. Frontend

Next.js renders pages and proxies API calls.

Global ranking UI paths:

- `/rankings`
- `/universities/[slug]`
- `/universities/[slug]/sources`
- `/data-quality`
- `/system-status`

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
canonical resolution
      |
      v
warehouse.subject_ranking_record
      |
      v
analytics.v_subject_rankings_latest
      |
      v
subject ranking API
      |
      v
Next.js subject ranking UI
```

Subject rankings are intentionally separate from global aggregation. They provide discipline-specific evidence without modifying global composite ranks.

Important paths:

- `crawlernest_ranking_crawler/subjects/`
- `crawlernest/scripts/smoke_subject_rankings.py`
- `crawlernest/servise_for_java/src/main/java/clawer/api/SubjectRankingController.java`
- `crawlernest/crawlernest-web/src/app/subject-rankings/page.tsx`

## Diagnostics Data Flow

```text
warehouse + analytics state
        |
        +--> HealthService
        +--> FreshnessService
        +--> DiagnosticsService
        +--> DataQualityService
        +--> SourceIntelligenceService
        |
        v
/api/v1/health
/api/v1/freshness
/api/v1/diagnostics/*
        |
        v
/system-status and /data-quality
```

Diagnostics use the same database state as product reads, which keeps operational signals aligned with user-visible data.

## Snapshot and Report Flow

```text
live database
      |
      v
scripts/export_system_snapshot.py
      |
      +--> snapshots/system_snapshot_*.json
      +--> snapshots/latest_status.json
      |
      v
scripts/build_failure_summary.py
      |
      v
reports or CI artifact
```

Snapshots are useful for handoff, CI summaries, and incident analysis when live services are not available.

## Related Documents

- [Architecture Overview](ARCHITECTURE_OVERVIEW.md)
- [Repository Map](REPOSITORY_MAP.md)
- [Operational Runbook](OPERATIONAL_RUNBOOK.md)
- [API Surface](API_SURFACE.md)
