# CrawlerNest API Surface

This document lists the current Spring Boot API surface used by the product UI, diagnostics, explainability, and operations. Next.js proxy routes generally mirror these endpoints under `/api/...` where needed.

## Rankings API

| Method | Path | Purpose | Response summary |
| --- | --- | --- | --- |
| `GET` | `/api/v1/rankings` | Product rankings list. Supports page, pageSize, year, search, scope, region, country, and `source=AGGREGATED`. | `items` with canonical id, name, slug, ranks, composite score, source count, year, country, and metadata. |
| `GET` | `/api/v1/rankings/{source}` | Compatibility route for aggregated rankings. Currently only `AGGREGATED` is supported for product rankings. | Same item shape as `/api/v1/rankings`; unsupported sources return a validation error. |

## Subject Rankings API

| Method | Path | Purpose | Response summary |
| --- | --- | --- | --- |
| `GET` | `/api/v1/subject-rankings/subjects` | List active subject options. | Subject keys and display names. |
| `GET` | `/api/v1/subject-rankings` | Query subject ranking rows by subject, source, year, country, search, page, and pageSize. | `items` with canonical id, slug, university name, country, source, subject, year, rank, score, and metadata. |
| `GET` | `/api/v1/subject-rankings/{subjectKey}` | Path-style subject ranking query. | Same subject ranking item shape. |
| `GET` | `/api/v1/universities/{id}/subject-rankings` | Subject ranking evidence for one canonical university. | Subject ranking rows for the requested university. |

## University API

| Method | Path | Purpose | Response summary |
| --- | --- | --- | --- |
| `GET` | `/api/v1/universities` | Paginated university list. | University DTO list. |
| `GET` | `/api/v1/universities/{id}` | University detail by id. | University detail with aggregate ranking, source rankings, admission requirements, and data quality fields. |
| `GET` | `/api/v1/universities/by-slug/{slug}` | University detail by URL slug. | Same university detail shape as id lookup. |
| `GET` | `/api/v1/preview/universities` | Canonical university preview lookup by id or name. | Canonical identity, aliases, ranking preview, and admission preview summary. |

## Recommendation and Comparison API

| Method | Path | Purpose | Response summary |
| --- | --- | --- | --- |
| `GET` | `/api/v1/recommendations` | Rank-aware recommendation groups. | Reach, target, and safety recommendation groups with explanations. |
| `POST` | `/api/v1/compare` | Compare selected universities. | Side-by-side university comparison result. |

## Diagnostics API

| Method | Path | Purpose | Response summary |
| --- | --- | --- | --- |
| `GET` | `/api/v1/diagnostics/rankings` | Ranking pipeline/API diagnostics. | Ranking counts, latest data, and readiness signals. |
| `GET` | `/api/v1/diagnostics/subjects` | Subject ranking diagnostics. | Subject counts, latest source/year state, and readiness signals. |
| `GET` | `/api/v1/diagnostics/data-quality` | Data quality evaluation. | Unresolved entities, duplicate savings, drift warnings, regression summary, and low-confidence matches. |
| `GET` | `/api/v1/diagnostics/source-agreement` | Cross-source agreement diagnostics. | QS/THE average rank difference, largest disagreement outliers, missing-source coverage, source overlap, and confidence buckets. |
| `GET` | `/api/v1/diagnostics/operational-status` | Operational dashboard state. | Service and data status for system-status UI. |

## Explainability API

| Method | Path | Purpose | Response summary |
| --- | --- | --- | --- |
| `GET` | `/api/v1/universities/{id}/source-comparison` | Compare QS, THE, and ARWU evidence for one university. | Source ranks and scores, aggregation contribution, missing sources, rank spread, confidence, and disagreement metrics. |
| `GET` | `/api/v1/rankings/{id}/explain` | Explain why a stored aggregated rank exists. | Source contributions, weighted aggregation inputs, normalized scores, missing-source penalties, confidence reasoning, and formula note. |

## Health and Freshness API

| Method | Path | Purpose | Response summary |
| --- | --- | --- | --- |
| `GET` | `/api/v1/health` | Health check and database connectivity. | Service status, PostgreSQL connectivity, and key record counts. |
| `GET` | `/api/v1/freshness` | Data freshness status. | Freshness by global rankings, subject rankings, and aggregation state. |

## Legacy/Adjacent API

| Method | Path | Purpose | Response summary |
| --- | --- | --- | --- |
| `GET` | `/admissions` | Legacy admission requirement query. | Admission requirement records. |

## Frontend Proxy Notes

Next.js proxy routes live under:

```text
crawlernest/crawlernest-web/src/app/api/
```

They forward browser-safe requests to the Spring Boot API and normalize local backend candidates for development.

## Related Documents

- [Architecture Overview](ARCHITECTURE_OVERVIEW.md)
- [Data Flow](DATA_FLOW.md)
- [Repository Map](REPOSITORY_MAP.md)
- [Operational Runbook](OPERATIONAL_RUNBOOK.md)
