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

# Returns the value of .metadata.totalCount from a rankings API response.
# Uses python3 (always available) so jq is not required.
fetch_rankings_total_count() {
  local url="$1"
  local body
  body="$(curl -sS "${url}" || true)"
  python3 - "${body}" <<'PYEOF'
import json, sys
body = sys.argv[1]
try:
    d = json.loads(body)
    print(d.get("metadata", {}).get("totalCount", 0))
except Exception:
    print(0)
PYEOF
}

# Returns the length of .data.items from a subject-rankings API response.
fetch_subject_items_count() {
  local url="$1"
  local body
  body="$(curl -sS "${url}" || true)"
  python3 - "${body}" <<'PYEOF'
import json, sys
body = sys.argv[1]
try:
    d = json.loads(body)
    print(len(d.get("data", {}).get("items", [])))
except Exception:
    print(0)
PYEOF
}

require_command psql
require_command curl
require_command python3

echo "[1/5] Checking PostgreSQL login..."
PGPASSWORD="${PGPASSWORD}" psql \
  -h "${PGHOST}" \
  -p "${PGPORT}" \
  -U "${PGUSER}" \
  -d "${PGDATABASE}" \
  -v ON_ERROR_STOP=1 \
  -c "SELECT 1;" >/dev/null
echo "OK   PostgreSQL: ${PGUSER}@${PGHOST}:${PGPORT}/${PGDATABASE}"

echo "[2/5] Checking aggregated rankings view..."
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
  echo "  Run the pipeline first: ./.venv/bin/python -m crawlernest.run_pipeline run --pg-password test --pg-database clawer"
  exit 1
fi

echo "OK   analytics.v_aggregated_rankings_latest count=${ranking_count}"

echo "[3/5] Checking Spring Boot API rankings and health..."
check_http_200 "Spring Boot /api/v1/health" \
  "${API_BASE_URL}/api/v1/health"

_health_body="$(curl -sS "${API_BASE_URL}/api/v1/health" || true)"
health_pg="$(echo "${_health_body}" | python3 -c "
import json, sys
body = sys.stdin.read()
try:
    d = json.loads(body)
    print('true' if d.get('data', {}).get('postgres_connected', False) else 'false')
except Exception:
    print('false')
")"
if [[ "${health_pg}" != "true" ]]; then
  echo "FAIL /api/v1/health: postgres_connected is not true"
  exit 1
fi
echo "OK   /api/v1/health postgres_connected=true"

check_http_200 "Spring Boot /api/v1/rankings" \
  "${API_BASE_URL}/api/v1/rankings?page=1&pageSize=5"

total_count="$(fetch_rankings_total_count "${API_BASE_URL}/api/v1/rankings?page=1&pageSize=5")"
if ! [[ "${total_count}" =~ ^[0-9]+$ ]] || (( total_count <= 0 )); then
  echo "FAIL /api/v1/rankings totalCount must be > 0, got '${total_count}'"
  exit 1
fi
echo "OK   /api/v1/rankings totalCount=${total_count}"

echo "[4/5] Checking subject-rankings subjects endpoint and freshness..."
check_http_200 "Spring Boot /api/v1/subject-rankings/subjects" \
  "${API_BASE_URL}/api/v1/subject-rankings/subjects"

subject_count="$(fetch_subject_items_count "${API_BASE_URL}/api/v1/subject-rankings/subjects")"
if ! [[ "${subject_count}" =~ ^[0-9]+$ ]] || (( subject_count <= 0 )); then
  echo "FAIL /api/v1/subject-rankings/subjects items must be > 0, got '${subject_count}'"
  echo "  Run bootstrap-postgres if you haven't: python3 -m crawlernest.run_pipeline bootstrap-postgres --pg-password test --pg-database clawer"
  exit 1
fi
echo "OK   /api/v1/subject-rankings/subjects items=${subject_count}"

check_http_200 "Spring Boot /api/v1/freshness" \
  "${API_BASE_URL}/api/v1/freshness"

_freshness_body="$(curl -sS "${API_BASE_URL}/api/v1/freshness" || true)"
freshness_stale="$(echo "${_freshness_body}" | python3 -c "
import json, sys
body = sys.stdin.read()
try:
    d = json.loads(body)
    print('true' if d.get('data', {}).get('overall_stale', True) else 'false')
except Exception:
    print('unknown')
")"
missing_sources="$(echo "${_freshness_body}" | python3 -c "
import json, sys
body = sys.stdin.read()
try:
    d = json.loads(body)
    ms = d.get('data', {}).get('missing_sources', [])
    print(len(ms))
except Exception:
    print(0)
")"
echo "OK   /api/v1/freshness overall_stale=${freshness_stale} missing_sources=${missing_sources}"

echo "[5/5] Checking Next.js proxy (optional, skipped if not running)..."
web_status="$(curl -sS -o /dev/null -w "%{http_code}" --connect-timeout 3 \
  "${WEB_BASE_URL}/api/rankings?page=1&pageSize=5" 2>/dev/null || true)"
if [[ "${web_status}" == "200" ]]; then
  echo "OK   Next.js /api/rankings proxy: HTTP 200"
  frontend_status="$(curl -sS -o /dev/null -w "%{http_code}" --connect-timeout 3 \
    "${WEB_BASE_URL}/rankings" 2>/dev/null || true)"
  if [[ "${frontend_status}" == "200" ]]; then
    echo "OK   Next.js /rankings route: HTTP 200"
  else
    echo "WARN Next.js /rankings returned HTTP ${frontend_status}"
  fi
else
  echo "SKIP Next.js not running at ${WEB_BASE_URL} (start with: cd crawlernest/crawlernest-web && npm run dev)"
fi

echo ""
echo "Local stack smoke test passed."
