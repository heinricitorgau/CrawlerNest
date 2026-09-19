# User Data Safety Review

**Scope:** `app_user`, `saved_university`, `saved_recommendation` tables; session auth; related API surface.  
**Review date:** 2026-05-16  
**Reviewer:** Claude Code (automated, human-supervised)

> **Superseded in part (2026-09-19).** Session auth was replaced by a signed JWT in an
> http-only cookie, verified by a Spring Security filter chain. Everything below about
> `HttpSession`, `JSESSIONID`, session timeout and session fixation describes the model
> as it stood at the review date. The data-isolation findings still hold — the user id
> now comes from the token instead of a session attribute. See
> [Auth Limitations](AUTH_LIMITATIONS.md) for the current model and its trade-offs.

---

## 1. Data Inventory

| Table | Schema | Sensitive columns | Notes |
|---|---|---|---|
| `app_user` | `warehouse` | `email`, `password_hash` | password_hash is BCrypt, never returned in API responses |
| `saved_university` | `warehouse` | — | `user_id` FK, `canonical_university_id`, `saved_at` |
| `saved_recommendation` | `warehouse` | — | `user_id` FK, `title`, `request_json` (JSONB), `result_json` (JSONB), `created_at` |

`request_json` stores the user's profile inputs (country, IELTS score, target rank, risk profile). These are not PII but are preference data the user explicitly submitted. `result_json` stores the full recommendation API response snapshot; it contains university names and scores but no user-identifying fields.

---

## 2. Session Model

- **Engine:** Servlet container in-memory `HttpSession` via Spring Boot's default session management.
- **Timeout:** 30 minutes (`server.servlet.session.timeout=30m`).
- **Cookie attributes:** `HttpOnly=true`, `SameSite=Lax`. No `Secure` flag — localhost assumption (non-TLS development environment).
- **Session fixation:** On signin, the existing session is invalidated with `existing.invalidate()` before a new session is created with `getSession(true)`. This prevents fixation attacks.
- **Session storage:** Stored exclusively in JVM heap. A backend restart logs out all active users without warning. There is no session persistence layer (no Redis, no JDBC session store).
- **Session content:** Only `user_id` (Long) is stored. Email and other profile fields are not kept in session; the `/api/auth/me` endpoint re-reads only `user_id` and `email` from the session attribute and a lightweight lookup respectively.

### Invariants

- A request is authenticated only if `httpRequest.getSession(false)` returns a non-null session with a non-null `user_id` attribute.
- `resolveUserId()` in `UserController` is the single gating function; all user-data endpoints call it before any data access.

---

## 3. Data Lifecycle

| Event | Behaviour |
|---|---|
| Account created | Row inserted in `app_user`; no session started yet |
| Sign in | Session created; `user_id` stored in session attribute |
| Sign out | Session invalidated; cookie cleared |
| Backend restart | All in-memory sessions lost; users must re-authenticate |
| Row deletion | `saved_university` and `saved_recommendation` support user-initiated DELETE; `app_user` rows have no self-serve deletion endpoint (planned non-goal) |
| Schema re-init | `CREATE TABLE IF NOT EXISTS` — idempotent; no data loss on restart |

---

## 4. User Isolation Guarantees

Every data access query includes `WHERE user_id = ?` bound to the session-derived user ID. No endpoint accepts `user_id` as a path or query parameter from the client.

| Operation | Isolation predicate |
|---|---|
| GET saved universities | `WHERE user_id = ?` |
| POST / DELETE saved university | `WHERE user_id = ?` implicitly via `save(userId, …)` / `delete(userId, …)` |
| GET saved recommendations list | `WHERE user_id = ?` |
| GET saved recommendation detail | `WHERE id = ? AND user_id = ?` |
| DELETE saved recommendation | `WHERE id = ? AND user_id = ?` (returns 404 if not found or not owned) |

**404 vs 403:** Cross-user access returns HTTP 404, not 403. This avoids confirming that the record exists under a different owner, preventing record-existence enumeration. The trade-off is that a developer debugging a mistake will see "Not Found" rather than "Forbidden" — accepted for this threat model.

---

## 5. Persistence Boundaries

- **User data stays in PostgreSQL** (`warehouse` schema). No user data is written to application logs (log statements use `user_id` integers only, never email or payload content).
- **Diagnostics endpoints** (`/api/v1/diagnostics/rankings`, `/subjects`, `/source-agreement`) access only the `analytics` and `warehouse.ranking_*` schemas — no user tables.
- **Health endpoint** (`/api/v1/health`, unauthenticated) reports: Postgres connectivity, aggregated/subject ranking counts, ranking years, source record counts. It does **not** expose `app_user_count` or any user-derived metric. (User count was removed as a user enumeration risk — see §8.)
- **No user data in snapshots/exports:** `export_metadata_bundle.sh` bundles only `snapshots/*.json`, `reports/*.md`, and pipeline logs. `agent_context_snapshot.sh` uses only repository diagnostics files. Neither script touches user tables.

