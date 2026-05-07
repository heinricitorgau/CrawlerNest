#!/usr/bin/env bash
set -euo pipefail

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-test}"
PGPASSWORD="${PGPASSWORD:-test}"
PGDATABASE="${PGDATABASE:-clawer}"
API_BASE_URL="${API_BASE_URL:-http://localhost:8080}"
WEB_BASE_URL="${WEB_BASE_URL:-http://localhost:3000}"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "FAIL missing required command: $1"
    exit 1
  fi
}

check_http_200() {
  local label="$1"
  local url="$2"
  local status

  status="$(curl -sS -o /dev/null -w "%{http_code}" "${url}" || true)"
  if [[ "${status}" != "200" ]]; then
    echo "FAIL ${label}: expected HTTP 200, got ${status} (${url})"
    exit 1
  fi

  echo "OK   ${label}: HTTP 200"
}

require_command psql
require_command curl

echo "[1/4] Checking PostgreSQL login..."
PGPASSWORD="${PGPASSWORD}" psql \
  -h "${PGHOST}" \
  -p "${PGPORT}" \
  -U "${PGUSER}" \
  -d "${PGDATABASE}" \
  -v ON_ERROR_STOP=1 \
  -c "SELECT 1;" >/dev/null
echo "OK   PostgreSQL: ${PGUSER}@${PGHOST}:${PGPORT}/${PGDATABASE}"

echo "[2/4] Checking aggregated rankings view..."
ranking_count="$(PGPASSWORD="${PGPASSWORD}" psql \
  -h "${PGHOST}" \
  -p "${PGPORT}" \
  -U "${PGUSER}" \
  -d "${PGDATABASE}" \
  -v ON_ERROR_STOP=1 \
  -tA \
  -c "SELECT count(*) FROM analytics.v_aggregated_rankings_latest;")"

if ! [[ "${ranking_count}" =~ ^[0-9]+$ ]]; then
  echo "FAIL analytics.v_aggregated_rankings_latest count is not numeric: ${ranking_count}"
  exit 1
fi

if (( ranking_count <= 0 )); then
  echo "FAIL analytics.v_aggregated_rankings_latest count must be > 0, got ${ranking_count}"
  exit 1
fi

echo "OK   analytics.v_aggregated_rankings_latest count=${ranking_count}"

echo "[3/4] Checking Spring Boot API..."
check_http_200 "Spring Boot /api/v1/rankings" \
  "${API_BASE_URL}/api/v1/rankings?page=1&pageSize=5"

echo "[4/4] Checking Next.js route/proxy..."
check_http_200 "Next.js /api/rankings proxy" \
  "${WEB_BASE_URL}/api/rankings?page=1&pageSize=5"
check_http_200 "Next.js /rankings route" \
  "${WEB_BASE_URL}/rankings"

echo ""
echo "Local stack smoke test passed."
