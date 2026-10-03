# Operational Summary

Generated: 2026-05-22T15:59:23.359257+00:00
Latest snapshot timestamp: `2026-05-22T15:29:44.062167+00:00`

## Release / Demo Readiness

- Freshness state: **critical**
- Aggregated count: 1499
- Unresolved total: 4
- Drift warning count: 0
- Latest validation: `./scripts/verify_local_environment.sh`: Pass with warnings; `./scripts/smoke_release.sh`: Pass; `cd crawlernest/crawlernest-web && npm run build`: Pass; `cd crawlernest/servise_for_java && ./mvnw test`: Pass; `git diff --check`: Pass
- Latest drift report: Overall severity: info
- Latest freshness report: Escalation state: **critical**

## Freshness Reasons

- latest aggregation age is critical (353.1h)
- expected source gaps: THE, ARWU

## Source Health Summary

| Source | State | Signal |
| --- | --- | --- |
| QS | stale | age=353.1h |
| THE | unavailable | missing expected source |
| ARWU | unavailable | missing expected source |

## Readonly Boundary

This report only reads snapshot files, generated reports, and validation documentation. It does not rerun the pipeline, retry sources, mutate runtime state, change scoring, or write application data.