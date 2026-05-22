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
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi
export CRAWLERNEST_PG_PASSWORD="${CRAWLERNEST_PG_PASSWORD:-test}"

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
# 4. Copy latest failure summary and operational intelligence reports
# ---------------------------------------------------------------------------
echo "[4/7] Copying latest failure summary and operational intelligence reports..."

copy_or_missing \
  "${ROOT_DIR}/reports/latest_failure_summary.md" \
  "${BUNDLE_DIR}/latest_failure_summary.md" \
  "reports/latest_failure_summary.md"

copy_or_missing \
  "${ROOT_DIR}/reports/operational_summary.md" \
  "${BUNDLE_DIR}/operational_summary.md" \
  "reports/operational_summary.md"

copy_or_missing \
  "${ROOT_DIR}/reports/operational_index_summary.md" \
  "${BUNDLE_DIR}/operational_index_summary.md" \
  "reports/operational_index_summary.md"

copy_or_missing \
  "${ROOT_DIR}/reports/operational_trust_summary.md" \
  "${BUNDLE_DIR}/operational_trust_summary.md" \
  "reports/operational_trust_summary.md"

copy_or_missing \
  "${ROOT_DIR}/reports/maintenance_readiness_summary.md" \
  "${BUNDLE_DIR}/maintenance_readiness_summary.md" \
  "reports/maintenance_readiness_summary.md"

copy_or_missing \
  "${ROOT_DIR}/reports/demo_caveats.md" \
  "${BUNDLE_DIR}/demo_caveats.md" \
  "reports/demo_caveats.md"

copy_or_missing \
  "${ROOT_DIR}/reports/drift_timeline.md" \
  "${BUNDLE_DIR}/drift_timeline.md" \
  "reports/drift_timeline.md"

copy_or_missing \
  "${ROOT_DIR}/reports/freshness_escalation.md" \
  "${BUNDLE_DIR}/freshness_escalation.md" \
  "reports/freshness_escalation.md"

copy_or_missing \
  "${ROOT_DIR}/reports/maintenance_calm_summary.md" \
  "${BUNDLE_DIR}/maintenance_calm_summary.md" \
  "reports/maintenance_calm_summary.md"

copy_or_missing \
  "${ROOT_DIR}/reports/maintenance_steadiness_summary.md" \
  "${BUNDLE_DIR}/maintenance_steadiness_summary.md" \
  "reports/maintenance_steadiness_summary.md"

copy_or_missing \
  "${ROOT_DIR}/reports/maintenance_continuity_summary.md" \
  "${BUNDLE_DIR}/maintenance_continuity_summary.md" \
  "reports/maintenance_continuity_summary.md"

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
    "${PYTHON_BIN}" "${ROOT_DIR}/scripts/check_pipeline_health.py" 2>&1 || echo "[diagnostics script exited non-zero]"
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
# Operational artifacts map
# ---------------------------------------------------------------------------
echo "Writing operational artifacts map..."

cat > "${BUNDLE_DIR}/OPERATIONAL_ARTIFACTS.md" << 'EOF'
# Operational Artifacts

This bundle contains copied operational evidence. The files are historical
release/demo artifacts, not runtime authority.

## First Read

- `maintenance_calm_summary.md`: calm posture overview — read this first to
  distinguish known stable RC-1 conditions from signals that need attention.
- `maintenance_steadiness_summary.md`: steadiness assessment — caution level,
  stable degraded indicators, and steadiness guidance for the current posture.
- `maintenance_continuity_summary.md`: continuity posture — stable degraded
  continuity, operational memory durability, release honesty continuity, and
  no-continuity-regressions-detected confirmation when applicable.
- `demo_caveats.md`: presenter-facing caveats to state during demo/release.
- `operational_trust_summary.md`: conservative confidence and trust rollup.
- `smoke_release_output.txt`: build, syntax, fixture, diagnostics, and optional
  endpoint smoke evidence captured during bundle creation.
- `operational_summary.md`: demo-friendly source health and freshness summary.
- `maintenance_readiness_summary.md`: maintenance-oriented stale source,
  unresolved, and release/demo caveat summary.
- `operational_index_summary.md`: single-entry operational status for handoff.

## Snapshot Evidence

- `latest_status.json`: compact latest snapshot copied from `snapshots/`.
- `system_snapshot_*.json`: dated snapshot evidence copied from `snapshots/`.

Snapshots are append-oriented historical evidence. Runtime behavior remains
owned by PostgreSQL and running services.

## Report Evidence

- `latest_failure_summary.md`: failure and health detail.
- `drift_timeline.md`: historical drift classification.
- `freshness_escalation.md`: freshness and source-gap escalation.
- `maintenance_readiness_summary.md`: current maintenance readiness and known
  source blockers.
- `demo_caveats.md`: explicit demo caveats derived from freshness,
  maintenance, and source-state reports.
- `operational_trust_summary.md`: confidence relationship across freshness,
  completeness, release, demo, and maintenance dimensions.
- `diagnostics_summary.txt`: bundle-time readonly diagnostics output.

## Relationship

