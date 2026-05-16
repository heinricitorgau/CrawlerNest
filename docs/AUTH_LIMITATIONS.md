# Auth Limitations

This document records what the current CrawlerNest identity layer **does not do**, why, and what must change before broader deployment.

---

## Current Auth Model

CrawlerNest uses servlet-container `HttpSession` managed by Spring Boot's default session handling. There is no JWT, no OAuth, no Spring Security filter chain, and no distributed session store.

### How it works

1. Browser submits `{ email, password }` to `POST /api/v1/auth/signin`.
2. Spring Boot verifies the BCrypt hash and creates an `HttpSession`. The session stores only `user_id` (Long).
3. `JSESSIONID` is set in `Set-Cookie` and forwarded through the Next.js proxy to the browser.
4. Subsequent requests carry `JSESSIONID`, which the proxy forwards to Spring Boot.
5. All user-owned endpoints call `resolveUserId(httpRequest)`: `session.getSession(false)` → attribute `user_id`. Missing or expired session → 401.

### What it provides

| Guarantee | Mechanism |
|---|---|
| Session fixation prevention | Existing session invalidated before new session created on signin |
| Password confidentiality | BCrypt via `spring-security-crypto`; password hash never returned in responses |
| User isolation | All user-data SQL includes `WHERE user_id = ?` from session attribute |
| No record-existence leaking | Cross-user access returns 404 (not 403) |
| Cookie security | `HttpOnly=true`, `SameSite=Lax` |

---

## Non-Goals (Current Scope)

These are explicitly out of scope and should not be added without a deliberate scope change:

| Non-goal | Reason |
|---|---|
| RBAC / roles / permissions | Single-user local model; no team or admin use case |
| OAuth / OIDC / third-party login | No external identity provider integration needed for local demo |
| JWT or token-based auth | Adds complexity without benefit at single-node local scale |
| Frontend route protection | Routes render publicly; the data layer gating is the security boundary |
| Redis or JDBC session store | Not needed for single-node development; required before horizontal scaling |
| Rate limiting | No hardening needed for local dev; required before public deployment |
| Account lockout | No brute-force protection; acceptable for local dev use |
| Multi-factor authentication | Non-goal at current maturity |
| Email verification | Non-goal at current maturity |
| Account deletion / right to erasure | Non-goal for current scope |
| Per-user storage quota | Non-goal for current scope |
| Admin or user management UI | Non-goal for current scope |

---

## Localhost Assumptions

The current auth implementation is explicitly designed for `localhost` only. The following assumptions **must be revisited before any internet-accessible deployment**:

### No `Secure` cookie flag

`server.servlet.session.cookie.secure` is not set in `application.properties`. The `JSESSIONID` cookie will be sent over plain HTTP. This is intentional for local development but exposes the session cookie to interception over non-TLS connections.

**Before internet deployment:** Add `server.servlet.session.cookie.secure=true`.

### DB credentials are local dev values

`application.properties` uses `username=test` / `password=test`. These are hardcoded local dev values.

**Before internet deployment:** Use environment variables or a secrets manager for DB credentials.

### CORS allows all origins (local dev)

`WebMvcConfigurer` allows all origins for development. This is appropriate for `localhost:3000` ↔ `localhost:8080` but is too permissive for any multi-origin deployment.

**Before internet deployment:** Restrict `allowedOrigins` to the actual frontend origin.

### Single-node only

`HttpSession` is stored in JVM heap. There is no session serialization, clustering, or external store.

**Before multi-instance deployment:** Add Redis-backed or JDBC-backed session storage.

---

## Known Operational Limitations

| Limitation | Impact |
|---|---|
| Backend restart clears all sessions | All users are signed out silently; must re-authenticate |
| No session persistence | Planned maintenance restarts are disruptive |
| No refresh token | Sessions expire after 30 minutes of inactivity with no silent renewal |
| No sign-out notification | Other browser tabs do not detect sign-out until the next API call |
| No concurrent session limit | A user can have multiple active sessions from different browsers |

---

## Future Risks

### Horizontal scaling

`HttpSession` cannot be shared across JVM instances. Adding a second Spring Boot instance would create session affinity problems. Migration to a distributed session store (Redis via Spring Session) or stateless tokens (JWT) is required before any load-balanced deployment.

### User data growth

`warehouse.saved_recommendation.result_json` stores full recommendation API payloads as JSONB. There is no per-user quota and no automatic expiry. Storage growth should be monitored as user count or save frequency increases.

### Cookie interception

Without `Secure=true` and HTTPS, `JSESSIONID` can be read in transit. This is a non-issue on `localhost` but becomes a serious risk the moment the application is served over any non-loopback network.

### Account enumeration (residual)

Signin returns a uniform 401 regardless of whether the email exists. However, the signup endpoint returns 409 on duplicate email. An attacker who can call signup can still determine whether a given email is registered. This is acceptable for a local dev / demo tool but should be reviewed for any public-facing deployment.

---

## Scaling Boundaries

| Boundary | Current Limit | Action Required |
|---|---|---|
| Session store | JVM heap only | Redis or JDBC session for multi-instance |
| Cookie security | HTTP only (no `Secure` flag) | Enable `Secure` for HTTPS deployments |
| DB credentials | Hardcoded test values | Environment-variable injection |
| CORS | All origins allowed | Restrict to known frontend origins |
| Rate limiting | None | Add before public exposure |
| Auth scheme | Session cookies | Consider JWT for stateless horizontal scaling |

---

## Related Documents

- [Architecture Overview — Minimal Identity Layer](ARCHITECTURE_OVERVIEW.md)
- [User Data Safety Review](USER_DATA_SAFETY_REVIEW.md)
- [API Surface — Auth API](API_SURFACE.md)
- [Data Flow — Identity and User Data Flows](DATA_FLOW.md)
