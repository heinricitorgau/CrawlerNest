# Source Completeness Review

Current source completeness is based on latest snapshot and maintenance reports.
This review does not auto-fill sources or mutate ranking output.

---

## Current Source State

| Source | Coverage | Freshness | State | Implication |
| --- | ---: | --- | --- | --- |
| QS | 1499 records | stale | stale | Usable only with freshness caveat. |
| THE | 0 records | missing | unavailable | Do not claim THE coverage. |
| ARWU | 0 records | missing | unavailable | Do not claim ARWU coverage. |
| Subject rankings | 0 latest rows in compact snapshot | missing | partial/unavailable | Subject completeness claims must be limited. |

---

## Completeness Expectations

- Baseline source completeness expects QS, THE, and ARWU to be represented when
  making broad multi-source ranking claims.
- A scoped QS-only demo may proceed if it clearly states QS-only/stale caveats.
- Subject rankings require separate subject freshness evidence; global
  aggregation freshness does not prove subject completeness.

---

## Operational Implications

- Missing THE/ARWU lowers source completeness confidence to `low`.
- Stale QS lowers freshness confidence to `low`.
- Demo confidence can remain `limited` if caveats are explicit.
- Release confidence should remain `low` until source coverage and freshness are
  recovered or release scope is narrowed.

---

## Demo Caveat Implications

Say:

- "QS is present but stale."
- "THE and ARWU are unavailable in the latest snapshot."
- "Subject ranking completeness is limited."

Do not say:

- "All sources are healthy."
- "This is production-ready global coverage."
- "The system has complete multi-source freshness."
