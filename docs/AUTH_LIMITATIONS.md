# Auth Limitations

This document records what the current CrawlerNest identity layer **does not do**, why, and what must change before broader deployment.

---

## Current Auth Model

CrawlerNest authenticates with a **signed JWT in an http-only cookie**, verified by a Spring Security filter chain. Nothing per-user is stored server-side: there is no `HttpSession`, no `JSESSIONID`, and no session store to share between instances. There is still no OAuth, no refresh token, and no token revocation list.

### How it works

1. Browser submits `{ email, password }` to `POST /api/v1/auth/signin`.
2. Spring Boot verifies the BCrypt hash and issues an HS256 token (`clawer.auth.jwt.JwtService`) whose claims are the user id (`sub`) and email.
3. The token is set in `Set-Cookie` as `crawlernest_token` — `HttpOnly`, `SameSite=Strict`, `Path=/`, `Max-Age` = the token TTL — and forwarded through the Next.js proxy (`src/lib/authProxy.ts`) to the browser.
4. Subsequent requests carry the cookie, which the proxy forwards to Spring Boot. `JwtCookieAuthenticationFilter` verifies it and puts an `AuthenticatedUser` in the security context. An `Authorization: Bearer <token>` header works too, for callers that are not browsers.
5. `SecurityConfig` closes `/api/v1/user/**` and `/api/v1/admin/**` to unauthenticated callers; everything else — the whole read-only analytics API — stays public. User-owned endpoints read the id from `AuthenticatedUser.currentId()`, never from the request body.
6. `POST /api/v1/auth/signout` returns the same cookie expired (`Max-Age=0`).

### What it provides

| Guarantee | Mechanism |
|---|---|
| Identity cannot be forged | HS256 signature over the claims; an unsigned, re-signed or edited token verifies as nobody |
| No shared server state | Stateless tokens: a second API instance accepts a token issued by the first |
| Password confidentiality | BCrypt via `spring-security-crypto`; password hash never returned in responses |
| User isolation | All user-data SQL includes `WHERE user_id = ?` from the token's subject |
| No record-existence leaking | Cross-user access returns 404 (not 403) |
| Closed by default | The filter chain gates the `/user/**` and `/admin/**` prefixes, so a new endpoint under either is protected before anyone remembers to check |
| CSRF | `SameSite=Strict` — the browser attaches the cookie to no request another site starts |
| Cookie confidentiality | `HttpOnly=true` (no script can read the token); `Secure` when `CRAWLERNEST_JWT_COOKIE_SECURE=true` |
| No default signing key | With `CRAWLERNEST_JWT_SECRET` unset a random per-process key is generated and logged as a warning; nothing ships with a key an attacker could know |

Covered by `JwtServiceTest`, `SecurityFilterChainIntegrationTest` and `AuthControllerCookieTest`.

---

## Non-Goals (Current Scope)

These are explicitly out of scope and should not be added without a deliberate scope change:

| Non-goal | Reason |
|---|---|
| RBAC / roles / permissions | Entity review uses an e-mail allowlist (`crawlernest.reviewer.emails`); no broader role model is needed |
| OAuth / OIDC / third-party login | No external identity provider integration needed |
| Refresh tokens / silent renewal | A 12-hour token and a re-login is acceptable at this maturity |
| Token revocation (denylist) | Would reintroduce the shared server-side state the token removed; see the trade-off below |
| Frontend route protection | Routes render publicly; the data layer gating is the security boundary |
| Rate limiting | Required before public exposure; not implemented |
| Account lockout | No brute-force protection |
| Multi-factor authentication | Non-goal at current maturity |
| Email verification | Non-goal at current maturity |
| Account deletion / right to erasure | Non-goal for current scope |
| Per-user storage quota | Non-goal for current scope |
| Admin or user management UI | Non-goal for current scope |

---

## Deployment Requirements

### `CRAWLERNEST_JWT_SECRET` must be set

Unset, `JwtService` generates a key for the process and logs a warning. Everyone is then signed out on restart, and two instances do not accept each other's tokens. That is deliberate — the alternative, a default secret in the repository, would let anyone mint a token for any user.

