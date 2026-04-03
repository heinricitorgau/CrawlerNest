#!/usr/bin/env bash
# =============================================================================
# run_production_safe.sh
# CrawlerNest — production-safe pipeline runner
#
# Usage:
#   bash crawlernest/scripts/run_production_safe.sh
#   (or, from any directory)
#   bash /path/to/crawlernest/crawlernest/scripts/run_production_safe.sh
#
# Designed to run under systemd on a long-running Linux desktop node.
# Boring, reliable, no background jobs, no retries — systemd handles restarts.
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# 1. Resolve repo root (script-location independent)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

PIPELINE="crawlernest/run_pipeline.py"
PG_USER="${PG_USER:-test}"
PG_DATABASE="${PG_DATABASE:-clawer}"
# Default deferred-enrichment file (mirrors run_pipeline.py default)
DEFERRED_FILE="crawlernest/crawlernest-kb/databases/pending_detail_enrichment.json"
PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"

# ---------------------------------------------------------------------------
# 2. Timestamped log file
# ---------------------------------------------------------------------------
LOG_DIR="${REPO_ROOT}/logs"
mkdir -p "${LOG_DIR}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/run_${TIMESTAMP}.log"

# Tee all output (stdout + stderr) to log file AND to terminal.
exec > >(tee -a "${LOG_FILE}") 2>&1

render_single_progress_line() {
    "${PYTHON_BIN}" -u -c '
import sys

normal_buffer = []
progress_buffer = []
in_progress = False

def flush_normal() -> None:
    global normal_buffer
    if normal_buffer:
        sys.stdout.write("".join(normal_buffer))
        sys.stdout.flush()
        normal_buffer = []

def flush_progress(final: bool) -> None:
    global progress_buffer, in_progress
    if progress_buffer:
        line = "".join(progress_buffer)
        if final:
            sys.stdout.write("\r" + line + "\n")
        else:
            sys.stdout.write("\r" + line)
        sys.stdout.flush()
    progress_buffer = []
    in_progress = False

while True:
    chunk = sys.stdin.read(1)
    if not chunk:
        break
    if chunk == "\r":
        flush_normal()
        progress_buffer = []
        in_progress = True
        continue
    if chunk == "\n":
        if in_progress:
            flush_progress(final=True)
        else:
            normal_buffer.append(chunk)
            flush_normal()
        continue
    if in_progress:
        progress_buffer.append(chunk)
    else:
        normal_buffer.append(chunk)

flush_normal()
if in_progress:
    flush_progress(final=True)
'
}

run_with_single_progress_line() {
    "$@" 2>&1 | render_single_progress_line
}

run_qs_region_single_pass() {
    local region="$1"
    local limit="$2"

    "${PYTHON_BIN}" -u - "${PYTHON_BIN}" "${PIPELINE}" "${region}" "${PG_USER}" "${PG_DATABASE}" "${limit}" <<'PY'
import re
import signal
import subprocess
import sys

python_bin, pipeline, region, pg_user, pg_database, limit = sys.argv[1:]
cmd = [
    python_bin,
    pipeline,
    "run-qs-region",
    "--region",
    region,
    "--ranking-year",
    "2026",
    "--limit",
    limit,
    "--pg-user",
    pg_user,
    "--pg-database",
    pg_database,
]

completion_marker = f"[qs-universe] region/{region} "
saw_completion = False
rows_written = None
_rows_m = re.compile(r"rows_written=(\d+)")
proc = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
)

assert proc.stdout is not None
for line in proc.stdout:
    sys.stdout.write(line)
    sys.stdout.flush()
    if not saw_completion and completion_marker in line and "matched=" in line:
        saw_completion = True
        m = _rows_m.search(line)
        if m:
            rows_written = int(m.group(1))
        try:
            proc.send_signal(signal.SIGINT)
        except ProcessLookupError:
            pass

return_code = proc.wait()
if saw_completion and return_code in (0, -signal.SIGINT, 130):
    # Exit 3: run finished but wrote 0 rows (e.g. live_blocked_no_fallback) — not a subprocess crash.
    if rows_written is not None and rows_written == 0:
        sys.exit(3)
    sys.exit(0)
sys.exit(return_code)
PY
}

# ---------------------------------------------------------------------------
# 3. Pre-flight environment checks
# ---------------------------------------------------------------------------
if ! command -v python3 &>/dev/null; then
    if [[ ! -x "${PYTHON_BIN}" ]]; then
        echo "[ERROR] python3 not found in PATH and project venv is unavailable."
        echo "        Expected interpreter: ${PYTHON_BIN}"
        exit 1
    fi
fi

if [[ ! -x "${PYTHON_BIN}" ]]; then
    PYTHON_BIN="$(command -v python3)"
fi

if [[ ! -f "${REPO_ROOT}/${PIPELINE}" ]]; then
    echo "[ERROR] Pipeline entrypoint not found: ${REPO_ROOT}/${PIPELINE}"
    exit 1
fi

# ---------------------------------------------------------------------------
# 4. Timing
# ---------------------------------------------------------------------------
START_TS="$(date +%s)"

