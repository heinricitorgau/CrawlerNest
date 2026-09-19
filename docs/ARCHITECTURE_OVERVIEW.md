# CrawlerNest Architecture Overview

This document maps the current CrawlerNest system as implemented in the repository. It focuses on how ranking data moves from crawlers into PostgreSQL, how analytics views feed APIs, and how operations and CI keep the platform observable.

## High-Level Architecture

```mermaid
flowchart TB
    sources["External sources<br/>QS / THE / ARWU"]
    ingestion["Python ingestion<br/>crawlers + adapters"]
    matching["Normalization<br/>canonical matching"]
    warehouse[("PostgreSQL<br/>warehouse schema")]
    analytics[("Analytics schema<br/>aggregations / views")]
    api["Spring Boot API<br/>servise_for_java"]
    frontend["Next.js frontend<br/>crawlernest-web"]
    diagnostics["Autoeval / diagnostics<br/>scripts + reports"]
    evidence["Snapshots / bundles<br/>operations evidence"]

    sources --> ingestion --> matching --> warehouse --> analytics
    analytics --> api --> frontend
    analytics --> diagnostics --> evidence
```

Core runtime split:

- Python owns crawling, normalization, canonical resolution, ingestion, aggregation writes, snapshots, and operational scripts.
- PostgreSQL owns durable warehouse records and analytics views.
- Spring Boot owns product API reads and operational API diagnostics.
- Next.js owns the web UI and server-side proxy routes.
- GitHub Actions and scripts own repeatable verification.

## Ingestion Pipeline

```mermaid
flowchart TB
    crawler["QS / THE / ARWU crawler"]
    adapter["Source adapter"]
    standardized["Standardized ranking records"]
    canonical["Canonical university resolution"]
    rankingRecord[("warehouse.ranking_record")]
    aggregated[("analytics.aggregated_rankings")]
    latest[("analytics.v_aggregated_rankings_latest")]

    crawler --> adapter --> standardized --> canonical --> rankingRecord --> aggregated --> latest
```

Main code paths:

- `crawlernest/run_pipeline.py`
- `crawlernest/crawlernest-core/multi_source/`
- `crawlernest/crawlernest-core/ranking_aggregation/`
- `crawlernest/db/analytics_bridge.py`
- `crawlernest/servise_for_java/src/main/java/clawer/api/RankingController.java`

The aggregation formula is owned by the ranking aggregation layer. API explainability reads existing stored aggregation output and does not recalculate or change ranking scores.

## Analytics Flow

```mermaid
flowchart TB
    rankingRecord[("warehouse.ranking_record")]
    aggregator["RankingAggregator"]
    aggregated[("analytics.aggregated_rankings")]
    latest[("analytics.v_aggregated_rankings_latest")]
    rankingsApi["Rankings API"]
    recommendations["Recommendation candidates"]
    quality["Data quality diagnostics"]
    explainability["Cross-source explainability"]

    rankingRecord --> aggregator --> aggregated --> latest
    latest --> rankingsApi
    latest --> recommendations
    latest --> quality
    latest --> explainability
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

```mermaid
flowchart TB
    source["QS subject source"]
    crawler["Subject crawler"]
    normalization["Subject normalization"]
    canonical["Canonical university resolution"]
    record[("warehouse.subject_ranking_record")]
    latest[("analytics.v_subject_rankings_latest")]
    product["Subject ranking API and UI"]

    source --> crawler --> normalization --> canonical --> record --> latest --> product
```

Subject rankings are a parallel read path. They do not feed the global ranking aggregation formula.

Key entry points:

- `python3 -m crawlernest.run_pipeline run-qs-subject`
- `crawlernest/servise_for_java/src/main/java/clawer/api/SubjectRankingController.java`
- `crawlernest/crawlernest-web/src/app/subject-rankings/page.tsx`

## Diagnostics Flow

```mermaid
flowchart TB
    tables[("Warehouse + analytics tables")]
    services["Spring Boot diagnostic services"]
    health["/api/v1/health"]
    freshness["/api/v1/freshness"]
    rankings["/api/v1/diagnostics/rankings"]
    subjects["/api/v1/diagnostics/subjects"]
    quality["/api/v1/diagnostics/data-quality"]
    agreement["/api/v1/diagnostics/source-agreement"]
    pages["Next.js status / data-quality pages"]

    tables --> services
    services --> health
    services --> freshness
    services --> rankings
    services --> subjects
    services --> quality
    services --> agreement
    services --> pages
```

Diagnostics cover:

- PostgreSQL connectivity and counts
- freshness and stale source detection
- ranking and subject API readiness
- unresolved canonical entities
- source drift and low-confidence matches
- source agreement, overlap, and disagreement outliers

## Operational Automation Flow

```mermaid
flowchart TB
    trigger["Operator or cron"]
    daily["scripts/run_daily_pipeline.sh"]
    ranking["Ranking pipeline"]
    subject["Subject ranking pipeline"]
    smoke["Smoke checks"]
    autoeval["Autoeval diagnostics"]
    snapshot["scripts/export_system_snapshot.py"]
    bundle["scripts/export_metadata_bundle.sh"]
    evidence["logs/ + snapshots/ + reports/"]

    trigger --> daily
    daily --> ranking --> evidence
    daily --> subject --> evidence
    daily --> smoke --> evidence
    daily --> autoeval --> evidence
    daily --> snapshot --> evidence
    daily --> bundle --> evidence
