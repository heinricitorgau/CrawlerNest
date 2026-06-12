# Competition Storytelling

This document defines the storytelling framework for the CrawlerNest competition presentation.
It explains what to say, what to emphasize, what to avoid, and what caveats must be spoken aloud.

---

## The Story in Three Sentences

> University rankings are opaque black boxes — students see a number, not the evidence behind it.
> CrawlerNest makes every rank explainable: you can see which sources contributed, how much they
> agree, and why confidence is high or low. And when data is missing or stale, the platform says so.

---

## Story Arc

### Act 1 — The Problem

**The data problem:**

- University ranking bodies (QS, THE, ARWU) often disagree significantly for the same university
- A student ranked 50 by QS and 150 by THE is in an uncertain position — but that uncertainty is
  invisible in a single published number
- Recommendations built on single-source data have false precision: they look confident but lack
  the evidence to justify that confidence

**The explainability gap:**

- Existing systems give a recommendation without explaining why
- Confidence scores appear without derivation — the formula is opaque
- Caveats are suppressed to make results look cleaner

**Why this matters for real decisions:**

- Students making multi-year, high-cost decisions deserve to see the evidence
- Advisors need to know whether a recommendation is backed by three sources or one
- Honest uncertainty signals are more useful than false precision

---

### Act 2 — What CrawlerNest Does

**Multi-source aggregation with explainability:**

Navigate to the analytics page. Show the ranking trends table and the source disagreement section.
Say:

> "This table shows which universities have the largest disagreement between sources. A spread of
> 200 means QS ranks the university at 50 and THE ranks it at 250. That disagreement is real
> information — and it's displayed, not hidden."

**Source availability transparency:**

Point to the Source Coverage and Operational Posture sections. Say:

> "THE and ARWU data are not available at RC-1. We show this explicitly in the source availability
> panel. Every university in this dataset is QS-sourced only. The confidence score reflects that
> gap — it is not inflated to look better."

**Evidence-backed recommendations:**

Navigate to the recommendations page. Enter inputs. Click "Why this recommendation?" Say:

> "This panel shows the Evidence Chain: stored reasons derived from the scoring algorithm, not
> generated text. You can see the ranking fit, IELTS fit, country match, and data confidence.
> The confidence bar is derived from source coverage completeness, not asserted."

**Honest data posture:**

Point to the Data Caveats section in the explain panel. Say:

> "These caveats are always present. They are not optional. We do not suppress warnings to make
> results look cleaner."

---

### Act 3 — Why This Matters

**Operational credibility:**

> "This is not a system that looks impressive until you ask a hard question. Every number is
> traceable. Every limitation is labeled. The Operational Posture section tells you exactly what
> data we have and what we don't."

**Differentiation:**

> "Most academic data platforms claim AI-powered recommendations. This one claims the opposite:
> deterministic, version-tracked, reproducible scoring — with every evidence step visible."

**Closing:**

> "CrawlerNest is not the most confident university ranking platform. It is the most honest one."

---

## What to Emphasize

| Theme | What to Say |
|---|---|
| Source transparency | "Every rank shows which sources contributed and whether they agree." |
| Confidence derivation | "Confidence is derived from data coverage, not asserted. You can see the formula." |
| Honest limitations | "THE and ARWU are not available. We say so. The confidence score reflects that." |
| Evidence chain | "Every recommendation reason comes from stored data, not generated text." |
| Caveat visibility | "Caveats are always present. They are not optional disclosures." |
| Operational awareness | "The system knows what data it has and what it doesn't. It tells you." |

---

## What NOT to Exaggerate

| Claim | Why Not |
|---|---|
| "Our AI recommends..." | The recommendation engine is deterministic; no AI/ML model is used |
| "Real-time data" | Batch ingestion only; data is not streamed |
| "Multi-source agreement" | At RC-1, only QS is available — all universities are single-source |
| "Comprehensive rankings" | THE and ARWU are missing at RC-1 |
| "Predictive analytics" | No historical depth for trend prediction at RC-1 |
| "AI-powered confidence" | Confidence is formula-derived, not learned |

---

## Caveats to State Aloud

These must be spoken during any demo. Do not skip them.

1. "The data was ingested at RC-1 packaging and has not been refreshed. Data age is
   approximately 354 hours."

2. "THE and ARWU data are not available. All rankings in this demo reflect QS source only.
   Source agreement analysis will improve when these sources are added."

3. "Subject ranking coverage is incomplete. Subject analytics are not shown in this release."

4. "This is a localhost demonstration. The architecture is production-ready but the deployment
   is not production-scale."

---

## What the Evidence Chain Visualization Communicates

When a reviewer sees the "Evidence Chain" label on the explain panel, the story is:

1. **The reasons are derived, not generated.** They come from the scoring algorithm's stored
   intermediate values, not from an LLM.

2. **The warnings are honest.** They surface data gaps — missing IELTS requirements, single
   source coverage — rather than hiding them.

3. **The confidence bar is derivable.** A reviewer can reproduce the 65% + 35% formula from
   `docs/RECOMMENDATION_EVIDENCE_MODEL.md` and arrive at the same number.

4. **The caveats are unconditional.** They appear regardless of how clean the result looks.

---

## What the Operational Posture Section Communicates

When a reviewer sees the Operational Posture section on the analytics page, the story is:

1. **The system knows its own limitations.** Source availability is not buried in docs — it
   is shown on the main analytics page.

2. **THE and ARWU being Unavailable is not a failure.** It is a documented, expected state
   that the platform reports accurately.

3. **The confidence posture reflects reality.** "Mostly Low" at RC-1 is correct — all data
   is single-source. The system does not inflate this.

4. **The system directs you to more operational detail.** The pointer to `/system-status`
   shows that operational transparency goes deeper than one page.

---

## Boundary

This document defines storytelling framing. It does not constrain what the audience can ask.
If asked a question the platform cannot honestly answer, say so. Improvising claims beyond
what the data supports violates the operational honesty principle this platform is built on.

See also:
- [COMPETITION_DEMO_NARRATIVE.md](COMPETITION_DEMO_NARRATIVE.md) — step-by-step demo flow
- [ANALYTICS_VISUALIZATION_PLAN.md](../analytics/ANALYTICS_VISUALIZATION_PLAN.md) — visualization decisions
- [RECOMMENDATION_EVIDENCE_MODEL.md](../analytics/RECOMMENDATION_EVIDENCE_MODEL.md) — evidence API contract
- [DEMO_HONESTY_GUIDELINES.md](../demo/DEMO_HONESTY_GUIDELINES.md) — required phrasing guidance
