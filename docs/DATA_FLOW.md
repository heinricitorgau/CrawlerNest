# CrawlerNest Data Flow

This document traces global ranking and subject ranking data from source acquisition to frontend rendering.

## Global Ranking Flow

```mermaid
flowchart TB
    source["QS / THE / ARWU source"]
    crawler["Crawler"]
    adapter["Source adapter"]
    normalization["Normalization"]
    canonical["Canonical resolution"]
    rankingRecord[("warehouse.ranking_record")]
    aggregation["Aggregation"]
    aggregated[("analytics.aggregated_rankings")]
    latest[("analytics.v_aggregated_rankings_latest")]
    api["Spring Boot API"]
    frontend["Next.js frontend"]

    source --> crawler --> adapter --> normalization --> canonical --> rankingRecord --> aggregation --> aggregated --> latest --> api --> frontend
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

```mermaid
flowchart TB
    rankingRecord[("warehouse.ranking_record")]
    aggregator["RankingAggregator"]
    aggregated[("analytics.aggregated_rankings")]

    rankingRecord --> aggregator --> aggregated
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

```mermaid
flowchart TB
    source["QS subject source"]
    crawler["Subject crawler"]
    normalization["Subject normalization"]
    canonical["Canonical resolution"]
    record[("warehouse.subject_ranking_record")]
    latest[("analytics.v_subject_rankings_latest")]
    api["Subject ranking API"]
    ui["Next.js subject ranking UI"]

    source --> crawler --> normalization --> canonical --> record --> latest --> api --> ui
```

Subject rankings are intentionally separate from global aggregation. They provide discipline-specific evidence without modifying global composite ranks.

Important paths:

- `crawlernest_ranking_crawler/subjects/`
- `crawlernest/scripts/smoke_subject_rankings.py`
- `crawlernest/servise_for_java/src/main/java/clawer/api/SubjectRankingController.java`
- `crawlernest/crawlernest-web/src/app/subject-rankings/page.tsx`

## Diagnostics Data Flow

```mermaid
flowchart TB
    state[("Warehouse + analytics state")]
    health["HealthService"]
    freshness["FreshnessService"]
    diagnostics["DiagnosticsService"]
    quality["DataQualityService"]
    intelligence["SourceIntelligenceService"]
    healthApi["/api/v1/health"]
    freshnessApi["/api/v1/freshness"]
    diagnosticsApi["/api/v1/diagnostics/*"]
    pages["/system-status and /data-quality"]

    state --> health --> healthApi --> pages
    state --> freshness --> freshnessApi --> pages
    state --> diagnostics --> diagnosticsApi --> pages
    state --> quality --> diagnosticsApi
    state --> intelligence --> diagnosticsApi
```

Diagnostics use the same database state as product reads, which keeps operational signals aligned with user-visible data.

## Snapshot and Report Flow

```mermaid
flowchart TB
    database[("Live database")]
    export["scripts/export_system_snapshot.py"]
    snapshot["snapshots/system_snapshot_*.json"]
    latest["snapshots/latest_status.json"]
    summary["scripts/build_failure_summary.py"]
    report["Reports or CI artifact"]

    database --> export
    export --> snapshot
    export --> latest
    latest --> summary --> report
```

Snapshots are useful for handoff, CI summaries, and incident analysis when live services are not available.

## Identity and User Data Flows

### Signin Flow

```mermaid
flowchart TB
    browser["Browser<br/>POST /api/auth/signin"]
    proxy["Next.js proxy<br/>/app/api/auth/signin/route.ts"]
    spring["Spring Boot<br/>AuthController.signin()"]
    authservice["AuthService.signin()"]
    pg[("warehouse.app_user")]
    jwt["JwtService.issue(id, email)"]

    browser --> proxy
    proxy -- "forwards Cookie header" --> spring
    spring --> authservice
    authservice -- "SELECT by email + BCrypt verify" --> pg
    spring -- "sign {sub, email} with HS256" --> jwt
    spring -- "Set-Cookie crawlernest_token (HttpOnly, SameSite=Strict)" --> proxy
    proxy -- "Set-Cookie forwarded to browser" --> browser
```

