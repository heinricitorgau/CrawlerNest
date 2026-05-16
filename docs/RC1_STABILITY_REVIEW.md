# RC-1 Long-run Stability Review

Assesses the long-run operational behavior of the current system under sustained demo and testing conditions. No behavior was changed as a result of this review; only risks and known bounds are documented.

---

## Session Lifecycle

**Model:** Spring Boot `HttpSession` (in-memory, JVM heap). No external session store.

| Behavior | Status | Notes |
|---|---|---|
| Session timeout | 30 minutes idle | Configured via `server.servlet.session.timeout=30m`. Browser cookie expires accordingly. |
| Session fixation prevention | Implemented | On signin: old session invalidated, new session created before writing user ID. |
| Session loss on restart | Expected | JVM restart clears all sessions. Users are signed out. No persistence across restarts. |
| Concurrent session handling | Not controlled | Multiple logins from the same user are independent sessions. No single-session enforcement. |
| Session expiry UX | Handled | All user-facing API calls detect 401 and show the sign-in prompt. `useAuth().refresh()` re-syncs client state. |
| Cookie security | HttpOnly, SameSite=Lax, no Secure flag | Appropriate for localhost. Must add `Secure=true` before any HTTPS deployment. |

**Long-run risk:** If the server is left running for days under active use, the in-memory session store grows until idle sessions expire (30m). Under normal demo load this is not a concern. Under heavy concurrent testing, heap monitoring is advisable.

---

## Save/Remove Persistence

**Model:** PostgreSQL-backed. Two tables: `app_user_saved_university` and `saved_recommendation`.

| Behavior | Status | Notes |
|---|---|---|
| User isolation | Enforced | All queries include `WHERE user_id = ?` sourced from session, never from request body. |
| Save idempotency | Enforced | `warehouse.saved_university` has `UNIQUE (user_id, canonical_university_id)` and inserts use `ON CONFLICT ... DO NOTHING`. |
| Delete cross-user prevention | Enforced | Returns 404 (not 403) if the row doesn't belong to the requesting user. No information leak. |
| Save recommendation payload size | Unbounded | `request_json` and `result_json` are JSONB with no size cap at the database level. Validated by 200-char title limit at API level only. Large IELTS scores or long country lists could produce large payloads; not a concern at current usage scale. |
| Transaction boundaries | Not explicit | User data mutations use Spring Data / JPA default transaction management. Single-operation mutations are atomic. No multi-step transaction is required. |

**Long-run risk:** Saved recommendation payloads remain the main persistence growth vector because recommendation snapshots are stored as JSONB without a DB-side size cap.

---

## Diagnostics Readonly Guarantees

| Guarantee | Status | Notes |
|---|---|---|
| Diagnostics endpoints are read-only | Verified | `/api/v1/diagnostics/*` and `/api/v1/health` are HTTP GET only; no write-path code. |
| No auth required for diagnostics | By design | Diagnostics are intentionally public for operational monitoring. The previous `app_user_count` exposure was removed in the safety review. |
| Agent wrappers are readonly | Verified | `scripts/agent_*.sh` wrappers call only GET endpoints and read-only Python scripts. |
| Snapshot export | Readonly | `compare_snapshots.py` reads JSON files; does not write to the database. |

---

## Snapshot Growth Risks

| Risk | Assessment |
|---|---|
| Snapshot files accumulate in `snapshots/` | Low. Snapshots are small JSON files (~1–3 KB each). The `snapshots/` directory is gitignored. Manual cleanup is sufficient at current frequency. |
| No automatic rotation | Current policy: manual. The `scripts/cleanup_old_artifacts.sh` script exists for rotation. Acceptable for RC-1 demo cadence. |
| `latest_status.json` overwrites on each run | By design. No historical version is lost since dated snapshot files are also written. |

Current snapshot directory size: ~3 KB (2 files). No growth concern for RC-1.

---

## JSON Payload Growth Risks

| Payload | Current Size | Growth Risk |
|---|---|---|
| Saved recommendation `request_json` | Small (≤ 5 fields) | Low. User input is a form with a fixed field set. |
| Saved recommendation `result_json` | Medium (3 university lists × ≤ N entries each) | Low-Medium. Result set size is bounded by the recommendation engine's output caps. |
| Rankings API response | Depends on page size | Low. Paginated; `pageSize` defaults enforce a ceiling. |
| Subject rankings response | Moderate | Low. Subject lists are finite and bounded by the data pipeline output. |

No payload is expected to cause a production-scale problem at current demo volumes.

---

## Local Storage Assumptions

The system uses browser `localStorage` for client-side shortlist and
recommendation decision-flow convenience state. Auth sessions, saved
universities, and saved recommendation plans remain server-side in Spring Boot
sessions or PostgreSQL.

| State | Storage | Durability / Risk |
| --- | --- | --- |
| Auth identity | Spring Boot session | Lost on API restart or timeout; expected. |
| Saved universities | PostgreSQL | Durable across restart. |
| Saved recommendation plans | PostgreSQL | Durable across restart. |
| Shortlist / decision-flow helpers | Browser `localStorage` | Per-browser convenience state; may be cleared locally and is not a source of truth. |

**Long-run risk:** local browser state can drift from server-backed saved data,
but it does not threaten persisted user records or backend correctness.

---

## Restart Behavior

| Component | On Restart | Impact |
|---|---|---|
| Spring Boot | All in-memory sessions lost. DB connections re-established. Schema check via `AuthSchemaInitializer` runs. | Users are signed out. No data loss. |
| Next.js | Stateless. No in-memory user state. | No impact on persistence. |
| PostgreSQL | All persisted data preserved (ACID). | Users' saved universities and recommendation plans survive. |

**Recovery time:** Spring Boot restart typically completes in 5–10 seconds on local hardware. No warm-up required.

---

## Operational Recovery Readiness

| Scenario | Recovery Path | Documented |
|---|---|---|
| PostgreSQL unreachable | Spring Boot fails health check. Frontend shows backend unavailable banner. | Yes — `OPERATIONAL_RECOVERY.md` |
| Spring Boot down | Next.js proxy returns 503. Frontend shows unavailable state. | Yes — `UX_STABILIZATION_NOTES.md` |
| Session expired mid-session | User sees sign-in prompt. No data loss. | Yes — `UX_STABILIZATION_NOTES.md` |
| Stale snapshot data | Diagnostics show `stale` status. No user-facing degradation. | Yes — `PIPELINE_HEALTH_MODEL.md` |
| Data pipeline failure | Rankings data becomes stale. Frontend continues serving cached DB rows. | Yes — `OPERATIONAL_RECOVERY.md` |

All primary failure modes have documented recovery paths. No novel failure modes were identified in this review.

---

## Overall Stability Assessment for RC-1

| Area | Rating | Notes |
|---|---|---|
| Session model | Acceptable | In-memory, appropriate for localhost demo. Known limits documented. |
| Data persistence | Good | PostgreSQL-backed, ACID, user-isolated, and saved-university writes are idempotent. |
| Diagnostics isolation | Good | Fully readonly, no auth-gated data exposed. |
| Snapshot management | Good | Small, gitignored, manually rotated. |
| Payload bounds | Good | No unbounded growth risk at current scale. |
| Restart recovery | Good | Stateless frontend + ACID database = clean recovery profile. |
| Operational documentation | Good | All primary failure modes have documented recovery paths. |
