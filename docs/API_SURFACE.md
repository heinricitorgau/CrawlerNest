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

## Auth API

Auth endpoints live at `/api/v1/auth/` in Spring Boot. The Next.js proxy forwards them under `/api/auth/`. The session cookie (`JSESSIONID`) is set by Spring Boot and forwarded transparently through the Next.js proxy layer; the browser treats it as a first-party cookie for `localhost:3000`.

### Summary

| Method | Path | Auth required | Purpose |
|---|---|---|---|
| `POST` | `/api/v1/auth/signup` | No | Register a new account |
| `POST` | `/api/v1/auth/signin` | No | Sign in and start a session |
| `POST` | `/api/v1/auth/signout` | Optional | End the current session |
| `GET` | `/api/v1/auth/me` | Session | Get the currently authenticated user |

### `POST /api/v1/auth/signup`

**Auth required:** No.

**Request:** `{ "email": "string", "password": "string" }`

Email is lowercased and trimmed. Password must be ≥ 8 characters.

**Response (201 Created):** `{ "success": true, "data": { "id": number, "email": "string" } }`

**Error cases:**
- 400 — email or password missing, or password under 8 characters.
- 409 — email already registered.

**Limitations:** No email verification. No password-strength enforcement beyond minimum length. No rate limiting.

**Session:** Does not start a session. The user must call `signin` to obtain a cookie.

---

### `POST /api/v1/auth/signin`

**Auth required:** No.

**Request:** `{ "email": "string", "password": "string" }`

**Response (200 OK):** `{ "success": true, "data": { "id": number, "email": "string" } }`. Sets `JSESSIONID` HttpOnly cookie in `Set-Cookie` header.

**Session behavior:** Any existing session is invalidated before a new one is created (session-fixation prevention). The new session stores `user_id` (Long) and expires after 30 minutes of inactivity.

**Error cases:**
- 401 — credentials invalid. Response is uniform regardless of whether the email exists (prevents account enumeration).

**Limitations:** No rate limiting, no failed-attempt lockout, no multi-factor authentication.

---

### `POST /api/v1/auth/signout`

**Auth required:** Optional (safe to call without a session).

**Request:** Empty body.

**Response (200 OK):** `{ "success": true }`. Sends `Set-Cookie` header to clear `JSESSIONID`.

**Session behavior:** Invalidates the current session if one exists.

---

### `GET /api/v1/auth/me`

**Auth required:** Session.

**Request:** No body. The `JSESSIONID` cookie is forwarded automatically by the Next.js proxy.

**Response (200 OK):** `{ "success": true, "data": { "id": number, "email": "string" } }`

**Error cases:**
- 401 — no valid session.

**Limitations:** Returns only `id` and `email`. Password hash is never included in any auth response.

---

## User-Owned APIs

User-owned endpoints live at `/api/v1/user/` in Spring Boot. The Next.js proxy forwards them under `/api/user/`. All endpoints require an active session (`JSESSIONID` cookie). Unauthenticated requests receive 401. All data queries are scoped to the authenticated user; `user_id` is derived only from the session, never from client-supplied parameters.

### Saved Universities

| Method | Path | Auth required | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/user/saved-universities` | Session | List saved universities |
| `POST` | `/api/v1/user/saved-universities/{canonicalUniversityId}` | Session | Save a university |
| `DELETE` | `/api/v1/user/saved-universities/{canonicalUniversityId}` | Session | Remove a saved university |

#### `GET /api/v1/user/saved-universities`

**Response (200 OK):**
```json
{
  "success": true,
  "data": [
    {
      "canonicalUniversityId": number,
      "universityName": "string",
      "slug": "string",
      "country": "string",
      "savedAt": "ISO-8601 timestamp"
    }
  ]
}
```
Ordered by `saved_at DESC`. Returns only records owned by the session user.

#### `POST /api/v1/user/saved-universities/{canonicalUniversityId}`

**Path parameter:** `canonicalUniversityId` — numeric ID of the canonical university.

**Request:** Empty body.

**Response (201 Created):** `{ "success": true, "data": { "saved": true } }`

**Behavior:** Idempotent. Duplicate saves are silently ignored (`INSERT ... ON CONFLICT DO NOTHING`).

#### `DELETE /api/v1/user/saved-universities/{canonicalUniversityId}`

**Request:** Empty body.

**Response (200 OK):** `{ "success": true, "data": { "deleted": true } }`

**Behavior:** No-op if the record does not exist or belongs to another user. No error is returned.

---

### Saved Recommendations

| Method | Path | Auth required | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/user/saved-recommendations` | Session | List recommendation plan summaries |
| `POST` | `/api/v1/user/saved-recommendations` | Session | Save a recommendation snapshot |
| `GET` | `/api/v1/user/saved-recommendations/{id}` | Session | Get full plan detail |
| `DELETE` | `/api/v1/user/saved-recommendations/{id}` | Session | Delete a saved plan |

#### `GET /api/v1/user/saved-recommendations`

**Response (200 OK):**
```json
{
  "success": true,
  "data": [
    {
      "id": number,
      "title": "string",
      "createdAt": "ISO-8601 timestamp",
      "requestSummary": "string or null",
      "topRecommendationName": "string or null"
    }
  ]
}
```
`requestSummary` is derived from JSONB fields (country, IELTS, target rank, risk profile). `topRecommendationName` is the first university from the reach or target bucket. Ordered by `created_at DESC`.

#### `POST /api/v1/user/saved-recommendations`

**Request:**
```json
{
  "title": "string",
  "request": { /* recommendation request params */ },
  "result":  { /* full recommendation response */ }
}
```

**Validation:**
- `title` must be non-blank and ≤ 200 characters; 400 otherwise.
- `request` and `result` must be present (non-null); 400 otherwise.

**Response (201 Created):** `{ "success": true, "data": { "id": number } }`

**Limitations:** No deduplication. A user can save the same plan multiple times. No per-user quota. `result` is stored as JSONB; no size cap is enforced at the API layer.

#### `GET /api/v1/user/saved-recommendations/{id}`

**Path parameter:** `id` — numeric plan ID.

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "id": number,
    "title": "string",
    "createdAt": "ISO-8601 timestamp",
    "requestJson": { /* stored request object */ },
    "resultJson":  { /* stored result object */ }
  }
}
```

**Isolation:** Returns 404 if the record does not exist or belongs to another user (not 403, to prevent confirming record existence).

#### `DELETE /api/v1/user/saved-recommendations/{id}`

**Request:** Empty body.

**Response (200 OK):** `{ "success": true, "data": { "deleted": true } }`

**Isolation:** Returns 404 if not found or not owned by the session user.

---

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
