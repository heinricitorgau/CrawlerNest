#!/usr/bin/env bash
# Hold the committed warehouse exports against the live warehouse.
#
#   ./scripts/check_warehouse_drift.sh                 # fail if the database is unreachable
#   ./scripts/check_warehouse_drift.sh --if-available  # skip, with a notice, if it is (the pre-push hook uses this)
#
# Three committed files are derived from the warehouse and nothing else keeps them in step with it:
#   crawlernest-kb/databases/cross_edition_ranks.csv        <- export_cross_edition_ranks.py --commit
#   crawlernest-kb/databases/qs_the_pairing_2026.json       <- the pairing export (see crawlernest-ml README)
#   crawlernest-kb/databases/*_university_aliases_*.json    <- edited by hand, referenced by canonical id
# CI cannot make this comparison: its database is bootstrapped empty, and the warehouse it would compare against
# lives on the developer's machine. So this is the gate, and it fails where the test suite would have skipped:
# CRAWLERNEST_REQUIRE_WAREHOUSE=1 turns "the warehouse is too small to compare" into a failure, because a check
# that compared nothing has not shown there is no drift.
#
# Environment (defaults match the local setup): CRAWLERNEST_PG_HOST, _PORT, _DATABASE, _USER, _PASSWORD.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="python3"

export CRAWLERNEST_PG_HOST="${CRAWLERNEST_PG_HOST:-localhost}"
export CRAWLERNEST_PG_PORT="${CRAWLERNEST_PG_PORT:-5432}"
export CRAWLERNEST_PG_DATABASE="${CRAWLERNEST_PG_DATABASE:-clawer}"
export CRAWLERNEST_PG_USER="${CRAWLERNEST_PG_USER:-test}"
export CRAWLERNEST_PG_PASSWORD="${CRAWLERNEST_PG_PASSWORD:-test}"

if ! "$PY" - <<'PYEOF' 2>/dev/null
import os, psycopg2
psycopg2.connect(host=os.environ["CRAWLERNEST_PG_HOST"], port=int(os.environ["CRAWLERNEST_PG_PORT"]),
                 dbname=os.environ["CRAWLERNEST_PG_DATABASE"], user=os.environ["CRAWLERNEST_PG_USER"],
                 password=os.environ["CRAWLERNEST_PG_PASSWORD"], connect_timeout=3).close()
PYEOF
then
  msg="warehouse drift check: cannot connect to $CRAWLERNEST_PG_DATABASE at $CRAWLERNEST_PG_HOST:$CRAWLERNEST_PG_PORT"
  if [ "${1:-}" = "--if-available" ]; then
    echo "$msg -- skipped. The exports were NOT compared with the warehouse." >&2
    exit 0
  fi
  echo "$msg" >&2
  exit 2
fi

cd "$ROOT/crawlernest/crawlernest-tests" || exit 2
export PYTHONPATH=".:../crawlernest-core:../.."
export CRAWLERNEST_RUN_PG_TESTS=1
export CRAWLERNEST_REQUIRE_WAREHOUSE=1

if "$PY" -m unittest \
    test_cross_edition_export_matches_warehouse.TestCrossEditionExportMatchesWarehouse \
    test_pairing_matches_warehouse \
    test_alias_files.TestAliasFilesAgainstWarehouse; then
  echo "warehouse drift check: the committed exports match $CRAWLERNEST_PG_DATABASE"
  exit 0
fi

cat >&2 <<'MSG'

warehouse drift check FAILED: a committed export no longer matches the warehouse.
  cross_edition_ranks.csv  ->  ./.venv/bin/python crawlernest/scripts/export_cross_edition_ranks.py --pg-password test --commit
                               then re-run the MATLAB forecast (crawlernest-ml/matlab/README.md)
  qs_the_pairing_2026.json ->  re-export the pairing, then retrain the disagreement model
  *_university_aliases_*   ->  a hand-edited file: fix the row the failure names
Read the failure above before regenerating anything: the warehouse may be the side that is wrong.
MSG
exit 1