**Required in any deployment:** `CRAWLERNEST_JWT_SECRET`, at least 32 bytes (`openssl rand -base64 32`). A shorter value is refused at startup rather than padded. `docker-compose.yml` declares it with `${CRAWLERNEST_JWT_SECRET:?}`, so the stack refuses to start without it.

### `Secure` cookie flag is off by default

`crawlernest.jwt.cookie-secure` defaults to `false` so a plain-http local run can sign in. Over any non-loopback network the token would travel in the clear.

**Before internet deployment:** `CRAWLERNEST_JWT_COOKIE_SECURE=true`, behind TLS.

### DB credentials come from the environment

`application.properties` reads `${SPRING_DATASOURCE_USERNAME:test}` / `${SPRING_DATASOURCE_PASSWORD:test}`. The defaults are the local development database; a deployment sets the variables and nothing in the file applies. `docker-compose.yml` requires them with `${VAR:?}`.

### CORS is an explicit allowlist

`crawlernest.cors.allowed-origins` (default `http://localhost:3000`) is a comma-separated list; `*` is refused, because an API that allows credentials cannot accept every origin. Set `CRAWLERNEST_CORS_ALLOWED_ORIGINS` to the real frontend origin.

---

## Known Operational Limitations

| Limitation | Impact |
|---|---|
| A token cannot be revoked before it expires | Sign-out clears the cookie, but a token already copied out of a browser stays valid until it expires. This is the trade a stateless token makes, and why the TTL is 12 hours rather than weeks. Rotating `CRAWLERNEST_JWT_SECRET` invalidates every outstanding token at once — the only revocation available. |
| No refresh token | After the TTL the user is signed out and must sign in again; there is no silent renewal. |
| Restarting with no configured secret signs everyone out | Only when `CRAWLERNEST_JWT_SECRET` is unset. With it set, restarts are transparent. |
| No sign-out notification | Other browser tabs do not detect sign-out until the next API call. |
| No concurrent session limit | A user can hold tokens in several browsers at once, and there is no way to enumerate or end them. |
| Password change does not invalidate tokens | Tokens issued before the change keep working until they expire. |

---

## Future Risks

### User data growth

`warehouse.saved_recommendation.result_json` stores full recommendation API payloads as JSONB. There is no per-user quota and no automatic expiry. Storage growth should be monitored as user count or save frequency increases.

### Token interception

Without `Secure=true` and HTTPS the cookie can be read in transit. A stolen token is worse than a stolen session id here, because it cannot be revoked — it is valid wherever it is replayed until it expires. This is a non-issue on `localhost` and a serious risk the moment the application is served over any non-loopback network.

### Secret handling

The signing key is the whole authentication system: anyone holding it can mint a token for any user. It must reach the process through the environment only, never a committed file, and rotating it is the only way to invalidate outstanding tokens.

### Account enumeration (residual)

Signin returns a uniform 401 regardless of whether the email exists. However, the signup endpoint returns 409 on duplicate email. An attacker who can call signup can still determine whether a given email is registered. This is acceptable for a demo tool but should be reviewed for any public-facing deployment.

---

## Scaling Boundaries

| Boundary | Current Limit | Action Required |
|---|---|---|
| Auth scheme | Stateless HS256 tokens | Fine for multiple instances; all must share one secret |
| Token revocation | None before expiry | Rotate the secret, or add a denylist (and the state that comes with it) |
| Cookie security | `Secure` off by default | `CRAWLERNEST_JWT_COOKIE_SECURE=true` for HTTPS deployments |
| DB credentials | Env vars with local-dev defaults | Set `SPRING_DATASOURCE_*` in every deployment |
| CORS | Allowlist, default `localhost:3000` | Set `CRAWLERNEST_CORS_ALLOWED_ORIGINS` |
| Rate limiting | None | Add before public exposure |

---

## Related Documents

- [Architecture Overview — Minimal Identity Layer](ARCHITECTURE_OVERVIEW.md)
- [User Data Safety Review](USER_DATA_SAFETY_REVIEW.md)
- [API Surface — Auth API](API_SURFACE.md)
- [Data Flow — Identity and User Data Flows](DATA_FLOW.md)
