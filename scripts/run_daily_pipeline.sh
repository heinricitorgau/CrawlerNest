#!/usr/bin/env bash
# CrawlerNest daily pipeline runner.
#
# Flow:
#   1. Verify prerequisites (PostgreSQL, Python venv)
#   2. bootstrap-postgres (idempotent)
#   3. run global rankings
#   4. run subject rankings
#   5. smoke_local_stack.sh (requires Spring Boot + Next.js)
#   6. ranking regression + source drift evaluation
#   7. export_system_snapshot.py
#   8. build_failure_summary.py
#   9. export_metadata_bundle.sh
#
# All output is tee'd to logs/daily_pipeline_YYYYMMDD.log
#
# Usage:
#   ./scripts/run_daily_pipeline.sh [--dry-run] [--skip-smoke]
#     [--ranking-year 2026] [--limit 30]
#     [--pg-password test] [--pg-database clawer]
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── Defaults ──────────────────────────────────────────────────────────────────
DRY_RUN=false
SKIP_SMOKE=false
RANKING_YEAR="${RANKING_YEAR:-$(date +%Y)}"
LIMIT="${LIMIT:-30}"
PG_HOST="${PGHOST:-localhost}"
PG_PORT="${PGPORT:-5432}"
PG_USER="${PGUSER:-test}"
PG_PASSWORD="${PGPASSWORD:-test}"
PG_DATABASE="${PGDATABASE:-clawer}"

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)        DRY_RUN=true ;;
    --skip-smoke)     SKIP_SMOKE=true ;;
    --ranking-year)   RANKING_YEAR="$2"; shift ;;
    --limit)          LIMIT="$2"; shift ;;
    --pg-password)    PG_PASSWORD="$2"; shift ;;
    --pg-database)    PG_DATABASE="$2"; shift ;;
    --pg-user)        PG_USER="$2"; shift ;;
    --pg-host)        PG_HOST="$2"; shift ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
  shift
done

# ── Logging setup ─────────────────────────────────────────────────────────────
DATESTAMP="$(date +%Y%m%d)"
LOG_DIR="${ROOT_DIR}/logs"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/daily_pipeline_${DATESTAMP}.log"

exec > >(tee -a "${LOG_FILE}") 2>&1

PIPELINE_START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "============================================================"
echo "CrawlerNest Daily Pipeline — ${PIPELINE_START}"
echo "  ranking_year=${RANKING_YEAR}  limit=${LIMIT}"
echo "  pg=${PG_USER}@${PG_HOST}:${PG_PORT}/${PG_DATABASE}"
echo "  dry_run=${DRY_RUN}  skip_smoke=${SKIP_SMOKE}"
echo "============================================================"

# ── Helpers ───────────────────────────────────────────────────────────────────
run_cmd() {
  local label="$1"; shift
  echo ""
  echo "[$(date -u +%H:%M:%SZ)] STEP: ${label}"
  if "${DRY_RUN}"; then
    echo "  [dry-run] would run: $*"
    return 0
  fi
  "$@"
  echo "[$(date -u +%H:%M:%SZ)] DONE: ${label}"
}

PG_FLAGS=(
  "--pg-host" "${PG_HOST}"
  "--pg-port" "${PG_PORT}"
  "--pg-user" "${PG_USER}"
  "--pg-password" "${PG_PASSWORD}"
  "--pg-database" "${PG_DATABASE}"
)

PYTHON="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
  PYTHON="$(command -v python3 || true)"
  if [[ -z "${PYTHON}" ]]; then
    echo "ERROR: Python not found. Activate the venv first: source .venv/bin/activate"
    exit 1
  fi
fi

# ── Step 1: Verify PostgreSQL ─────────────────────────────────────────────────
echo ""
echo "[1/9] Verifying PostgreSQL connectivity..."
if ! PGPASSWORD="${PG_PASSWORD}" psql \
    -h "${PG_HOST}" -p "${PG_PORT}" -U "${PG_USER}" -d "${PG_DATABASE}" \
    -v ON_ERROR_STOP=1 -c "SELECT 1;" >/dev/null 2>&1; then
  echo "ERROR: Cannot connect to PostgreSQL ${PG_USER}@${PG_HOST}:${PG_PORT}/${PG_DATABASE}"
  echo "  Start PostgreSQL: sudo service postgresql start"
  exit 1