---

## 6. JSON Snapshot Risks

`saved_recommendation.result_json` stores the full `RecommendationResponse` payload as JSONB. Known risks and current mitigations:

| Risk | Current state | Mitigation |
|---|---|---|
| Result payload size growth | No quota or size cap | Soft risk accepted; PostgreSQL JSONB compresses reasonably; operator can run `SELECT pg_total_relation_size('warehouse.saved_recommendation')` to monitor |
| Malformed JSON on write | `objectMapper.writeValueAsString(JsonNode)` always produces valid JSON; `?::jsonb` cast at DB rejects invalid JSON | Defence-in-depth: Jackson serialization + PostgreSQL JSONB type enforcement |
| Null `request_json` / `result_json` | Controller validates not null → 400 before reaching service | See validation hardening below |
| Title length unbounded | Capped at 200 characters; VARCHAR(255) column has additional DB-level cap | Controller returns 400 if `title.length() > 200` |
| No per-user quota | A single user can save unlimited plans | Non-goal for this release; no quota system implemented |
| Duplicate saves | No deduplication; user can save the same plan multiple times | Accepted; user-initiated behaviour |

---

## 7. Validation Hardening (Applied)

Changes made during this review:

1. **Title max length:** `UserController.saveRecommendation` rejects titles longer than 200 characters with HTTP 400 before any service call.
2. **Existing null checks preserved:** `title` blank → 400; `requestJson` or `resultJson` null → 400.
3. **Service-level safety:** `SavedRecommendationService.parseJson` has a try/catch fallback; `save()` wraps serialisation in a try/catch and rethrows as `RuntimeException`.

No schema changes, compression, or payload structure changes were made.

---

## 8. Public Health Endpoint — User Enumeration Risk (Fixed)

**Finding:** `HealthService` previously included `app_user_count` (total registered user count) in the unauthenticated `/api/v1/health` response. This allowed anyone to determine how many registered accounts exist.

**Fix applied:** The `app_user_count` field and its backing SQL query have been removed from `HealthService.getHealth()`. The health endpoint now exposes only pipeline/ranking operational data.

**Smoke script:** `smoke_release.sh` checks `/api/v1/health` for HTTP 200 status only — it does not assert on any specific field values. No script changes required.

---

## 9. Operational Limitations

| Limitation | Implication |
|---|---|
| In-memory sessions | Backend restart signs out all users; no warning mechanism |
| No `Secure` cookie flag | Cookies are transmitted in plaintext over HTTP — acceptable for localhost; must be set before any non-localhost deployment |
| No session cluster sharing | Multiple backend instances would not share sessions; horizontal scaling requires session store (out of scope) |
| No account deletion | Users cannot delete their account or all their data via the API |
| No retention policy | `saved_recommendation` rows accumulate indefinitely; no automatic expiry |
| No rate limiting | Auth endpoints and save endpoints accept unlimited requests |

---

## 10. Known Non-Goals

The following were explicitly excluded from this review and implementation:

- RBAC / admin / team / sharing features
- Redis session store or JWT
- Spring Security filter chain
- Schema redesign, compression, or recommendation payload structure changes
- Frontend UX changes
- Telemetry system
- Automatic architecture fixes
- Recommendation scoring / ordering / aggregation / ranking pipeline changes

---

## 11. Attack Surface Summary

| Vector | Risk | Current defence |
|---|---|---|
| Unauthenticated health endpoint | Was: user count exposure. Now: ranking operational data only | `app_user_count` removed |
| Session theft (cookie) | HttpOnly prevents JS access; SameSite=Lax limits CSRF | No Secure flag on localhost |
| Cross-user data access | 404 for wrong-owner records | All queries include `WHERE user_id = ?` from session |
| Oversized title injection | DB VARCHAR(255) + controller 200-char cap | Returns 400 before service call |
| Null/malformed JSON body | Spring deserializes to null; controller null-checks → 400 | Validated before service call |
| Password in logs/response | BCrypt hash; `AppUser` entity never serializes `passwordHash` | `AuthUserResponse` DTO excludes it |
| Email enumeration (signin) | Signin returns generic 401 regardless of whether email exists | Uniform response |

---

## 12. Localhost Assumptions

This system is designed for local development and demo use. Before any internet-accessible deployment:

- Enable `server.servlet.session.cookie.secure=true`
- Replace `username=test` / `password=test` DB credentials
- Add session clustering (Redis or similar) if multiple instances are needed
- Implement rate limiting on auth endpoints
- Review and scope CORS origins (`WebMvcConfigurer` currently allows all origins for development)
