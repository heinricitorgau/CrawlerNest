# Engineering Validation & Maintenance Guide

This document defines CrawlerNest's testing flows, API contract invariants, recommendation validation, and routine maintenance principles. It ensures the system remains strictly deterministic, explainable, and scalable.

---

## 1. Schema Source of Truth

**PostgreSQL is the ONLY operational datastore.**
- The runtime schema is located in `crawlernest/crawlernest-schema/postgresql_schema.sql` and its associated DDL files (`entity_resolution_postgresql.sql`, etc.).
- Legacy SQLite files (`.db`) are strictly offline archives.
- New fields MUST define purpose, type, nullability, and indexing strategy.
- All schema changes must retain backward compatibility (migrations, defaults, or backfills).

### Rollback Principles
- **Always retain an executable back-out path.** Schema changes must include a `DOWN` migration script.
- **Isolate the Blast Radius:** If a new schema causes upstream ingestion failures, isolate the failure to an incremental batch. Restore the `warehouse` baseline from the last known-good checkpoint before re-running the modified ingestion.

---

## 2. API Contract Invariants

To safely power the Web Platform, our Java Spring Boot API must adhere to the following invariants:

- **JSON Envelope:** Every successful response must be wrapped in `{"success": true, "data": ..., "metadata": ...}`.
- **Strict Typing:** All data transfers happen via strongly-typed DTOs (e.g., `RankingDTO`, `UniversityDTO`). The `data` body shape for a given endpoint must never unexpectedly shift.
- **Data Encapsulation:** Internal tracking fields (like the raw integer `type` of a ranking or the internal auto-increment ID) must be obfuscated or mapped to frontend-ready string fields (`canonicalUniversityId`, `rankingYear`).
- **Idempotency:** Re-issuing the same GET request or POST Comparison payload must return identical results.

---

## 3. Recommender Validation Logic

CrawlerNest utilizes a calibrated hybrid multi-factor recommendation system (`decision_engine v3`).

### Category Correctness Expectations
All evaluated universities must fall into exactly one of three deterministic categories based on the user's risk profile:
1. **Safety:** High probability of admission (score padding over minimums).
2. **Target:** Balanced probability of admission.
3. **Reach:** Aspirational targets where the user barely meets or slightly misses ideal thresholds.

**Edge-Case Rules (Calibration Limits):**
- A **Conservative** risk-profile must dynamically shrink the `Reach` output pool and increase `Safety` volume.
- An **Aggressive** risk-profile does the opposite.
- **Country Policies (Hard Filters):** When `countryPolicy=hard_filter` is applied, zero colleges outside the requested country may appear in the result set, overriding all other scoring logic.

### Explanation Consistency Checks
The `explanation` string payload in the API is actively read by users.
- Explanations must mechanically match the underlying `score_breakdown`. If a school is a "Safety" due to `risk_adjustment`, the explanation MUST mention the baseline vs risk adjustment dynamically.
- Empty justifications are considered application regressions.

---

## 4. How to Detect Regressions & Validation Queries

Regressions are typically caught during the CLI validation phase before the web API reads corrupt UI data.

### 4.1. Data Ingestion & Pipeline Queries
Run these checks via default `psql` against the `clawer` database:

**Verify Canonical Alignment:**
```sql
SELECT count(*) FROM warehouse.canonical_university;
SELECT count(*) FROM analytics.v_aggregated_rankings_latest;
```
*(Healthy baseline: Both should return > 0. If `v_aggregated_rankings_latest` drops drastically, the `ranking_record` joins or canonical maps are broken.)*

**Verify Pipeline Write Status:**
```bash
python3 crawlernest/run_pipeline.py run \
  --limit 30 \
  --pg-host localhost --pg-port 5432 --pg-database clawer --pg-user test
```
*(A healthy system should show successful inserts. "No canonical university profiles found" indicates a broken canonical seed.)*

### 4.2. Decision Layer Regression Checks
Use the CLI to output and diff the JSON payloads mathematically:

```bash
# Generate Conservative Baseline
python3 crawlernest/run_pipeline.py recommend-v3 \
  --target-rank 100 --ielts 6.5 --risk-profile conservative \
  --country "United Kingdom" --country-policy hard_filter \
  --pg-user test --pg-database clawer > /tmp/rec_conservative.json

# Generate Aggressive Baseline
python3 crawlernest/run_pipeline.py recommend-v3 \
  --target-rank 100 --ielts 6.5 --risk-profile aggressive \
  --country "United Kingdom" --country-policy hard_filter \
  --pg-user test --pg-database clawer > /tmp/rec_aggressive.json

diff -u /tmp/rec_conservative.json /tmp/rec_aggressive.json
```
*(The diff must demonstrate higher safety volume in conservative, and higher reach volume in aggressive).*

### 4.3. API Layer Smoke Tests
```bash
curl "http://localhost:8080/api/v1/recommendations?version=v3&targetRank=100&ielts=6.5&country=United%20Kingdom&countryPolicy=hard_filter&riskProfile=balanced"
curl -X POST "http://localhost:8080/api/v1/compare" \
     -H "Content-Type: application/json" \
     -d '{"leftUniversityId": 3, "rightUniversityId": 52}' 
```
*(Both must return HTTP 200 with `{"success": true}` envelopes).*

---

## 5. Maintenance Operations

For details on maintaining and deploying the actual crawler pipeline on the production node (Lobster-01), please refer to the [Production Node Runbook](docs/deployment/Lobster_01_Deployment_Guide.md).
