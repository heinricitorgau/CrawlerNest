#!/usr/bin/env bash
# =============================================================================
# run_continuous_mac.sh
# CrawlerNest — Continuous pipeline runner for Mac / Local Dev
#
# Usage:
#   bash crawlernest/scripts/run_continuous_mac.sh
#
# This script runs the production-safe pipeline in an infinite loop.
# It includes a 1-hour cooldown between full cycles to ensure stability.
# =============================================================================

set -euo pipefail

# Resolve repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

PRODUCTION_SCRIPT="crawlernest/scripts/run_production_safe.sh"

echo "============================================================"
echo "CrawlerNest Continuous Runner Started"
echo "Root: ${REPO_ROOT}"
echo "Press [Ctrl+C] to stop."
echo "============================================================"

while true; do
    echo ""
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting new pipeline cycle..."
    
    # Run the production safe script
    # We use a subshell to ensure environment isolation
    if bash "${PRODUCTION_SCRIPT}"; then
        echo ""
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Cycle completed successfully."
    else
        echo ""
        echo "[ERROR] Pipeline cycle failed with exit code $?."
        echo "Continuing to next cycle after cooldown..."
    fi

    echo ""
    echo "------------------------------------------------------------"
    echo "Cooldown initiated for 1 hour (3600s)..."
    echo "Next run at approximately $(date -v+1H '+%Y-%m-%d %H:%M:%S')"
    echo "------------------------------------------------------------"
    
    # Sleep for 1 hour
    sleep 3600
done
