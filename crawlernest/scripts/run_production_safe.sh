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
# Default deferred-enrichment file (mirrors run_pipeline.py default)
DEFERRED_FILE="crawlernest/crawlernest-kb/databases/pending_detail_enrichment.json"

# ---------------------------------------------------------------------------
# 2. Timestamped log file
# ---------------------------------------------------------------------------
LOG_DIR="${REPO_ROOT}/logs"
mkdir -p "${LOG_DIR}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/run_${TIMESTAMP}.log"

# Tee all output (stdout + stderr) to log file AND to terminal.
exec > >(tee -a "${LOG_FILE}") 2>&1

# ---------------------------------------------------------------------------
# 3. Pre-flight environment checks
# ---------------------------------------------------------------------------
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] python3 not found in PATH. Is your virtual environment activated?"
    echo "        Hint: source /path/to/venv/bin/activate"
    exit 1
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
echo "============================================================"
echo ""

# ---------------------------------------------------------------------------
# 5. STEP 1 — Rankings-only crawl
# ---------------------------------------------------------------------------
echo "[STEP 1] Starting rankings-only crawl  ($(date '+%H:%M:%S'))"
echo "         python3 ${PIPELINE} run --limit 200 --ranking-year 2026 \\"
echo "           --workers 1 --request-delay 10 --local-parse-workers 4 \\"
echo "           --write-batch-size 200 --rankings-only --resource-guard"
echo ""

python3 "${PIPELINE}" run \
    --limit 200 \
    --ranking-year 2026 \
    --workers 1 \
    --request-delay 10 \
    --local-parse-workers 4 \
    --write-batch-size 200 \
    --rankings-only \
    --resource-guard

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
    if python3 -c "
import json, sys
try:
    data = json.load(open('${DEFERRED_FILE}'))
    sys.exit(0 if isinstance(data, list) and len(data) > 0 else 1)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
        STEP2_TRIGGERED=true
        echo "[STEP 2] pending_detail_enrichment.json found with entries — starting enrichment  ($(date '+%H:%M:%S'))"
        echo "         python3 ${PIPELINE} enrich-details --limit 30 --request-delay 20"
        echo "         (20s delay: high-traffic QS pages require longer inter-request gap)"
        echo ""

        python3 "${PIPELINE}" enrich-details \
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
# 7. Summary
# ---------------------------------------------------------------------------
END_TS="$(date +%s)"
DURATION=$(( END_TS - START_TS ))
DURATION_FMT="$(printf '%02dh %02dm %02ds' $((DURATION/3600)) $((DURATION%3600/60)) $((DURATION%60)))"

echo "============================================================"
echo "[END]      $(date '+%Y-%m-%d %H:%M:%S')"
echo "[DURATION] ${DURATION_FMT}  (${DURATION}s)"
if [[ "${STEP2_TRIGGERED}" == "true" ]]; then
    echo "[STAGES]   Step 1: rankings crawl  |  Step 2: detail enrichment"
else
    echo "[STAGES]   Step 1: rankings crawl  |  Step 2: skipped (no pending enrichment)"
fi
echo "           Log written to: ${LOG_FILE}"
echo "============================================================"
echo ""
