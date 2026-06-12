# CrawlerNest v0.1 — Demo Script

**Version:** v0.1 Demo Release
**Audience:** Engineering reviewers, technical stakeholders, milestone evaluation

All demos assume the local stack is already running. See [Prerequisites](#prerequisites) before starting.

---

## Prerequisites

Confirm all services are up before any demo:

```bash
# PostgreSQL
pg_isready -h localhost -p 5432 -U test -d clawer

# API health
curl -s http://localhost:8080/api/v1/health | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print('postgres:', d['data']['postgres_connected'])"

# Frontend
curl -so /dev/null -w "%{http_code}" http://localhost:3000
```

Expected: `accepting connections`, `postgres: True`, `200`

If services are not running:

```bash
./scripts/start_localhost.sh
```

---

## 3-Minute Demo Flow

**Goal:** Show the system is operational end-to-end in the shortest possible path.

### Step 1 — Health check (20 seconds)

**Command:**
```bash
curl -s http://localhost:8080/api/v1/health | python3 -m json.tool
```

**Expected output:**
```json
{
  "status": "ok",
  "data": {
    "postgres_connected": true,
    "canonical_university_count": ...,
    "aggregated_ranking_count": 1499
  }
}
```

**Explain verbally:**
"The API is up, PostgreSQL is connected, and we have 1,499 aggregated universities in the analytics view. This is a live read from the database."

---

### Step 2 — Global rankings (60 seconds)

**Browser action:** Open `http://localhost:3000/rankings`

**Expected output:** Table with rank, university name, country, composite score. Pagination controls visible.

**Explain verbally:**
"The rankings page reads from `analytics.v_aggregated_rankings_latest` — a PostgreSQL view that aggregates QS and THE ranking data. Each row shows a deterministic composite rank. We can filter by country or region, and search by name."

**Optional:** Type "MIT" in the search box and show the result.

---

### Step 3 — System status (40 seconds)

**Browser action:** Open `http://localhost:3000/system-status`

**Expected output:** Data Freshness badges (FRESH/STALE), Health Overview, Rankings Diagnostics, Subject Coverage.

**Explain verbally:**
"The system status page is a live diagnostic dashboard. It reads from five API endpoints — health, freshness, ranking diagnostics, subject diagnostics, and operational status — and surfaces them in one view. This is the primary observability surface."

---

## 5-Minute Demo Flow

**Goal:** Show rankings, subject rankings, diagnostics, and system status with light narration.

### Step 1 — Startup and health (45 seconds)

**Command:**
```bash
./scripts/smoke_local_stack.sh
```

**Expected output:** Each check prints `OK   ...`. Final line: `Local stack smoke test passed.`

**Explain verbally:**
"The smoke test confirms PostgreSQL is reachable, the API responds on `/health`, the frontend is up, and the ranking count is non-zero. This is the pre-demo gate check — if this passes, the demo is ready."

---

### Step 2 — Global rankings browser (60 seconds)

**Browser action:** Open `http://localhost:3000/rankings`

**Demonstrate:**
1. Scroll through top 10 rows — point out rank, university, country, composite score
2. Select a country filter (e.g., United States)
3. Reset and search by name (e.g., "Cambridge")

**Explain verbally:**
"The rankings are derived from QS 2026 data with THE as a second source. The composite score is computed by the aggregation layer and stored in PostgreSQL. The frontend reads through a same-origin proxy with `no-store` cache and live polling so data updates surface within seconds."

---

### Step 3 — Subject rankings (60 seconds)

**Browser action:** Open `http://localhost:3000/subject-rankings`

**Demonstrate:**
1. Select "Computer Science" from the subject selector
2. Show the ranked university list
3. Switch to "Electrical Engineering"

**Explain verbally:**
"Subject rankings are a separate pipeline path. They come from QS subject data, stored in `warehouse.subject_ranking_record`, and served from `analytics.v_subject_rankings_latest`. Subject rankings do not affect the global composite score — they are a parallel read path."

---

### Step 4 — Diagnostics via API (45 seconds)

**Command:**
```bash
curl -s http://localhost:8080/api/v1/diagnostics/rankings | python3 -m json.tool | head -30
```

**Expected output:** JSON with `aggregated_count`, `latest_aggregation_run`, `api_ready`.

**Follow-up:**
```bash
curl -s http://localhost:8080/api/v1/freshness | python3 -m json.tool
```

**Explain verbally:**
"The diagnostics API exposes pipeline readiness as structured JSON. We can see the last aggregation run ID, the timestamp, and whether the API considers itself ready to serve rankings. The freshness endpoint shows per-source timestamps and stale flags."

---

### Step 5 — System status dashboard (30 seconds)

**Browser action:** Open `http://localhost:3000/system-status`

**Explain verbally:**
"The system status page is the operational dashboard. It aggregates health, freshness, ranking and subject diagnostics, and shows data quality metrics including unresolved entity count, drift warnings, and regression summary."

---

## 10-Minute Technical Walkthrough

**Goal:** Full technical review covering startup, rankings, subject rankings, explainability, diagnostics, system status, and CI smoke.

---

### Section 1 — Startup flow (90 seconds)

**Context:** Explain the local stack topology.

```
localhost:8080 — Spring Boot API (servise_for_java)
localhost:3000 — Next.js frontend (crawlernest-web)
localhost:5432 — PostgreSQL (clawer database)
```

**Command:**
```bash
./scripts/start_localhost.sh
```

**Explain verbally:**
"The startup script checks PostgreSQL is running, verifies Node.js >= 20.9, confirms `node_modules` exists, then starts Spring Boot with Maven and Next.js. The API and frontend are two separate processes. The database is PostgreSQL with two schemas: `warehouse` for raw pipeline output and `analytics` for the aggregated product views."

---

### Section 2 — Rankings demo (90 seconds)

**API call:**
```bash
curl -s "http://localhost:8080/api/v1/rankings?page=1&pageSize=5" | python3 -m json.tool
```

**Expected:** JSON with `items` array, each containing `display_rank`, `composite_score`, `source_count`, `source_ranks_json`.

**Browser:** Open `http://localhost:3000/rankings`

**Explain verbally:**
"Each university in the rankings has a `composite_score` computed by the aggregation layer. The score is stored in `analytics.aggregated_rankings` and exposed read-only by the API. The `source_ranks_json` field shows the individual QS and THE ranks before aggregation. We have 1,499 aggregated universities from QS 2026."

---

### Section 3 — Subject rankings demo (90 seconds)

**API call:**
```bash
curl -s "http://localhost:8080/api/v1/subject-rankings?subject=computer-science&pageSize=5" | python3 -m json.tool
```

**Browser:** Open `http://localhost:3000/subject-rankings`

**Explain verbally:**
"Subject rankings are a v0.1 MVP. We ingest QS subject data via `run-qs-subject`, which writes to `warehouse.subject_ranking_record`. The analytics view `v_subject_rankings_latest` serves the UI. Subject rankings are independent from the global aggregation — they show QS subject-specific ranks, not the composite score."

**Explain the subject diagnostic:**
```bash
curl -s http://localhost:8080/api/v1/diagnostics/subjects | python3 -m json.tool
```

---

### Section 4 — Diagnostics demo (90 seconds)

Walk through the full diagnostics surface:

**Health:**
```bash
curl -s http://localhost:8080/api/v1/health | python3 -m json.tool
```
"PostgreSQL connected, canonical university count, aggregated ranking count."

**Freshness:**
```bash
curl -s http://localhost:8080/api/v1/freshness | python3 -m json.tool
```
"Per-source freshness timestamps and stale flags. QS 2026 is fresh."

**Data quality:**
```bash
curl -s "http://localhost:8080/api/v1/diagnostics/data-quality" | python3 -m json.tool
```
"4 unresolved canonical entities from QS 2026 ingestion. 0 drift warnings. The regression summary shows coverage distribution."

**Source agreement:**
```bash
curl -s "http://localhost:8080/api/v1/diagnostics/source-agreement" | python3 -m json.tool
```
"Cross-source QS/THE agreement metrics. Shows rank difference, largest disagreement outliers, and source overlap."

---

### Section 5 — Explainability demo (60 seconds)

**Context:** Pick any university ID from the rankings response.

```bash
# Get a university ID
UNIV_ID=$(curl -s "http://localhost:8080/api/v1/rankings?pageSize=1" | \
  python3 -c "import json,sys; print(json.load(sys.stdin)['items'][0]['id'])")

# Explainability
curl -s "http://localhost:8080/api/v1/rankings/${UNIV_ID}/explain" | python3 -m json.tool
```

**Expected:** JSON with `source_contributions`, `weighted_inputs`, `normalized_scores`, `missing_source_penalties`, `formula_note`.

**Explain verbally:**
"The explainability endpoint reads the stored aggregation output for a specific university and reconstructs the reasoning: which sources contributed, what weight each received, and what the formula note says. It does not recalculate — it reads stored values. This lets reviewers audit why any university has its current rank."

```bash
# Source comparison
curl -s "http://localhost:8080/api/v1/universities/${UNIV_ID}/source-comparison" | python3 -m json.tool
```

"Source comparison shows QS rank, THE rank, rank spread, and confidence level side by side."

---

### Section 6 — System status demo (30 seconds)

**Browser:** Open `http://localhost:3000/system-status`

**Explain verbally:**
"The system status page is a read-only operational dashboard. It aggregates the five diagnostic API endpoints into a single view: health, freshness, ranking diagnostics, subject diagnostics, and operational status. In a real operational context, this is where an operator would start when investigating pipeline issues."

---

### Section 7 — Smoke and release demo (60 seconds)

**Command:**
```bash
./scripts/smoke_release.sh
```

**Expected output:**
```
[1/8] Local environment verification (readonly)...
OK   Local environment verification completed
[2/8] Spring Boot compile (no tests)...
OK   Spring Boot compile: BUILD SUCCESS
[3/8] Next.js build...
OK   Next.js build: success (Node v20.x.x)
[4/8] Python syntax check...
OK   Python syntax: all files OK
[5/8] Pipeline health diagnostics (readonly)...
OK   Pipeline health diagnostics completed
[6/8] Snapshot comparison validation (readonly fixtures)...
OK   Snapshot comparison fixture validation completed
[7/8] Failure-state fixture validation (readonly fixtures)...
OK   Failure-state fixture validation completed
[8/8] API endpoint checks (optional — requires Spring Boot on http://localhost:8080)...
OK   /api/v1/health: HTTP 200
...
Results: N passed, 0 failed
Release smoke passed.
```

**Explain verbally:**
"The release smoke script validates the full build artifact chain without modifying any data. Spring Boot compiles, Next.js builds, Python syntax is checked, fixture-mode diagnostics pass, and if the API is running, endpoint checks confirm HTTP 200s. This is what CI runs on every push to main."

---

*For the CI perspective, point to GitHub Actions: `release-smoke.yml` and `data-quality.yml` both run without a live database.*

---

## Quick Reference — Service URLs

| Service | URL |
|---------|-----|
| Web app | http://localhost:3000 |
| API | http://localhost:8080 |
| Global rankings | http://localhost:3000/rankings |
| Subject rankings | http://localhost:3000/subject-rankings |
| Recommendations | http://localhost:3000/recommendations |
| System status | http://localhost:3000/system-status |

## Quick Reference — Key API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/health` | Service health and DB connectivity |
| `GET /api/v1/freshness` | Per-source freshness |
| `GET /api/v1/rankings` | Global rankings list |
| `GET /api/v1/subject-rankings` | Subject rankings list |
| `GET /api/v1/diagnostics/rankings` | Ranking pipeline diagnostics |
| `GET /api/v1/diagnostics/subjects` | Subject diagnostics |
| `GET /api/v1/diagnostics/data-quality` | Data quality metrics |
| `GET /api/v1/diagnostics/source-agreement` | Cross-source agreement |
| `GET /api/v1/rankings/{id}/explain` | Aggregation explainability |
| `GET /api/v1/universities/{id}/source-comparison` | Source evidence comparison |
