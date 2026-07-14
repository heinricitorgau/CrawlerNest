#!/usr/bin/env bash
# One-command first-time setup for CrawlerNest.
#
# Takes a fresh clone to a runnable state: Python venv, dependencies,
# PostgreSQL (local install or Docker), schema bootstrap, first data crawl,
# and frontend dependencies. Idempotent — safe to re-run after a failure.
#
# The repository ships with no ranking data. This script crawls it from the
# source sites using the pipeline's polite defaults (10s request delay).
# Review the source sites' robots.txt and terms before increasing crawl
# volume or lowering the delay.
#
# Usage:
#   ./scripts/setup_from_scratch.sh                # full setup + first crawl
#   ./scripts/setup_from_scratch.sh --skip-data    # setup only, no crawl
#   ./scripts/setup_from_scratch.sh --limit 50     # crawl detail limit (default 20)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-test}"
PGPASSWORD="${PGPASSWORD:-test}"
PGDATABASE="${PGDATABASE:-clawer}"
RANKING_YEAR="${RANKING_YEAR:-2026}"
LIMIT=20
SKIP_DATA=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-data) SKIP_DATA=true ;;
    --limit) LIMIT="$2"; shift ;;
    -h|--help) tail -n +2 "$0" | sed -n '/^#/s/^# \{0,1\}//p'; exit 0 ;;
    *) echo "Unknown argument: $1 (see --help)"; exit 1 ;;
  esac
  shift
done

step() { echo ""; echo "==> $*"; }

# ── 1. Prerequisites ─────────────────────────────────────────────────────────
step "Checking prerequisites"

# Non-interactive shells don't load nvm; pick it up if it's installed so the
# node found here matches what the user gets in their terminal.
if [[ -s "${HOME}/.nvm/nvm.sh" ]]; then
  # shellcheck disable=SC1091
  source "${HOME}/.nvm/nvm.sh" >/dev/null 2>&1 || true
fi

missing=false
for cmd in python3 psql pg_isready; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "MISSING: $cmd"
    missing=true
  fi
done
if ! command -v node >/dev/null 2>&1; then
  echo "MISSING: node (>= 20.9). Install via nvm: https://github.com/nvm-sh/nvm"
  missing=true
elif [[ "$(node --version | sed 's/^v//' | cut -d. -f1)" -lt 20 ]]; then
  echo "MISSING: Node.js >= 20.9 (found $(node --version)). Try: nvm install 20"
  missing=true
fi
if ! command -v java >/dev/null 2>&1; then
  echo "MISSING: java (JDK 17). On Ubuntu: sudo apt install openjdk-17-jdk"
  missing=true
fi
if [[ "$missing" == true ]]; then
  echo ""
  echo "Install the missing prerequisites above, then re-run this script."
  echo "psql/pg_isready come with the PostgreSQL client packages"
  echo "(Ubuntu: sudo apt install postgresql-client)."
  exit 1
fi
echo "All prerequisites found."

# ── 2. Python environment ────────────────────────────────────────────────────
step "Python virtual environment (.venv)"

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
  echo "Created .venv"
fi
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -r requirements.txt
echo "Dependencies installed."

# ── 3. PostgreSQL ────────────────────────────────────────────────────────────
step "PostgreSQL at ${PGHOST}:${PGPORT}/${PGDATABASE}"

if ! pg_isready -h "${PGHOST}" -p "${PGPORT}" >/dev/null 2>&1; then
  if command -v docker >/dev/null 2>&1; then
    echo "PostgreSQL is not running — starting it via Docker Compose..."
    docker compose -f docker-compose.postgres.yml up -d
    for _ in $(seq 1 15); do
      pg_isready -h "${PGHOST}" -p "${PGPORT}" >/dev/null 2>&1 && break
      sleep 2
    done
  else
    echo "PostgreSQL is not reachable and Docker is not available."
    echo "Either start a local PostgreSQL:"
    echo "  sudo service postgresql start"
    echo "or install Docker and re-run this script (it will use"
    echo "docker-compose.postgres.yml, which provides the expected"
    echo "user/password/database out of the box)."
    exit 1
  fi
fi

if ! pg_isready -h "${PGHOST}" -p "${PGPORT}" >/dev/null 2>&1; then
  echo "PostgreSQL still not reachable at ${PGHOST}:${PGPORT}. Aborting."
  exit 1
fi

if ! PGPASSWORD="${PGPASSWORD}" psql -h "${PGHOST}" -p "${PGPORT}" \
    -U "${PGUSER}" -d "${PGDATABASE}" -c "SELECT 1;" >/dev/null 2>&1; then
  echo "Cannot log in as ${PGUSER}/${PGDATABASE}. Create the role and database:"
  echo "  sudo -u postgres psql -c \"CREATE ROLE ${PGUSER} WITH LOGIN PASSWORD '${PGPASSWORD}';\""
  echo "  sudo -u postgres createdb -O ${PGUSER} ${PGDATABASE}"
  echo "(Docker users get these automatically — check the container logs.)"
  exit 1
fi
echo "PostgreSQL is up and credentials work."

# ── 4. Schema bootstrap ──────────────────────────────────────────────────────
step "Bootstrapping database schema (safe to re-run)"

./.venv/bin/python -m crawlernest.run_pipeline bootstrap-postgres \
  --pg-host "${PGHOST}" --pg-port "${PGPORT}" \
  --pg-user "${PGUSER}" --pg-password "${PGPASSWORD}" --pg-database "${PGDATABASE}"

# ── 5. First data crawl ──────────────────────────────────────────────────────
if [[ "${SKIP_DATA}" == true ]]; then
  step "Skipping data crawl (--skip-data). Load data later with:"
  echo "  ./.venv/bin/python -m crawlernest.run_pipeline run --limit ${LIMIT} \\"
  echo "    --ranking-year ${RANKING_YEAR} --pg-user ${PGUSER} --pg-password ${PGPASSWORD} --pg-database ${PGDATABASE}"
else
  step "Crawling ranking data (polite defaults: 10s request delay)"
  echo "This fetches live data from the ranking source. It can take a while."

  ./.venv/bin/python -m crawlernest.run_pipeline run \
    --limit "${LIMIT}" --ranking-year "${RANKING_YEAR}" \
    --pg-host "${PGHOST}" --pg-port "${PGPORT}" \
    --pg-user "${PGUSER}" --pg-password "${PGPASSWORD}" --pg-database "${PGDATABASE}"

  rows="$(PGPASSWORD="${PGPASSWORD}" psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" -tA \
    -c 'SELECT count(*) FROM analytics.v_aggregated_rankings_latest;' 2>/dev/null || echo '?')"
  echo "Aggregated ranking rows now in analytics views: ${rows}"
fi

# ── 6. Frontend dependencies ─────────────────────────────────────────────────
step "Frontend dependencies (npm ci)"

(cd crawlernest/crawlernest-web && npm ci --no-audit --no-fund)

# ── Done ─────────────────────────────────────────────────────────────────────
step "Setup complete"
echo "Start everything with:   ./scripts/start_localhost.sh"
echo "Then open:               http://localhost:3000/rankings"
echo ""
echo "Optional next steps:"
echo "  Subject rankings:  see docs/GETTING_STARTED.md (run-qs-subject)"
echo "  Environment check: ./scripts/verify_local_environment.sh"
