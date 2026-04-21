#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

if [[ -f "$REPO_ROOT/.ai-dev.config" ]]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.ai-dev.config"
fi

AI_DEV_TMP_DIR="${AI_DEV_TMP_DIR:-tmp/ai-dev}"
AI_DEV_DEFAULT_TEST_COMMAND="${AI_DEV_DEFAULT_TEST_COMMAND:-python3 -m unittest discover crawlernest/crawlernest-tests}"

LOG_DIR="$REPO_ROOT/$AI_DEV_TMP_DIR"
mkdir -p "$LOG_DIR"

TEST_LOG="$LOG_DIR/latest-test-output.log"
PROMPT_OUT="$LOG_DIR/latest-debug-prompt.md"

echo "[ai-dev] Running tests: $AI_DEV_DEFAULT_TEST_COMMAND"

set +e
bash -lc "$AI_DEV_DEFAULT_TEST_COMMAND" >"$TEST_LOG" 2>&1
status=$?
set -e

if [[ "$status" -ne 0 ]]; then
  echo "[ai-dev] Test run failed. Generating debug prompt..."
  python3 scripts/ai-dev/generate-debug-prompt.py "$TEST_LOG" "$PROMPT_OUT"
  echo "[ai-dev] Debug prompt written to: $PROMPT_OUT"
  exit "$status"
fi

echo "[ai-dev] All tests passed."
