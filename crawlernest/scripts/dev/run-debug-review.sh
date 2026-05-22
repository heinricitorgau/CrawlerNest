#!/usr/bin/env bash
set -euo pipefail

# Minimal, non-intrusive debug review wrapper
# Usage: TEST_CMD="npm test" ./scripts/dev/run-debug-review.sh

# Find main repo root
if ! MAIN_ROOT=$(git rev-parse --show-toplevel 2>/dev/null); then
  echo "Not inside a git repository or unable to find repo root." >&2
  exit 1
fi

# Determine agents repo root
if [ -n "${CRAWLERNEST_AGENTS_ROOT:-}" ]; then
  AGENTS_ROOT=$CRAWLERNEST_AGENTS_ROOT
else
  AGENTS_ROOT="$MAIN_ROOT/../crawlernest-agents"
fi

if [ ! -d "$AGENTS_ROOT" ]; then
  echo "crawlernest-agents not found. Set CRAWLERNEST_AGENTS_ROOT=/path/to/crawlernest-agents" >&2
  exit 2
fi

GENERATOR="$AGENTS_ROOT/scripts/generate-debug-prompt.py"
if [ ! -f "$GENERATOR" ]; then
  echo "generate-debug-prompt.py not found. Expected at: $GENERATOR" >&2
  exit 3
fi

# Prepare output directory
OUT_DIR="$MAIN_ROOT/tmp/ai-dev"
mkdir -p "$OUT_DIR"

# Determine test command (allow override via env)
: ${TEST_CMD:="./mvnw test"}

OUT_FILE="$OUT_DIR/latest-test-output.log"
PROMPT_FILE="$OUT_DIR/latest-debug-prompt.md"

# Run tests and capture output and exit code
pushd "$MAIN_ROOT" >/dev/null
set +e
bash -lc "$TEST_CMD" > "$OUT_FILE" 2>&1
TEST_EXIT_CODE=$?
set -e
popd >/dev/null

if [ "$TEST_EXIT_CODE" -eq 0 ]; then
  echo "tests passed"
  echo "Test log preserved at: $OUT_FILE"
  exit 0
else
  # Invoke agents prompt generator
  if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 not found; cannot generate debug prompt." >&2
    exit "$TEST_EXIT_CODE"
  fi

  python3 "$GENERATOR" "$OUT_FILE" "$PROMPT_FILE"
  echo "Generated debug prompt at: $PROMPT_FILE"
  exit "$TEST_EXIT_CODE"
fi
