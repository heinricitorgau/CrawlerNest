# Auth Limitations

This document records what the current CrawlerNest identity layer **does not do**, why, and what must change before broader deployment.

---

## Current Auth Model

CrawlerNest authenticates with a **signed JWT in an http-only cookie**, verified by a Spring Security filter chain. Nothing per-user is stored server-side: there is no `HttpSession`, no `JSESSIONID`, and no session store to share between instances. There is still no OAuth, no refresh token, and no denylist; a per-account token generation (below) is what lets a token end early.

### How it works

1. Browser submits `{ email, password }` to `POST /api/v1/auth/signin`.
2. Spring Boot verifies the BCrypt hash and issues an HS256 token (`clawer.auth.jwt.JwtService`) whose claims are the user id (`sub`), email, and the account's token generation (`ver`).
3. The token is set in `Set-Cookie` as `crawlernest_token` — `HttpOnly`, `SameSite=Strict`, `Path=/`, `Max-Age` = the token TTL — and forwarded through the Next.js proxy (`src/lib/authProxy.ts`) to the browser.
4. Subsequent requests carry the cookie, which the proxy forwards to Spring Boot. `JwtCookieAuthenticationFilter` verifies it, checks that the account is active and still at the token's generation (`warehouse.app_user.token_version`, one primary-key read), and puts an `AuthenticatedUser` in the security context. An `Authorization: Bearer <token>` header works too, for callers that are not browsers.
5. `SecurityConfig` closes `/api/v1/user/**` and `/api/v1/admin/**` to unauthenticated callers; everything else — the whole read-only analytics API — stays public. User-owned endpoints read the id from `AuthenticatedUser.currentId()`, never from the request body.
6. `POST /api/v1/auth/signout` returns the same cookie expired (`Max-Age=0`). `POST /api/v1/auth/signout-everywhere` ("Sign out everywhere" in the nav bar) also increments the account's token generation, which ends every token issued to it; a password reset does the same.

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
| Cookie confidentiality | `HttpOnly=true` (no script can read the token); `Secure` whenever `CRAWLERNEST_PUBLIC_BASE_URL` is https (`CRAWLERNEST_JWT_COOKIE_SECURE=auto`, the default) |
| Early revocation | Token generation per account (V009): sign-out-everywhere and password reset end every earlier token; a deactivated or deleted account's tokens are refused |
| Rate limiting | Per client address and per account, in memory (`clawer.security.RateLimits`); see below |
| No signup enumeration | Sign-up answers 202 with one body for a new and a taken email; sign-in and sign-up spend the same bcrypt work either way |
| No default signing key | With `CRAWLERNEST_JWT_SECRET` unset a random per-process key is generated and logged as a warning; nothing ships with a key an attacker could know |

Covered by `JwtServiceTest`, `SecurityFilterChainIntegrationTest`, `AuthControllerCookieTest`, `CookieSecureSettingTest`, `TokenRevocationIntegrationTest` and `RateLimitFilterTest`.

---

## Non-Goals (Current Scope)

These are explicitly out of scope and should not be added without a deliberate scope change:

| Non-goal | Reason |
|---|---|
| RBAC / roles / permissions | Entity review uses an e-mail allowlist (`crawlernest.reviewer.emails`); no broader role model is needed |
| OAuth / OIDC / third-party login | No external identity provider integration needed |
| Refresh tokens / silent renewal | A 12-hour token and a re-login is acceptable at this maturity |
| Per-token revocation (denylist) | Would reintroduce shared server-side state; the per-account generation ends all of an account's tokens at once, which covers sign-out-everywhere and password reset |
| Frontend route protection | Routes render publicly; the data layer gating is the security boundary |
| Shared rate-limit store | Limits are counted per process; see Rate limiting below |
| Multi-factor authentication | Non-goal at current maturity |
| Email verification | Non-goal at current maturity |
| Account deletion / right to erasure | Non-goal for current scope |
| Per-user storage quota | Non-goal for current scope |
| Admin or user management UI | Non-goal for current scope |

---

## Deployment Requirements

### `CRAWLERNEST_JWT_SECRET` must be set

Unset, `JwtService` generates a key for the process and logs a warning. Everyone is then signed out on restart, and two instances do not accept each other's tokens. That is deliberate — the alternative, a default secret in the repository, would let anyone mint a token for any user.

**Required in any deployment:** `CRAWLERNEST_JWT_SECRET`, at least 32 bytes (`openssl rand -base64 32`). A shorter value is refused at startup rather than padded. `deploy/docker-compose.yml` declares it with `${CRAWLERNEST_JWT_SECRET:?}`, so the stack refuses to start without it.

