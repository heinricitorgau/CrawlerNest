#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

LOG_DIR="$REPO_ROOT/tmp"
mkdir -p "$LOG_DIR"

TEST_LOG="$LOG_DIR/latest-test-output.log"
PROMPT_OUT="$LOG_DIR/latest-debug-prompt.md"
TEST_CMD="${TEST_CMD:-python3 -m unittest discover}"

echo "[tests] Running: $TEST_CMD"

set +e
eval "$TEST_CMD" >"$TEST_LOG" 2>&1
status=$?
set -e

if [[ "$status" -ne 0 ]]; then
  echo "[tests] Test run failed. Generating debug prompt..."
  python3 scripts/generate-debug-prompt.py "$TEST_LOG" "$PROMPT_OUT"
  echo "[tests] Debug prompt written to: $PROMPT_OUT"
  exit "$status"
fi

echo "[tests] All tests passed."
