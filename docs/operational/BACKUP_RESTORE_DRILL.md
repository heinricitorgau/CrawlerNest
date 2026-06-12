# Backup Restore Drill

CrawlerNest backup and restore operations should be deliberate, reviewed, and
separate from normal diagnostics. The drill script is readonly-safe: it checks
readiness and prints command previews, but does not run backup or restore.

## Drill Command

```bash
./scripts/run_backup_restore_drill.sh --dry-run
```

The drill checks:

- snapshot directory existence
- latest JSON snapshot availability
- backup directory existence
- backup directory writability
- `pg_dump` command shape
- `pg_restore` command shape

## Backup Flow

Manual backup command shape:

```bash
PGPASSWORD="$CRAWLERNEST_PG_PASSWORD" pg_dump \
  --format=custom \
  --host="${CRAWLERNEST_PG_HOST:-127.0.0.1}" \
  --port="${CRAWLERNEST_PG_PORT:-5432}" \
  --username="${CRAWLERNEST_PG_USER:-test}" \
  --dbname="${CRAWLERNEST_PG_DATABASE:-clawer}" \
  --file="backups/crawlernest_clawer_YYYYMMDD_HHMMSS.dump"
```

Before backup:

- capture or confirm latest snapshot
- confirm target backup path
- confirm available disk space
- record PostgreSQL connection settings

## Restore Flow

Restore is destructive and must never be triggered by automation in this repo.
The drill prints the restore command only as a preview:

```bash
PGPASSWORD="$CRAWLERNEST_PG_PASSWORD" pg_restore \
  --clean \
  --if-exists \
  --host="${CRAWLERNEST_PG_HOST:-127.0.0.1}" \
  --port="${CRAWLERNEST_PG_PORT:-5432}" \
  --username="${CRAWLERNEST_PG_USER:-test}" \
  --dbname="${CRAWLERNEST_PG_DATABASE:-clawer}" \
  backups/crawlernest_clawer_YYYYMMDD_HHMMSS.dump
```

Before restore:

- stop dependent services if needed
- confirm target database
- confirm backup file checksum or timestamp
- save current diagnostics and latest snapshot
- get human approval

## Rollback Flow

Rollback should be scoped:

- code rollback through git
- DB rollback through reviewed backup restore
- artifact rollback from retained `snapshots/`, `reports/`, or `backups/`
- config rollback through known-good environment variables and datasource files

Do not use cleanup or health scripts as rollback tools. They observe state.

## Snapshot Dependency

Snapshots are not backups, but they provide operational evidence around backup
and restore decisions. Keep a latest snapshot before and after a restore drill.

Useful files:

```text
snapshots/latest_status.json
snapshots/system_snapshot_*.json
reports/latest_failure_summary.md
```

## Disaster Recovery Assumptions

Current assumptions:

- PostgreSQL is the durable data store.
- Local backups are filesystem artifacts under `backups/`.
- Restore is a manual operator action.
- Application services can be restarted after DB restoration.
- Snapshots help validate state but cannot reconstruct the database.

## Operational Cautions

- Never run restore against the wrong database.
- Never treat `pg_restore --clean` as safe; it drops/replaces objects.
- Never automate destructive restore from smoke, CI, agent wrappers, or health
  checks.
- Keep backup files out of commits.
- Validate recovery with readonly health checks before resuming pipeline writes.
