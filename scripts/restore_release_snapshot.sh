#!/usr/bin/env bash
# Restore a frozen release into an empty database and check it against the release's manifest.json.
#
#   PGDATABASE=clawer ./scripts/restore_release_snapshot.sh                       # the latest release
#   RELEASE_DIR=docs/releases/v0.2-2026-snapshot ./scripts/restore_release_snapshot.sh
#
# The counts used to be literals in this file, which made it a check of v0.2 alone. They now live in each
# release's manifest.json, written by `scripts/release_snapshot.py build` from a restored copy of the dump.
# Set API_BASE_URL (e.g. http://localhost:8080) to smoke-test the API against the restored data as well.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELEASE_DIR="${RELEASE_DIR:-${ROOT_DIR}/docs/releases/v0.3-multi-year-snapshot}"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
[[ -x "${PYTHON_BIN}" ]] || PYTHON_BIN="python3"
export PGHOST="${PGHOST:-localhost}" PGPORT="${PGPORT:-5432}" PGUSER="${PGUSER:-test}"
export PGPASSWORD="${PGPASSWORD:-test}" PGDATABASE="${PGDATABASE:-clawer}"

MANIFEST="${RELEASE_DIR}/manifest.json"
if [[ ! -f "${MANIFEST}" ]]; then
  echo "No manifest.json in ${RELEASE_DIR}" >&2
  exit 1
fi
SNAPSHOT_FILE="${RELEASE_DIR}/$("${PYTHON_BIN}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["dump"]["file"])' "${MANIFEST}")"

for attempt in $(seq 1 30); do
  if pg_isready -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" >/dev/null 2>&1; then
    break
  fi
  if [[ "${attempt}" == "30" ]]; then
    echo "PostgreSQL did not become ready at ${PGHOST}:${PGPORT}/${PGDATABASE}." >&2
    exit 1
  fi
  sleep 2
done

echo "Restoring ${SNAPSHOT_FILE} into ${PGDATABASE}..."
pg_restore -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDATABASE}" \
  --no-owner --no-acl --exit-on-error "${SNAPSHOT_FILE}"

echo "Verifying against ${MANIFEST}..."
"${PYTHON_BIN}" "${ROOT_DIR}/scripts/release_snapshot.py" verify --release-dir "${RELEASE_DIR}"

if [[ -n "${API_BASE_URL:-}" ]]; then
  echo "Verifying API endpoints at ${API_BASE_URL}..."
  rankings="$(curl --fail --silent --show-error "${API_BASE_URL}/api/v1/rankings?page=1&pageSize=1")"
  trends="$(curl --fail --silent --show-error "${API_BASE_URL}/api/v1/analytics/ranking-trends")"
  "${PYTHON_BIN}" - "${MANIFEST}" "${rankings}" "${trends}" <<'PY'
import json, sys
manifest = json.load(open(sys.argv[1]))
rankings = json.loads(sys.argv[2])["data"]
trends = json.loads(sys.argv[3])["data"]
by_year = manifest["counts"]["aggregated_rows_by_year_universe"]
latest = max(int(year) for year in by_year)
item = rankings["items"][0]
assert item["rankingYear"] == latest, item
assert rankings["metadata"]["totalCount"] == by_year[str(latest)]["global"], rankings["metadata"]
years = trends["available_years"]
assert latest in years and set(years) <= {int(y) for y in by_year}, years
assert trends["single_year_only"] is (len(years) == 1), trends
print(f"OK   API serves {latest} ({rankings['metadata']['totalCount']} global rows), trend years {years}")
PY
fi