```mermaid
flowchart TD
    snapshots["latest_status.json / system_snapshot_*.json"]
    failure["latest_failure_summary.md"]
    drift["drift_timeline.md"]
    freshness["freshness_escalation.md"]
    ops["operational_summary.md"]
    index["operational_index_summary.md"]
    trust["operational_trust_summary.md"]
    maintenance["maintenance_readiness_summary.md"]
    caveats["demo_caveats.md"]
    smoke["smoke_release_output.txt"]
    diagnostics["diagnostics_summary.txt"]

    snapshots --> failure
    snapshots --> drift
    snapshots --> freshness
    snapshots --> ops
    snapshots --> maintenance
    freshness --> caveats
    maintenance --> caveats
    failure --> index
    drift --> index
    freshness --> index
    ops --> index
    maintenance --> index
    caveats --> index
    freshness --> trust
    maintenance --> trust
    caveats --> trust
    trust --> index
    smoke --> index
    diagnostics --> index
```

## Report Lifecycle Notes

All report files in this bundle are historical — accurate at bundle-build time.
After the bundle is created, the live `reports/` directory is authoritative.

| Lifecycle | Reports in This Bundle |
| --- | --- |
| Critical (read before demo) | `demo_caveats.md`, `operational_trust_summary.md`, `smoke_release_output.txt`, `freshness_escalation.md` |
| Important (context when needed) | `maintenance_calm_summary.md`, `operational_summary.md`, `maintenance_readiness_summary.md`, `drift_timeline.md` |
| Reference/historical | `operational_index_summary.md`, `latest_failure_summary.md`, `system_snapshot_*.json`, `latest_status.json` |

## Stable Degraded Posture

The following six degraded conditions are present at RC-1. They are expected,
documented, and non-worsening. They do not constitute an active incident.

| Condition | Value | Why Accepted |
| --- | --- | --- |
| QS freshness | stale (~354h) | No crawl since RC-1 packaging; expected for packaged demo |
| THE availability | unavailable (0) | Source files not acquired; out-of-scope at RC-1 |
| ARWU availability | unavailable (0) | Source files not acquired; out-of-scope at RC-1 |
| Subject ranking rows | 0 | QS subject ranking not ingested at MVP scope |
| Release confidence | limited | Derived from above; documented and caveat-covered |
| Operational trust level | critical | Derived from freshness + source gaps; known and disclosed |

See `docs/STABLE_DEGRADED_STATE.md` for escalation triggers and communication
guidance. See `docs/MAINTENANCE_CADENCE_REVIEW.md` for when to run what.

## Maintenance Calmness

`maintenance_calm_summary.md` contextualizes the operational posture without
alarm amplification. Read it first to understand which signals are known
stable conditions (RC-1 posture) versus signals that require action.

`maintenance_steadiness_summary.md` provides caution level and steadiness
guidance derived from the same signals. Read it alongside the calm summary
before a demo or release.

Known stable conditions at RC-1 (expected and documented):
- QS data is stale — no new crawl since RC-1 packaging
- THE and ARWU are unavailable — out-of-scope at RC-1
- Release confidence is limited — caveats are documented and demo-ready

## Reading Mode Guidance

For demo/release preparation, use this reading order (Mode 2):
1. `maintenance_calm_summary.md` — calm posture overview
2. `maintenance_steadiness_summary.md` — caution level and steadiness
3. `maintenance_continuity_summary.md` — continuity posture and honesty check
4. `demo_caveats.md` — required caveats before any demo
5. `operational_trust_summary.md` — confidence posture
6. `smoke_release_output.txt` — build/runtime health confirmation

Full reading modes are in `docs/MAINTENANCE_READING_MODES.md`.
Full maintenance cadence (daily/weekly/release-demo/incident-only) is in
`docs/MAINTENANCE_CADENCE_REVIEW.md`
(both available in the live repository, not copied into this bundle).

## Operational Continuity Semantics

The bundle captures the operational continuity posture at bundle-build time.

| Continuity Dimension | Bundle Evidence |
| --- | --- |
| Stable degraded continuity | `maintenance_continuity_summary.md` — no regression confirmation |
| Operational memory durability | Named snapshots (durable); reports (ephemeral at bundle-build time) |
| Report continuity | All `*.md` reports frozen at bundle-build timestamp in `MANIFEST.txt` |
| Release honesty continuity | `demo_caveats.md` — required disclosures at bundle-build time |
| Confidence continuity | `operational_trust_summary.md` — confidence derived from observable signals |

See `docs/OPERATIONAL_MEMORY_DURABILITY.md` for full durability classification.
See `docs/STABLE_DEGRADED_CONTINUITY.md` for long-term stable degraded guidance.
See `docs/MAINTENANCE_CONTINUITY_MODEL.md` for continuity concept definitions.

## Readonly Boundary

Bundle creation copies artifacts and runs readonly/build validation. It does
not rerun the data pipeline, retry sources, mutate scoring, change aggregation,
modify auth/session behavior, or make autonomous operational decisions.
EOF

ok "OPERATIONAL_ARTIFACTS.md written"
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
