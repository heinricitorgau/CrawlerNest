# Operational Calmness Review

This document analyzes which parts of the current maintenance surface are calm
and coherent, which are beginning to produce noise, and where maintainer fatigue
or false urgency may accumulate.

It does not suppress warnings or hide state. It helps operators read the
maintenance surface without being conditioned to treat all signals as emergencies.

---

## What Is Calm And Coherent

### Operational Posture

The system has a well-understood, stable posture at RC-1:

- Data is present and browsable.
- QS, THE and ARWU 2026 rankings are ingested — 10,125 aggregated rows across all
  universes (2,098 of them global), carrying 9,530 QS, 1,637 THE and 838 ARWU ranks.
- Smoke consistently passes (15/15).
- Auth and session model is stable.
- The localhost posture is documented, not hidden.

### Known Limitations Are Documented

The three primary operational limitations are documented and accepted:

| Limitation | Where Documented |
| --- | --- |
| QS data is stale (~354h old) | `reports/demo_caveats.md`, `reports/freshness_escalation.md` |
| THE and ARWU are unavailable | `reports/demo_caveats.md`, `reports/operational_summary.md` |
| Subject ranking rows are zero | `reports/maintenance_readiness_summary.md` |

These are RC-1 scope conditions. They are not emergency signals requiring
immediate response each time a maintenance check runs.

### Readonly Boundary Is Stable

No maintenance script modifies PostgreSQL, reruns crawlers, or changes
application state. This boundary has held across all five maintenance phases.
Operators can run the full maintenance suite with no risk of state mutation.

---

## Where Noise Exists

### Repeated "Critical" Wording

The word `critical` appears in:

- `reports/maintenance_readiness_summary.md` — `Freshness state: **critical**`
- `reports/freshness_escalation.md` — escalation state
- `reports/demo_caveats.md` — "critical freshness warnings"
- `docs/MAINTENANCE_PRIORITY_MATRIX.md` — Priority 0 framing
- `docs/REPORT_CRITICALITY.md` — report criticality tier

In every case the usage is technically correct. The aggregate effect is that
every maintenance check begins with the word "critical" appearing multiple
times in the first scroll. An operator who runs `maintenance_overview.sh`
daily will encounter `critical` on nearly every run because the data freshness
state has not changed since RC-1 packaging.

**Impact:** Operators may become desensitized to `critical` wording, or
conversely may experience recurring anxiety without any new information.

### Overlapping Escalation Language

Both `freshness_escalation.md` and `maintenance_readiness_summary.md` carry
escalation language (`stale`, `degraded`, `critical`, `unavailable`) for the
same underlying conditions. An operator reading both in sequence encounters the
same facts stated twice in escalation framing, amplifying perceived severity.

### "Low" Confidence Framing

`operational_trust_summary.md` displays:

- Freshness confidence: low
- Source completeness confidence: low
- Release confidence: limited
- Operational trust level: critical

This is accurate given the current freshness state. But for an operator
maintaining a stable demo system where no new data is expected, this framing
reads as a failing grade rather than a documented stable posture.

### Unresolved Entity Count

The current snapshot shows 4 unresolved entities. This is a very small number.
It does not indicate system health risk. However it appears in multiple reports
without the contextual note that this has been stable and non-growing.

---

## Where False Urgency Can Occur

| Source | False Urgency Risk |
| --- | --- |
| `Freshness state: **critical**` appearing on every run | Operator may feel compelled to act on a condition that is accepted and documented. |
| `Release confidence: limited` in trust summary | Operator may hesitate before a demo where the posture is already known and caveat-documented. |
| Priority 0 in maintenance matrix | The Priority 0 row describes production-grade incidents; the current system is a localhost demo, making Priority 0 scenarios very unlikely. |
| "Missing expected source: THE, ARWU" | Operator unfamiliar with the RC-1 posture may treat this as a new failure rather than a known accepted state. |

---

## Calmness Preservation Guidelines

These guidelines help operators read the maintenance surface accurately without
being conditioned to treat stable known-state signals as emergencies.

### 1. Distinguish Known State from New State

Before acting on a signal, check whether it appeared on the previous maintenance
run. If the signal is unchanged from the last check, it is a stable known
limitation, not a new incident.

Known stable states at RC-1:
- QS freshness is stale (data was ingested once; no new crawl has run)
- THE and ARWU are unavailable (source files not acquired)
- Subject ranking rows are zero (expected at current MVP scope)
- Release confidence is limited (documented and caveat-covered)

### 2. Do Not Escalate Unchanged State

An escalation signal that has not changed since the last check is a reminder,
not a call to action. The appropriate response is to verify caveats are documented
and the demo is prepared to state them — not to attempt source recovery or
system modification.

### 3. Reserve "Critical" Response for New Failures

Treat `critical` wording as requiring same-day response only when:
- The signal is new (it did not appear on the previous maintenance check).
- The signal affects something that was previously healthy (smoke, auth, aggregation count).
- The signal is a regression, not a known stable limitation.

### 4. Read `demo_caveats.md` As Acceptance, Not Warning

The caveats document is the operator's evidence that known limitations are
handled, not a list of unresolved problems. Caveats that have been present for
multiple maintenance cycles represent accepted posture, not open incidents.

### 5. Calm Summary Before Full Report Review

Run `build_maintenance_calm_summary.py` (or read `reports/maintenance_calm_summary.md`)
before diving into detailed reports. The calm summary contextualizes the current
posture without alarm amplification.

---

## Recommended Wording Discipline

When writing maintenance documentation or reports, apply these constraints:

| Avoid | Prefer |
| --- | --- |
| "CRITICAL — immediate action required" | "Freshness state is critical (known RC-1 condition)." |
| "WARNING: missing sources" | "THE and ARWU are not available in the current snapshot (expected at RC-1 scope)." |
| "Confidence: FAILING" | "Release confidence is limited; caveats are documented and demo-ready." |
| "Unresolved: 4 — NEEDS ATTENTION" | "4 unresolved entities; stable and non-growing." |
| Repeating the same caveat in three consecutive report sections | State it once, reference the canonical caveats document. |

---

## Conclusion

The CrawlerNest maintenance surface is accurate and honest. The primary calmness
risk is not inaccuracy but repetition: the same known limitations appear in
escalation framing across multiple reports on every maintenance run, which can
produce false urgency without new information.

The calm summary report, reading-mode guidance, and wording discipline above
address this without suppressing any signal. The goal is a maintainer who reads
the system accurately — neither complacent nor anxious.

See also:
- [MAINTENANCE_FATIGUE_REVIEW.md](MAINTENANCE_FATIGUE_REVIEW.md)
- [SIGNAL_TO_NOISE_REVIEW.md](../data/SIGNAL_TO_NOISE_REVIEW.md)
- [MAINTENANCE_READING_MODES.md](MAINTENANCE_READING_MODES.md)
