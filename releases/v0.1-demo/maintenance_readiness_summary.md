# Maintenance Readiness Summary

Generated: 2026-05-22T16:48:35.151764+00:00
Snapshot: `2026-05-22T15:29:44.062167+00:00`
Freshness state: **critical**

## Aggregation

- Aggregated count: 1499
- Latest aggregation: 2026-05-08T06:24:35.935171+08:00
- Latest aggregation age hours: 354.4
- Latest aggregation status: finished

## Source Coverage

| Source | Count | State | Reason |
| --- | ---: | --- | --- |
| QS | 1499 | stale | aggregation age 354.40h |
| THE | 0 | unavailable | missing expected source |
| ARWU | 0 | unavailable | missing expected source |

## Unresolved Trend

- Total unresolved: 4
- Last 7 days: 0
- Trend pct: None

## Subject Freshness

- Latest subject year: None
- Subject ranking rows: 0

## Maintenance Readiness

- Drift state: see `reports/drift_timeline.md`
- Known stale sources: QS
- Known unavailable sources: THE, ARWU
- Known blockers: freshness state is critical, missing sources: THE, ARWU
- Release/demo readiness: needs caveats
- Operational confidence level: limited
- Demo caveat presence: required
- Freshness confidence: low
- Source completeness confidence: low

## Readonly Boundary

This inspection reads snapshot JSON only. It does not rerun ingestion, mutate pipeline state, auto-repair source fetches, change scoring, or substitute fallback ranking data.