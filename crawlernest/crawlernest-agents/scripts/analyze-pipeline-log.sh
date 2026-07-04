#!/usr/bin/env bash

set -euo pipefail

if [[ "$#" -ne 1 ]]; then
  echo "Usage: ./scripts/analyze-pipeline-log.sh <log_file>"
  exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

LOG_FILE="$1"
OUT_FILE="$REPO_ROOT/tmp/pipeline-analysis-prompt.md"

mkdir -p "$REPO_ROOT/tmp"

python3 scripts/generate-pipeline-analysis.py "$LOG_FILE" "$OUT_FILE"
echo "Pipeline analysis prompt written to $OUT_FILE"
