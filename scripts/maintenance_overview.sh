#!/usr/bin/env bash
# Single-entry readonly maintenance overview.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

echo "CrawlerNest Maintenance Overview"
echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""
echo "--- Calm Posture Summary ---"
echo "Read reports/maintenance_calm_summary.md first to distinguish"
echo "known stable RC-1 conditions from signals that need attention."
echo "Calm summary is regenerated in step [7/9] below."
echo ""
echo "--- Maintenance Reading Mode ---"
echo "  Quick status check  → scan this output for changes vs last session"
echo "  Pre-demo/release    → Mode 2: read calm summary, demo_caveats, trust summary"
echo "  Freshness concern   → Mode 3: read freshness_escalation, readiness, drift"
echo "  Something broke     → Mode 4: triage per MAINTENANCE_PRIORITY_MATRIX.md"
echo "Full reading modes: docs/MAINTENANCE_READING_MODES.md"
echo ""
echo "--- Report Criticality Hint ---"
echo "  critical:  smoke_release, operational_trust_summary, freshness_escalation, demo_caveats"
echo "  important: operational_summary, maintenance_readiness_summary, drift_timeline, calm_summary"
echo "  reference: snapshot_timeline, operational_index_summary, bundle copies"
echo "Full classification: docs/REPORT_CRITICALITY.md"
echo ""
echo "--- Operational Restraint Reminder ---"
echo "  Before adding any new script, report, or diagnostic:"
echo "  consult docs/OPERATIONAL_RESTRAINT_GUIDELINES.md"
echo ""
echo "--- Maintenance Cadence Hint ---"
echo "  Daily check   = this script only"
echo "  Weekly        = add calm/trust/demo_caveats builders"
echo "  Release/demo  = full suite per MAINTENANCE_CADENCE_REVIEW.md"
echo "  Incident-only = freshness, drift, snapshot scripts"
echo "Full cadence: docs/MAINTENANCE_CADENCE_REVIEW.md"
echo ""
echo "--- Stable Degraded State Reminder ---"
echo "  Known degraded conditions (freshness critical, THE/ARWU unavailable)"
echo "  are RC-1 stable background — not active incidents."
echo "Full posture: docs/STABLE_DEGRADED_STATE.md"
echo ""
echo "--- Operational Continuity Reminder ---"
echo "  Check for CHANGE vs last session, not presence of known signals."
echo "  Stable degraded continuity = no new worsening since last check."
echo "  Continuity model: docs/MAINTENANCE_CONTINUITY_MODEL.md"
echo ""

echo "[1/9] Source freshness"
"${PYTHON_BIN}" "${ROOT_DIR}/scripts/inspect_source_freshness.py" || true
echo ""

echo "[2/9] Operational trust summary"
"${PYTHON_BIN}" "${ROOT_DIR}/scripts/build_operational_trust_summary.py" >/dev/null 2>&1 || true
if [[ -f "${ROOT_DIR}/reports/operational_trust_summary.md" ]]; then
  sed -n '1,42p' "${ROOT_DIR}/reports/operational_trust_summary.md"
else
  echo "[missing] reports/operational_trust_summary.md"
fi
echo ""

echo "[3/9] Operational index summary"
"${PYTHON_BIN}" "${ROOT_DIR}/scripts/build_operational_index_summary.py" >/dev/null 2>&1 || true
if [[ -f "${ROOT_DIR}/reports/operational_index_summary.md" ]]; then
  sed -n '1,32p' "${ROOT_DIR}/reports/operational_index_summary.md"
else
  echo "[missing] reports/operational_index_summary.md"
fi
echo ""

echo "[4/9] Latest snapshot comparison hint"
latest_named="$(ls -t "${ROOT_DIR}/snapshots/system_snapshot_"*.json 2>/dev/null | head -1 || true)"
if [[ -n "${latest_named}" && -f "${ROOT_DIR}/snapshots/latest_status.json" ]]; then
  "${PYTHON_BIN}" "${ROOT_DIR}/scripts/compare_snapshots.py" \
    "${latest_named}" \
    "${ROOT_DIR}/snapshots/latest_status.json" \
    --json 2>/dev/null | "${PYTHON_BIN}" -c '
import json, sys
try:
    data = json.load(sys.stdin)
    print("latest_named:", data.get("before_snapshot_timestamp"))
    print("latest_status:", data.get("after_snapshot_timestamp"))
    print("aggregated_delta:", data.get("aggregated_count", {}).get("delta"))
    print("drift_warning_delta:", data.get("drift_warning_count", {}).get("delta"))
except Exception as exc:
    print("[warning] snapshot comparison unavailable:", exc)
'
else
  echo "[missing] latest named snapshot or snapshots/latest_status.json"
fi
echo ""

echo "[5/9] Demo caveat hint and latest smoke summary"
if [[ -f "${ROOT_DIR}/reports/demo_caveats.md" ]]; then
  grep -E "^- " "${ROOT_DIR}/reports/demo_caveats.md" | sed -n '1,8p' || true
else
  echo "[missing] reports/demo_caveats.md"
fi
echo ""
smoke="${ROOT_DIR}/releases/v0.1-demo/smoke_release_output.txt"
if [[ -f "${smoke}" ]]; then
  grep -E "Results:|Release smoke" "${smoke}" | tail -5 || true
else
  echo "[missing] releases/v0.1-demo/smoke_release_output.txt"
fi
echo ""

echo "[6/9] Maintenance navigation report"
"${PYTHON_BIN}" "${ROOT_DIR}/scripts/build_maintenance_navigation.py" >/dev/null 2>&1 || true
if [[ -f "${ROOT_DIR}/reports/maintenance_navigation.md" ]]; then
  grep -E "^##|^\-\-\-|missing" "${ROOT_DIR}/reports/maintenance_navigation.md" | head -12 || true
else
  echo "[missing] reports/maintenance_navigation.md"
fi
echo ""

echo "[7/9] Maintenance calm summary"
"${PYTHON_BIN}" "${ROOT_DIR}/scripts/build_maintenance_calm_summary.py" >/dev/null 2>&1 || true
if [[ -f "${ROOT_DIR}/reports/maintenance_calm_summary.md" ]]; then
  sed -n '1,30p' "${ROOT_DIR}/reports/maintenance_calm_summary.md"
else
  echo "[missing] reports/maintenance_calm_summary.md"
fi
echo ""

echo "[8/9] Maintenance steadiness summary"
"${PYTHON_BIN}" "${ROOT_DIR}/scripts/build_maintenance_steadiness_summary.py" >/dev/null 2>&1 || true
if [[ -f "${ROOT_DIR}/reports/maintenance_steadiness_summary.md" ]]; then
  sed -n '1,30p' "${ROOT_DIR}/reports/maintenance_steadiness_summary.md"
else
  echo "[missing] reports/maintenance_steadiness_summary.md"
fi
echo ""

echo "[9/9] Maintenance continuity summary"
"${PYTHON_BIN}" "${ROOT_DIR}/scripts/build_maintenance_continuity_summary.py" >/dev/null 2>&1 || true
if [[ -f "${ROOT_DIR}/reports/maintenance_continuity_summary.md" ]]; then
  sed -n '1,30p' "${ROOT_DIR}/reports/maintenance_continuity_summary.md"
else
  echo "[missing] reports/maintenance_continuity_summary.md"
fi
