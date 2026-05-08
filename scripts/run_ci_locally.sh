#!/usr/bin/env bash
# Simulate both CI workflows locally (no live database required).
# Runs: smoke_release.sh, ranking regression (fixture mode), failure summary (fixture mode).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURE_DB="${REPO_ROOT}/crawlernest/crawlernest-autoeval/datasets/ci_fixtures/db_state.json"
FIXTURE_SNAP="${REPO_ROOT}/crawlernest/crawlernest-autoeval/datasets/ci_fixtures/snapshot_fixture.json"
RUNNER="${REPO_ROOT}/crawlernest/crawlernest-autoeval/runners/run_ranking_regression.py"
SUMMARY="${REPO_ROOT}/scripts/build_failure_summary.py"
REGRESSION_OUT="/tmp/ci_regression_result.json"
SUMMARY_OUT="/tmp/ci_failure_summary.md"

PASS=0
FAIL=0

step() { echo; echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; echo "▶ $*"; echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; }
ok()   { echo "  [PASS] $*"; PASS=$((PASS + 1)); }
fail() { echo "  [FAIL] $*"; FAIL=$((FAIL + 1)); }

# ── [1/3] smoke_release.sh ────────────────────────────────────────────────────
step "[1/3] smoke_release.sh"
if bash "${REPO_ROOT}/scripts/smoke_release.sh"; then
    ok "smoke_release.sh"
else
    fail "smoke_release.sh (exit $?)"
fi

# ── [2/3] Ranking regression (fixture mode) ───────────────────────────────────
step "[2/3] Ranking regression — fixture mode (no DB)"
if python3 "${RUNNER}" \
    --fixture-file "${FIXTURE_DB}" \
    --json | tee "${REGRESSION_OUT}" | python3 - <<'PY'
import json, sys
r = json.load(open("/tmp/ci_regression_result.json"))
passed = r.get("passed", 0)
failed = r.get("failed", 0)
result = r.get("result", "UNKNOWN")
print(f"  assertions: {passed} passed, {failed} failed → {result}")
sys.exit(0 if result == "PASS" else 1)
PY
then
    ok "ranking regression (fixture)"
else
    fail "ranking regression (fixture) — see ${REGRESSION_OUT}"
fi

# ── [3/3] Failure summary (snapshot fixture mode) ─────────────────────────────
step "[3/3] Failure summary — snapshot fixture mode (no DB)"
if python3 "${SUMMARY}" \
    --snapshot-file "${FIXTURE_SNAP}" \
    --output "${SUMMARY_OUT}"; then
    ok "failure summary (fixture snapshot)"
    echo
    echo "  Summary written to: ${SUMMARY_OUT}"
else
    fail "failure summary — see above"
fi

# ── Final report ──────────────────────────────────────────────────────────────
echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "CI local simulation complete: ${PASS} passed, ${FAIL} failed"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [[ ${FAIL} -gt 0 ]]; then
    echo
    echo "Artifacts:"
    echo "  Regression : ${REGRESSION_OUT}"
    echo "  Summary    : ${SUMMARY_OUT}"
    exit 1
fi
