#!/usr/bin/env bash

set -euo pipefail

if [[ "$#" -ne 1 ]]; then
  echo "Usage: ./scripts/ai-dev/analyze-pipeline-log.sh <log_file>"
  exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

if [[ -f "$REPO_ROOT/.ai-dev.config" ]]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.ai-dev.config"
fi

AI_DEV_TMP_DIR="${AI_DEV_TMP_DIR:-tmp/ai-dev}"
LOG_FILE="$1"
OUT_DIR="$REPO_ROOT/$AI_DEV_TMP_DIR"
OUT_FILE="$OUT_DIR/pipeline-analysis-prompt.md"

mkdir -p "$OUT_DIR"

python3 scripts/ai-dev/generate-pipeline-analysis.py "$LOG_FILE" "$OUT_FILE"
echo "[ai-dev] Pipeline analysis prompt written to $OUT_FILE"
