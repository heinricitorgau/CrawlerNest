# Demo Route

Step-by-step click sequence for the CrawlerNest competition demo.
Each stop includes its purpose, estimated dwell time, and the single most important sentence.

---

## Pre-Demo Checklist

Before starting:
- [ ] Backend running: `cd crawlernest/servise_for_java && ./mvnw spring-boot:run`
- [ ] Frontend running: `cd crawlernest/crawlernest-web && npm run dev`
- [ ] Open browser to `http://localhost:3000/analytics`
- [ ] Confirm analytics page loads (disagreement table visible)
- [ ] Confirm `/recommendations` loads (backend is reachable)
- [ ] Close unrelated browser tabs

---

## Stop 1 — Analytics: Source Disagreement (0:45–1:30)

**URL:** `http://localhost:3000/analytics`

**Purpose:** Establish the core problem — sources disagree, and we show it visibly.

**Actions:**
1. Scroll to the **Source Disagreement** section
2. Point to the first row with a **High** severity chip
3. Note: the spread number and the **Low** confidence badge beside it

**Core sentence:**
> "When ranking sources disagree by 200 positions, we classify that as High severity — and the
> confidence drops to Low. That disagreement is real information."

**Estimated dwell:** 30 seconds

**Do not:** Scroll through all 10 rows. Point to one clear example and move on.

---

## Stop 2 — Analytics: Source Coverage + Availability (1:30–1:50)

**URL:** `http://localhost:3000/analytics` (scroll down to Source Coverage)

**Purpose:** Show that source availability is surfaced prominently, not hidden.

**Actions:**
1. Scroll to **Source Coverage** section
2. Point to: `QS ✓ Available`, `THE — Unavailable`, `ARWU — Unavailable`
3. Note the progress bars (QS 100%, THE 0%, ARWU 0%)

**Core sentence:**
> "THE and ARWU are not in this dataset. We show that — not hide it."

**Estimated dwell:** 20 seconds

**Do not:** Spend time on the percentage numbers. The availability badge is the message.

---

## Stop 3 — Analytics: Operational Posture (1:50–2:05)

**URL:** `http://localhost:3000/analytics` (scroll down to Operational Posture)

**Purpose:** Show the system's self-awareness about its data state.

**Actions:**
1. Scroll to **Operational Posture**
2. Show source availability chips: `QS ✓ Available`, `THE — Unavailable`, `ARWU — Unavailable`
3. Point to Confidence Posture label

**Core sentence:**
> "The platform assesses its own data posture and shows it here. No hidden confidence inflation."

**Estimated dwell:** 15 seconds

**Do not:** Spend time explaining "Mostly Low" — it's self-explanatory with single-source data.

---

## Stop 4 — Recommendations: Generate Results (2:05–2:30)

**URL:** `http://localhost:3000/recommendations`

**Purpose:** Transition from analytics to the user-facing recommendation surface.

**Actions:**
1. Enter: Country = `United Kingdom`
2. IELTS Score = `6.5`
3. Target Rank = `100`
4. Risk Profile = `balanced`
5. Click **Generate Recommendations**
6. Wait for results to load (3–5 seconds)

**Core sentence:**
> "A student enters their profile. We generate reach, target, and safety recommendations — with
> explainability on every result."

**Estimated dwell:** 25 seconds (mostly waiting for load)

**Do not:** Explain all the form fields. Enter values quickly and click.

---

## Stop 5 — Recommendations: Evidence Chain (2:30–3:15)

**URL:** `http://localhost:3000/recommendations` (clicked open on first result)

**Purpose:** Show the Evidence Chain — the core Phase 2 capability.

**Actions:**
1. Click **"Why this recommendation?"** on the first result card
2. Panel opens — point to:
   - **"Evidence Chain"** heading
   - At least 2–3 `✓` reason lines
   - Any `⚠` warning lines (if present)
3. Point to the **Data Confidence bar** and the "Not AI-generated" note
4. Point to **Source Coverage**: `QS ✓ Available`, `THE — Unavailable`, `ARWU — Unavailable`
5. Point to **Data Caveats** list (QS stale, THE unavailable, ARWU unavailable)

**Core sentence:**
> "These reasons are stored algorithm outputs — not generated text. The confidence bar is a
> formula, not an assertion. The caveats are present on every result."

**Estimated dwell:** 45 seconds

**Do not:** Read every reason aloud. Show the structure; say "from stored data."

---

## Stop 6 — Closing Statement (3:15–3:30)

**URL:** Stay on `/recommendations` or return to `/analytics`

**Purpose:** Land the core differentiator.

**Core sentence:**
> "CrawlerNest is not the most confident university ranking platform. It is the most honest one.
> Every rank is explainable. Every limitation is labeled. Every confidence score is derivable."

**Estimated dwell:** 15 seconds

---

## Optional Stop A — System Status (if asked about freshness)

**URL:** `http://localhost:3000/system-status`

**Purpose:** Show operational depth — ingestion timestamps, pipeline state.

**Core sentence:**
> "Source ingestion timestamps and aggregation run history are visible here. Not hidden."

**Estimated dwell:** 20 seconds maximum

---

## Optional Stop B — Saved Recommendations (if asked about persistence)

**URL:** `http://localhost:3000/saved-recommendations`

**Purpose:** Show that evidence is preserved in snapshots.

**Core sentence:**
> "Saved plans preserve the evidence snapshot — so the explanation doesn't change after the fact."

**Estimated dwell:** 20 seconds maximum

---

## Route Summary

| Stop | URL | Duration | Core Message |
|---|---|---|---|
| 1 | /analytics — disagreement | 0:30 | "Sources disagree; we show it" |
| 2 | /analytics — source coverage | 0:20 | "THE/ARWU unavailable; shown, not hidden" |
| 3 | /analytics — operational posture | 0:15 | "System knows its own limits" |
| 4 | /recommendations — generate | 0:25 | "Profile → results with explainability" |
| 5 | /recommendations — explain panel | 0:45 | "Evidence Chain; not black box" |
| 6 | Closing | 0:15 | "Most honest, not most confident" |
| **Total** | | **2:30–3:30** | |

Note: The route is designed for 2:30–3:30 core flow. With intro and pauses, expect 3:30–4:30 total.
