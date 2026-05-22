# Operational Index Summary

Generated: 2026-05-22T19:11:06.428592+00:00

## Single-Entry Status

- Latest snapshot timestamp: `2026-05-22T15:29:44.062167+00:00`
- Operational freshness state: **critical**
- Freshness escalation: **critical**
- Drift severity: **info**
- Validation status: pass (5 pass rows)
- Latest release bundle: v0.1-demo built 2026-05-22T18:57:55Z
- Latest smoke result: pass (10 passed, 0 failed)

## Source Evidence

| Evidence | Path | Role |
| --- | --- | --- |
| Operational summary | `reports/operational_summary.md` | Demo-friendly current state. |
| Freshness escalation | `reports/freshness_escalation.md` | Staleness and source-gap classification. |
| Drift timeline | `reports/drift_timeline.md` | Historical drift event classification. |
| Latest snapshot | `snapshots/latest_status.json` | Latest compact snapshot pointer. |
| Validation results | `docs/RC1_VALIDATION_RESULTS.md` | Latest recorded validation table. |
| Release bundle manifest | `releases/v0.1-demo/MANIFEST.txt` | Latest bundle contents and timestamp. |
| Smoke output | `releases/v0.1-demo/smoke_release_output.txt` | Latest bundle-captured smoke run. |

## Readonly Boundary

This summary only reads existing reports, docs, snapshots, and release bundle files. It does not run the pipeline, connect to PostgreSQL, change scoring, mutate runtime state, modify diagnostics semantics, or make autonomous decisions.