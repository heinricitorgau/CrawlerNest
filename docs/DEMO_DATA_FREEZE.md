# Demo Data Freeze

Defines which data artifacts should be frozen before a competition demo, which should not be
changed, and why stable degraded consistency is preferable to unstable freshness.

---

## Core Principle

The CrawlerNest competition demo is a demonstration of an **operational system at RC-1 scope**.
The demo posture is **stable degraded** — a documented, caveat-covered state that is expected,
not a failure to be corrected before the demo.

**Do not attempt to "improve" the data state the day before a demo.**
A partially re-ingested dataset, a partially refreshed snapshot, or a pipeline run with
unexpected output is harder to explain than a consistently stale dataset.

---

## Data That Should Be Frozen

### QS Ranking Data

**Status:** Ingested at RC-1 packaging (~354 hours stale at time of demo).
**Action:** Freeze — do not re-run ingestion.
**Why:** The stale caveat is already disclosed and caveat-covered in:
- `reports/demo_caveats.md`
- The Data Caveats section of every recommendation explain panel
- The `RC1_STANDARD_CAVEATS` in `caveatMessages.ts`

Re-ingesting QS data immediately before the demo would change:
- The "Data ingested N hours ago" caveat wording
- Potentially the rank data itself (if a new QS dataset was acquired)
- The snapshot used by maintenance reports

All three changes introduce uncertainty without adding any demo value.

---

### THE and ARWU Data

**Status:** Not available at RC-1 — zero records.
**Action:** Freeze — do not attempt to acquire or ingest.
**Why:** The demo explicitly discloses THE/ARWU unavailability as a known RC-1 scope
limitation. A partial or incomplete THE/ARWU dataset added the day before a demo would:
- Change the source coverage display unpredictably
- Potentially inflate confidence scores beyond what is correct
- Require updating caveats that are already tested and validated

---

### Subject Ranking Data

**Status:** Incomplete at RC-1 — limited rows.
**Action:** Freeze — do not rerun subject ingestion.
**Why:** Subject ranking data is not on the primary demo route. Its caveat is acknowledged.
Partial updates would appear in the data quality diagnostics without being understood.

---

### Aggregated University Count

**Status:** ~1,499 rows (QS global rankings).
**Action:** Do not run re-aggregation before a demo.
**Why:** A count change (e.g. 1,499 → 1,502) is unexplained during a demo and distracts.
The existing count is caveat-covered. Stability is more valuable than marginal freshness.

---

### Snapshots and Reports

**Status:** Maintained by `scripts/maintenance_overview.sh`.
**Action:** Do not regenerate snapshots immediately before the demo.
**Why:** Snapshots are referenced by maintenance reports. A new snapshot generated
immediately before a demo:
- Resets the comparison baseline for drift detection
- May show changes that require investigation
- Adds cognitive load without demo value

---

## Data That Is Safe to Refresh (After the Demo)

These operations are safe outside of a demo window:

- `python3 scripts/build_competition_demo_summary.py` — readonly, no data change
- `python3 scripts/build_demo_readiness_summary.py` — readonly, no data change
- `bash scripts/maintenance_overview.sh` — readonly (but avoid immediately before demo)
- `bash scripts/smoke_release.sh` — safe in testing, but modifies report files

---

## Why Stable Degraded Consistency Is Preferable to Unstable Freshness

A judge or reviewer evaluating a competition demo will see one of two things:

**Scenario A — Stable degraded posture:**
- THE and ARWU are Unavailable. The platform says so on the main page.
- QS data is ~354 hours old. The platform caveat-covers this on every surface.
- Confidence is "Mostly Low". The platform explains why with a formula.
- Every limitation is disclosed, consistent, and non-worsening.

**Scenario B — Unstable freshness:**
- QS data was partially re-ingested last night, but the count changed unexpectedly.
- The "hours ago" caveat now shows a different number than expected.
- One source briefly showed as available but then dropped back to zero.
- The confident posture label changed from "Mostly Low" to "Mixed" unexpectedly.

Scenario A is defensible in a Q&A session: "Yes, the data is stale. It's an RC-1
scope decision. The platform discloses it unconditionally."

Scenario B generates questions you cannot answer: "Why did the count change?",
"Is THE now partially available?", "Why is confidence different from yesterday?"

**The stable degraded posture is the correct demo posture.**

---

## Pre-Demo Operational Checklist (Data)

Perform 24 hours before the demo:

- [ ] Confirm `reports/demo_caveats.md` exists and its caveats match what you plan to say aloud
- [ ] Confirm Source Coverage shows: `QS ✓`, `THE —`, `ARWU —` (no unexpected changes)
- [ ] Confirm aggregated count is ~1,499 (within 10 rows)
- [ ] Confirm no `scripts/` or `maintenance/` runs are scheduled during the demo window
- [ ] Confirm database is not being migrated, reset, or updated during the demo window
- [ ] Confirm the report in `reports/competition_demo_summary.md` is current

---

## After the Demo

Post-demo operations are unrestricted. The freeze only applies to the window:
**24 hours before the demo through the end of the demo session.**

After the demo, resume normal maintenance cadence per [MAINTENANCE_CADENCE_REVIEW.md](MAINTENANCE_CADENCE_REVIEW.md).