fi
echo "OK   PostgreSQL connected"

# ── Step 2: bootstrap-postgres ────────────────────────────────────────────────
run_cmd "bootstrap-postgres (idempotent)" \
  "${PYTHON}" -m crawlernest.run_pipeline bootstrap-postgres \
    "${PG_FLAGS[@]}"

# ── Step 3: Global rankings pipeline ─────────────────────────────────────────
run_cmd "global rankings (year=${RANKING_YEAR} limit=${LIMIT})" \
  "${PYTHON}" -m crawlernest.run_pipeline run \
    --ranking-year "${RANKING_YEAR}" \
    --limit "${LIMIT}" \
    --skip-existing-source \
    "${PG_FLAGS[@]}"

# ── Step 4: Subject rankings ──────────────────────────────────────────────────
for SUBJECT in computer-science electrical-engineering; do
  run_cmd "subject ranking: ${SUBJECT} (year=${RANKING_YEAR})" \
    "${PYTHON}" -m crawlernest.run_pipeline run-qs-subject \
      --subject "${SUBJECT}" \
      --year "${RANKING_YEAR}" \
      --skip-existing-year \
      "${PG_FLAGS[@]}"
done

# ── Step 5: Smoke test (optional) ────────────────────────────────────────────
if "${SKIP_SMOKE}"; then
  echo ""
  echo "[5/9] SKIP smoke_local_stack.sh (--skip-smoke)"
else
  echo ""
  echo "[5/9] Running smoke_local_stack.sh..."
  if "${DRY_RUN}"; then
    echo "  [dry-run] would run: ${ROOT_DIR}/scripts/smoke_local_stack.sh"
  else
    PGHOST="${PG_HOST}" PGPORT="${PG_PORT}" PGUSER="${PG_USER}" \
    PGPASSWORD="${PG_PASSWORD}" PGDATABASE="${PG_DATABASE}" \
    "${ROOT_DIR}/scripts/smoke_local_stack.sh" || {
      echo "WARN smoke_local_stack.sh failed — continuing pipeline"
    }
  fi
fi

# ── Step 6: Evaluation runners ────────────────────────────────────────────────
AUTOEVAL="${ROOT_DIR}/crawlernest/crawlernest-autoeval/runners"

run_cmd "ranking regression" \
  "${PYTHON}" "${AUTOEVAL}/run_ranking_regression.py" \
    "${PG_FLAGS[@]}" || {
  echo "WARN ranking regression reported failures — check output above"
}

run_cmd "source drift detection" \
  "${PYTHON}" "${AUTOEVAL}/run_source_drift.py" \
    "${PG_FLAGS[@]}" || true

run_cmd "canonical diagnostics" \
  "${PYTHON}" "${AUTOEVAL}/run_canonical_diagnostics.py" \
    "${PG_FLAGS[@]}" || true

run_cmd "subject evaluation" \
  "${PYTHON}" "${AUTOEVAL}/run_subject_eval.py" \
    "${PG_FLAGS[@]}" || true

# ── Step 7: Export system snapshot ───────────────────────────────────────────
run_cmd "export system snapshot" \
  "${PYTHON}" "${ROOT_DIR}/scripts/export_system_snapshot.py" \
    "${PG_FLAGS[@]}"

# ── Step 8: Build failure summary ────────────────────────────────────────────
run_cmd "build failure summary" \
  "${PYTHON}" "${ROOT_DIR}/scripts/build_failure_summary.py" \
    "${PG_FLAGS[@]}"

# ── Step 9: Export metadata bundle ───────────────────────────────────────────
run_cmd "export metadata bundle" \
  "${ROOT_DIR}/scripts/export_metadata_bundle.sh"

# ── Done ──────────────────────────────────────────────────────────────────────
PIPELINE_END="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""
echo "============================================================"
echo "Pipeline finished: ${PIPELINE_END}"
echo "Log: ${LOG_FILE}"
echo "Snapshot: ${ROOT_DIR}/snapshots/latest_status.json"
echo "Report:   ${ROOT_DIR}/reports/latest_failure_summary.md"
echo "============================================================"
