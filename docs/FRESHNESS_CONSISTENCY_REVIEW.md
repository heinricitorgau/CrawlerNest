# Freshness Consistency Review

This review explains how freshness-related surfaces currently align and where
they diverge. It is documentation only; runtime semantics are not changed.

---

## Surfaces Reviewed

| Surface | Evidence Source | Current Signal |
| --- | --- | --- |
| `scripts/check_pipeline_health.py` | Live readonly PostgreSQL query | `stale` because aggregation age exceeds 36h and THE/ARWU are missing. |
| `reports/freshness_escalation.md` | Latest snapshot-derived report | `critical` because aggregation age is very old and THE/ARWU are missing. |
| `reports/operational_summary.md` | Snapshot/report-derived summary | `critical`, with QS stale and THE/ARWU unavailable. |
| `snapshots/latest_status.json` compact field | Snapshot export compact status | `overall_stale=false` in the current compact snapshot. |

---

## Consistent Semantics

- All human-facing reports agree that current freshness needs caveats.
- All current report paths identify THE and ARWU as missing/unavailable.
- All current report paths keep QS present but stale, not unavailable.
- No surface attempts automatic repair or hidden source substitution.

---

## Current Divergence

The main divergence is:

- compact snapshot `overall_stale=false`
- live health / freshness reports classify current state as stale or critical

This exists because compact snapshot status was captured by
`export_system_snapshot.py` using its own snapshot-time freshness fields, while
`check_pipeline_health.py` applies a stricter live threshold and the newer
maintenance reports apply explicit source-gap escalation.

---

## Intentional Divergence

Some divergence is acceptable:

- live health checks may be stricter than stored compact metadata
- release/demo reports may escalate source gaps more strongly than raw snapshot
  booleans
- snapshot evidence is historical, not runtime authority

---

## Future Cleanup Candidates

- Align compact `overall_stale` calculation with the same source-gap and age
  thresholds used by maintenance reports.
- Add a separate compact field for `source_gap_state` rather than overloading
  `overall_stale`.
- Document freshness thresholds directly in snapshot export output.

These are future cleanup candidates only. Phase 2 does not change runtime or
snapshot semantics.
