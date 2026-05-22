# Maintenance Continuity Summary

Generated: 2026-05-22T19:11:06.563284+00:00
Snapshot: `2026-05-22T15:29:44.062167+00:00`

This summary assesses operational continuity at RC-1.
Read this alongside the calm and steadiness summaries to confirm
the system remains coherent across sessions and operators.

---

## Continuity Posture

| Signal | Value |
| --- | --- |
| Aggregated universities | 1499 |
| Available sources | QS |
| Freshness state | critical |
| Operational trust level | critical |
| Smoke | passed |
| Demo caveats | present |

---

## Stable Degraded Continuity

The following conditions have been stable since RC-1 packaging.
They are expected, documented, and non-worsening.
They do not represent continuity regressions.

- QS data is stale (no new crawl since RC-1 packaging)
- THE and ARWU source files not acquired (out-of-scope for RC-1)
- Subject ranking rows at zero (MVP scope: QS global rankings only)
- Release confidence limited (localhost demo, caveats documented)

See `docs/STABLE_DEGRADED_CONTINUITY.md` for long-term maintenance guidance.

---

## Operational Memory Durability Posture

| Artifact Class | Status |
| --- | --- |
| Named snapshots | append-only; durable |
| Release bundle (v0.1-demo) | frozen at bundle-build time; durable |
| Live reports (reports/*.md) | ephemeral; regenerated each session |
| Demo caveats | present |

See `docs/OPERATIONAL_MEMORY_DURABILITY.md` for full durability classification.

---

## Release Honesty Continuity

demo_caveats.md is present. Before any demo or release:

1. Read `reports/demo_caveats.md` in full.
2. State all listed caveats to the audience explicitly.
3. Do not omit caveats for audiences who have heard them before.

See `docs/DEMO_HONESTY_GUIDELINES.md` for required phrasing.

---

## Continuity Dimensions

| Dimension | Assessment |
| --- | --- |
| Stable degraded continuity | RC-1 degraded conditions unchanged and non-worsening |
| Report continuity | Report semantics stable; no classification drift detected |
| Snapshot continuity | Named snapshots append-only; latest_status.json is current pointer |
| Confidence continuity | Trust levels derived from observable signals; not manually adjusted |
| Release honesty continuity | demo_caveats.md exists and was last generated this session |
| Operational vocabulary continuity | Terminology consistent with docs/OPERATIONAL_VOCABULARY.md |

---

## No Continuity Regressions Detected

All signals are within the known stable RC-1 posture.
No continuity regressions were detected in this session.

---

## Maintenance Steadiness Posture

See `reports/maintenance_steadiness_summary.md` for caution level and
steadiness guidance. See `reports/maintenance_calm_summary.md` for the
full calm posture context.

---

## Readonly Guarantee

This script reads existing report and snapshot files only.
It does not connect to PostgreSQL, mutate application state,
rerun crawlers, or change any operational artifact other than
`reports/maintenance_continuity_summary.md`.