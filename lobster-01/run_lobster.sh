#!/usr/bin/env bash
# =============================================================================
# run_lobster.sh
# CrawlerNest — Optimized runner for Lobster-01 (Low-spec Node)
# =============================================================================

set -euo pipefail

# 1. Resolve paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PIPELINE="${REPO_ROOT}/crawlernest/run_pipeline.py"
NODE_CONF="${SCRIPT_DIR}/node_config.json"
LOG_DIR="${REPO_ROOT}/logs/lobster"

mkdir -p "${LOG_DIR}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="${LOG_DIR}/lobster_${TIMESTAMP}.log"

# Tee output to log
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "============================================================"
echo "[LOBSTER-01] Starting Node Pipeline  ($(date))"
echo "             Config: ${NODE_CONF}"
echo "             Log   : ${LOG_FILE}"
echo "============================================================"

# OPTIONAL: Load virtualenv if it exists in root
if [[ -d "${REPO_ROOT}/.venv" ]]; then
    source "${REPO_ROOT}/.venv/bin/activate"
fi

# STEP 1: Rankings Crawl (High Limit, Low Concurrency)
echo ""
echo "[STEP 1] Rankings-only crawl..."
python3 "${PIPELINE}" run \
    --limit 2500 \
    --ranking-year 2026 \
    --workers 1 \
    --request-delay 10 \
    --local-parse-workers 2 \
    --write-batch-size 100 \
    --rankings-only \
    --resource-guard

# STEP 2: Enrichment (if pending)
DEFERRED_FILE="${REPO_ROOT}/crawlernest/crawlernest-kb/databases/pending_detail_enrichment.json"
if [[ -f "${DEFERRED_FILE}" ]]; then
    echo ""
    echo "[STEP 2] Found pending details. Starting enrichment..."
    python3 "${PIPELINE}" enrich-details \
        --limit 50 \
        --request-delay 15
fi

echo ""
echo "============================================================"
echo "[LOBSTER-01] Node task finished.  ($(date))"
echo "============================================================"
