#!/usr/bin/env bash
# Build the v0.1 demo release bundle.
#
# Creates releases/v0.1-demo/ with release documentation, operational artifacts,
# and smoke output. READONLY-SAFE: does not modify runtime state, does not delete
# data, does not run the pipeline. Missing artifacts are marked [missing] rather
# than causing a crash.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE_DIR="${ROOT_DIR}/releases/v0.1-demo"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "========================================"
echo " CrawlerNest v0.1 Demo Bundle Builder"
echo " ${TIMESTAMP}"
echo "========================================"
echo ""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ok()      { echo "  OK   $*"; }
skipped() { echo "  SKIP $*"; }
missing() { echo "  MISS $*"; }

copy_or_missing() {
  local src="$1"
  local dst="$2"
  local label="$3"
  if [[ -f "${src}" ]]; then
    cp "${src}" "${dst}"
    ok "${label}"
  else
    echo "[missing — ${label} not found at ${src}]" > "${dst}"
    missing "${label}"
  fi
}

# ---------------------------------------------------------------------------
# 1. Create bundle directory structure
# ---------------------------------------------------------------------------
echo "[1/7] Creating bundle directory: ${BUNDLE_DIR}"
mkdir -p "${BUNDLE_DIR}/screenshots"
ok "Bundle directory created"
echo ""

# ---------------------------------------------------------------------------
# 2. Copy release documentation
# ---------------------------------------------------------------------------
echo "[2/7] Copying release documentation..."

copy_or_missing \
  "${ROOT_DIR}/docs/RELEASE_NOTES_v0.1.md" \
  "${BUNDLE_DIR}/RELEASE_NOTES_v0.1.md" \
  "RELEASE_NOTES_v0.1.md"

copy_or_missing \
  "${ROOT_DIR}/docs/DEMO_SCRIPT_v0.1.md" \
  "${BUNDLE_DIR}/DEMO_SCRIPT_v0.1.md" \
  "DEMO_SCRIPT_v0.1.md"

copy_or_missing \
  "${ROOT_DIR}/docs/VERSION_SCOPE_v0.1.md" \
  "${BUNDLE_DIR}/VERSION_SCOPE_v0.1.md" \
  "VERSION_SCOPE_v0.1.md"

copy_or_missing \
  "${ROOT_DIR}/docs/SCREENSHOT_CHECKLIST_v0.1.md" \
  "${BUNDLE_DIR}/SCREENSHOT_CHECKLIST_v0.1.md" \
  "SCREENSHOT_CHECKLIST_v0.1.md"

copy_or_missing \
  "${ROOT_DIR}/docs/RELEASE_STRUCTURE.md" \
  "${BUNDLE_DIR}/RELEASE_STRUCTURE.md" \
  "RELEASE_STRUCTURE.md"

echo ""

# ---------------------------------------------------------------------------
# 3. Copy latest snapshot
# ---------------------------------------------------------------------------
echo "[3/7] Copying latest snapshot..."

copy_or_missing \
  "${ROOT_DIR}/snapshots/latest_status.json" \
  "${BUNDLE_DIR}/latest_status.json" \
  "snapshots/latest_status.json"

# Also try the most recent named snapshot
latest_snapshot="$(ls -t "${ROOT_DIR}/snapshots/system_snapshot_"*.json 2>/dev/null | head -1 || true)"
if [[ -n "${latest_snapshot}" ]]; then
  snapshot_name="$(basename "${latest_snapshot}")"
  cp "${latest_snapshot}" "${BUNDLE_DIR}/${snapshot_name}"
  ok "Latest named snapshot: ${snapshot_name}"
else
  echo "[missing — no system_snapshot_*.json found in snapshots/]" \
    > "${BUNDLE_DIR}/system_snapshot_MISSING.json"
  missing "Named system snapshot"
fi

echo ""

# ---------------------------------------------------------------------------
# 4. Copy latest failure summary
# ---------------------------------------------------------------------------
echo "[4/7] Copying latest failure summary..."

copy_or_missing \
  "${ROOT_DIR}/reports/latest_failure_summary.md" \
  "${BUNDLE_DIR}/latest_failure_summary.md" \
  "reports/latest_failure_summary.md"

echo ""

# ---------------------------------------------------------------------------
# 5. Run diagnostics summary (readonly)
# ---------------------------------------------------------------------------
echo "[5/7] Generating diagnostics summary (readonly)..."

