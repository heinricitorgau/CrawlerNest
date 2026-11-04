#!/usr/bin/env bash
# Recapture the README screenshots from a running local stack.
#
# The README says its screenshots come from a local run against the real
# database, so this refuses to run unless the Spring Boot API answers with
# data; a stand-in or an empty warehouse would make that sentence false.
#
# Start the stack first (./scripts/start_localhost.sh), then:
#   ./scripts/capture_readme_screenshots.sh
#   WEB_BASE_URL=http://localhost:4000 ./scripts/capture_readme_screenshots.sh
#   PLAYWRIGHT_CHANNEL=chrome ./scripts/capture_readme_screenshots.sh   # use an installed Google Chrome
#
# Writes docs/assets/screenshots/rankings.png and analytics.png in place.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_BASE_URL="${API_BASE_URL:-http://localhost:8080}"
WEB_BASE_URL="${WEB_BASE_URL:-http://localhost:${WEB_PORT:-3000}}"
OUT_DIR="${OUT_DIR:-${ROOT_DIR}/docs/assets/screenshots}"
PLAYWRIGHT_VERSION="${PLAYWRIGHT_VERSION:-1.49.1}"
PLAYWRIGHT_CHANNEL="${PLAYWRIGHT_CHANNEL:-}"
TMP_DIR="${ROOT_DIR}/.local/tmp"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "FAIL missing required command: $1"
    exit 1
  fi
}

require_command curl
require_command npx

echo "[1/3] Checking the stack..."
rankings_json="$(curl -sS "${API_BASE_URL}/api/v1/rankings?page=1&pageSize=1&year=2026" || true)"
if ! grep -q '"totalCount"' <<<"${rankings_json}"; then
  echo "FAIL the Spring Boot API at ${API_BASE_URL} did not return rankings."
  echo "     Start it first: ./scripts/start_localhost.sh"
  exit 1
fi
if grep -q '"totalCount":0[,}]' <<<"${rankings_json}"; then
  echo "FAIL the API returned zero rankings; load the warehouse before capturing."
  exit 1
fi
web_status="$(curl -sS -o /dev/null -w "%{http_code}" "${WEB_BASE_URL}/" || true)"
if [[ "${web_status}" != "200" ]]; then
  echo "FAIL the web app at ${WEB_BASE_URL} returned HTTP ${web_status}."
  echo "     Set WEB_BASE_URL (or WEB_PORT) to where Next.js is running."
  exit 1
fi
echo "OK   API and web are up"

echo "[2/3] Preparing a headless browser (Playwright ${PLAYWRIGHT_VERSION})..."
if [[ -n "${PLAYWRIGHT_CHANNEL}" ]]; then
  browser_args=(--channel "${PLAYWRIGHT_CHANNEL}")
  echo "OK   using the installed ${PLAYWRIGHT_CHANNEL}"
elif ! npx -y "playwright@${PLAYWRIGHT_VERSION}" install chromium >/dev/null; then
  echo "FAIL could not install Chromium for Playwright."
  echo "     On a fresh WSL it may need system libraries once:"
  echo "       sudo npx -y playwright@${PLAYWRIGHT_VERSION} install-deps chromium"
  exit 1
else
  browser_args=(--browser chromium)
fi

# Accept the cookie notice and clear any shortlist, so the shots show the page
# a first-time visitor sees without the consent bar over it.
mkdir -p "${TMP_DIR}" "${OUT_DIR}"
storage_file="${TMP_DIR}/readme-screenshot-storage.json"
origin="$(sed -E 's#^(https?://[^/]+).*#\1#' <<<"${WEB_BASE_URL}")"
cat > "${storage_file}" <<JSON
{"cookies": [], "origins": [{"origin": "${origin}", "localStorage": [
  {"name": "crawlernest_cookie_consent", "value": "accepted"}
]}]}
JSON

capture() {
  local path="$1" file="$2" height="$3"
  npx -y "playwright@${PLAYWRIGHT_VERSION}" screenshot \
    "${browser_args[@]}" \
    --load-storage "${storage_file}" \
    --viewport-size "1100,${height}" \
    --wait-for-timeout 2500 \
    "${WEB_BASE_URL}${path}" "${OUT_DIR}/${file}" >/dev/null
  echo "OK   ${file}"
}

echo "[3/3] Capturing..."
capture "/" "rankings.png" 1450
capture "/analytics" "analytics.png" 1300

echo
echo "Done. Review the two files, then check the README captions still match"
echo "what they show (the rankings caption quotes a university count)."
