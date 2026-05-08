# Operational Recovery

This runbook covers readonly triage and safe recovery paths for local
CrawlerNest operations. Prefer observation first, then make one deliberate
change at a time.

## First Checks

```bash
./scripts/verify_local_environment.sh
python3 scripts/check_pipeline_health.py
./scripts/smoke_release.sh
```

These checks do not auto-fix code, mutate pipeline data, change schemas, or write
to production paths.

## PostgreSQL Recovery

Symptoms:

- `pg_isready` fails
- Spring Boot health reports `postgres_connected=false`
- pipeline health reports a connection error

Checks:

```bash
pg_isready -h 127.0.0.1 -p 5432 -d clawer -U test
sudo service postgresql status
```

Recovery:

- Start PostgreSQL: `sudo service postgresql start`
- Confirm the `clawer` database exists.
- Confirm local credentials match `application.properties` and the `CRAWLERNEST_PG_*` environment variables.
- Run readonly health checks again before rerunning any pipeline command.

## Broken Analytics Views

Symptoms:

- rankings API is empty despite ranking records
- `check_pipeline_health.py` reports a view/table error
- `/api/v1/diagnostics/rankings` fails

Recovery:

- Inspect the error from `python3 scripts/check_pipeline_health.py`.
- Reapply schema only when intentionally repairing local DB state:
  `python3 -m crawlernest.run_pipeline bootstrap-postgres --pg-user test --pg-password test --pg-database clawer`.
- Do not change aggregation SQL until the failing view and source data are identified.

## Empty Rankings API

Symptoms:

- `/api/v1/rankings` returns no records
- `analytics.v_aggregated_rankings_latest` has zero rows

Checks:

```sql
SELECT COUNT(*) FROM warehouse.ranking_record;
SELECT COUNT(*) FROM analytics.v_aggregated_rankings_latest;
SELECT * FROM analytics.aggregation_runs ORDER BY started_at DESC LIMIT 5;
```

Recovery:

- If `ranking_record` is empty, ranking ingestion has not produced source facts.
- If `ranking_record` has rows but the latest view is empty, inspect finished aggregation runs.
- Rerun only the minimum intended pipeline step after saving current diagnostics.

## Node Mismatch

Symptoms:

- Next.js build fails with unsupported Node version
- `verify_local_environment.sh` reports Node.js `<20.9`

Recovery:

```bash
nvm install 20
nvm use 20
node --version
```

Then rerun:

```bash
cd crawlernest/crawlernest-web
npm install
```

## Next.js Startup Failure

Symptoms:

- port `3000` is already in use
- missing `node_modules`
- `npm run dev` exits early

Recovery:

- Check `./scripts/verify_local_environment.sh`.
- Stop the process occupying port `3000`, or start Next.js on a deliberate alternate port.
- Reinstall dependencies only when `node_modules` is missing or stale.

## Spring Boot Datasource Failure

Symptoms:

- API starts but health shows PostgreSQL disconnected
- datasource authentication errors in logs

Recovery:

- Confirm `crawlernest/servise_for_java/src/main/resources/application.properties`.
- Confirm PostgreSQL role and database exist.
- Keep local datasource credentials consistent with README quick start values unless intentionally testing another database.

## psycopg2 Failure

Symptoms:

- `verify_local_environment.sh` reports `psycopg2 is not importable`
- `check_pipeline_health.py` reports `No module named psycopg2`

Recovery:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python3 -c "import psycopg2"
```

If system packages are missing, install PostgreSQL development headers for the
local OS, then reinstall Python dependencies.

## QS Upstream Outage

Symptoms:

- QS crawler fails before producing normalized rows
- source ingestion logs show missing or low QS records
- source coverage reports QS missing

Recovery:

- Treat upstream outage as degraded, not an aggregation bug.
- Preserve the raw error log and latest snapshot.
- Avoid changing canonical matching or scoring logic to compensate for upstream availability.
- Rerun ingestion only after the upstream source is reachable.

## Snapshot Recovery

Snapshots and reports are generated operational evidence. If they are missing:

- rerun readonly checks first
- regenerate a system snapshot only when local DB is reachable
- keep at least the latest known-good snapshot before cleanup

Use cleanup only for retention:

```bash
./scripts/cleanup_old_artifacts.sh --dry-run
./scripts/cleanup_old_artifacts.sh
```

## Rollback Guidance

Rollback should be scoped to the smallest changed surface:

- code rollback: use git history and avoid resetting unrelated local work
- DB rollback: restore from an intentional database backup
- artifact rollback: restore the needed snapshot/report from `backups/`
- config rollback: restore datasource and environment variables to known-good values

Do not use cleanup, diagnostics, or smoke scripts as rollback mechanisms. They
observe state; they do not repair it automatically.
