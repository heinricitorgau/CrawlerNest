# Maintenance Calm Summary

Generated: 2026-05-22T19:11:06.508642+00:00
Snapshot: `2026-05-22T15:29:44.062167+00:00`

This summary contextualizes the current maintenance posture calmly.
Read this before detailed reports to distinguish known stable conditions
from signals that require attention.

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

## Known Stable Conditions (RC-1)

The following conditions are expected at RC-1 posture.
They are documented, accepted, and caveat-covered.
They do not require action unless a demo or release is blocked.

- QS data is stale (no new crawl since RC-1 packaging)
- THE and ARWU source files not acquired (out-of-scope for RC-1)
- Subject ranking rows at zero (MVP scope: QS global rankings only)
- Release confidence limited (localhost demo, caveats documented)

These conditions appear as escalation signals in detailed reports.
Treat them as reminders, not unresolved incidents.

---

## No New Signals

No signals outside the known stable posture were detected.
The system is in expected RC-1 maintenance state.

---

## Release Honesty Reminder

Before any demo or release, verify:

1. `reports/demo_caveats.md` exists and was regenerated this session.
2. The caveats listed are stated honestly to the audience.
3. Smoke passed in this session.
4. No new signals (above) appeared since the last session.

Known limitations do not block a demo. Undisclosed limitations do.

---

## Readonly Guarantee

This script reads existing report and snapshot files only.
It does not connect to PostgreSQL, mutate application state,
rerun crawlers, or change any operational artifact other than
`reports/maintenance_calm_summary.md`.