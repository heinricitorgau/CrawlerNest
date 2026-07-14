# Getting Started

Complete setup guide for running CrawlerNest locally from scratch.

> **Shortcut:** `./scripts/setup_from_scratch.sh` automates steps 1–4 and 6
> below (venv, PostgreSQL via local install or Docker, schema bootstrap,
> first data crawl, npm ci). Use this guide when you want to run the steps
> manually or when the script tells you something is missing.

## Prerequisites

| Dependency | Version | Notes |
|-----------|---------|-------|
| Python | 3.11+ | |
| PostgreSQL | 14+ | local install or WSL |
| Java JDK | 17 | set `JAVA_HOME` if multiple JDKs installed |
| Node.js | ≥ 20.9 | use `.nvmrc` with nvm |
| Maven | bundled | via `mvnw` wrapper |

---

## 1. Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 2. PostgreSQL

**Option A — Docker (easiest):**

```bash
docker compose -f docker-compose.postgres.yml up -d
```

This provides PostgreSQL 16 with the expected role, password, and database
already created, persisted in a named volume.

**Option B — local install (WSL / Ubuntu):**

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo service postgresql start
```

Create the development role and database:

```bash
sudo -u postgres psql -c "CREATE ROLE test WITH LOGIN PASSWORD 'test';"
sudo -u postgres createdb -O test clawer
```

Connection settings used throughout the project:

```
host:     localhost
port:     5432
database: clawer
user:     test
password: test
```

---

## 3. Bootstrap Schema

Run once per new environment. Safe to re-run.

```bash
python3 -m crawlernest.run_pipeline bootstrap-postgres \
  --pg-user test --pg-password test --pg-database clawer
```

---

## 4. Load Ranking Data

The repository ships with no ranking data — this step crawls it live from
the ranking source. Requests are spaced 10 seconds apart by default
(`--request-delay`); keep the pacing respectful and check the source site's
`robots.txt` and terms before increasing crawl volume. If the live fetch
fails, the pipeline falls back to your most recent local snapshot under
`crawlernest/crawlernest-kb/` (created automatically on each successful run).

```bash
./.venv/bin/python -m crawlernest.run_pipeline run \
  --limit 20 --ranking-year 2026 \
  --pg-user test --pg-password test --pg-database clawer
```

Verify:

```bash
PGPASSWORD=test psql -h localhost -U test -d clawer \
  -c "SELECT count(*) FROM analytics.v_aggregated_rankings_latest;"
```

---

## 5. Spring Boot API

Confirm `crawlernest/servise_for_java/src/main/resources/application.properties`:

```properties
spring.datasource.url=jdbc:postgresql://localhost:5432/clawer
spring.datasource.username=test
spring.datasource.password=test
```

---

## 6. Frontend

```bash
nvm use          # optional: select Node version from .nvmrc
cd crawlernest/crawlernest-web
npm ci
cd ../..
```

---

## 7. Start All Services

```bash
./scripts/start_localhost.sh
```

The script starts PostgreSQL, Spring Boot, and the Next.js frontend in sequence.
Press `Ctrl+C` to stop everything.

**Service URLs:**

```
Web:       http://localhost:3000
API:       http://localhost:8080
Agent API: http://localhost:8090
```

**Main pages:**

```
Global rankings:  http://localhost:3000/rankings
Subject rankings: http://localhost:3000/subject-rankings
Analytics:        http://localhost:3000/analytics
Agent:            http://localhost:3000/agent
Sign up / in:     http://localhost:3000/signup
```

---

## 8. Smoke Check

```bash
./scripts/smoke_local_stack.sh
curl -i "http://localhost:8080/api/v1/rankings?page=1&pageSize=5"
curl -I "http://localhost:3000/rankings"
```

---

## Subject Rankings

Load QS 2026 subject data (run once per subject):

```bash
./.venv/bin/python -m crawlernest.run_pipeline run-qs-subject \
  --subject computer-science --year 2026 \
  --pg-user test --pg-password test --pg-database clawer

./.venv/bin/python -m crawlernest.run_pipeline run-qs-subject \
  --subject electrical-engineering --year 2026 \
  --pg-user test --pg-password test --pg-database clawer

./.venv/bin/python -m crawlernest.run_pipeline run-qs-subject \
  --subject business-management --year 2026 \
  --pg-user test --pg-password test --pg-database clawer
```

Verify:

```bash
python3 crawlernest/scripts/smoke_subject_rankings.py
```

---

## Manual Service Start

If you need to start services individually:

```bash
# API
cd crawlernest/servise_for_java
./mvnw -Dmaven.test.skip=true spring-boot:run

# Frontend
cd crawlernest/crawlernest-web
npm run dev

# Frontend with mock agent provider
AGENT_MODEL_PROVIDER=mock npm run dev
```

For Ollama / OpenAI agent setup, see [Agent Model Integration](agent/AGENT_MODEL_INTEGRATION.md).

---

## Common Issues

**Port 8080 already in use:**

```bash
lsof -i :8080
kill -9 <PID>
```

**UI has no data:** Run the pipeline (Step 4), then reload the page.

**Subject ranking table is empty:** Run the subject loader for that subject, then confirm the Java API is running:

```bash
curl "http://localhost:8080/api/v1/subject-rankings?subject=computer-science&year=2026"
```

**Docker not found:** Docker is not required for local development. Use the PostgreSQL install in Step 2.

**Multiple JDKs installed:** Set `JAVA_HOME` to the Java 17 JDK before starting the backend.

---

## Recommended Workflow

```
1. Start PostgreSQL
2. Run data pipeline (Steps 3–4)
3. Start services (Step 7)
4. Open /rankings or /subject-rankings
5. When something looks wrong: check warehouse/analytics views before debugging the UI
```

CrawlerNest is correctness-first. Data problems are almost always upstream of the UI.

---

## CI / CD

```
.github/workflows/release-smoke.yml   — full stack smoke check
.github/workflows/data-quality.yml    — fixture-mode data quality
```

Operational scripts:

```
scripts/run_daily_pipeline.sh
scripts/export_system_snapshot.py
scripts/export_metadata_bundle.sh
scripts/smoke_local_stack.sh
```
