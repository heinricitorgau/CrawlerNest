# CrawlerNest PostgreSQL Migration Plan

## Audit Findings

### Active SQLite Usage Found

1. One-time import tool
- `crawlernest/scripts/migrate_sqlite_to_postgres.py`
- Uses Python `sqlite3` to copy legacy baseline tables into PostgreSQL.
- Keep this script only as a migration / rollback import utility, not as a runtime path.

2. Archived file-based databases
- `crawlernest/clawer.db`
- `crawlernest/crawlernest-kb/databases/universities.db`
- These are legacy artifacts and should be treated as read-only backups during cutover.

3. Legacy schema files
- `crawlernest/crawlernest-schema/schema.sql`
- `crawlernest/crawlernest-schema/schema_min.sql`
- These describe SQLite-era layouts and are no longer the runtime source of truth.

4. Legacy config and docs
- `crawlernest/crawlernest-core/config.py` contained `db_path`
- Java `pom.xml` still included `sqlite-jdbc`
- Java comments and several READMEs still described SQLite as an active runtime database

### PostgreSQL-Incompatible / SQLite-Specific Patterns

1. DDL patterns in legacy schema
- `PRAGMA foreign_keys = ON`
- `INTEGER PRIMARY KEY AUTOINCREMENT`
- `TEXT` JSON payload storage instead of `JSONB`

2. File-based DB assumptions
- `.db` snapshots referenced in docs and migration examples

3. Connection pattern drift
- Some Python signatures still accepted `db_path` even though the runtime path was already PostgreSQL-only
- Java build still carried an unused SQLite JDBC dependency

### Current Runtime State

1. Python runtime
- Main pipeline path already writes to PostgreSQL
- Recommendation, aggregation, entity resolution, and comparison paths already read from PostgreSQL

2. Java runtime
- Spring Boot already uses PostgreSQL datasource configuration
- REST endpoints read from PostgreSQL

## Safe Migration Strategy

### Step 1: Make PostgreSQL Primary

1. Bootstrap schemas in dependency order:
- `postgresql_schema.sql`
- `entity_resolution_postgresql.sql`
- `multi_source_postgresql.sql`
- `ranking_aggregation_postgresql.sql`
- `recommendation_postgresql.sql`

2. Freeze SQLite writes
- Stop legacy jobs that might still write to `.db` files
- Mark archived `.db` files as read-only backups

3. Cut Python and Java runtime paths to PostgreSQL-only
- Remove `db_path` runtime parameters
- Remove SQLite JDBC dependency
- Keep only PostgreSQL datasource/config paths

### Step 2: Migrate Data

1. Take final SQLite backup
- Copy `crawlernest/clawer.db` to an external backup location

2. Run import
```bash
python3 crawlernest/scripts/migrate_sqlite_to_postgres.py \
  --sqlite-path crawlernest/clawer.db \
  --pg-user test \
  --pg-database clawer \
  --truncate-first
```

3. Rebuild downstream PostgreSQL-only derived state
- canonical links
- multi-source mappings
- aggregated rankings
- recommendation candidate view consumers

### Step 3: Update Code

1. Python
- Remove dead SQLite runtime parameters
- Use PostgreSQL connection pooling
- Use PostgreSQL batch insert primitives

2. Java
- Remove SQLite JDBC dependency
- Keep Spring Boot PostgreSQL datasource only
- Verify endpoint behavior unchanged

### Step 4: Remove SQLite Runtime Dependency

1. Keep only the migration/import script for historical recovery
2. Treat `.db` files as offline archives, not runtime stores
3. Keep PostgreSQL schema files as the only source of truth for production

## Rollback Plan

1. Before cutover
- Keep the original SQLite files untouched
- Take a PostgreSQL schema/data snapshot if importing into a shared environment

2. If PostgreSQL cutover fails
- Stop pipeline/API writes to PostgreSQL
- Restore PostgreSQL from pre-cutover snapshot if needed
- Resume from the archived SQLite backup only in a controlled rollback branch/tag