echo ""
echo "============================================================"
echo "[START]  $(date '+%Y-%m-%d %H:%M:%S')"
echo "         Log  : ${LOG_FILE}"
echo "         Root : ${REPO_ROOT}"
echo "         Py   : ${PYTHON_BIN}"
echo "============================================================"
echo ""

# ---------------------------------------------------------------------------
# 5. STEP 1 — Rankings-only crawl
# ---------------------------------------------------------------------------
# QS World Ranking 2026 generally contains ~1500-1700 rows.
# Set LIMIT to 2500 to ensure we capture the entire dataset.
LIMIT=${1:-2500}
RESUME_FLAG="${2:-}"
RESUME_ARGS=()
RESUME_LABEL="disabled"

if [[ "${RESUME_FLAG}" == "--resume" ]]; then
    RESUME_ARGS+=("--resume")
    RESUME_LABEL="enabled"
fi

echo "[STEP 1] Starting rankings-only crawl (LIMIT: ${LIMIT})  ($(date '+%H:%M:%S'))"
echo "         Resume: ${RESUME_LABEL}"
echo "         ${PYTHON_BIN} ${PIPELINE} run --limit ${LIMIT} --ranking-year 2026 \\"
echo "           --workers 1 --request-delay 10 --local-parse-workers 4 \\"
echo "           --write-batch-size 200 --rankings-only --resource-guard ${RESUME_FLAG}"
echo ""

run_with_single_progress_line "${PYTHON_BIN}" "${PIPELINE}" run \
    --limit "${LIMIT}" \
    --ranking-year 2026 \
    --workers 1 \
    --request-delay 10 \
    --local-parse-workers 4 \
    --write-batch-size 200 \
    --rankings-only \
    --resource-guard \
    ${RESUME_ARGS[@]+"${RESUME_ARGS[@]}"}

STEP1_EXIT=$?
if [[ ${STEP1_EXIT} -ne 0 ]]; then
    echo ""
    echo "[ERROR] STEP 1 (rankings crawl) failed with exit code ${STEP1_EXIT}."
    echo "        Check log: ${LOG_FILE}"
    exit ${STEP1_EXIT}
fi

echo ""
echo "[STEP 1] Rankings crawl completed successfully.  ($(date '+%H:%M:%S'))"
echo ""

# ---------------------------------------------------------------------------
# 6. STEP 2 — Deferred detail enrichment (optional, safe if file missing)
# ---------------------------------------------------------------------------
STEP2_TRIGGERED=false

if [[ -f "${DEFERRED_FILE}" ]]; then
    # Check file is non-empty (non-empty JSON array means at least "[]" — 2 bytes;
    # we require at least one entry, so the file must contain '[{' somewhere).
    if "${PYTHON_BIN}" -c "
