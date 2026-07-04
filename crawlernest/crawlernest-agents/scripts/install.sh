#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE_DIR="$REPO_ROOT/agents"
TARGET_DIR=""

usage() {
  cat <<'EOF'
Usage:
  ./scripts/install.sh --target <directory>

Example:
  ./scripts/install.sh --target ~/.claude/agents
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      TARGET_DIR="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$TARGET_DIR" ]]; then
  echo "--target is required" >&2
  usage
  exit 1
fi

mkdir -p "$TARGET_DIR"
cp "$SOURCE_DIR"/*.md "$TARGET_DIR"/

echo "Installed CrawlerNest agents to $TARGET_DIR"