1. Browser `POST`s `{ email, password }` to the Next.js proxy (`/api/auth/signin`).
2. Proxy forwards the request — including any existing `Cookie` header — to Spring Boot.
3. `AuthService` queries `warehouse.app_user` by email and verifies the BCrypt hash.
4. On success: `JwtService` signs a token carrying the user id and email. Nothing is written server-side, so there is no session to fixate on.
5. Spring Boot includes `Set-Cookie: crawlernest_token=...` in the response. The proxy forwards this header back to the browser unchanged.
6. The browser stores the cookie and sends it automatically on subsequent requests to `localhost:3000`.

### Token Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Unauthenticated
    Unauthenticated --> Authenticated : POST /api/auth/signin (valid credentials)
    Authenticated --> Unauthenticated : POST /api/auth/signout (cookie cleared)
    Authenticated --> Unauthenticated : token TTL elapses (default 12h)
    Authenticated --> Unauthenticated : CRAWLERNEST_JWT_SECRET rotated or unset at restart
```

- No state is held anywhere: every request is authenticated by verifying the signature again.
- The TTL is fixed at issue, not sliding; there is no silent renewal.
- Signout clears the browser's copy. A token already copied elsewhere stays valid until it expires — rotating the secret is the only way to invalidate outstanding tokens.
- A restart signs everyone out only when the secret is unconfigured (an ephemeral per-process key).

### Save University Flow

```mermaid
flowchart TB
    browser["Browser — /rankings"]
    hook["useSavedUniversities hook<br/>optimistic update"]
    proxy["Next.js proxy<br/>/api/user/saved-universities/[id]"]
    spring["Spring Boot<br/>UserController.save()"]
    service["SavedUniversityService.save()"]
    pg[("warehouse.saved_university")]

    browser -- "click Save button" --> hook
    hook -- "optimistic UI update" --> browser
    hook -- "POST /api/user/saved-universities/{id}" --> proxy
    proxy -- "forwards crawlernest_token cookie" --> spring
    spring -- "verify token → userId" --> spring
    spring --> service
    service -- "INSERT ON CONFLICT DO NOTHING" --> pg
    pg --> service
    service --> spring
    spring -- "201 Created" --> proxy
    proxy --> hook
    hook -- "revert on error" --> browser
```

- Optimistic update is applied immediately. If the API call fails, the hook reverts the UI.
- Duplicate saves are no-ops at the DB level.

### Save Recommendation Flow

```mermaid
flowchart TB
    browser["Browser — /recommendations"]
    page["recommendations/page.tsx<br/>handleSavePlan()"]
    proxy["Next.js proxy<br/>/api/user/saved-recommendations"]
    spring["Spring Boot<br/>UserController.saveRecommendation()"]
    service["SavedRecommendationService.save()"]
    pg[("warehouse.saved_recommendation")]

    browser -- "click Save This Plan" --> page
    page -- "POST { title, request, result }" --> proxy
    proxy -- "forwards crawlernest_token cookie" --> spring
    spring -- "verify token → userId" --> spring
    spring -- "validate title ≤ 200 chars, request/result non-null" --> spring
    spring --> service
    service -- "serialize to JSON strings → INSERT RETURNING id" --> pg
    pg -- "new id" --> service
    service --> spring
    spring -- "201 Created { id }" --> proxy
    proxy --> page
    page -- "Saved ✓ + link to /saved-recommendations" --> browser
```

- `title` is validated (non-blank, ≤ 200 chars) at the controller before the service is called.
- Both `request` (recommendation inputs) and `result` (full API response) are serialized and stored as JSONB.
- The UI transitions to a "Saved ✓" state with a link to `/saved-recommendations` on success.

---

## Related Documents

- [Architecture Overview](ARCHITECTURE_OVERVIEW.md)
- [Repository Map](REPOSITORY_MAP.md)
- [Operational Runbook](operational/OPERATIONAL_RUNBOOK.md)
- [API Surface](API_SURFACE.md)
