# CrawlerNest PostgreSQL Migration Plan

## Objective

Switch CrawlerNest from SQLite to PostgreSQL as the single production database.

This is a controlled migration, not a dual-write architecture.

## Order of Operations

1. Bootstrap PostgreSQL schema in dependency order
- `postgresql_schema.sql`
- `entity_resolution_postgresql.sql`
- `multi_source_postgresql.sql`
- `ranking_aggregation_postgresql.sql`

2. Freeze SQLite writes
- stop long-running crawl jobs
- take a final SQLite snapshot / backup

3. Migrate baseline operational data
- `crawl_runs`
- `countries`
- `universities`
- `university_aliases`
- `raw_source_records`
- `rankings`
- `admission_requirements`

4. Switch Python pipeline defaults to PostgreSQL
- `run_pipeline.py`
- `DBWriter`
- helper scripts

5. Switch Java API defaults to PostgreSQL
- Spring `application.properties`
- validate read endpoints

6. Run verification suite
- pipeline write test
- query/API smoke test
- aggregation smoke test

7. Remove SQLite operational dependency
- stop using SQLite CLI/config
- retain migration script only for historical import/recovery

## Main Risks

- Schema order mistakes: resolved by `bootstrap_postgres.py`
- Sequence drift after import: resolved by `migrate_sqlite_to_postgres.py` sequence reset
- Type differences (`TEXT` vs `JSONB`): resolved by explicit JSON conversion in migration script
- Silent config drift between Python and Java: resolved by standardizing on `localhost:5432/clawer`, user `test`

## Rollback Strategy

1. Keep SQLite DB untouched until PostgreSQL verification passes
2. If PostgreSQL cutover fails:
- stop PostgreSQL writes
- point pipeline back to last known SQLite branch/tag
- keep migrated PostgreSQL DB for forensic comparison
3. Do not delete SQLite backup until:
- one full pipeline run passes
- API read checks pass
- aggregation outputs match expectations

## Local Dev Setup

Create DB:

```bash
createdb -h localhost -U test clawer
```

Docker option:

```bash
docker compose -f docker-compose.postgres.yml up -d
```

Bootstrap schema:

```bash
python3 crawlernest/scripts/bootstrap_postgres.py --user test --database clawer
```

Migrate existing SQLite:

```bash
python3 crawlernest/scripts/migrate_sqlite_to_postgres.py \
  --sqlite-path crawlernest/clawer.db \
  --pg-user test \
  --pg-database clawer \
  --truncate-first
```

## Verification Steps

1. Python pipeline write:

```bash
python3 crawlernest/run_pipeline.py run --limit 30 --pg-user test --pg-database clawer
```

2. Query smoke test:

```bash
python3 crawlernest/run_pipeline.py query MIT --pg-user test --pg-database clawer
```

3. Java API smoke test:

```bash
curl http://localhost:8080/universities
curl http://localhost:8080/rankings
curl http://localhost:8080/admissions
```

4. Aggregation smoke test:

```bash
python3 crawlernest/scripts/ranking_aggregation_example.py
```
