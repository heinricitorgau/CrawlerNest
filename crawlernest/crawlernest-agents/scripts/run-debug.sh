#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

TMP_DIR="tmp"
LOG_FILE="$TMP_DIR/latest-test-output.log"
PROMPT_FILE="$TMP_DIR/latest-debug-prompt.md"

mkdir -p "$TMP_DIR"

echo "[debug-runner] Running tests..."

set +e
python3 -m unittest discover > "$LOG_FILE" 2>&1
TEST_EXIT_CODE=$?
set -e

if [ "$TEST_EXIT_CODE" -eq 0 ]; then
  echo "[debug-runner] Tests passed."
  echo "[debug-runner] Log saved to: $LOG_FILE"
  exit 0
fi

echo "[debug-runner] Tests failed."
echo "[debug-runner] Exit code: $TEST_EXIT_CODE"
echo "[debug-runner] Generating debug prompt..."

python3 scripts/generate-debug-prompt.py "$LOG_FILE" "$PROMPT_FILE"

echo "[debug-runner] Debug prompt generated:"
echo "$PROMPT_FILE"

echo ""
echo "Next step:"
echo "Open the prompt and give it to crawlernest-debug-reliability-engineer:"
echo ""
echo "cat $PROMPT_FILE"

exit "$TEST_EXIT_CODE"