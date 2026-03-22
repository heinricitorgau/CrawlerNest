#!/usr/bin/env bash
set -euo pipefail

# Production-safe default runner for QS crawl.
# Usage:
#   bash crawlernest/scripts/run_production_safe.sh
#   bash crawlernest/scripts/run_production_safe.sh --limit 300 --resume

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

python3 crawlernest/run_pipeline.py run \
  --limit 200 \
  --workers 1 \
  --request-delay 10 \
  --local-parse-workers 4 \
  --write-batch-size 200 \
  --resource-guard \
  "$@"
