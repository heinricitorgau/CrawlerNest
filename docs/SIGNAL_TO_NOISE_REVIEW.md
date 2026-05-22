# Signal-to-Noise Review

This document classifies the current operational signals by value, identifies
primary versus secondary sources, and recommends a reading hierarchy for each
operator role.

It does not add signals. It clarifies which ones matter most.

---

## Signal Classification

### High-Value Signals

These signals directly answer the question: "Is the system safe to demo or
release right now?"

| Signal | Location | Why High-Value |
| --- | --- | --- |
| Smoke release result | `releases/v0.1-demo/smoke_release_output.txt` | Confirms the build, startup, and basic API surface are healthy. Release-blocking. |
| Demo caveats | `reports/demo_caveats.md` | The authoritative list of caveats a presenter must state. Demo-blocking if unread. |
| Freshness escalation | `reports/freshness_escalation.md` | Classifies source data age into escalation states. Directly affects demo honesty. |
| Operational trust summary | `reports/operational_trust_summary.md` | Confidence rollup across all observable surfaces. Release-facing synthesis. |
| Maintenance overview output | `./scripts/maintenance_overview.sh` (stdout) | Single-command human-readable health readout. First stop for any operator. |

### Secondary Context Signals

These signals provide supporting evidence. They are useful for deeper
investigation but should not be the first read.

| Signal | Location | Why Secondary |
| --- | --- | --- |
| Operational summary | `reports/operational_summary.md` | Source-health detail view. Useful after reading trust summary. |
| Drift timeline | `reports/drift_timeline.md` | Historical drift classification. Useful for trend questions, not current-state questions. |
| Maintenance readiness summary | `reports/maintenance_readiness_summary.md` | Confidence/caveat detail. Useful for pre-release scoping, not daily maintenance. |
| Snapshot timeline | `reports/snapshot_timeline.md` | Historical comparison narrative. Reference, not operational. |
| Operational index summary | `reports/operational_index_summary.md` | Handoff-oriented index. Useful for onboarding, not recurring maintenance. |

### Historical/Reference Only

These artifacts are point-in-time evidence. They should not be used as
current-state authority.

| Signal | Location | Why Reference Only |
| --- | --- | --- |
| Named snapshots | `snapshots/system_snapshot_*.json` | Frozen at capture time. Not live. |
| Bundle report copies | `releases/v0.1-demo/*.md` | Copied at bundle time. May be stale relative to `reports/`. |
| Snapshot timeline JSON | `reports/snapshot_timeline.json` | Machine-readable form of historical snapshots. Not human-first. |
| Failure summary | `reports/latest_failure_summary.md` | Diagnostics-era failure log. Useful only when debugging a specific past failure. |
| Agent context | `tmp/agent-context/` | Ephemeral AI reasoning context. Not authoritative operational state. |

---

## Reports That Should NOT Be First-Stop Reading

The following reports contain valid information but are not the right starting
point for a maintenance or release check:

- `reports/snapshot_timeline.md` — Provides historical narrative, not current
  state. Reading it without `freshness_escalation.md` gives false confidence.
- `reports/operational_index_summary.md` — Designed for handoff and onboarding,
  not recurring operator checks.
- `reports/operational_summary.md` — Source-detail view. Useful after, not
  instead of, `operational_trust_summary.md`.
- `releases/v0.1-demo/operational_trust_summary.md` — Bundle copy. The live
  version is `reports/operational_trust_summary.md`.

---

## Recommended Reading Hierarchy

### Maintainer (Daily or Pre-Demo Check)

1. `./scripts/maintenance_overview.sh` — Single-command readout. Run first,
   always.
2. `reports/operational_trust_summary.md` — Confidence rollup. Read if overview
   flags any concern.
3. `reports/demo_caveats.md` — Required caveats. Read before any demo.
4. `reports/freshness_escalation.md` — Read if any source shows stale or
   degraded state.
5. `docs/SOURCE_FRESHNESS_RECOVERY.md` — Read only if escalation is
   `stale` or `critical` and human action is needed.

### Release / Demo Preparation

1. `reports/demo_caveats.md` — Start here. Non-negotiable.
2. `reports/operational_trust_summary.md` — Confidence and accepted limitations.
3. `reports/maintenance_readiness_summary.md` — Pre-release caveat detail.
4. `releases/v0.1-demo/smoke_release_output.txt` — Verify smoke passed.
5. `docs/DEMO_HONESTY_GUIDELINES.md` — Confirm phrasing is compliant.

### New Operator Onboarding

1. `docs/README.md` — Documentation hub overview.
2. `docs/ARCHITECTURE_OVERVIEW.md` — System structure.
3. `docs/OPERATIONAL_RUNBOOK.md` — Startup, smoke, daily jobs.
4. `reports/operational_index_summary.md` — Current operational state summary.
5. `docs/MAINTENANCE_SIGNAL_CLARITY.md` — Signal hierarchy reference.

### Incident / Anomaly Investigation

1. `./scripts/maintenance_overview.sh` — Immediate health readout.
2. `reports/freshness_escalation.md` — Freshness state.
3. `reports/drift_timeline.md` — Historical drift events.
4. `reports/snapshot_timeline.md` — Point-in-time comparison context.
5. `docs/MAINTENANCE_PRIORITY_MATRIX.md` — Triage guidance.

---

## Noise Reduction Recommendations

The following behaviors increase signal noise without adding signal value.
Avoid them:

1. **Reading bundle copies instead of live reports.** Always prefer
   `reports/*.md` over `releases/v0.1-demo/*.md` for current state.
2. **Running all build scripts before checking `maintenance_overview.sh`.**
   The overview already calls the key builders. Build separately only when
   you need a fresh regeneration.
3. **Consulting `snapshot_timeline.md` for current state.** It is historical.
   Use `operational_trust_summary.md` for current state.
4. **Using `operational_summary.md` as a release gate.** It is a source-detail
   view, not a confidence summary. Use `operational_trust_summary.md` for
   release decisions.
5. **Adding a new summary report to resolve disagreement between existing
   reports.** That creates a third opinion, not a resolution. Address the
   divergence in the existing reports directly.

---

## Boundary

This hierarchy is advisory. It does not enforce reading order at runtime or gate
any automated process. It guides human decisions only.

See also:
- [MAINTENANCE_SIGNAL_CLARITY.md](MAINTENANCE_SIGNAL_CLARITY.md) — signal class
  definitions and authoritative vs derived distinction.
- [REPORT_CRITICALITY.md](REPORT_CRITICALITY.md) — criticality classification
  per report.
- [OPERATIONAL_RESTRAINT_GUIDELINES.md](OPERATIONAL_RESTRAINT_GUIDELINES.md) —
  criteria for adding new signals.