```

The operational scripts create evidence that can be inspected without rerunning the full system:

- `snapshots/latest_status.json`
- `snapshots/system_snapshot_*.json`
- `reports/`
- `logs/daily_pipeline_*.log`

## CI/CD Flow

```mermaid
flowchart TB
    change["Push or pull request"]
    release["release-smoke.yml"]
    quality["data-quality.yml"]
    smoke["scripts/smoke_release.sh"]
    fixture["Fixture-mode data quality"]
    spring["Spring compile"]
    next["Next.js build"]
    python["Python syntax"]
    curl["Optional API curl"]
    golden["Golden dataset checks"]
    regression["Ranking regression"]
    artifact["Failure summary artifact"]

    change --> release
    change --> quality
    release --> smoke
    smoke --> spring
    smoke --> next
    smoke --> python
    smoke --> curl
    quality --> fixture
    fixture --> golden
    fixture --> regression
    fixture --> artifact
```

CI is intentionally split:

- Release smoke confirms the platform can compile/build and that Python entry points are syntactically valid.
- Data quality CI runs fixture-mode checks without requiring a live database.

## Minimal Identity Layer

CrawlerNest includes a minimal token-based identity and user-owned persistence layer. It is deliberately thin: a signed cookie, a filter chain, and per-user tables.

```mermaid
flowchart TB
    browser["Browser"]
    nextjs["Next.js proxy<br/>crawlernest-web"]
    spring["Spring Boot<br/>AuthController + UserController"]
    filter["JwtCookieAuthenticationFilter<br/>+ SecurityConfig"]
    pg[("PostgreSQL<br/>warehouse.app_user<br/>warehouse.saved_university<br/>warehouse.saved_recommendation")]

    browser -- "HttpOnly crawlernest_token cookie" --> nextjs
    nextjs -- "Cookie header forwarded" --> spring
    spring -- "verify signature, no stored state" --> filter
    spring -- "WHERE user_id = ? (from token claims)" --> pg
```

### Token Model

- **Engine:** HS256 JWT issued and verified by `clawer.auth.jwt.JwtService`. Stateless: no session store, no Redis, nothing per-user held in the JVM.
- **Cookie:** `crawlernest_token`, `HttpOnly=true`, `SameSite=Strict`, `Path=/`. `Secure` follows `CRAWLERNEST_JWT_COOKIE_SECURE` (off by default for plain-http local runs).
- **Lifetime:** `crawlernest.jwt.ttl`, default 12 hours, fixed at issue — no sliding renewal, and no revocation before expiry.
- **Secret:** `CRAWLERNEST_JWT_SECRET`, at least 32 bytes. Unset, a random key is generated per process and logged as a warning; nothing ships with a default key.
- **Restart behavior:** Transparent when the secret is configured. With an ephemeral key, a restart signs everyone out.
- **Claims:** `sub` (user id) and `email`. Nothing else, and nothing the client can choose.

### User-Owned Persistence

| Table | Schema | Purpose |
|---|---|---|
| `app_user` | `warehouse` | Accounts: `id`, `email`, `password_hash` (BCrypt), `created_at` |
| `saved_university` | `warehouse` | Per-user saved ranking entries with `canonical_university_id` FK |
| `saved_recommendation` | `warehouse` | Per-user recommendation snapshots: `title`, `request_json` (JSONB), `result_json` (JSONB) |

Tables are created idempotently on `ApplicationReadyEvent` via `AuthSchemaInitializer` (`CREATE TABLE IF NOT EXISTS`).

### Current Auth Boundaries

This layer **provides:**
- Account registration with BCrypt password hashing.
- An http-only, SameSite=Strict token cookie no script can read and no other site can send.
- A Spring Security filter chain that closes `/api/v1/user/**` and `/api/v1/admin/**` while the read-only analytics API stays public.
- User-isolation enforcement: all data queries include `WHERE user_id = ?` from the verified token only.
- 404 (not 403) for cross-user record access, to avoid confirming record existence.

This layer **does not provide** (explicit non-goals for the current scope):
- No RBAC or role management.
- No OAuth or third-party identity providers.
- No refresh tokens, and no revocation before expiry (rotating the secret invalidates everything at once).
- No frontend route protection (pages render; data requests are gated at the API layer).
- No rate limiting or account lockout.
- No rate limiting, account lockout, or multi-factor authentication.
- No admin tooling or user management surface.

See [AUTH_LIMITATIONS.md](AUTH_LIMITATIONS.md) for the full non-goals list and scaling risks.

---

## Companion Components

### crawlernest-agents

`crawlernest/crawlernest-agents/` is a repo-native AI dev agent collection (not a
runtime dependency). It provides readonly development analysis agents — debug,
pipeline, and code-review roles — and shell scripts that wrap them. No agent
writes to the database, calls the API, or modifies source files. Output artifacts
are written to `tmp/` directories only.

### crawlernest-normalization

`crawlernest/crawlernest-normalization/` is a standalone C-language CSV
normalization engine that standardizes heterogeneous crawler output (university
names, country abbreviations, rank-range strings) into comparable numeric records.
The Python bridge in `crawlernest/crawlernest-normalization-py/` calls the compiled
binary with automatic fallback to a pure-Python normalizer. This component is a
research deliverable and is not called by the Spring Boot API or Next.js frontend
at runtime.

---

## Related Documents

- [Repository Map](REPOSITORY_MAP.md)
- [Data Flow](DATA_FLOW.md)
- [Operational Runbook](operational/OPERATIONAL_RUNBOOK.md)
- [API Surface](API_SURFACE.md)
- [CI Pipelines](release/CI_PIPELINES.md)
