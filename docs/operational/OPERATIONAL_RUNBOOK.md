# CrawlerNest Operational Runbook

This runbook covers local startup, smoke checks, daily operations, snapshots, diagnostics, CI troubleshooting, and rollback guidance.

## Startup

### 1. Start PostgreSQL

```bash
sudo service postgresql start
```

Expected local database settings:

```text
database: clawer
user: test
password: test
host: localhost
port: 5432
```

### 2. Bootstrap schemas if needed

```bash
python3 -m crawlernest.run_pipeline bootstrap-postgres \
  --pg-user test \
  --pg-password test \
  --pg-database clawer
```

### 3. Load ranking data

```bash
./.venv/bin/python -m crawlernest.run_pipeline run \
  --limit 20 \
  --ranking-year 2026 \
  --pg-user test \
  --pg-password test \
  --pg-database clawer
```

### 4. Start API and web services

Preferred:

```bash
./scripts/start_localhost.sh
```

Manual:

```bash
cd crawlernest/servise_for_java
./mvnw -Dmaven.test.skip=true spring-boot:run
```

```bash
cd crawlernest/crawlernest-web
npm run dev
```

Service URLs:

```text
API: http://localhost:8080
Web: http://localhost:3000
Agent API: http://localhost:8090
```

## Release Smoke

Run before merging or handing off a release:

```bash
bash scripts/smoke_release.sh
```

The smoke script checks:

- Spring Boot compile
- Next.js build
- Python syntax for selected entry points
- pipeline health diagnostics, snapshot comparison, failure-state fixtures

It starts no services and checks no endpoints. It used to end with API checks
that skipped themselves whenever Spring Boot was unreachable, which meant a pass
implied a working API nothing had touched.

For endpoint coverage, start Spring Boot and run the checks directly:

```bash
bash scripts/smoke_api_endpoints.sh
```

CI runs that script in the `Analytics bridge smoke` job, against a server the
job starts, so it cannot skip there.

## Local Stack Smoke

After services are running:

```bash
./scripts/smoke_local_stack.sh
```

This verifies common local API and web paths, including freshness and subject ranking checks.

## Daily Pipeline

Daily operations are coordinated by:

```bash
./scripts/run_daily_pipeline.sh
```

Useful options:

```bash
./scripts/run_daily_pipeline.sh --dry-run
./scripts/run_daily_pipeline.sh --skip-smoke
```

The daily script runs ranking and subject operations, diagnostics, snapshots, and metadata bundle export. Logs are written under `logs/`.

## Snapshot Export

Export a point-in-time system snapshot:

```bash
python3 scripts/export_system_snapshot.py \
  --pg-user test \
  --pg-password test \
  --pg-database clawer
```

Outputs:

```text
snapshots/system_snapshot_YYYYMMDD_HHMMSS.json
snapshots/latest_status.json
```

Build a human-readable failure summary:

```bash
python3 scripts/build_failure_summary.py \
  --snapshot-file snapshots/latest_status.json \
  --output reports/failure_summary.md
```

## Metadata Bundle Export

```bash
./scripts/export_metadata_bundle.sh
```

The bundle includes snapshots, reports, and recent daily logs. It does not create a full database dump.

## Drift Diagnostics

Use API diagnostics when services are running:

```bash
curl "http://localhost:8080/api/v1/diagnostics/data-quality"
curl "http://localhost:8080/api/v1/diagnostics/source-agreement"
```

Use autoeval runners for local or CI-style checks:

```bash
python3 crawlernest/crawlernest-autoeval/runners/run_source_drift.py
python3 crawlernest/crawlernest-autoeval/runners/run_canonical_diagnostics.py
```

Review:

- source count drops
- unresolved entity spikes
- low-confidence canonical matches
- QS/THE overlap and rank disagreement
- missing-source coverage

## Freshness Checks

API:

```bash
curl "http://localhost:8080/api/v1/freshness"
```

UI:

```text
http://localhost:3000/system-status
```

Snapshot:

```bash
python3 scripts/export_system_snapshot.py --pg-password test
cat snapshots/latest_status.json
```

Investigate stale data by checking:

- latest `warehouse.ranking_record` rows
- latest `warehouse.subject_ranking_record` rows
- latest `analytics.aggregated_rankings` rows
- `analytics.source_ingestion_log`

## CI Troubleshooting

CI workflows:

- `.github/workflows/release-smoke.yml`
- `.github/workflows/data-quality.yml`

Run release smoke locally:

```bash
bash scripts/smoke_release.sh
```

Run fixture-mode CI helpers:

```bash
./scripts/run_ci_locally.sh
```

Common failures:

- Node version too old: use Node.js 20 or newer.
- `node_modules` missing locally: run `npm install` in `crawlernest/crawlernest-web`.
- Maven wrapper not executable: run `chmod +x crawlernest/servise_for_java/mvnw`.
- Database unavailable for integration tests: start PostgreSQL and confirm `application.properties`.
- Data quality fixture mismatch: inspect `crawlernest/crawlernest-autoeval/datasets/ci_fixtures/`.

## Rollback Guidance

CrawlerNest is data-first. Prefer rolling back at the smallest layer that introduced the issue.

### Code rollback

Use normal Git rollback for application code, then rerun:

```bash
bash scripts/smoke_release.sh
```

### Data rollback

If a recent ingestion produced bad data:

1. Stop scheduled ingestion or daily operations.
2. Export a snapshot with `scripts/export_system_snapshot.py`.
3. Identify affected source/year/universe rows.
4. Restore from a database backup or replay a known-good snapshot/source payload.
5. Rebuild aggregation views or rerun the relevant pipeline step.
6. Rerun freshness, diagnostics, and smoke checks.

### Operational rollback

If an automation script changed behavior unexpectedly:

1. Disable the scheduler or cron entry.
2. Preserve `logs/daily_pipeline_*.log`.
3. Export metadata bundle.
4. Revert the script change.
5. Run `scripts/run_daily_pipeline.sh --dry-run`.

## Related Documents

- [Architecture Overview](../ARCHITECTURE_OVERVIEW.md)
- [Data Flow](../DATA_FLOW.md)
- [Repository Map](../REPOSITORY_MAP.md)
- [API Surface](../API_SURFACE.md)
- [Scheduled Operations](SCHEDULED_OPERATIONS.md)
- [Local Troubleshooting](../LOCAL_TROUBLESHOOTING.md)
