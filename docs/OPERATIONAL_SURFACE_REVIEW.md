# Operational Surface Review

This review classifies the current operational artifact surface. It does not
delete artifacts or change runtime behavior.

---

## Current Surface

| Area | Artifacts | Assessment |
| --- | --- | --- |
| Snapshots | `system_snapshot_*.json`, `latest_status.json` | Necessary. Keep append-oriented dated snapshots plus compact latest pointer. |
| Failure summary | `latest_failure_summary.md` | Useful but overlaps with newer summaries. Keep as historical health/failure view. |
| Timeline intelligence | `snapshot_timeline.md/json` | Useful for historical comparison. Not a release-entry file. |
| Drift intelligence | `drift_timeline.md` | Useful for specific drift questions and release caveats. |
| Freshness intelligence | `freshness_escalation.md` | Useful for demo claims and stale-data clarity. |
| Operational summary | `operational_summary.md` | Demo-friendly current state. |
| Operational index summary | `operational_index_summary.md` | Preferred single-entry summary for handoff. |
| Bundle diagnostics | `diagnostics_summary.txt`, `smoke_release_output.txt` | Necessary release evidence. |
| Agent context | `tmp/agent-context/*` | Useful but temporary and non-authoritative. |

---

## Duplicated Or Overlapping Reports

| Overlap | Recommendation |
| --- | --- |
| `latest_failure_summary.md` and `operational_summary.md` both summarize current health. | Keep both. Treat `operational_summary.md` as demo-facing; treat failure summary as diagnostics/failure detail. |
| `snapshot_timeline.md` and `drift_timeline.md` both read snapshot history. | Keep both. Timeline is descriptive; drift timeline classifies events. |
| `freshness_escalation.md` and `check_pipeline_health.py` both surface stale data. | Keep both. Freshness escalation is snapshot-based and report-oriented; pipeline health is live/readonly DB diagnostics. |
| `operational_summary.md` and `operational_index_summary.md` both offer a first read. | Use `operational_index_summary.md` as the top entry; use `operational_summary.md` for source-health details. |

---

## Terminology Risks

- `stale` appears in both snapshot export and live pipeline health. Keep the
  wording, but document that thresholds may come from the producing surface.
- `critical` is advisory in reports, not an automated action trigger.
- `release-ready` must include known limitations; it must not imply data is
  fresh when reports show stale evidence.

---

## Surface Reduction Guidance

Do not delete current artifacts during Phase 1. Instead:

1. Point handoff readers to `docs/OPERATIONAL_INDEX.md`.
2. Point demo readers to `reports/operational_index_summary.md`.
3. Use `REPORT_RELATIONSHIPS.md` to decide where a future report belongs.
4. Avoid creating another top-level summary unless it replaces an existing
   report role.
5. Keep generated evidence under `reports/`, `snapshots/`, `tmp/`, or
   `releases/`.

---

## Conclusion

The current surface is larger than early MVP needs, but it is manageable after
adding hierarchy, vocabulary, lineage, and a single-entry summary. No artifact
needs deletion in Phase 1.
