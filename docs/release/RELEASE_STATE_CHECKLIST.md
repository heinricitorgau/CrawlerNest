# Release State Checklist

Use this before any demo, handoff, or early release candidate.

---

## Required Checks

| Check | Command / Evidence | Status |
| --- | --- | --- |
| Release smoke passes | `./scripts/smoke_release.sh` | Required |
| Latest snapshot exists | `ls snapshots/latest_status.json` | Required |
| Operational summary generated | `./scripts/build_operational_index_summary.py` | Required |
| Source freshness inspected | `./scripts/inspect_source_freshness.py` | Required |
| Demo caveats generated | `./scripts/build_demo_caveats.py` | Required |
| Maintenance overview checked | `./scripts/maintenance_overview.sh` | Recommended |
| Freshness escalation reviewed | `reports/freshness_escalation.md` | Required |
| Drift severity reviewed | `reports/drift_timeline.md` | Required |
| Release bundle rebuilt | `./scripts/build_demo_bundle.sh` | Required |
| Stale warnings documented | `reports/maintenance_readiness_summary.md` or demo notes | Required if stale |
| Source availability documented | `reports/maintenance_readiness_summary.md` | Required |

---

## Current Caveat Template

```text
Current operational data is suitable for a scoped demo with caveats:
- QS is present but stale.
- THE and ARWU are unavailable in the latest source coverage.
- Drift severity is currently info.
- Release smoke passes.
```

---

## Stop Conditions

Do not claim release/demo readiness without re-scoping if:

- `smoke_release.sh` fails
- latest snapshot is missing or malformed
- aggregation count collapses
- auth/session behavior is broken
- freshness state is critical and the demo claim depends on freshness
- source gaps are hidden rather than documented