import json, sys
try:
    data = json.load(open('${DEFERRED_FILE}'))
    sys.exit(0 if isinstance(data, list) and len(data) > 0 else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
        STEP2_TRIGGERED=true
        echo "[STEP 2] pending_detail_enrichment.json found with entries — starting enrichment  ($(date '+%H:%M:%S'))"
        echo "         ${PYTHON_BIN} ${PIPELINE} enrich-details --limit 30 --request-delay 20"
        echo "         (20s delay: high-traffic QS pages require longer inter-request gap)"
        echo ""

        run_with_single_progress_line "${PYTHON_BIN}" "${PIPELINE}" enrich-details \
            --limit 30 \
            --request-delay 20

        STEP2_EXIT=$?
        if [[ ${STEP2_EXIT} -ne 0 ]]; then
            echo ""
            echo "[WARN]   STEP 2 (detail enrichment) exited with code ${STEP2_EXIT}."
            echo "         Rankings data is intact. This is non-fatal; enrichment will resume next run."
            # Do NOT exit — rankings succeeded; enrichment failure is recoverable.
        else
            echo ""
            echo "[STEP 2] Detail enrichment completed.  ($(date '+%H:%M:%S'))"
        fi
    else
        echo "[STEP 2] SKIP — ${DEFERRED_FILE} is empty or contains no pending entries."
    fi
else
    echo "[STEP 2] SKIP — ${DEFERRED_FILE} not found (no deferred enrichment queued)."
fi

echo ""

# ---------------------------------------------------------------------------
# 7. STEP 3 — THE world rankings ingestion
# ---------------------------------------------------------------------------
STEP3_TRIGGERED=true
STEP3_EXIT=0

echo "[STEP 3] Starting THE rankings ingestion  ($(date '+%H:%M:%S'))"
echo "         ${PYTHON_BIN} ${PIPELINE} run-the-rankings \\"
echo "           --ranking-year 2026 --pg-user ${PG_USER} --pg-database ${PG_DATABASE}"
echo ""

if run_with_single_progress_line "${PYTHON_BIN}" "${PIPELINE}" run-the-rankings \
    --ranking-year 2026 \
    --pg-user "${PG_USER}" \
    --pg-database "${PG_DATABASE}"; then
    STEP3_EXIT=0
    echo ""
    echo "[STEP 3] THE rankings ingestion completed.  ($(date '+%H:%M:%S'))"
else
    STEP3_EXIT=$?
    echo ""
    echo "[WARN] STEP 3 (THE rankings) exited with code ${STEP3_EXIT}. Continuing."
fi

echo ""

# ---------------------------------------------------------------------------
# 9. STEP 4 — QS major universe rankings
# ---------------------------------------------------------------------------
STEP4_TRIGGERED=true
STEP4_EXIT=0
STEP4_SUCCEEDED=()
STEP4_FAILED=()
STEP4_REGIONS=(europe asia latin-america arab-region oceania africa north-america)

echo "[STEP 4] Starting QS major universe ingestion  ($(date '+%H:%M:%S'))"

for region in "${STEP4_REGIONS[@]}"; do
    echo "         ${PYTHON_BIN} ${PIPELINE} run-qs-region --region ${region} \\"
    echo "           --ranking-year 2026 --limit 2500 --pg-user ${PG_USER} --pg-database ${PG_DATABASE}"
    echo ""

    region_exit=0
    run_with_single_progress_line run_qs_region_single_pass "${region}" "2500" || region_exit=$?
    if [[ ${region_exit} -eq 0 ]]; then
        STEP4_SUCCEEDED+=("${region}")
        echo ""
        echo "[STEP 4] region ${region} completed.  ($(date '+%H:%M:%S'))"
    elif [[ ${region_exit} -eq 3 ]]; then
        STEP4_EXIT=1
        STEP4_FAILED+=("${region}")
        echo ""
        echo "[WARN] STEP 4 region ${region} finished with 0 rows_written (live blocked / no fallback data). Continuing."
    else
        STEP4_EXIT=1
        STEP4_FAILED+=("${region}")
        echo ""
        echo "[WARN] STEP 4 region ${region} failed (exit ${region_exit}). Continuing."
    fi
    echo ""
done

echo "[STEP 4] succeeded regions: ${STEP4_SUCCEEDED[*]:-none}"
echo "[STEP 4] failed regions: ${STEP4_FAILED[*]:-none}"
echo ""

# ---------------------------------------------------------------------------
# 10. STEP 5 — Seed canonical from missing THE entities
# ---------------------------------------------------------------------------
STEP5_TRIGGERED=true
STEP5_EXIT=0

echo "[STEP 5] Seeding canonical entities from missing THE log  ($(date '+%H:%M:%S'))"
echo "         ${PYTHON_BIN} ${PIPELINE} seed-canonical-from-missing \\"
echo "           --pg-user ${PG_USER} --pg-database ${PG_DATABASE}"
echo ""

if run_with_single_progress_line "${PYTHON_BIN}" "${PIPELINE}" seed-canonical-from-missing \
    --pg-user "${PG_USER}" \
    --pg-database "${PG_DATABASE}"; then
    STEP5_EXIT=0
    echo ""
    echo "[STEP 5] Seeding completed.  ($(date '+%H:%M:%S'))"
else
    STEP5_EXIT=$?
    echo ""
    echo "[WARN] STEP 5 failed with exit ${STEP5_EXIT}. Continuing."
fi

echo ""

# ---------------------------------------------------------------------------
# 11. Summary
# ---------------------------------------------------------------------------
END_TS="$(date +%s)"
DURATION=$(( END_TS - START_TS ))
DURATION_FMT="$(printf '%02dh %02dm %02ds' $((DURATION/3600)) $((DURATION%3600/60)) $((DURATION%60)))"

STEP2_SUMMARY="Step 2: skipped (no pending enrichment)"
if [[ "${STEP2_TRIGGERED}" == "true" ]]; then
    STEP2_SUMMARY="Step 2: detail enrichment"
fi

STEP3_SUMMARY=""
if [[ "${STEP3_TRIGGERED}" == "true" ]]; then
    STEP3_SUMMARY="Step 3: THE rankings"
    if [[ ${STEP3_EXIT} -ne 0 ]]; then
        STEP3_SUMMARY="${STEP3_SUMMARY} (warn)"
    fi
fi

STEP4_SUMMARY=""
if [[ "${STEP4_TRIGGERED}" == "true" ]]; then
    STEP4_SUMMARY="Step 4: QS major universes"
    if [[ ${STEP4_EXIT} -ne 0 ]]; then
        STEP4_SUMMARY="${STEP4_SUMMARY} (warn)"
    fi
fi

STEP5_SUMMARY=""
if [[ "${STEP5_TRIGGERED}" == "true" ]]; then
    STEP5_SUMMARY="Step 5: seed canonical from missing THE"
    if [[ ${STEP5_EXIT} -ne 0 ]]; then
        STEP5_SUMMARY="${STEP5_SUMMARY} (warn)"
    fi
fi

echo "============================================================"
echo "[END]      $(date '+%Y-%m-%d %H:%M:%S')"
echo "[DURATION] ${DURATION_FMT}  (${DURATION}s)"
echo "[STAGES]   Step 1: rankings crawl  |  ${STEP2_SUMMARY}  |  ${STEP3_SUMMARY}  |  ${STEP4_SUMMARY}  |  ${STEP5_SUMMARY}"
echo "           Log written to: ${LOG_FILE}"
echo "============================================================"
echo ""
