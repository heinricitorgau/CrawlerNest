#!/usr/bin/env bash
#
# Snapshot the whole run_pipeline CLI surface: top-level --help plus --help for
# every subcommand.
#
# This exists for refactoring crawlernest/run_pipeline.py. That file is the
# entry point for the entire pipeline and most of its commands cannot be
# exercised without a live crawl or a populated database, so the practical
# regression net for a pure code move is the CLI surface itself:
#
#   ./scripts/snapshot_pipeline_cli.sh /tmp/cli_before.txt
#   ...refactor...
#   ./scripts/snapshot_pipeline_cli.sh /tmp/cli_after.txt
#   diff /tmp/cli_before.txt /tmp/cli_after.txt   # must be empty
#
# It is a stronger check than it first appears. Every subcommand's --help forces
# the parser to build and the module to import, so a moved function that lost a
# dependency, or a registry that dropped a command, shows up as a diff rather
# than as a failure weeks later in a command nobody runs often.
#
# What it does NOT catch: behaviour inside a handler. Pair it with
# scripts/smoke_local_stack.sh and the Release Smoke workflow.

set -u

OUT="${1:?usage: snapshot_pipeline_cli.sh <output-file>}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PY="${PYTHON:-./.venv/bin/python}"
if [ ! -x "$PY" ]; then
  PY="python3"
fi

: > "$OUT"

echo "########## TOP LEVEL" >> "$OUT"
"$PY" -m crawlernest.run_pipeline --help >> "$OUT" 2>&1

# argparse prints the subcommand names as a {a,b,c} choices group.
CMDS=$("$PY" -m crawlernest.run_pipeline --help 2>&1 \
  | tr -d '\n' \
  | grep -o '{[^}]*}' \
  | head -1 \
  | tr -d '{}' \
  | tr ',' ' ')

COUNT=$(echo "$CMDS" | wc -w)
if [ "$COUNT" -eq 0 ]; then
  echo "ERROR: no subcommands discovered -- did the parser fail to build?" >&2
  exit 1
fi

for c in $CMDS; do
  echo "" >> "$OUT"
  echo "########## $c" >> "$OUT"
  "$PY" -m crawlernest.run_pipeline "$c" --help >> "$OUT" 2>&1
done

# Something on the entry path prints its own wall-clock timing, which differs
# between runs and would make every diff non-empty regardless of the refactor.
# Normalise the volatile parts so a diff means a real change.
sed -i -E \
  -e 's/(Execution Finished in )[0-9]+\.[0-9]+( seconds)/\1N\2/' \
  -e 's/[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}[^ ]*/<timestamp>/g' \
  "$OUT"

echo "captured $COUNT subcommands into $OUT ($(wc -l < "$OUT") lines)"
