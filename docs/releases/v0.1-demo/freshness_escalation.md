# Freshness Escalation Summary

Generated: 2026-05-22T15:59:18.358517+00:00
Latest snapshot: `2026-05-22T15:29:44.062167+00:00`
Escalation state: **critical**

## Signals

- Aggregated count: 1499
- Latest aggregation age hours: 353.1
- Latest aggregation status: finished
- Overall stale flag: False
- Expected source gaps: THE, ARWU
- Latest subject ranking age hours: None

## Escalation Reasons

- latest aggregation age is critical (353.1h)
- expected source gaps: THE, ARWU

## Semantics

- `healthy`: freshness and expected source signals are within normal bounds.
- `degraded`: usable but incomplete source or subject coverage is present.
- `stale`: data age crossed freshness thresholds, but the system can still serve cached data.
- `critical`: aggregation is missing, very old, empty, or expected source gaps are severe.

No pipeline rerun, source retry, selector repair, or remediation is performed by this report.