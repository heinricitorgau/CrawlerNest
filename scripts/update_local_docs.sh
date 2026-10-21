#!/usr/bin/env bash
# Rewrite the nine local-only files in one go: the eight diagnostics in .repo-diagnostics/ (update_diagnostics.py)
# and docs/COMMIT_LOG.md (generate_commit_log.py). All nine are gitignored; this refuses to finish if one is not.
#
#   ./scripts/update_local_docs.sh                    # rewrite all nine, no tests
#   ./scripts/update_local_docs.sh --run-tests        # also run python,jest and record the results in 01-*.json
#   ./scripts/update_local_docs.sh --run-tests all    # python,jest,junit (or any comma list of them)
#   ./scripts/update_local_docs.sh --quiet            # print failures only (the post-commit hook uses this)
#
# The post-commit hook runs this in the background after every commit, without tests.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY=python3

DIAG_ARGS=()
QUIET=0
while [ $# -gt 0 ]; do
  case "$1" in
    --run-tests)
      if [ $# -gt 1 ] && [[ "$2" != --* ]]; then DIAG_ARGS+=(--run-tests "$2"); shift; else DIAG_ARGS+=(--run-tests); fi ;;
    --quiet) QUIET=1; DIAG_ARGS+=(--quiet) ;;
    -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1 (see --help)" >&2; exit 2 ;;
  esac
  shift
done

FILES=(
  .repo-diagnostics/01-git-test-status.json
  .repo-diagnostics/02-db-schema-migrations.md
  .repo-diagnostics/03-architecture-api-docs.md
  .repo-diagnostics/04-environment-config-template.md
  .repo-diagnostics/05-issues-backlog-summary.md
  .repo-diagnostics/06-cicd-workflow-rules.md
  .repo-diagnostics/07-llm-rubric-evals.json
  .repo-diagnostics/08-entity-warehouse-aliases.md
  docs/COMMIT_LOG.md
)

say() { [ "$QUIET" = 1 ] || echo "$@"; }
status=0

say "== diagnostics (8 files)"
"$PY" "$ROOT/scripts/update_diagnostics.py" "${DIAG_ARGS[@]}" || { echo "update_diagnostics.py failed" >&2; status=1; }

say "== commit log"
if [ "$QUIET" = 1 ]; then
  "$PY" "$ROOT/scripts/generate_commit_log.py" >/dev/null || { echo "generate_commit_log.py failed" >&2; status=1; }
else
  "$PY" "$ROOT/scripts/generate_commit_log.py" || { echo "generate_commit_log.py failed" >&2; status=1; }
fi

say "== check"
for f in "${FILES[@]}"; do
  if [ ! -s "$ROOT/$f" ]; then
    echo "missing or empty: $f" >&2; status=1
  elif ! git -C "$ROOT" check-ignore -q "$f"; then
    echo "NOT gitignored, would be committed: $f" >&2; status=1
  elif [ -n "$(git -C "$ROOT" ls-files -- "$f")" ]; then
    echo "tracked by git despite the ignore rule: $f" >&2; status=1
  else
    say "  ok  $f"
  fi
done

[ "$status" = 0 ] && say "all ${#FILES[@]} files rewritten, gitignored and untracked"
exit "$status"
