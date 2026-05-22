# Maintenance Cadence Review

This document defines the appropriate maintenance cadence for each operational
activity in CrawlerNest. Its purpose is to prevent over-checking: not every
script needs to run daily, and not every report needs to be read every session.

---

## Cadence Definitions

| Cadence | Meaning |
| --- | --- |
| **daily** | Run every working day while the system is being actively maintained. |
| **weekly** | Run once per week or before any significant handoff. |
| **release/demo** | Run immediately before any demo presentation or release packaging. |
| **incident-only** | Run only when a signal outside the stable degraded posture is detected. |
| **archival/reference** | Read once during onboarding; consult only when the question is specifically about history. |

---

## Daily Cadence

These are the only actions needed for a routine daily maintenance check.

**Scripts to run:**

```bash
./scripts/maintenance_overview.sh
```

This single command is sufficient. It runs all necessary builders internally
and surfaces every signal needed to confirm "nothing changed."

**Signals to check:**

- Smoke result — must show `0 failed` matching the previous session
- Aggregated count — must match the previous session (expected: 1,499)
- Any escalation language that is NEW vs the previous session

**Signals to ignore (stable background context at RC-1):**

- `Freshness state: critical` — expected; unchanged since RC-1 packaging
- `THE unavailable`, `ARWU unavailable` — expected; out-of-scope at RC-1
- `Release confidence: limited` — expected; documented posture
- `Operational trust level: critical` — expected; derived from above

**Reports to skip during daily check:**

- `reports/drift_timeline.md` — read only if aggregation count changed
- `reports/freshness_escalation.md` — read only if freshness state changed
- `reports/operational_summary.md` — read only if a source state changed
- All `docs/` files — no changes needed for routine daily check

---

## Weekly Cadence

**Scripts to run:**

```bash
./scripts/maintenance_overview.sh
./scripts/build_demo_caveats.py
./scripts/build_operational_trust_summary.py
```

**Reports to read:**

- `reports/maintenance_calm_summary.md` — calm posture review
- `reports/demo_caveats.md` — confirm caveats are current
- `reports/operational_trust_summary.md` — confidence posture review

**Purpose:** Confirm the stable degraded posture has not drifted. Verify that
demo caveats are accurate and up to date. This takes approximately 10 minutes.

**Signals that are change-triggered (not weekly):**

- Running `build_freshness_escalation.py` — only needed when source state changes
- Running `build_drift_timeline.py` — only needed when new snapshots are added
- Exporting a new snapshot — only needed when a meaningful state change occurs

---

## Release / Demo Cadence

Run these before any demo presentation or before creating a release bundle.

**Scripts to run (in order):**

```bash
./scripts/build_operational_trust_summary.py
./scripts/build_demo_caveats.py
./scripts/build_maintenance_calm_summary.py
./scripts/build_maintenance_steadiness_summary.py
./scripts/smoke_release.sh
./scripts/build_demo_bundle.sh
```

**Reports to read (in order):**

1. `reports/maintenance_calm_summary.md` — calm posture first
2. `reports/maintenance_steadiness_summary.md` — steadiness and caution level
3. `reports/demo_caveats.md` — required presenter caveats
4. `reports/operational_trust_summary.md` — confidence and release posture
5. `releases/v0.1-demo/smoke_release_output.txt` — smoke passed confirmation

**Purpose:** Ensure all evidence is fresh, all caveats are accurate, smoke
passes, and the presenter is informed of the current posture.

---

## Incident-Only Cadence

Run these only when a signal outside the stable degraded posture appears.

**Trigger conditions (NEW since last session):**

- Smoke shows any failures
- Aggregated count drops from expected baseline (1,499)
- A source that was previously available becomes unavailable
- Auth or session behavior changes unexpectedly
- Any `[error]` or `[fail]` in the maintenance overview output

**Scripts to run when triggered:**

```bash
./scripts/maintenance_overview.sh           # immediate readout
./scripts/inspect_source_freshness.py       # freshness detail
./scripts/build_freshness_escalation.py     # escalation classification
./scripts/build_drift_timeline.py           # drift context if count changed
```

**Triage guidance:** See `docs/MAINTENANCE_PRIORITY_MATRIX.md`.

**Do NOT run these during routine daily checks.** They are incident-context
tools, not daily tools.

---

## Archival / Reference Cadence

These artifacts and documents are read once during onboarding and referenced
only when their specific question is raised.

| Artifact | When to Consult |
| --- | --- |
| `docs/SNAPSHOT_LINEAGE.md` | When investigating snapshot history or lineage questions |
| `docs/REPORT_RELATIONSHIPS.md` | When adding or modifying a report |
| `docs/SNAPSHOT_COMPARISON.md` | When doing a targeted snapshot diff |
| `docs/OPERATIONAL_MEMORY_PRESERVATION.md` | When planning a bundle or archival action |
| `docs/STABLE_DEGRADED_STATE.md` | When explaining the RC-1 posture to a new operator |
| `reports/snapshot_timeline.md` | When investigating a historical trend question |
| `reports/latest_failure_summary.md` | When investigating a specific past failure |
| `releases/v0.1-demo/*.md` (bundle copies) | When reviewing the state at release time |

**Do NOT read these reports routinely.** They accumulate historical context
that is irrelevant to current-state maintenance.

---

## Anti-Patterns to Avoid

| Anti-Pattern | Why It Causes Problems |
| --- | --- |
| Running all build scripts before checking the overview | Over-generates reports that may not be needed; adds noise to the session |
| Reading all 10 reports in `reports/` on every check | Most reports carry the same stable information; redundant reads increase fatigue |
| Exporting a new snapshot every session | Snapshots should capture meaningful state changes, not routine observation |
| Reading drift timeline daily | Drift is a slow signal; daily reads of a non-changing timeline add no information |
| Re-running phase validation scripts routinely | Phase scripts validate milestones, not current operational state |

---

## Cadence Summary Table

| Activity | Daily | Weekly | Release/Demo | Incident-Only | Reference |
| --- | :---: | :---: | :---: | :---: | :---: |
| `maintenance_overview.sh` | ✓ | ✓ | ✓ | ✓ | |
| `build_demo_caveats.py` | | ✓ | ✓ | | |
| `build_operational_trust_summary.py` | | ✓ | ✓ | | |
| `build_maintenance_calm_summary.py` | | ✓ | ✓ | | |
| `build_maintenance_steadiness_summary.py` | | ✓ | ✓ | | |
| `smoke_release.sh` | | | ✓ | ✓ | |
| `build_demo_bundle.sh` | | | ✓ | | |
| `inspect_source_freshness.py` | | | | ✓ | |
| `build_freshness_escalation.py` | | | | ✓ | |
| `build_drift_timeline.py` | | | | ✓ | |
| `export_system_snapshot.py` | | | | ✓ | |
| `reports/snapshot_timeline.md` | | | | | ✓ |
| `docs/STABLE_DEGRADED_STATE.md` | | | | | ✓ |

---

## Boundary

This cadence is a recommended workflow, not an enforced policy. It does not
gate any operation or block any script. It exists to reduce over-checking
and maintenance fatigue.

See also:
- [MAINTENANCE_READING_MODES.md](MAINTENANCE_READING_MODES.md) — structured reading paths
- [MAINTENANCE_FATIGUE_REVIEW.md](MAINTENANCE_FATIGUE_REVIEW.md) — fatigue reduction
- [STABLE_DEGRADED_STATE.md](STABLE_DEGRADED_STATE.md) — stable background context definition