3. Rollback exit criteria
- PostgreSQL import validation fails
- pipeline write path fails
- API endpoints return inconsistent results

## Minimal-Downtime Approach

1. Bootstrap PostgreSQL schemas ahead of time
2. Freeze SQLite writes only during final export/import window
3. Import SQLite baseline into PostgreSQL
4. Restart pipeline and API against PostgreSQL
5. Re-run smoke tests before opening traffic fully

## Schema Alignment

### PostgreSQL Runtime Schema Requirements

1. Identity / serial keys
- Warehouse and analytics tables use `SERIAL`, `SMALLSERIAL`, or `BIGSERIAL`

2. Runtime types
- Text fields use `TEXT`
- Canonical IDs use `BIGINT`
- Structured payloads use `JSONB`
- Numeric scores use `NUMERIC` where precision matters

3. Foreign keys
- `ranking_record.canonical_university_id`
- `source_university_mapping.canonical_university_id`
- `aggregated_rankings.canonical_university_id`
- `canonical_university_link.canonical_university_id`
- `admission_requirements.university_id`

4. Required indexes
- canonical university:
  - `warehouse.source_university_mapping(canonical_university_id)`
  - `warehouse.ranking_record(canonical_university_id, ranking_year)`
  - `warehouse.canonical_university_link(canonical_university_id)`
- source:
  - `warehouse.ranking_record(ranking_source_id, ranking_year, ranking_type, rank_position)`
  - `analytics.source_ingestion_log(source_code, started_at)`
- year:
  - `warehouse.ranking_record(ranking_year)`
  - `analytics.aggregated_rankings(ranking_year, aggregation_method_version, display_rank)`

## Schema Differences: SQLite to PostgreSQL

1. Primary keys
- SQLite: `INTEGER PRIMARY KEY AUTOINCREMENT`
- PostgreSQL: `SERIAL` / `BIGSERIAL`

2. JSON storage
- SQLite: `TEXT`
- PostgreSQL: `JSONB`

3. Numeric fields
- SQLite: `REAL`
- PostgreSQL: `NUMERIC(...)`

4. Null handling
- Empty JSON strings become `NULL`
- Empty numeric strings become `NULL`
- Missing optional relations remain `NULL`

## Validation Steps

### Pipeline

```bash
python3 crawlernest/scripts/bootstrap_postgres.py --user test --database clawer
python3 crawlernest/run_pipeline.py run --limit 30 --pg-user test --pg-database clawer
```

### Recommender

```bash
python3 crawlernest/run_pipeline.py recommend --country "United Kingdom" --ielts-score 6.5 --target-rank 100 --pg-user test --pg-database clawer
python3 crawlernest/run_pipeline.py recommend-v2 --target-rank 100 --ielts 6.5 --risk-profile balanced --pg-user test --pg-database clawer
```

### API

```bash
curl "http://localhost:8080/universities"
curl "http://localhost:8080/rankings"
curl "http://localhost:8080/admissions"
curl "http://localhost:8080/recommendations?targetRank=100&ielts=6.5&version=v2"
curl "http://localhost:8080/compare?u1=Oxford&u2=LSE"
```

## Performance Considerations

1. Indexing
- Keep canonical/source/year composite indexes hot
- Add JSONB GIN indexes only on payloads that are actually queried

2. Batch ingestion
- Prefer `execute_values` today
- Upgrade heavy bulk imports to `COPY` when import volume justifies it

3. Query optimization
- Read recommendation/comparison data from materialized or pre-joined views where possible
- Avoid rebuilding aggregation logic in request-time code

4. Optional materialized views
- Consider a materialized latest-candidate view if `v_recommendation_candidates_latest` becomes expensive under load

## Future Personalization-Safe Extension

1. Keep PostgreSQL as the only operational store
2. Add more derived views or materialized views rather than new databases
3. Keep personalization features rule-based on top of the same PostgreSQL source of truth
