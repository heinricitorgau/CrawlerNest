# Historical migration document — system is now PostgreSQL-only

*This document serves as an archive of the migration process from legacy SQLite databases to the robust PostgreSQL architecture currently in production.*

## Audit Findings (Historical SQLite Context)

### Active SQLite Usage Found
1. One-time import tools like `crawlernest/scripts/migrate_sqlite_to_postgres.py` were built to copy legacy baseline tables.
2. Archived file-based databases (`crawlernest/clawer.db`, `crawlernest-kb/databases/universities.db`).
3. Legacy schema scripts utilizing SQLite specific DDL patterns like `PRAGMA foreign_keys = ON` and `INTEGER PRIMARY KEY AUTOINCREMENT`.

### PostgreSQL-Incompatible Patterns Resolved
1. DDL patterns required upgrading (e.g., SQLite `TEXT` JSON payloads were transitioned to PostgreSQL `JSONB`).
2. Numeric score fields (`REAL`) transitioned to PostgreSQL `NUMERIC` for precision.

## Transition Strategy (Historical Execution Plan)

### Step 1: Making PostgreSQL Primary
- Bootstrapped canonical and analytics schemas in dependency order (`postgresql_schema.sql`, `entity_resolution_postgresql.sql`, etc.).
- Froze SQLite runtime paths, permanently removing `db_path` configurations from Python and `sqlite-jdbc` from the Java backend.

### Step 2: Data Migration
The master database was seeded using the legacy `.db` files:
```bash
python3 crawlernest/scripts/migrate_sqlite_to_postgres.py \
  --sqlite-path crawlernest/clawer.db \
  --pg-user test \
  --pg-database clawer \
  --truncate-first
```
Following this, downstream multi-source canonical mappings and aggregated rankings were manually reconstructed using the new schema layout.

### Step 3: Deprecation
- Legacy SQLite files are now treated strictly as read-only, offline archives.
- The PostgreSQL schema serves as the sole runtime source of truth.
