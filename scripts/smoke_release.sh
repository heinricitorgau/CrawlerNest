#!/usr/bin/env bash
# Release smoke test — verifies build artefacts only.
# Does NOT require running services for the compile/build steps.
# API endpoint checks are skipped if Spring Boot is not reachable.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JAVA_DIR="${ROOT_DIR}/crawlernest/servise_for_java"
WEB_DIR="${ROOT_DIR}/crawlernest/crawlernest-web"
CRAWLERNEST_DIR="${ROOT_DIR}/crawlernest"
API_BASE="${API_BASE:-http://localhost:8080}"

# Auto-activate nvm if current Node is too old and nvm is available.
_node_major_now() { node --version 2>/dev/null | cut -d. -f1 | tr -d 'v'; }
if command -v node >/dev/null 2>&1 && (( $(_node_major_now) < 20 )); then
  if [[ -s "${NVM_DIR:-${HOME}/.nvm}/nvm.sh" ]]; then
    # shellcheck source=/dev/null
    source "${NVM_DIR:-${HOME}/.nvm}/nvm.sh"
    nvm use 20 >/dev/null 2>&1 || true
  fi
fi

PASS=0
FAIL=0

ok()   { echo "OK   $*"; (( PASS++ )) || true; }
fail() { echo "FAIL $*"; (( FAIL++ )) || true; }
skip() { echo "SKIP $*"; }

# ---------------------------------------------------------------------------
# 1. Spring Boot compile
# ---------------------------------------------------------------------------
echo "[1/4] Spring Boot compile (no tests)..."
if [[ ! -f "${JAVA_DIR}/mvnw" ]]; then
  fail "mvnw not found at ${JAVA_DIR}/mvnw"
else
  compile_out="$(cd "${JAVA_DIR}" && ./mvnw compile -q -Dmaven.test.skip=true 2>&1)" && rc=0 || rc=$?
  if [[ ${rc} -eq 0 ]]; then
    ok "Spring Boot compile: BUILD SUCCESS"
  else
    fail "Spring Boot compile failed"
    echo "${compile_out}" | tail -20
  fi
fi

# ---------------------------------------------------------------------------
# 2. Next.js build
# ---------------------------------------------------------------------------
echo "[2/4] Next.js build..."
if [[ ! -d "${WEB_DIR}/node_modules" ]]; then
  fail "node_modules not found — run: cd crawlernest/crawlernest-web && npm install"
else
  # Detect Node.js version
  if ! command -v node >/dev/null 2>&1; then
    fail "node not found — install Node.js >= 20.9 (nvm install 20)"
  else
    _node_major="$(node --version 2>/dev/null | cut -d. -f1 | tr -d 'v')"
    if (( _node_major < 20 )); then
      fail "Node.js >= 20.9 required, found $(node --version) — run: nvm use 20"
    else
      build_out="$(cd "${WEB_DIR}" && npm run build 2>&1)" && rc=0 || rc=$?
      if [[ ${rc} -eq 0 ]]; then
        ok "Next.js build: success (Node $(node --version))"
      else
        fail "Next.js build failed"
        echo "${build_out}" | tail -30
      fi
    fi
  fi
fi

# ---------------------------------------------------------------------------
# 3. Python syntax check
# ---------------------------------------------------------------------------
echo "[3/4] Python syntax check..."
if ! command -v python3 >/dev/null 2>&1; then
  fail "python3 not found"
else
  py_errors=0

  check_py() {
    local f="$1"
    if ! python3 -m py_compile "${f}" 2>/dev/null; then
      fail "Python syntax error: ${f}"
      (( py_errors++ )) || true
    fi
  }

  check_py "${CRAWLERNEST_DIR}/run_pipeline.py"
  check_py "${CRAWLERNEST_DIR}/pipeline/cli.py"

  # Check all .py files under pipeline/ and subjects/
  while IFS= read -r -d '' pyfile; do
    check_py "${pyfile}"
  done < <(find "${CRAWLERNEST_DIR}/pipeline" -name "*.py" -print0 2>/dev/null)

  if [[ ${py_errors} -eq 0 ]]; then
    ok "Python syntax: all files OK"
  fi
fi

# ---------------------------------------------------------------------------
# 4. API endpoint checks (skipped if Spring Boot is not running)
# ---------------------------------------------------------------------------
echo "[4/4] API endpoint checks (optional — requires Spring Boot on ${API_BASE})..."

api_reachable=false
reach_status="$(curl -sS -o /dev/null -w "%{http_code}" \
  --connect-timeout 3 "${API_BASE}/api/v1/health" 2>/dev/null || true)"
if [[ "${reach_status}" == "200" ]]; then
  api_reachable=true
fi

if ! ${api_reachable}; then
  skip "Spring Boot not reachable at ${API_BASE} — start it to run endpoint checks"
else
  check_endpoint() {
    local label="$1"
    local url="$2"
    local status
    status="$(curl -sS -o /dev/null -w "%{http_code}" --connect-timeout 5 "${url}" 2>/dev/null || true)"
    if [[ "${status}" == "200" ]]; then
      ok "${label}: HTTP 200"
    else
      fail "${label}: expected 200, got ${status}"
    fi
  }

  check_endpoint "/api/v1/health"               "${API_BASE}/api/v1/health"
  check_endpoint "/api/v1/freshness"            "${API_BASE}/api/v1/freshness"
  check_endpoint "/api/v1/diagnostics/rankings" "${API_BASE}/api/v1/diagnostics/rankings"
  check_endpoint "/api/v1/diagnostics/subjects" "${API_BASE}/api/v1/diagnostics/subjects"

  # Verify postgres_connected in health response
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
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "Results: ${PASS} passed, ${FAIL} failed"
echo ""

if [[ ${FAIL} -gt 0 ]]; then
  echo "Release smoke FAILED."
  exit 1
fi

echo "Release smoke passed."
