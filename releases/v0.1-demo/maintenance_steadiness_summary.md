# Maintenance Steadiness Summary

Generated: 2026-05-22T19:11:06.535407+00:00
Snapshot: `2026-05-22T15:29:44.062167+00:00`

This summary assesses the operational steadiness of CrawlerNest at RC-1.
Read this alongside the calm summary to confirm the system remains in its
expected stable degraded posture.

---

## Current Posture

| Signal | Value |
| --- | --- |
| Aggregated universities | 1499 |
| Available sources | QS |
| Freshness state | critical |
| Data age (hours) | 354.4 |
| Operational trust level | critical |
| Smoke | passed |

---

## Stable Degraded Posture

The following degraded indicators are present at RC-1. They are expected,
documented, and non-worsening. They do not constitute an active incident.

- **QS freshness**: stale (~354h) — No crawl run since RC-1 packaging; expected for packaged demo
- **THE availability**: unavailable (0 records) — Source files not acquired; out-of-scope at RC-1
- **ARWU availability**: unavailable (0 records) — Source files not acquired; out-of-scope at RC-1
- **Subject ranking rows**: 0 — no subject data — QS subject ranking not yet ingested at MVP scope
- **Release confidence**: limited — Derived from freshness and source gaps; documented and caveat-covered
- **Operational trust level**: critical — Derived from freshness + source gaps; known and disclosed

See `docs/STABLE_DEGRADED_STATE.md` for the full posture definition and
communication guidance.

---

## Caution Level

**low — no action required**

No signals outside the known stable RC-1 posture were detected.

---

## No New Signals

No signals outside the known stable posture were detected.
The system is in expected RC-1 maintenance state.

---

## Steadiness Guidance

- Daily maintenance check: run `maintenance_overview.sh` only. No additional scripts needed.
- Any concern listed above requires Mode 4 investigation before demo or release.
- Full maintenance cadence (daily/weekly/release-demo/incident-only) is in
  `docs/MAINTENANCE_CADENCE_REVIEW.md`.

---

## Readonly Guarantee

This script reads existing report and snapshot files only.
It does not connect to PostgreSQL, mutate application state,
rerun crawlers, or change any operational artifact other than
`reports/maintenance_steadiness_summary.md`.