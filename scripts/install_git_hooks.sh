#!/usr/bin/env bash
# Point this clone's git at the repository's hooks (scripts/hooks/). A local setting; nothing is pushed.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
chmod +x "$ROOT/scripts/hooks/"* "$ROOT/scripts/check_warehouse_drift.sh"
git -C "$ROOT" config core.hooksPath scripts/hooks
echo "hooks installed: core.hooksPath = $(git -C "$ROOT" config core.hooksPath)"
echo "pre-push now runs scripts/check_warehouse_drift.sh when the database is reachable."
echo "post-commit now refreshes .repo-diagnostics/ (local, gitignored) via scripts/update_diagnostics.py."
