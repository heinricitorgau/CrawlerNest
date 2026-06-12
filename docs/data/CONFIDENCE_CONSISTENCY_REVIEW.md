# Confidence Consistency Review

This review compares confidence semantics across operational reports. It does
not change report logic or runtime semantics.

---

## Surfaces Reviewed

| Surface | Current Role |
| --- | --- |
| `reports/operational_summary.md` | Demo-friendly state and source health. |
| `reports/maintenance_readiness_summary.md` | Maintenance confidence and readiness caveats. |
| `reports/freshness_escalation.md` | Freshness/source-gap escalation. |
| `reports/drift_timeline.md` | Historical drift severity. |
| `reports/demo_caveats.md` | Presenter-facing caveats. |
| `reports/operational_trust_summary.md` | Conservative confidence rollup. |

---

## Consistent Semantics

- Freshness-critical evidence lowers confidence.
- Missing THE/ARWU lowers source completeness confidence.
- Drift severity is currently `info`, so drift is not the limiting signal.
- Demo can proceed only as scoped and caveated.
- No report treats missing sources as healthy.

---

## Possible Divergence

- `operational_summary.md` may lag if not regenerated after maintenance reports.
- `demo_caveats.md` depends on report text and snapshot availability.
- `operational_trust_summary.md` intentionally uses the most conservative
  interpretation when inputs disagree.

---

## Intentional Divergence

- Demo confidence may be `limited` while release confidence is `low`, because a
  scoped demo can be honest even when release confidence is constrained.
- Drift can be `info` while freshness is `critical`; those are different
  dimensions.
- Compact snapshot `overall_stale=false` can coexist with report-level critical
  freshness until future cleanup aligns snapshot fields.

---

## Future Cleanup Candidates

- Generate freshness, maintenance, caveats, and trust summaries in one scripted
  sequence.
- Add machine-readable confidence JSON if reports need stronger consistency.
- Align compact snapshot stale semantics with maintenance reports.
