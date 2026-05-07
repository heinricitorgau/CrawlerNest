#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-test}"
PGPASSWORD="${PGPASSWORD:-test}"
PGDATABASE="${PGDATABASE:-clawer}"
API_PORT="${API_PORT:-8080}"
WEB_PORT="${WEB_PORT:-3000}"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1"
    exit 1
  fi
}

port_in_use() {
  local port="$1"

  if command -v lsof >/dev/null 2>&1; then
    lsof -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
    return $?
  fi

  if command -v ss >/dev/null 2>&1; then
    ss -ltn "( sport = :${port} )" 2>/dev/null | grep -q ":${port}"
    return $?
  fi

  return 1
}

echo "[1/4] Checking local PostgreSQL..."
require_command pg_isready
require_command psql

if ! pg_isready -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" >/dev/null 2>&1; then
  echo "PostgreSQL is not ready at ${PGHOST}:${PGPORT}/${PGDATABASE}."
  echo "Start it first, for example: sudo service postgresql start"
  exit 1
fi

if ! PGPASSWORD="${PGPASSWORD}" psql \
  -h "${PGHOST}" \
  -p "${PGPORT}" \
  -U "${PGUSER}" \
  -d "${PGDATABASE}" \
  -v ON_ERROR_STOP=1 \
  -c "SELECT 1;" >/dev/null; then
  echo "PostgreSQL is reachable, but login failed for ${PGUSER}/${PGDATABASE}."
  echo "Expected local credentials: user=test password=test database=clawer"
  exit 1
fi

echo "[2/4] Checking localhost ports..."
if port_in_use "${API_PORT}"; then
  echo "Port ${API_PORT} is already in use. Stop the existing API process first."
  echo "Helpful check: lsof -i :${API_PORT}"
  exit 1
fi

if port_in_use "${WEB_PORT}"; then
  echo "Port ${WEB_PORT} is already in use. Stop the existing web process first."
  echo "Helpful check: lsof -i :${WEB_PORT}"
  exit 1
fi

API_PID=""
WEB_PID=""

cleanup() {
  if [[ -n "${API_PID}" ]]; then
    kill "${API_PID}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${WEB_PID}" ]]; then
    kill "${WEB_PID}" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

echo "[3/4] Starting Spring Boot API..."
cd "${ROOT_DIR}/crawlernest/servise_for_java"
./mvnw -Dmaven.test.skip=true spring-boot:run &
API_PID=$!

echo "[4/4] Starting Next.js frontend..."
cd "${ROOT_DIR}/crawlernest/crawlernest-web"
npm run dev -- --port "${WEB_PORT}" &
WEB_PID=$!

echo ""
echo "CrawlerNest localhost started:"
echo "API:  http://localhost:${API_PORT}"
echo "Web:  http://localhost:${WEB_PORT}"
echo "Rankings: http://localhost:${WEB_PORT}/rankings"
echo "API smoke: curl \"http://localhost:${API_PORT}/api/v1/rankings?page=1&pageSize=5\""
echo ""
echo "Press Ctrl+C to stop API and frontend."

wait -n "${API_PID}" "${WEB_PID}"