### `Secure` cookie flag follows the public address

`crawlernest.jwt.cookie-secure` is `auto` by default: the cookie is `Secure` exactly when `CRAWLERNEST_PUBLIC_BASE_URL` starts with `https://`, so a TLS deployment gets it from the setting it needs anyway and a plain-http local run can still sign in. `true` forces it. `false` together with an https public URL is refused at startup.

**Before internet deployment:** serve behind TLS and set `CRAWLERNEST_PUBLIC_BASE_URL` to the https address.

### Rate limiting

`clawer.security.RateLimitFilter` answers `429` with `Retry-After` (defaults; each has a `CRAWLERNEST_RATE_LIMIT_*` variable):

| Limit | Default | Keyed by |
|---|---|---|
| Any `/api/**` request | 600 / minute | client address |
| `signin`, `signup`, `password-reset/*` | 20 / minute | client address |
| `signup` | 10 / hour | client address |
| Failed sign-ins | 10 / 15 minutes | account (email), from any address |
| Model-calling web routes (`/api/agent/chat`, `/tasks`, `/explain`) | 30 / minute and 500 / day, shared by the three, sliding windows | client address; enforced by the Next.js server (`src/lib/rateLimit.ts`, `CRAWLERNEST_AGENT_RATE_LIMIT_PER_MINUTE`, `_PER_DAY`) |
| Model calls by a signed-in user (`desk/essays/evaluate`, `desk/story/*generate`, `desk/chat/message`) | 20 / minute and 300 / day, sliding windows, weighted: an evaluation or generation counts 2, a chat turn 4 | the account (`ModelCallBudgetFilter`; `X-Model-Calls-Left-Today` on each answer) |

- **The client address.** `X-Forwarded-For` is believed only when the connection comes from `CRAWLERNEST_TRUSTED_PROXIES` (default loopback; the compose stack adds its network), and then the right-most hop that is not a trusted proxy counts. The Next.js auth proxy forwards the visitor's address. A trusted proxy that names no visitor is the frontend's own server-side rendering and is not limited by address.
- **Next.js exposed directly** keeps an `X-Forwarded-For` the visitor sent, so a visitor can choose their own key. Put a reverse proxy in front that replaces the header with the address it saw: `deploy/nginx/crawlernest.conf.example`, with `WEB_BIND=127.0.0.1`. The per-account failure limit does not depend on the address.
- **The failure limit is a lockout an attacker can trigger**, for at most 15 minutes, on an account whose email they know. That is the usual price of stopping a distributed password guess.
- **The agent routes are limited in Next.js, not in the API.** `/api/agent/chat` calls the model from the web server and the other two go to the agent API on 8090, so none of them passes the Java filter. The agent API itself bounds total concurrency and body size only, and must stay unreachable from outside (the compose file binds it to loopback).
- **Model calls are charged by what a request may cost, before it runs.** The weight is the most model calls the endpoint can make, so a request answered from a stored review, or refused for bad input, is still charged. That errs toward the budget, and keeps the charge independent of anything the request body can influence.
- **Sliding windows for model budgets, fixed windows elsewhere.** A fixed window lets through up to twice its limit around a boundary; acceptable for cheap requests, not for model calls. The sliding budget remembers each spend (at most `limit` entries per key), which is why the 600-a-minute general limit stays a single counter.
- **In memory, per process.** N API instances allow N times each limit, and a restart forgets the counts.

### DB credentials come from the environment

`application.properties` reads `${SPRING_DATASOURCE_USERNAME:test}` / `${SPRING_DATASOURCE_PASSWORD:test}`. The defaults are the local development database; a deployment sets the variables and nothing in the file applies. `deploy/docker-compose.yml` requires them with `${VAR:?}`.

### CORS is an explicit allowlist

`crawlernest.cors.allowed-origins` (default `http://localhost:3000`) is a comma-separated list; `*` is refused, because an API that allows credentials cannot accept every origin. Set `CRAWLERNEST_CORS_ALLOWED_ORIGINS` to the real frontend origin.

---

## Known Operational Limitations

| Limitation | Impact |
|---|---|
| Revocation is per account, not per token | Sign-out ends this browser's cookie only; `signout-everywhere` (or a password reset) ends every token for the account at once. Rotating `CRAWLERNEST_JWT_SECRET` still ends every token for everyone. |
| No refresh token | After the TTL the user is signed out and must sign in again; there is no silent renewal. |
| Restarting with no configured secret signs everyone out | Only when `CRAWLERNEST_JWT_SECRET` is unset. With it set, restarts are transparent. |
| No sign-out notification | Other browser tabs do not detect sign-out until the next API call. |
| No concurrent session limit | A user can hold tokens in several browsers at once; they cannot be listed, only ended together. |

