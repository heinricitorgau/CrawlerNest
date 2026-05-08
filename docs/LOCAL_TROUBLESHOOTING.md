# Local Troubleshooting

Known issues encountered during local development on WSL2/Ubuntu. Each entry gives the symptom, root cause, and fix.

---

## docker: command not found

**Symptom**

```
docker: command not found
```

**Cause**

Docker Desktop is not installed, or it is not running and the CLI is not on `PATH`.

**Fix**

Docker is **not required** for the local development flow. Use the native PostgreSQL package instead:

```bash
sudo apt update && sudo apt install postgresql postgresql-contrib
sudo service postgresql start
```

---

## postgresql.service not found / Failed to start postgresql.service

**Symptom**

```
Failed to start postgresql.service: Unit not found.
```

**Cause**

On WSL2, `systemctl` is not available in older kernels. The service manager is `service`, not `systemctl`.

**Fix**

```bash
sudo service postgresql start
sudo service postgresql status
```

---

## psql: connection refused / could not connect to server

**Symptom**

```
psql: error: connection to server on socket "/var/run/postgresql/.s.PGSQL.5432" failed:
  Connection refused
```

or

```
pg_isready: could not connect to server: Connection refused
```

**Cause**

PostgreSQL is not running.

**Fix**

```bash
sudo service postgresql start
```

Verify it is up:

```bash
pg_isready -h localhost -p 5432
```

---

## psycopg2 not found / ModuleNotFoundError: No module named 'psycopg2'

**Symptom**

```
ModuleNotFoundError: No module named 'psycopg2'
```

**Cause**

The Python virtual environment is not activated, or `pip install -r requirements.txt` was not run.

**Fix**

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

If `psycopg2` still fails to build from source, install the binary wheel:

```bash
pip install psycopg2-binary
```

---

## psql: fe_sendauth: no password supplied

**Symptom**

```
psql: error: fe_sendauth: no password supplied
```

**Cause**

The password is not passed via the `PGPASSWORD` environment variable or the connection string.

**Fix**

Always pass the password explicitly:

```bash
PGPASSWORD=test psql -h localhost -U test -d clawer -c "SELECT 1;"
```

Or set it for the session:

```bash
export PGPASSWORD=test
```

---

## Spring Boot fails to start: password authentication failed / "test" not found

**Symptom**

```
org.postgresql.util.PSQLException: FATAL: password authentication failed for user "test"
```

or the datasource connects as the wrong user.

**Cause**

`application.properties` has the password written as a shell variable literal instead of the actual value. This happens when the file is edited by copy-pasting from a terminal prompt with `$` intact.

Broken example:

```properties
spring.datasource.username=$test
spring.datasource.password=$test
```

**Fix**

`crawlernest/servise_for_java/src/main/resources/application.properties` must contain bare string values:

```properties
spring.datasource.url=jdbc:postgresql://localhost:5432/clawer
spring.datasource.username=test
spring.datasource.password=test
```

---

## Port 8080 already in use

**Symptom**

```
Web server failed to start. Port 8080 was already in use.
```

**Cause**

A previous Spring Boot process is still running, or another service occupies port 8080.

**Fix**

Find the occupying process and kill it:

```bash
lsof -i :8080
kill <PID>
```

Or use the one-liner:

```bash
kill "$(lsof -t -iTCP:8080 -sTCP:LISTEN)"
```

---

## Port 3000 already in use

Same pattern as port 8080:

```bash
kill "$(lsof -t -iTCP:3000 -sTCP:LISTEN)"
```

---

## next: not found / sh: next: command not found

**Symptom**

```
sh: next: command not found
```

**Cause**

`npm install` has not been run in `crawlernest/crawlernest-web`, so the `next` binary is missing from `node_modules/.bin`.

**Fix**

```bash
cd crawlernest/crawlernest-web
npm install
```

---

## Node.js version too old / Unsupported engine

**Symptom**

```
error next@16.x.x: The engine "node" is incompatible with this module.
Expected version ">=20.9.0". Got "18.x.x"
```

or `npm run dev` / `npm run build` silently fails with cryptic errors.

**Cause**

System Node.js is version 18 (installed via `apt`). Next.js 16 requires Node.js ≥ 20.9.

**Fix**

Use `nvm` to switch to Node 20:

```bash
# Install nvm if not present
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc

nvm install 20
nvm use 20
node --version   # should print v20.x.x
```

`start_localhost.sh` and `smoke_release.sh` check the Node.js version and abort early if it is too old.

---

## next.config.ts not supported / SyntaxError in config file

**Symptom**

```
Failed to load next.config.ts
SyntaxError: Cannot use import statement in a module
```

or

```
next.config.ts is not supported by this version of Next.js
```

**Cause**

The project uses a TypeScript config file (`next.config.ts`) which requires Next.js ≥ 15. If the `node_modules` tree contains a mismatched or older Next.js installation (e.g. version 9 from a global `npm install next`), the config loader rejects the `.ts` extension.

**Fix**

Make sure you are running the project-local Next.js, not a global one:

```bash
cd crawlernest/crawlernest-web
rm -rf node_modules package-lock.json
npm install
npx next --version   # should match package.json: ^16.x
```

Never install Next.js globally in the same environment.

---

## analytics view is empty after pipeline run

**Symptom**

```sql
SELECT count(*) FROM analytics.v_aggregated_rankings_latest;
-- returns 0
```

**Cause**

The pipeline `run` command finished, but the aggregation step did not write to the view, or `bootstrap-postgres` was not run first.

**Fix**

1. Confirm bootstrap was run:

   ```bash
   PGPASSWORD=test psql -h localhost -U test -d clawer \
     -c "SELECT count(*) FROM warehouse.ranking_subject;"
   ```

   Should be ≥ 1. If 0, run bootstrap-postgres.

2. Re-run the pipeline:

   ```bash
   ./.venv/bin/python -m crawlernest.run_pipeline run \
     --limit 30 --ranking-year 2026 \
     --pg-user test --pg-password test --pg-database clawer
   ```

3. Check the aggregation run table:

   ```bash
   PGPASSWORD=test psql -h localhost -U test -d clawer \
     -c "SELECT status, output_record_count FROM analytics.aggregation_runs ORDER BY aggregation_run_id DESC LIMIT 3;"
   ```

---

## smoke_local_stack.sh fails: FAIL /api/v1/freshness

**Symptom**

```
FAIL Spring Boot /api/v1/freshness: expected HTTP 200, got 503
```

**Cause**

Spring Boot is not running or did not finish starting before the smoke script ran.

**Fix**

Wait for the Spring Boot startup log line:

```
Started Application in X.XXX seconds
```

Then re-run:

```bash
./scripts/smoke_local_stack.sh
```
