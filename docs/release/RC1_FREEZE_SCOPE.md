# RC-1 Regression Freeze Scope

Defines what is frozen, what is permitted, and what is explicitly blocked for the RC-1 release candidate. This document is the canonical reference for deciding whether a proposed change is in scope.

---

## Frozen (Do Not Change Without a Deliberate Unfreeze Decision)

Changes to the following areas require a conscious RC-1 unfreeze decision and re-validation:

### Aggregation Formula
- The deterministic ranking aggregation logic in `crawlernest/crawlernest-core/ranking_aggregation/`
- Weighting, tie-breaking, and source normalization behavior
- Output shape of `aggregated_ranking` rows

### Recommendation Scoring
- University categorization logic (reach / target / safety) in `RecommendationService.java`
- Candidate selection thresholds and pool construction
- IELTS, rank, and risk-profile input parsing
- The `RecommendationGroupResponse` payload shape

### Auth Model
- `HttpSession`-based session lifecycle (30-minute idle timeout)
- BCrypt password hashing via `spring-security-crypto`
- Session fixation prevention pattern in `AuthController`
- Cookie attributes: HttpOnly, SameSite=Lax
- The `AuthSchemaInitializer` DDL approach

### Diagnostics Behavior
- Semantics of all `/api/v1/diagnostics/*` endpoints
- Health check logic in `HealthService`
- Freshness calculation and staleness thresholds in `PIPELINE_HEALTH_MODEL.md`

### Explainability Payload Shape
- The `source_contributions` / `source_ranks` structure in ranking responses
- Any `explainability` field naming or nesting in API responses

### Saved Recommendation Schema
- PostgreSQL schema for `saved_recommendation` (columns, types, JSONB field names)
- `request_json` and `result_json` field structure
- `app_user` and `app_user_saved_university` table schema

### API Contract
- Response shapes for `/api/v1/rankings`, `/api/v1/subject-rankings`, `/api/v1/compare`, `/api/v1/universities/*`
- Auth API shapes: `/api/auth/signup`, `/api/auth/signin`, `/api/auth/signout`, `/api/auth/me`
- User data API shapes: `/api/user/saved-universities`, `/api/user/saved-recommendations`

---

## Permitted Changes

The following categories of changes are allowed without an unfreeze decision:

| Category | Examples |
|---|---|
| Documentation | New or updated `.md` files in `docs/`, README files, inline comments |
| Readonly diagnostics | Adding new read-only diagnostic endpoints that do not change existing ones |
| UX polish | Frontend text, label, color, spacing, animation adjustments |
| Bug fixes | Fixes to existing behavior that demonstrably contradicts the spec or causes incorrect output |
| Operational scripts | New helper scripts in `scripts/` that are readonly or purely additive |
| Test additions | New unit or integration tests that cover existing behavior |
| Dependency patch updates | Applying security patches within a pinned minor version (e.g., 3.2.3 → 3.2.4) |
| Environment documentation | `.nvmrc`, `docs/`, environment notes |

---

## Explicitly Blocked

The following are blocked for the duration of the RC-1 freeze:

| Blocked Area | Reason |
|---|---|
| RBAC / role-based access control | Adds auth complexity; requires schema, API, and UI changes |
| JWT migration / token refresh | Architectural change; incompatible with current session model |
| Recommendation engine redesign | Frozen by scope; existing scoring is the validated baseline |
| Distributed architecture / microservice split | Not in scope; single-node localhost is the deployment model |
| Redis session store | Infrastructure change; not justified at current scale |
| Kubernetes / Terraform / Docker Compose | Infrastructure not in scope for this repository |
| Autonomous agent mutation | Agents are read-only; no write-path agent capabilities |
| OAuth / external identity provider | No IdP integration planned |
| Realtime sync / WebSocket | No push infrastructure |
| Global frontend rewrite | Not in scope |
| Shared / collaborative saved lists | No multi-user sharing model |
| Admin dashboard / user management UI | No admin role exists |

---

## Decision Boundary

If a proposed change is ambiguous, apply this test:

1. **Does it change a frozen area's behavior, schema, or payload shape?** If yes — blocked.
2. **Does it add a new user-visible feature beyond current scope?** If yes — blocked until RC-2.
3. **Is it a fix to something that is demonstrably broken?** If yes — allowed, but must re-run `smoke_release.sh` and `./mvnw test`.
4. **Is it documentation, tests, or a readonly operational helper?** If yes — allowed.

---

## Re-Validation Requirements

Any change in the "permitted" category that touches the following files must re-run full validation (`smoke_release.sh`, `npm run build`, `./mvnw test`) before being considered complete:

- Any file under `crawlernest/servise_for_java/src/`
- Any file under `crawlernest/crawlernest-web/src/`
- `requirements.txt`
- `pom.xml`
- `package.json` / `package-lock.json`
