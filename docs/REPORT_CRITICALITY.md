# Report Criticality Classification

This document classifies all generated reports and release artifacts by
criticality. Its purpose is to reduce maintainer ambiguity about which reports
must be read, which provide supporting context, and which are historical
evidence only.

---

## Criticality Levels

| Level | Meaning |
| --- | --- |
| **critical** | Must be read before any demo or release. A missing or degraded critical report is a release blocker. |
| **important** | Should be read when a critical report flags concern. Provides depth and context for a critical signal. |
| **reference** | Historical or structural context. Not a first-stop read. Do not use for current-state decisions. |

---

## Critical Reports

These reports must be present and reviewed before any demo or release.

| Report | Location | Role |
| --- | --- | --- |
| `smoke_release_output.txt` | `releases/v0.1-demo/smoke_release_output.txt` | Build and API smoke validation. Release-blocking if absent or failed. |
| `operational_trust_summary.md` | `reports/operational_trust_summary.md` | Confidence rollup across freshness, sources, drift, and maintenance. Single-sentence release confidence answer. |
| `freshness_escalation.md` | `reports/freshness_escalation.md` | Source data age classification with escalation states. Directly informs demo honesty. |
| `demo_caveats.md` | `reports/demo_caveats.md` | The authoritative list of caveats that must be stated to any demo audience. Demo-blocking if unread. |

**Regeneration commands:**

```bash
./scripts/build_operational_trust_summary.py
./scripts/build_freshness_escalation.py
./scripts/build_demo_caveats.py
# smoke is regenerated as part of:
./scripts/smoke_release.sh
```

---

## Important Reports

Read these when a critical report raises a concern or when planning a release.

| Report | Location | Role | When To Read |
| --- | --- | --- | --- |
| `operational_summary.md` | `reports/operational_summary.md` | Source-health detail. Per-source coverage and freshness breakdown. | When `operational_trust_summary.md` shows source completeness concerns. |
| `maintenance_readiness_summary.md` | `reports/maintenance_readiness_summary.md` | Caveat and confidence detail. Pre-release maintenance scope. | Before release when caveats need to be documented or accepted. |
| `drift_timeline.md` | `reports/drift_timeline.md` | Historical drift classification. Shows whether counts are trending. | When `freshness_escalation.md` shows degraded or critical state. |

**Regeneration commands:**

```bash
./scripts/build_operational_summary.py
./scripts/inspect_source_freshness.py --summary-output reports/maintenance_readiness_summary.md
./scripts/build_drift_timeline.py
```

---

## Reference Artifacts

Use these for historical context, onboarding, or structural understanding.
Do not use them as the basis for current-state decisions.

| Artifact | Location | Role |
| --- | --- | --- |
| `snapshot_timeline.md` | `reports/snapshot_timeline.md` | Narrative comparison of snapshot history. Historical. |
| `snapshot_timeline.json` | `reports/snapshot_timeline.json` | Machine-readable snapshot history. Not human-first. |
| `operational_index_summary.md` | `reports/operational_index_summary.md` | Handoff and onboarding summary. One-time read, not recurring. |
| `latest_failure_summary.md` | `reports/latest_failure_summary.md` | Diagnostics-era failure detail. Use when investigating a specific past failure. |
| `system_snapshot_*.json` | `snapshots/` | Point-in-time snapshots. Frozen at capture time. |
| `maintenance_navigation.md` | `reports/maintenance_navigation.md` | Operator navigation guide. Meta-reference. |
| Release bundle copies | `releases/v0.1-demo/*.md` | Bundle-time copies of reports. May be stale relative to `reports/`. |
| Agent context | `tmp/agent-context/` | Ephemeral AI context. Not operational authority. |
| `latest_status.json` | `snapshots/latest_status.json` | Compact latest state pointer. Input to report builders, not a reading artifact. |

---

## Classification Notes

### Why Smoke Is Critical

Smoke output confirms that the runtime build, startup sequence, and basic API
surface are healthy. Without it, no confidence claim about the demo is grounded.
A missing smoke output does not mean smoke passed; it means the evidence is absent.

### Why Demo Caveats Is Critical

The caveats document is the presenter's contract with the audience. Reading it
is not optional — it determines which claims are honest and which are misleading.
An unread caveats file is an operational gap, not a stylistic choice.

### Why Bundle Copies Are Reference Only

Report copies in `releases/v0.1-demo/` were accurate at bundle time. The live
operational state is in `reports/`. Bundle copies must not be used to assess
current freshness or confidence — only the live `reports/` files are authoritative
after the bundle was created.

### Why Snapshot Timeline Is Reference Only

The snapshot timeline describes what happened historically. It does not describe
current state. Reading it without `operational_trust_summary.md` may give false
confidence if recent snapshots look healthy but the live state is degraded.

---

## Boundary

This classification is advisory. No runtime process reads it. It guides human
reading decisions and helps maintainers avoid spending time on reference artifacts
when critical ones are unread.

See also:
- [SIGNAL_TO_NOISE_REVIEW.md](SIGNAL_TO_NOISE_REVIEW.md) — reading hierarchy by role
- [MAINTENANCE_SIGNAL_CLARITY.md](MAINTENANCE_SIGNAL_CLARITY.md) — signal class definitions
- [OPERATIONAL_RESTRAINT_GUIDELINES.md](OPERATIONAL_RESTRAINT_GUIDELINES.md) — criteria before adding a new report
