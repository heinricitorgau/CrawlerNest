#!/usr/bin/env bash
# API endpoint checks against a running Spring Boot.
#
# Extracted from smoke_release.sh so there is one copy. The difference between
# the two callers is what an unreachable API means, and that is the caller's to
# decide: smoke_release.sh skips these when nobody has the server running
# locally, while the CI job runs this directly after waiting for /health, where
# unreachable is a failure rather than a reason to pass quietly.
#
# Exits non-zero if any check fails. Reachability is not special-cased here --
# a server that does not answer fails the first check, which is the point.
set -uo pipefail

API_BASE="${API_BASE:-http://localhost:8080}"

PASS=0
FAIL=0

ok()   { echo "OK   $*"; PASS=$((PASS + 1)); }
fail() { echo "FAIL $*"; FAIL=$((FAIL + 1)); }

check_endpoint() {
  local label="$1"
  local url="$2"
  local status
  status="$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 5 "${url}" 2>/dev/null || true)"
  if [[ "${status}" == "200" ]]; then
    ok "${label}: HTTP 200"
  else
    fail "${label}: expected 200, got ${status:-no response}"
  fi
}

check_endpoint "/api/v1/health"               "${API_BASE}/api/v1/health"
check_endpoint "/api/v1/freshness"            "${API_BASE}/api/v1/freshness"
check_endpoint "/api/v1/diagnostics/rankings" "${API_BASE}/api/v1/diagnostics/rankings"
check_endpoint "/api/v1/diagnostics/subjects" "${API_BASE}/api/v1/diagnostics/subjects"

# A 200 from /health says the process is up; this says it can actually reach the
# warehouse. Without it the endpoint answers fine while every query behind it
# fails, which is the failure worth catching.
health_pg="$(curl -sS --connect-timeout 5 "${API_BASE}/api/v1/health" 2>/dev/null | \
  python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print('true' if d.get('data', {}).get('postgres_connected') else 'false')
except Exception:
    print('false')
" 2>/dev/null || echo 'false')"
if [[ "${health_pg}" == "true" ]]; then
  ok "/api/v1/health: postgres_connected=true"
else
  fail "/api/v1/health: postgres_connected is not true"
fi

echo ""
echo "API endpoint checks: ${PASS} passed, ${FAIL} failed"

if (( FAIL > 0 )); then
  exit 1
fi
