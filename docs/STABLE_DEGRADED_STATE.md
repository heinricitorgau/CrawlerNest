# Stable Degraded State

This document defines the current CrawlerNest RC-1 stable degraded operational
posture, explains what it means, how to communicate it, and what would or would
not escalate it into an active incident.

---

## Definition

A **stable degraded state** is an operational posture where:

- One or more signals show degraded or critical values
- The degradation is **documented**, **accepted**, and **non-worsening**
- The **runtime is functioning correctly** within that degraded posture
- **No corrective action is pending** or expected in the near term
- The state is **disclosed** to any demo audience or reviewer

This is not a healthy state. It is not an emergency. It is a documented,
known posture that is sustained intentionally within a scoped release context.

---

## Current RC-1 Degraded Conditions

| Condition | Signal | Value | Why Accepted |
| --- | --- | --- | --- |
| QS data freshness | `freshness_escalation.md`: escalation state | stale (~354h) | No new crawl run since RC-1 packaging; expected for a packaged demo |
| THE source availability | `operational_summary.md`: THE count | 0 — unavailable | Source files not acquired; THE ingestion is out of scope at RC-1 |
| ARWU source availability | `operational_summary.md`: ARWU count | 0 — unavailable | Source files not acquired; ARWU ingestion is out of scope at RC-1 |
| Subject ranking rows | `maintenance_readiness_summary.md` | 0 — no subject data | QS subject ranking not yet ingested in the live environment |
| Release confidence | `operational_trust_summary.md` | limited | Derived from above; documented and caveat-covered |
| Operational trust level | `operational_trust_summary.md` | critical | Derived from freshness + source gaps; known and disclosed |

These six degraded conditions have been present since RC-1 packaging and have
not worsened since then.

---

## What Is Stable (Not Degraded)

| Signal | Status | Meaning |
| --- | --- | --- |
| Smoke | 15/15 passing | Build and API runtime are healthy |
| Aggregated count | 1,499 — stable | QS data is fully ingested and correctly aggregated |
| Auth and session | Stable | Login, registration, and session expiry work correctly |
| Drift | No escalation | No unexpected count movements since last snapshot |
| Corruption signals | None | No evidence of data corruption in aggregation |
| Unresolved entities | 4 — stable, non-growing | Entity resolution gaps are small and not worsening |

The runtime is functioning correctly within the degraded source posture.

---

## This Is Not an Active Incident

An **active incident** is characterized by:

- A NEW failure that did not exist in the previous session
- A WORSENING of a previously stable signal
- Unexplained behavior change in smoke, auth, or aggregation

The current degraded conditions are:

- All previously known and documented
- All present in every maintenance session since RC-1 packaging
- None worsening
- None causing runtime malfunction

**Conclusion:** The system is in stable degraded operational posture, not in
an active incident. An operator who reads "freshness: critical" on every run
should treat it as a reminder of the known posture, not a new alarm.

---

## How To Communicate This Posture

### To a Demo Audience

State the caveats from `reports/demo_caveats.md` clearly. Do not soften or
omit them. The caveats are the honest disclosure of the degraded conditions.

Acceptable phrasing:
> "The data is sourced from QS 2026. THE and ARWU data are not available in
> this demo. The ranking data was ingested at launch and has not been
> refreshed — freshness is limited but the ingested data is correct and
> complete for QS."

Unacceptable phrasing:
> "The data is fully up to date." (false — QS data is stale)
> "All sources are available." (false — THE and ARWU are unavailable)

### To a New Operator

Refer to this document and `docs/OPERATIONAL_MEMORY_PRESERVATION.md`. Explain:
- The system functions correctly within the known degraded posture
- The degraded conditions are expected and documented
- The maintenance workflow is designed to work with this posture, not to hide it

### To a Stakeholder Review

Present the `reports/maintenance_calm_summary.md` or
`reports/maintenance_steadiness_summary.md` output. These contextualize the
posture without alarm amplification while being fully honest.

---

## What Would Escalate This Into an Active Incident

The stable degraded posture would become an active incident if any of the
following NEW conditions appear:

| Escalation Trigger | Why It Breaks the "Stable" Criterion |
| --- | --- |
| Smoke starts failing | Runtime health was stable; failure is a new regression |
| Aggregated count drops from 1,499 | Previously stable aggregation is now degrading |
| QS count drops to 0 | Previously available source becomes unavailable |
| Auth stops working (login/session breaks) | Previously stable feature regresses |
| Unresolved entity count grows rapidly | Previously stable gap is now worsening |
| A new source error appears that was absent before | New failure, not part of known posture |

In any of these cases, switch to Mode 4 (Incident Investigation) from
`docs/MAINTENANCE_READING_MODES.md` and triage per
`docs/MAINTENANCE_PRIORITY_MATRIX.md`.

---

## What Would NOT Escalate This Into an Incident

The following conditions do NOT escalate the posture, even if they appear
alarming in report language:

| Non-Escalating Condition | Why It Does Not Escalate |
| --- | --- |
| `Freshness state: critical` on every run | Stable, documented, non-worsening; the data has not become fresher because no crawl ran |
| `THE unavailable`, `ARWU unavailable` | Known, documented, non-worsening |
| `Release confidence: limited` | Derived from known limitations; not a new failure |
| `Operational trust level: critical` | Derived from freshness and source gaps; not a new failure |
| `Subject ranking rows: 0` | Expected at current MVP scope |
| QS aggregation age increasing with each daily check | Expected; age increases because no new crawl runs |

**The key principle:** A condition that was present on the previous maintenance
check and has not changed is part of the stable degraded posture, not a new
incident — regardless of the severity language used to describe it.

---

## Posture Evolution

The stable degraded posture will change when:

- A new QS crawl is run and data is refreshed
- THE or ARWU source files are acquired and ingested
- Subject ranking data is loaded

Until those explicit actions are taken, the posture described here is the
correct and honest description of the system state.

---

## Boundary

This document describes an operational concept and the current RC-1 posture.
It does not suppress any signal, change any report, or gate any operation.
All escalation signals remain visible in their respective reports.

See also:
- [OPERATIONAL_MEMORY_PRESERVATION.md](OPERATIONAL_MEMORY_PRESERVATION.md) — memory semantics
- [MAINTENANCE_DISCIPLINE.md](MAINTENANCE_DISCIPLINE.md) — healthy response to known degraded state
- [OPERATIONAL_CALMNESS_REVIEW.md](OPERATIONAL_CALMNESS_REVIEW.md) — false urgency analysis
- [DEMO_HONESTY_GUIDELINES.md](DEMO_HONESTY_GUIDELINES.md) — required demo disclosure
