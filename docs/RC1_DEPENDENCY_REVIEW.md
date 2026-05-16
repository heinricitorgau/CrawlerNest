# RC-1 Dependency Review

Covers the frontend (Next.js), backend (Spring Boot / Maven), and Python runtime dependencies as of RC-1. The goal is to identify risks, not to upgrade everything — only blockers warrant action.

---

## Frontend (Next.js)

**Source:** `crawlernest/crawlernest-web/package.json` + `package-lock.json` (lockfileVersion 3)

### Production Dependencies

| Package | Declared | Resolved | Assessment |
|---|---|---|---|
| `next` | `^16.2.6` | 16.2.6 | Core framework dependency. The local frontend guidance warns that this line has breaking changes. **Treat as frozen for RC-1 and upgrade only with a deliberate changelog review.** |
| `react` | `^19.2.6` | 19.2.6 | React 19 stable. Matches `react-dom`. No known issues for this usage pattern. |
| `react-dom` | `^19.2.6` | 19.2.6 | Locked with `react`. Good. |

### Dev Dependencies

| Package | Declared | Resolved | Assessment |
|---|---|---|---|
| `typescript` | `^5` | 5.9.3 | TypeScript 5.x stable. `strict: true` enforced in `tsconfig.json`. No issues. |
| `tailwindcss` | `^4` | 4.2.4 | Tailwind v4. Used via `@tailwindcss/postcss`; upgrade the pair together. |
| `jest` | `^30.3.0` | 30.4.0 | Used with `jest-environment-jsdom`. |
| `@testing-library/react` | `^16.3.2` | — | Correct for React 19. |
| `eslint` | `^9` | 9.39.4 | ESLint 9 (flat config format). Config in `eslint.config.mjs`. |
| `eslint-config-next` | `16.2.1` | 16.2.1 | Pinned beside the framework line. **Keep synchronized with `next` version.** |

### Risk Assessment

| Risk | Severity | Notes |
|---|---|---|
| `next@16.2.6` framework-line drift | Medium | The local frontend guidance already treats this line as behaviorally sensitive. Stable for the current feature set, but not a dependency to auto-update during freeze. |
| `^` prefix allows minor/patch drift on `npm install` | Low | `package-lock.json` v3 pins exact resolved versions. Always use `npm ci` in CI/automation. |
| Node major mismatch | Low | `.nvmrc` now pins Node 20 for local shells, while automation still verifies `>=20.9`. Use `nvm use` before install/build. |
| `eslint-config-next` pinned to `16.2.1` | Low | Must stay synchronized with `next`. Acceptable for RC-1 freeze. |

---

## Backend (Spring Boot / Maven)

**Source:** `crawlernest/servise_for_java/pom.xml`

### Core Dependencies (managed via Spring Boot BOM 3.2.3)

| Dependency | Version Source | Assessment |
|---|---|---|
| `spring-boot-starter-web` | SB 3.2.3 BOM | Spring MVC + embedded Tomcat. Stable LTS. |
| `spring-boot-starter-data-jpa` | SB 3.2.3 BOM | Hibernate 6.x (ORM) + Spring Data. JSONB support is native in Hibernate 6. |
| `postgresql` (JDBC driver) | SB BOM | Runtime scope. Matches PostgreSQL 16. |
| `spring-security-crypto` | SB BOM | BCrypt only. No full Spring Security chain. Session is pure `HttpSession`. |
| `spring-boot-starter-test` | SB BOM | JUnit 5 + Mockito + AssertJ. Test scope only. |

### Version Drift Risks

| Risk | Severity | Notes |
|---|---|---|
| Spring Boot 3.2.3 is not the latest 3.2.x patch | Low | 3.2.x patch releases are security/bug fixes. RC-1 freeze: acceptable. Track and apply patch upgrades post-RC-1. |
| Java 17 (not Java 21 LTS) | Low | Java 17 is still supported LTS. Java 21 would be the next LTS upgrade. Not urgent for RC-1. |
| `net.bytebuddy.experimental=true` in Surefire config | Low | Required for Mockito + Java 17. Bytebuddy does not natively support Java 17 without this flag. Acceptable workaround; no action needed. |
| No explicit version pins in `pom.xml` (BOM-managed) | Low-positive | All versions flow from the Spring Boot BOM — this is the correct pattern. Avoids version conflicts. |

### Notable Absence

- No Liquibase / Flyway for schema management. Identity table creation is handled by `AuthSchemaInitializer` (application-level DDL at startup). This is a known operational limitation documented in [`AUTH_LIMITATIONS.md`](AUTH_LIMITATIONS.md).
- No Redis, no JWT library. Session model is intentionally minimal.

---

## Python Runtime

**Source:** `requirements.txt` (root and `deployment-support/lobster-01/requirements.txt` — identical content)

### Dependencies

| Package | Pinned Version | Assessment |
|---|---|---|
| `aiohttp` | 3.13.3 | Async HTTP client for crawler operations. Pinned. Stable. |
| `requests` | 2.32.5 | Sync HTTP. Pinned. Stable. |
| `psycopg2-binary` | 2.9.11 | PostgreSQL adapter. Binary wheel. Pinned. Works with PostgreSQL 16. |
| `fastapi` | 0.135.2 | Local Python API utilities. Pinned. |
| `uvicorn` | 0.42.0 | ASGI server for FastAPI. Pinned. |
| `pydantic` | 2.12.5 | Pydantic v2. Pinned. Compatible with FastAPI 0.135. |
| `starlette` | 1.0.0 | Underlying framework for FastAPI. Pinned. **See risk note below.** |
| `pytest` | 9.0.2 | Test runner. Pinned. |

### Risk Assessment

| Risk | Severity | Notes |
|---|---|---|
| `starlette==1.0.0` — very recent major version | Medium | Starlette 1.0.0 is a recent release and represents a significant versioning step. The combination with `fastapi==0.135.2` should be tested together. Currently working; monitor for breakage on reinstall. |
| `psycopg2-binary` not recommended for production | Low | Upstream recommends building from source for production. For local/demo use, binary is acceptable. |
| No `pip` lockfile (no `pip freeze` equivalent committed) | Low | `requirements.txt` pins exact versions, which is adequate. No secondary lockfile (`pip.lock`, `poetry.lock`) is in use. Reinstall is reproducible from pinned versions. |
| Python 3.12 not pinned in requirements | Low | `requirements.txt` specifies packages but not Python version. Documented in environment freeze. |

---

## Version Pinning Summary

| Layer | Pinning Mechanism | Status |
|---|---|---|
| Frontend packages | `package-lock.json` v3 (exact resolved) | Strong — use `npm ci` |
| Java dependencies | Spring Boot BOM 3.2.3 (ranges managed) | Strong |
| Python packages | `requirements.txt` (exact pins) | Adequate |
| Node.js version | No `.nvmrc` | Weak — document gap |
| Java version | `<java.version>17</java.version>` in pom.xml | Strong |
| Python interpreter | Not pinned | Weak — document gap |

---

## Optional Future Cleanup (post-RC-1, no action required now)

- Consider `pip-tools` or `uv` for a true Python lockfile if dependency reproducibility becomes critical.
- Evaluate Spring Boot 3.2.x patch upgrade cadence post-freeze.
- Evaluate Java 21 migration on the next major development cycle.
- `starlette==1.0.0` warrants a sanity check on the next full reinstall to confirm the FastAPI/Starlette combination remains stable.
