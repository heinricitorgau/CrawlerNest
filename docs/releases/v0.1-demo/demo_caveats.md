# Demo Caveats

Generated: 2026-05-22T16:57:34.546226+00:00
Snapshot: `2026-05-22T15:29:44.062167+00:00`
Release/demo readiness: needs caveats

## Caveats To State

- Ranking data freshness is critical; latest aggregation age is 354.4 hours.
- Expected sources unavailable in latest coverage: THE, ARWU.
- Subject ranking freshness/completeness is limited in the latest snapshot.
- This is a localhost/single-node demo posture, not a production deployment.
- Sessions are in-memory; API restart signs users out.

## What This Does Not Mean

- It does not hide stale data.
- It does not substitute missing source data.
- It does not soften critical freshness warnings.
- It does not authorize automatic source retry or pipeline repair.