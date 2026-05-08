# Demo Checklist

Use this checklist before any demo or handover. Each step maps to an existing script or command. Work top-to-bottom; later steps depend on earlier ones.

---

## Prerequisites

- [ ] Python virtual environment activated: `source .venv/bin/activate`
- [ ] Node.js ≥ 20.9 available (check with `node --version`; use `nvm use 20` if needed)
- [ ] `node_modules` installed: `cd crawlernest/crawlernest-web && npm install && cd ../..`

---

## 1. PostgreSQL

- [ ] Service is running

  ```bash
  pg_isready -h localhost -p 5432 -U test -d clawer
  ```

  If not running:

  ```bash
  sudo service postgresql start
  ```

- [ ] Login works

  ```bash
  PGPASSWORD=test psql -h localhost -U test -d clawer -c "SELECT 1;"
  ```

---

## 2. Bootstrap schemas and seed data

Run once in a new environment (safe to re-run):

```bash
./.venv/bin/python -m crawlernest.run_pipeline bootstrap-postgres \
  --pg-user test --pg-password test --pg-database clawer
```

- [ ] Output shows `ranking_subject_count` ≥ 1

---

## 3. Load global ranking data

```bash
./.venv/bin/python -m crawlernest.run_pipeline run \
  --limit 30 --ranking-year 2026 \
  --pg-user test --pg-password test --pg-database clawer
```

- [ ] Command exits 0
- [ ] Data visible in the view:

  ```bash
  PGPASSWORD=test psql -h localhost -U test -d clawer \
    -c "SELECT count(*) FROM analytics.v_aggregated_rankings_latest;"
  ```

---

## 4. Load subject ranking data

```bash
./.venv/bin/python -m crawlernest.run_pipeline run-qs-subject \
  --subject computer-science --year 2026 \
  --pg-user test --pg-password test --pg-database clawer

./.venv/bin/python -m crawlernest.run_pipeline run-qs-subject \
  --subject electrical-engineering --year 2026 \
  --pg-user test --pg-password test --pg-database clawer
```

- [ ] Both commands exit 0

---

## 5. Spring Boot API

Start (if not already running via `start_localhost.sh`):

```bash
cd crawlernest/servise_for_java
./mvnw -Dmaven.test.skip=true spring-boot:run
```

- [ ] Server is accepting requests:

  ```bash
  curl -s http://localhost:8080/api/v1/health | python3 -c \
    "import json,sys; d=json.load(sys.stdin); print('postgres:', d['data']['postgres_connected'])"
  ```

---

## 6. Next.js frontend

Start (if not already running via `start_localhost.sh`):

```bash
cd crawlernest/crawlernest-web
npm run dev
```

- [ ] Dev server is up: `curl -so /dev/null -w "%{http_code}" http://localhost:3000`

---

## 7. Global rankings page

- [ ] Open `http://localhost:3000/rankings`
- [ ] Table rows are visible with rank, university name, country, score
- [ ] Page/filter controls respond

---

## 8. Subject rankings page

- [ ] Open `http://localhost:3000/subject-rankings`
- [ ] Subject selector shows "Computer Science" and "Electrical Engineering"
- [ ] Selecting a subject loads ranked universities

---

## 9. Recommendations page

- [ ] Open `http://localhost:3000/recommendations`
- [ ] Country or filter input returns a list of universities
- [ ] Results are non-empty and ordered

---

## 10. System status page

- [ ] Open `http://localhost:3000/system-status`
- [ ] "Data Freshness" section shows per-source `FRESH` / `STALE` / `MISSING` badges
- [ ] "Health Overview" shows `postgres_connected: true`
- [ ] "Rankings Diagnostics" shows source counts and ingestion log
- [ ] "Subject Coverage" shows row counts per subject

---

## 11. Smoke test (automated)

```bash
./scripts/smoke_local_stack.sh
```

- [ ] All steps print `OK   …`
- [ ] Final line: `Local stack smoke test passed.`

---

## 12. Release smoke test (build only)

Run this before pushing or handing over — no running services required:

```bash
./scripts/smoke_release.sh
```

- [ ] Spring Boot compile: `BUILD SUCCESS`
- [ ] Next.js build: `○` and `ƒ` route lines visible, no errors
- [ ] Python syntax: `OK`
- [ ] Final line: `Release smoke passed.`

---

## Quick reference — service URLs

| Service   | URL                          |
|-----------|------------------------------|
| Web app   | http://localhost:3000        |
| API       | http://localhost:8080        |
| Rankings  | http://localhost:3000/rankings |
| Subjects  | http://localhost:3000/subject-rankings |
| Recommend | http://localhost:3000/recommendations |
| Status    | http://localhost:3000/system-status |
