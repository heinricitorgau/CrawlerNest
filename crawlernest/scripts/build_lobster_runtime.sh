#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo "[build] Delegating to canonical root build script..."
exec "${REPO_ROOT}/scripts/build_lobster_runtime.sh" "$@"
