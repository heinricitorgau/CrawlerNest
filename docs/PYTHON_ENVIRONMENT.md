# Python Environment

CrawlerNest standardizes local Python execution around the repo-root `.venv`.
System Python may be present and useful for OS tooling, but project commands
should use the virtual environment whenever they import project dependencies or
connect to PostgreSQL.

## Standard `.venv` Workflow

Create and activate the environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run project commands through the venv:

```bash
./.venv/bin/python -m crawlernest.run_pipeline --help
./.venv/bin/python scripts/check_pipeline_health.py
```

Verify consistency:

```bash
./scripts/verify_local_environment.sh
```

## psycopg2 Installation

CrawlerNest DB scripts require `psycopg2` or `psycopg2-binary`.

Preferred local install:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python -c "import psycopg2"
```

If compiling from source fails on Ubuntu or WSL, install PostgreSQL development
headers first:

```bash
sudo apt install libpq-dev python3-dev build-essential
```

Then reinstall the Python dependencies inside `.venv`.

## System Python vs Venv

Common mismatch:

```text
python3 imports one dependency set
.venv/bin/python imports another dependency set
```

Symptoms:

- `verify_local_environment.sh` says current `python3` cannot import
  `psycopg2`
- `.venv/bin/python -c "import psycopg2"` works
- smoke checks report DB health failed even though PostgreSQL is reachable

Fix:

```bash
source .venv/bin/activate
which python
python -c "import psycopg2"
```

Use explicit `.venv/bin/python` in scripts or docs when reproducibility matters.

## Ubuntu/WSL PEP 668

Recent Ubuntu and Debian Python packages may mark the system interpreter as
externally managed. In that state, global `pip install` can fail or warn.

Do not force install project dependencies into system Python. Use `.venv`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

This keeps OS Python stable and keeps CrawlerNest dependencies local to the
repository.

## Node + Java + Python Coexistence

CrawlerNest uses three runtimes locally:

- Python for ingestion, diagnostics, snapshots, and health scripts
- Java 17 for Spring Boot API
- Node.js >= 20.9 for Next.js frontend

Recommended checks:

```bash
./scripts/verify_local_environment.sh
java -version
node --version
./.venv/bin/python --version
```

Keep Node version management through `nvm` or an equivalent tool. Keep Java
through the system JDK. Keep Python dependencies inside `.venv`.

## Common Errors And Repairs

### `No module named psycopg2`

Cause: active Python does not have DB dependencies.

Repair:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python -c "import psycopg2"
```

### `externally-managed-environment`

Cause: global pip is blocked by PEP 668.

Repair: use `.venv`; do not bypass the OS guard for project dependencies.

### PostgreSQL reachable but health script says DB failed

Cause: PostgreSQL is running, but the Python interpreter running the health
script cannot import `psycopg2`.

Repair:

```bash
./.venv/bin/python scripts/check_pipeline_health.py
```

### Current Python differs from `.venv`

Cause: shell is not activated, or a tool invokes `/usr/bin/python3`.

Repair:

```bash
source .venv/bin/activate
which python
```

For CI and reproducible local checks, prefer explicit `.venv/bin/python`.
