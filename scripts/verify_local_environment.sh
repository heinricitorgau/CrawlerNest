#!/usr/bin/env bash
# Readonly local environment verification for CrawlerNest.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="${ROOT_DIR}/crawlernest/crawlernest-web"
SPRING_PORT="${SPRING_PORT:-8080}"
NEXT_PORT="${NEXT_PORT:-3000}"
PGHOST="${CRAWLERNEST_PG_HOST:-127.0.0.1}"
PGPORT="${CRAWLERNEST_PG_PORT:-5432}"
PGDATABASE="${CRAWLERNEST_PG_DATABASE:-clawer}"
PGUSER="${CRAWLERNEST_PG_USER:-test}"
VENV_PYTHON="${ROOT_DIR}/.venv/bin/python"
STRICT=false

PASS=0
WARN=0
FAIL=0

usage() {
  echo "Usage: ./scripts/verify_local_environment.sh [--strict]"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --strict) STRICT=true ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1"; usage; exit 1 ;;
  esac
  shift
done

pass() { echo "PASS $*"; PASS=$((PASS + 1)); }
warn() { echo "WARN $*"; WARN=$((WARN + 1)); }
fail() { echo "FAIL $*"; FAIL=$((FAIL + 1)); }

version_ge() {
  local have="$1"
  local need="$2"
  [[ "$(printf '%s\n%s\n' "${need}" "${have}" | sort -V | head -n1)" == "${need}" ]]
}

port_in_use() {
  local port="$1"
  python3 - "$port" <<'PY' 2>/dev/null
import socket
import sys

port = int(sys.argv[1])
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(0.5)
try:
    result = sock.connect_ex(("127.0.0.1", port))
finally:
    sock.close()
raise SystemExit(0 if result == 0 else 1)
PY
}

python_importable() {
  local python_bin="$1"
  local module="$2"
  [[ -x "${python_bin}" ]] || return 2
  "${python_bin}" -c "import ${module}" >/dev/null 2>&1
}

echo "[environment] readonly local verification"

if [[ -d "${ROOT_DIR}/.venv" ]]; then
  pass "Python venv exists: .venv"
else
  warn "Python venv missing: .venv"
fi

CURRENT_PYTHON=""
if command -v python3 >/dev/null 2>&1; then
  CURRENT_PYTHON="$(command -v python3)"
  pass "python3 found: $(python3 --version 2>/dev/null) (${CURRENT_PYTHON})"
  if python_importable "${CURRENT_PYTHON}" "psycopg2"; then
    pass "psycopg2 importable"
  else
    warn "psycopg2 is not importable in current python3"
  fi
else
  fail "python3 not found"
fi

if [[ -x "${VENV_PYTHON}" ]]; then
  pass ".venv python found: $("${VENV_PYTHON}" --version 2>/dev/null) (${VENV_PYTHON})"
else
  warn ".venv python missing or not executable: ${VENV_PYTHON}"
fi

current_has_psycopg2=false
venv_has_psycopg2=false

if [[ -n "${CURRENT_PYTHON}" ]] && python_importable "${CURRENT_PYTHON}" "psycopg2"; then
  current_has_psycopg2=true
fi
if [[ -x "${VENV_PYTHON}" ]] && python_importable "${VENV_PYTHON}" "psycopg2"; then
  venv_has_psycopg2=true
fi

if [[ -n "${CURRENT_PYTHON}" && -x "${VENV_PYTHON}" && "${CURRENT_PYTHON}" != "${VENV_PYTHON}" ]]; then
  warn "current python differs from .venv python"
fi

if "${venv_has_psycopg2}" && ! "${current_has_psycopg2}"; then
  warn "psycopg2 exists in .venv but not current python3; activate .venv for DB scripts"
elif "${current_has_psycopg2}" && ! "${venv_has_psycopg2}"; then
  warn "psycopg2 exists in current python3 but not .venv; install dependencies into .venv"
elif "${venv_has_psycopg2}" && "${current_has_psycopg2}"; then
  pass "psycopg2 consistency: current python and .venv both import it"
else
  fail "psycopg2 missing from both current python3 and .venv"
fi

if command -v pg_isready >/dev/null 2>&1; then
  if pg_isready -h "${PGHOST}" -p "${PGPORT}" -d "${PGDATABASE}" -U "${PGUSER}" >/dev/null 2>&1; then
    pass "PostgreSQL reachable at ${PGHOST}:${PGPORT}/${PGDATABASE}"
  else
    fail "PostgreSQL not reachable at ${PGHOST}:${PGPORT}/${PGDATABASE}"
  fi
else
  warn "pg_isready not found; skipping PostgreSQL reachability check"
fi

if command -v java >/dev/null 2>&1; then
  java_line="$(java -version 2>&1 | head -n 1)"
  pass "Java found: ${java_line}"
else
  fail "java not found"
fi

if [[ -n "${JAVA_HOME:-}" ]]; then
  pass "JAVA_HOME set: ${JAVA_HOME}"
else
  warn "JAVA_HOME is not set"
fi

if command -v node >/dev/null 2>&1; then
  node_version="$(node --version | sed 's/^v//')"
  if version_ge "${node_version}" "20.9.0"; then
    pass "Node.js version ${node_version} >= 20.9"
  else
    fail "Node.js version ${node_version} < 20.9"
  fi
else
  fail "node not found"
fi

if command -v npm >/dev/null 2>&1; then
  pass "npm found: $(npm --version 2>/dev/null)"
else
  fail "npm not found"
fi

if [[ -d "${WEB_DIR}/node_modules" ]]; then
  pass "crawlernest-web/node_modules exists"
else
  fail "crawlernest-web/node_modules missing"
fi

if command -v python3 >/dev/null 2>&1; then
  if port_in_use "${SPRING_PORT}"; then
    warn "Spring Boot port ${SPRING_PORT} is already in use"
  else
    pass "Spring Boot port ${SPRING_PORT} is available"
  fi

  if port_in_use "${NEXT_PORT}"; then
    warn "Next.js port ${NEXT_PORT} is already in use"
  else
    pass "Next.js port ${NEXT_PORT} is available"
  fi
else
  warn "Skipping port checks because python3 is unavailable"
fi

echo ""
echo "Summary: PASS=${PASS} WARN=${WARN} FAIL=${FAIL}"

if "${STRICT}" && [[ "${FAIL}" -gt 0 ]]; then
  exit 1
fi

exit 0
