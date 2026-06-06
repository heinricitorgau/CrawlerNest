# Demo Flow Architecture

Competition demo flow for a 3–5 minute presentation window.
Each section specifies timing, screen, core message, and what to avoid.

## Design Principles

- **Evidence-first**: show data before claiming capability
- **Explainability-first**: show how a result is derived before calling it correct
- **Calm pacing**: do not rush through screens to show feature count
- **One honest limitation per minute**: include at least one explicit limitation disclosure
- **No black-box claims**: every confidence score, rank, and caveat is sourceable

---

## Demo Flow (4-minute target)

### Section 1 — Opening Problem (0:00–0:45)

**Screen:** None — spoken intro.

**Core message:**
> "University rankings are opaque. A student sees a number — not which sources agreed, how
> much they disagreed, or how confident the data actually is."

**What to say:**
- QS, THE, and ARWU frequently disagree for the same university by 100+ positions
- A single published rank hides that disagreement completely
- Students and advisors make high-stakes, multi-year decisions on data they cannot interrogate

**What NOT to do:**
- Do not open with stack details (Java, Spring Boot, PostgreSQL)
- Do not lead with "1,499 universities in our dataset"
- Do not mention maintenance, ingestion pipelines, or operational scripts

---

### Section 2 — Analytics Surface (0:45–1:30)

**Screen:** `/analytics` — Source Disagreement table, then Operational Posture.

**Core message:**
> "We surface disagreement. When sources conflict, we show the spread — and we classify it."

**What to show:**
1. Source Disagreement table → point to a row with a **High** severity chip (spread ≥ 200)
2. The confidence badge on the same row — Low, because spread is high
3. Operational Posture section → `QS ✓ Available`, `THE — Unavailable`, `ARWU — Unavailable`

**What to say:**
- "This spread means two sources disagree by 200 positions. That's real uncertainty."
- "The severity classification — High — is derived from the spread value. Not from AI."
- "THE and ARWU are not available at RC-1. The platform says so on the main analytics page."

**Timing:** ~45 seconds on this section.

**What NOT to do:**
- Do not stay on the ranking trends table — that requires historical data context
- Do not read every row of the disagreement table

---

### Section 3 — Recommendation Evidence (1:30–2:45)

**Screen:** `/recommendations` — enter profile, generate results, click "Why this recommendation?".

**Core message:**
> "Every recommendation is explainable. The Evidence Chain shows stored data — not generated text."

**What to show:**
1. Enter: Country = United Kingdom, IELTS = 6.5, Target Rank = 100, Risk = balanced
2. Click "Generate Recommendations"
3. Click "Why this recommendation?" on the first result card
4. Show: **Evidence Chain** heading + checkmark reasons (from stored scoring algorithm)
5. Show: **Data Confidence bar** — "Derived from source coverage. Not AI-generated."
6. Show: **Source Coverage** — QS ✓ Available, THE — Unavailable, ARWU — Unavailable
7. Show: **Data Caveats** — present unconditionally

**What to say:**
- "These reasons are the scoring algorithm's stored intermediate values — not generated text."
- "The confidence bar is derived from completeness (65%) plus source agreement (35%)."
- "The caveats are unconditional. They appear on every result, not only when results look uncertain."

**Timing:** ~75 seconds on this section.

**What NOT to do:**
- Do not read out the IELTS margin arithmetic in detail — show it, say "it's from stored data"
- Do not over-explain the scoring formula — "the formula is documented" is enough

---

### Section 4 — Confidence Derivation (2:45–3:15)

**Screen:** Stay on the recommendation explain panel. Point to the confidence bar.

**Core message:**
> "Confidence is derived — you can reproduce it from the documented formula."

**What to say:**
- "This is not a black-box confidence score. The formula is: completeness (65%) + source agreement (35%)."
- "At RC-1 with only QS data, confidence is intentionally lower. We do not inflate it."
- "The formula is version-tracked in `docs/RECOMMENDATION_EVIDENCE_MODEL.md`."

**Timing:** ~30 seconds. Stay brief.

**What NOT to do:**
- Do not read out the formula components in full — point to the docs
- Do not apologize for low confidence — "the system is honest about what it knows"

---

### Section 5 — Operational Credibility (3:15–3:45)

**Screen:** `/analytics` Operational Posture section OR `/system-status`.

**Core message:**
> "The system knows its own limitations and states them on the main analytics page."

**What to say:**
- "THE and ARWU are not available. The platform says so here — not buried in documentation."
- "Data freshness details are at `/system-status` — ingestion timestamps, pipeline state."
- "Confidence posture is derived from the distribution of confidence buckets. Not asserted."

**Timing:** ~30 seconds. Show, don't narrate in detail.

---

### Section 6 — Closing (3:45–4:00)

**Screen:** Return to `/analytics` overview or close browser.

**Core message:**
> "CrawlerNest is not the most confident ranking platform. It is the most honest one."

**What to say:**
- "Every rank is explainable. Every limitation is labeled. Every caveat is stated."
- "The formula is deterministic, version-tracked, and reproducible from the source data."

**Timing:** 15 seconds. Short.

---

## Time Budget

| Section | Duration | Key Screen |
|---|---|---|
| 1. Opening Problem | 0:45 | Spoken only |
| 2. Analytics Surface | 0:45 | `/analytics` — disagreement table, operational posture |
| 3. Recommendation Evidence | 1:15 | `/recommendations` — explain panel |
| 4. Confidence Derivation | 0:30 | Stay on explain panel |
| 5. Operational Credibility | 0:30 | `/analytics` operational posture or `/system-status` |
| 6. Closing | 0:15 | Return to overview |
| **Total** | **4:00** | |

---

## 90-Second Condensed Flow

For lightning round format:

1. Open `/analytics` → point to source disagreement severity chip (15s)
2. Operational Posture → QS available, THE/ARWU unavailable (15s)
3. Open `/recommendations` → profile → "Why this recommendation?" (30s)
4. Evidence Chain + confidence bar + caveats (20s)
5. Closing statement: "most honest, not most confident" (10s)

---

## Absolute Minimums (30 seconds)

If given a 30-second window only:

1. Show the `/analytics` Operational Posture section (15s):
   "We show which sources are available and which aren't — right on the main page."
2. Say the closing: (15s):
   "Every recommendation has an Evidence Chain. Every confidence score is derivable.
   That is what CrawlerNest does differently."

---

## What NOT to Over-Explain

| Topic | Why | Instead |
|---|---|---|
| Java/Spring Boot internals | Judges care about output | "Backend is Java; API is documented" |
| Database schema | Too technical for opening | Show UI output first |
| Ingestion pipeline mechanics | Internal operational detail | "Batch ingestion; freshness at /system-status" |
| Maintenance scripts | Not competition-relevant | Skip entirely |
| Authentication model | Not a differentiator | "Auth is present; not the focus today" |
| Year-over-year trends | Single year only at RC-1 | Acknowledge and move to disagreement section |