if [[ -f "${ROOT_DIR}/scripts/check_pipeline_health.py" ]]; then
  diag_out="${BUNDLE_DIR}/diagnostics_summary.txt"
  {
    echo "# CrawlerNest v0.1 Diagnostics Summary"
    echo "# Generated: ${TIMESTAMP}"
    echo ""
    python3 "${ROOT_DIR}/scripts/check_pipeline_health.py" 2>&1 || echo "[diagnostics script exited non-zero]"
  } > "${diag_out}"
  ok "Diagnostics summary written to diagnostics_summary.txt"
else
  echo "[missing — check_pipeline_health.py not found]" \
    > "${BUNDLE_DIR}/diagnostics_summary.txt"
  missing "check_pipeline_health.py"
fi

echo ""

# ---------------------------------------------------------------------------
# 6. Run smoke_release (build artifacts only — no live services required)
# ---------------------------------------------------------------------------
echo "[6/7] Running release smoke test (build artifacts)..."

if [[ -x "${ROOT_DIR}/scripts/smoke_release.sh" ]]; then
  smoke_out="${BUNDLE_DIR}/smoke_release_output.txt"
  {
    echo "# CrawlerNest v0.1 Release Smoke Output"
    echo "# Generated: ${TIMESTAMP}"
    echo ""
    "${ROOT_DIR}/scripts/smoke_release.sh" 2>&1
  } > "${smoke_out}" && smoke_rc=0 || smoke_rc=$?

  if [[ ${smoke_rc} -eq 0 ]]; then
    ok "Release smoke passed — output written to smoke_release_output.txt"
  else
    skipped "Release smoke exited non-zero (rc=${smoke_rc}) — output captured in smoke_release_output.txt"
  fi
else
  echo "[missing — smoke_release.sh not found or not executable]" \
    > "${BUNDLE_DIR}/smoke_release_output.txt"
  missing "smoke_release.sh"
fi

echo ""

# ---------------------------------------------------------------------------
# 7. Create screenshot placeholder README
# ---------------------------------------------------------------------------
echo "[7/7] Creating screenshot placeholder README..."

cat > "${BUNDLE_DIR}/screenshots/README.md" << 'EOF'
# v0.1 Demo Screenshots

Place captured screenshots in this directory using the filenames specified in:

  docs/SCREENSHOT_CHECKLIST_v0.1.md

## Required screenshots (priority order)

1. `rankings_global_top10.png` — Global rankings page, top 10 rows
2. `rankings_subject_cs.png` — Subject rankings, Computer Science selected
3. `system_status_full.png` — System status page, all sections loaded
4. `api_health_terminal.png` — Terminal: curl /api/v1/health output
5. `smoke_release_pass.png` — Terminal: smoke_release.sh all OK

## Operational evidence

- `snapshot_latest_status.png`
- `failure_summary_report.png`
- `pipeline_health_check.png`

## Diagnostics

- `api_diagnostics_data_quality.png`
- `api_diagnostics_source_agreement.png`
- `api_diagnostics_rankings.png`

## CI evidence

- `ci_release_smoke_green.png`
- `ci_data_quality_green.png`

## Explainability

- `api_explain_ranking.png`
- `api_source_comparison.png`

See SCREENSHOT_CHECKLIST_v0.1.md for exact commands, routes, and viewports.
EOF

ok "Screenshot placeholder README created"
echo ""

# ---------------------------------------------------------------------------
# Bundle manifest
# ---------------------------------------------------------------------------
echo "Writing bundle manifest..."

manifest="${BUNDLE_DIR}/MANIFEST.txt"
{
  echo "CrawlerNest v0.1 Demo Bundle"
  echo "Built: ${TIMESTAMP}"
  echo ""
  echo "Contents:"
  find "${BUNDLE_DIR}" -type f | sort | sed "s|${BUNDLE_DIR}/||"
} > "${manifest}"
ok "MANIFEST.txt written"
echo ""

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo "========================================"
echo " Bundle complete: ${BUNDLE_DIR}"
echo "========================================"
echo ""
echo "Contents:"
find "${BUNDLE_DIR}" -type f | sort | sed "s|${BUNDLE_DIR}/|  |"
echo ""
echo "Next steps:"
echo "  1. Review smoke_release_output.txt for any build failures"
echo "  2. Capture screenshots per SCREENSHOT_CHECKLIST_v0.1.md"
echo "  3. Place screenshots in releases/v0.1-demo/screenshots/"
echo "  4. Share releases/v0.1-demo/ as the v0.1 demo package"
