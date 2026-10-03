#!/usr/bin/env bash
# Point this clone's git at the repository's hooks (.githooks/). A local setting; nothing is pushed.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
chmod +x "$ROOT/.githooks/"* "$ROOT/scripts/check_warehouse_drift.sh"
git -C "$ROOT" config core.hooksPath .githooks
echo "hooks installed: core.hooksPath = $(git -C "$ROOT" config core.hooksPath)"
echo "pre-push now runs scripts/check_warehouse_drift.sh when the database is reachable."
