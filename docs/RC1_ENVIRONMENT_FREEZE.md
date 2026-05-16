# RC-1 Environment Freeze

Defines the environment that RC-1 is developed, tested, and smoke-checked against. Environments outside these bounds are not supported and may fail silently.

---

## Required Versions

| Component | Required | Verified Version | Notes |
|---|---|---|---|
| Java (JDK) | 17 (LTS) | 17.0.18 (Ubuntu, OpenJDK) | Must be JDK 17. JDK 21+ not tested. JDK < 17 will fail (`sealed` classes, records). |
| Maven | 3.9.x (via wrapper) | 3.9.6 | Use `./mvnw` — do not rely on system Maven. Wrapper JAR is committed at `.mvn/wrapper/maven-wrapper.jar`. |
| Node.js | ≥ 20.9.0 (LTS) | 20.20.2 | Must be ≥ 20.9 (enforced by `verify_local_environment.sh`). Node 22 not tested. Use nvm if managing versions. |
| npm | ≥ 10 | 10.8.2 | Installed with Node.js. Do not use yarn or pnpm — `package-lock.json` v3 is canonical. |
| Python | 3.12.x | 3.12.3 | Pipeline scripts and diagnostics. Python 3.10+ likely works; < 3.10 untested. |
| PostgreSQL | 16.x | 16.13 (Ubuntu) | Schema uses `warehouse` schema and JSONB. PostgreSQL 14+ likely works; 16 is the verified version. |
| psycopg2 | 2.9.11 | 2.9.11 (binary) | Must be importable in the active Python environment. |

---

## Verified Environments

| Environment | Status | Notes |
|---|---|---|
| Ubuntu 24.04 (WSL2, x86-64) | Verified in this RC-1 pass | Primary development environment. Full validation results are recorded in `RC1_VALIDATION_RESULTS.md`. |
| Lobster-01 production node | Documented, not re-validated in this RC-1 pass | Debian-based deployment path documented in `docs/deployment/Lobster_01_Deployment_Guide.md`. |
| macOS (Apple Silicon) | Not verified for RC-1 | May work; `psycopg2-binary` wheel availability differs. Not smoke-checked. |
| Windows (native, no WSL) | Not supported | No `bash` for scripts; PostgreSQL socket paths differ; not in scope. |
| Docker Compose | Not supported | No `docker-compose.yml` provided. Not in scope for RC-1. |

---

## Localhost Assumptions

The following are hardcoded in `application.properties` and implicit in scripts:

- PostgreSQL at `localhost:5432` in Spring Boot config; helper scripts default to `127.0.0.1:5432`
- Database `clawer`, schema `warehouse`, user/password `test/test`
- Spring Boot on `localhost:8080`
- Next.js on `localhost:3000`
- No TLS on either service
- Session cookies are HttpOnly, SameSite=Lax, no `Secure` flag (localhost does not require HTTPS for cookies)
- No reverse proxy or load balancer between Next.js and Spring Boot

These assumptions are appropriate for a local or single-node demo environment. They are **not** production-ready and are documented in [`AUTH_LIMITATIONS.md`](AUTH_LIMITATIONS.md).

---

## Non-Supported Environments

The following are explicitly out of scope for RC-1:

- **Redis / distributed session store:** Sessions are in-memory (`HttpSession`). Multi-node or container restart will lose sessions.
- **JWT / OAuth / external IdP:** Not implemented. Cookie-only session model.
- **HTTPS / TLS termination:** No Secure cookie flag. Only valid on localhost.
- **Windows native (no WSL):** Shell scripts use bash; not compatible.
- **Python < 3.10:** Untested. Type annotations and match statements may fail.
- **Node.js < 20.9:** Explicitly rejected by `verify_local_environment.sh`.
- **JDK < 17:** Spring Boot 3.2 requires Java 17+.

---

## Known Incompatibilities

| Area | Issue |
|---|---|
| Python `psycopg2` vs active env | System Python may differ from `.venv` Python. `verify_local_environment.sh` warns but does not fail. Pipeline scripts should run inside `.venv`. |
| Node version management | `.nvmrc` pins the local project line to Node 20; developers using nvm should run `nvm use`. |
| `application.properties` credentials | `username=test / password=test` are hardcoded localhost credentials. These must be externalized before any non-local deployment. |
| Maven wrapper jar | `.mvn/wrapper/maven-wrapper.jar` is committed intentionally (makes `./mvnw` work without a pre-installed Maven). This is a deliberate exception to the "no binaries" rule. |
| Spring Boot port conflict | If port 8080 is in use, startup fails silently. `smoke_release.sh` warns but does not block. |

---

## Minimum Hardware Assumptions

| Resource | Minimum | Notes |
|---|---|---|
| RAM | 4 GB | Spring Boot JVM + Next.js dev server + PostgreSQL. 8 GB recommended for comfort. |
| Disk | 2 GB free | PostgreSQL data, venv, node_modules (~500 MB), Maven local repo (~300 MB). |
| CPU | Any x86-64 | ARM (Apple Silicon, AWS Graviton) not verified. |
| Network | Localhost only | No external network required to run. Pipeline data fetch is a separate operation. |

---

## Setup Reproducibility Notes

1. **Clone → verify:** Run `scripts/verify_local_environment.sh` immediately after clone to confirm the environment before anything else.
2. **Python venv:** Create with `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`. Activate before running pipeline scripts.
3. **Node deps:** run `nvm use`, then `cd crawlernest/crawlernest-web && npm ci` (uses lockfile exactly; prefer over `npm install` for reproducibility).
4. **PostgreSQL bootstrap:** Schema init is handled by `AuthSchemaInitializer` on Spring Boot startup (via `ApplicationReadyEvent`). No manual SQL migrations are required for the identity tables. The ranking schema must be present (loaded by the data pipeline).
5. **Build artifacts:** `crawlernest/servise_for_java/target/`, `node_modules/`, `.next/`, `.venv/`, generated operational evidence, and `tmp/` are excluded from git. See [`RC1_RELEASE_HYGIENE.md`](RC1_RELEASE_HYGIENE.md).
6. **Maven wrapper:** Use `./mvnw` not `mvn`. The wrapper `.jar` is committed and downloads the correct Maven version on first use.