---

## Password reset ("forgot password")

`POST /api/v1/auth/password-reset/request` and `.../confirm` (`clawer.auth.reset`), with the pages
`/forgot-password` and `/reset-password` linked from sign-in.

- **No enumeration.** The request answers with the same words for every email, registered or not.
- **The token.** 32 random bytes in the link. Only its SHA-256 is stored, in
  `warehouse.password_reset_token` (V006). It is good once, for `CRAWLERNEST_PASSWORD_RESET_TTL` (30
  minutes).
- **Other open links end.** A new request, or a successful reset, ends every other open link for that
  account.
- **Rate limit.** At most 3 links per account per hour. Over the limit, the answer is unchanged and nothing
  is sent.
- **Concurrent use.** Two uses of one link cannot both succeed; the confirm takes a row lock.
- **The new password** follows the same rule as sign-up (at least 8 characters).

**Delivery (`CRAWLERNEST_PASSWORD_RESET_DELIVERY`).**

| Value | What happens | Use |
|---|---|---|
| `smtp` | The link is emailed through `CRAWLERNEST_SMTP_HOST` / `_PORT` / `_USERNAME` / `_PASSWORD`, from `CRAWLERNEST_MAIL_FROM`. STARTTLS is required unless `CRAWLERNEST_SMTP_STARTTLS=false`. Missing host or from: the server logs an error and behaves as `none`. | Any deployment |
| `none` (default) | No token is created. The page says reset by email is not set up and to ask the administrator. | A deployment without email |
| `log` | The link is written to the API log, marked "DEV ONLY". The page says so. | Local development only: anyone who can read the log can reset any account that asks |

**Mail is sent on a background thread, not inside the request.** An SMTP round trip takes seconds, and only
a registered email triggers one. Sent inline, the response time alone would show a stranger which emails
have accounts. A failed send is logged without the address or the link.

**Before public exposure:**

- use `smtp` with a provider whose sending domain is verified (SPF/DKIM), or the mail lands in spam;
- set `CRAWLERNEST_PUBLIC_BASE_URL` so links point at the real site;
- never run with `log`.

A successful reset ends every token issued to the account before it (token generation, V009).

---

## Future Risks

### User data growth

`warehouse.saved_recommendation.result_json` stores full recommendation API payloads as JSONB. There is no per-user quota and no automatic expiry. Storage growth should be monitored as user count or save frequency increases.

### Token interception

Without TLS the cookie can be read in transit, and a stolen token is valid until it expires or its owner signs out everywhere. `Secure` follows the public address, so this is a risk only when the site is served over plain http to a non-loopback network.

### Secret handling

The signing key is the whole authentication system: anyone holding it can mint a token for any user. It must reach the process through the environment only, never a committed file, and rotating it is the only way to invalidate outstanding tokens.

### Account enumeration

Sign-in returns a uniform 401, and sign-up a uniform 202, whether or not the email has an account; both spend one bcrypt operation either way. Password reset answers the same words for every email. What remains is the per-account failure limit: its 429 appears only for an email that has had 10 failed sign-ins, which a caller who caused them already knows.

---

## Scaling Boundaries

| Boundary | Current Limit | Action Required |
|---|---|---|
| Auth scheme | Stateless HS256 tokens | Fine for multiple instances; all must share one secret |
| Token revocation | Per account (token generation) | A per-token denylist, if single-session sign-out must end a copied token |
| Cookie security | `Secure` when the public URL is https | Set `CRAWLERNEST_PUBLIC_BASE_URL` |
| DB credentials | Env vars with local-dev defaults | Set `SPRING_DATASOURCE_*` in every deployment |
| CORS | Allowlist, default `localhost:3000` | Set `CRAWLERNEST_CORS_ALLOWED_ORIGINS` |
| Rate limiting | In memory, per process | A shared store (Redis) if several API instances must share one limit |

---

## Related Documents

- [Architecture Overview — Minimal Identity Layer](ARCHITECTURE_OVERVIEW.md)
- [User Data Safety Review](USER_DATA_SAFETY_REVIEW.md)
- [API Surface — Auth API](API_SURFACE.md)
- [Data Flow — Identity and User Data Flows](DATA_FLOW.md)
