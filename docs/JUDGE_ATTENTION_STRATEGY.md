# Judge Attention Strategy

This document analyzes what competition judges are likely to notice, what they may misunderstand,
and how to guide their attention toward the platform's strongest evidence.

---

## What Judges Are Likely to Notice First

### High-attention signals (first 60 seconds)

| Signal | Why Judges Notice It |
|---|---|
| Source disagreement severity chips | Visual, immediate, unexplained by most platforms |
| "THE — Unavailable" in operational posture | Visible self-disclosure of a limitation is unusual |
| Evidence Chain heading in explain panel | Implies traceable provenance, not AI generation |
| "Not AI-generated" note under confidence bar | Direct, rare claim that invites verification |
| Unconditional caveats on every result | Caveats that cannot be dismissed or hidden |

### Secondary-attention signals (later in demo)

| Signal | Why It Reinforces |
|---|---|
| Confidence posture "Mostly Low" | Confirms the platform doesn't inflate |
| Source coverage progress bars (QS 100%, THE 0%) | Visual proof of single-source limitation |
| "Derived from source coverage and data completeness" note | Connects the bar to a formula |
| `/system-status` link in operational posture | Implies depth beyond what's shown |
| Recommendation scoring formula reference | Verifiability claim without assertion |

---

## What Judges Are Likely to Misunderstand

| Misunderstanding | Likely Cause | How to Preempt |
|---|---|---|
| "The platform uses AI for recommendations" | 'Confidence score' sounds like ML | Say "deterministic scoring algorithm" early |
| "Low confidence means the system is broken" | Confidence = 25% looks bad | Frame: "low confidence is correct — single source" |
| "THE/ARWU unavailable is a failure" | Missing data looks like a bug | Say "expected limitation; we disclose it" |
| "The explanations are generated text" | Evidence Chain looks like chatbot output | Point: "these are stored algorithm outputs" |
| "The data is real-time" | Clean UI implies live data | State: "batch ingestion; data is ~354 hours old" |
| "This is a limited prototype" | localhost demo, single QS source | Frame: "the architecture is production-ready; RC-1 scope is intentional" |

---

## High-Impact Screens

These are the screens most likely to differentiate CrawlerNest from competing demos.
Show these; do not rush past them.

### Screen 1: Source Disagreement Table with Severity Chips

**URL:** `/analytics` — Source Disagreement section

**Why high-impact:**
Most ranking platforms suppress disagreement. Showing a "High" severity chip on a university
where sources spread 200+ positions is a direct claim that the platform values honesty over
false precision.

**What must be visible:**
- At least one row with a "High" severity chip
- The spread value (e.g., 200+) next to the chip
- A "Low" or "Medium" confidence badge on the same row

**What must NOT be visible (as primary focus):**
- Raw SQL queries or debug output
- Maintenance report links
- Loading spinners at demo time (ensure backend is running)

---

### Screen 2: Operational Posture Section

**URL:** `/analytics` — Operational Posture

**Why high-impact:**
Showing "THE — Unavailable" and "ARWU — Unavailable" on the main analytics page is unusual.
Most systems hide data gaps. Surfacing them here, in the main demo surface, signals that
operational honesty is a first-class feature, not a footnote.

**What must be visible:**
- Three source availability badges: `QS ✓ Available`, `THE — Unavailable`, `ARWU — Unavailable`
- Confidence posture label (e.g., "Mostly Low")
- The note: "THE and ARWU data are not available at RC-1"

**What must NOT be visible as primary focus:**
- Long lists of caveats above this section
- Technical timestamps or ingestion details

---

### Screen 3: Recommendation Explain Panel — Evidence Chain

**URL:** `/recommendations` — clicked open on a result card

**Why high-impact:**
The "Evidence Chain" heading, followed by checkmark reasons from stored data, directly
addresses the black-box objection against recommendation systems.

**What must be visible:**
- "Evidence Chain" section heading
- At least 2–3 checkmark (✓) reasons derived from stored scoring
- The confidence bar with the "Not AI-generated" note
- Source Coverage: QS ✓ Available, THE — Unavailable, ARWU — Unavailable
- Data Caveats list (QS stale, THE unavailable, ARWU unavailable)

**What must NOT be visible as primary focus:**
- The raw JSON evidence endpoint response
- IELTS arithmetic details unless a judge asks
- The saved-recommendations UI (secondary feature)

---

## Secondary Detail Screens

Show these if a judge asks or if time permits. Do not lead with them.

| Screen | URL | When to Show |
|---|---|---|
| Source coverage progress bars | `/analytics` source coverage | "If you want to see the raw numbers" |
| System status / freshness | `/system-status` | "Pipeline state and ingestion timestamps are here" |
| Saved recommendation evidence | `/saved-recommendations` | "Evidence is preserved in snapshots too" |
| Ranking trends table | `/analytics` ranking trends | "When two years of data are available, this shows movement" |
| Subject ranking signal | `/recommendations` — subject fit card | "Subject fit is QS-sourced; data is partial at RC-1" |

---

## Do Not Lead With These

| Topic | Why Not | When It's Appropriate |
|---|---|---|
| Maintenance scripts | Not a competition differentiator | Never during demo |
| Java compilation details | Too implementation-focused | Only if directly asked |
| Ingestion pipeline mechanics | Operational internal detail | Only at /system-status |
| Authentication model | Not demo-relevant | "Auth is present" at most |
| Year-over-year trend deltas | Not available at RC-1 | Acknowledge and move on |
| Subject ranking completeness | Highlights a gap without resolution | Only if asked |
| Release bundle structure | Internal artifact | Never during demo |

---

## Framing Guidance

### On low confidence scores
**Incorrect framing:** "Sorry, the confidence is low because we only have QS data."
**Correct framing:** "The confidence reflects what the data supports. Single-source coverage
means lower confidence. The system does not pretend otherwise."

### On unavailable sources
**Incorrect framing:** "We don't have THE or ARWU data yet — that's a limitation."
**Correct framing:** "THE and ARWU are not available at RC-1. The platform discloses this
on the main analytics page, in source coverage, and in every recommendation's evidence panel.
That disclosure is the feature."

### On deterministic scoring
**Incorrect framing:** "We're not using AI for this."
**Correct framing:** "The scoring algorithm is deterministic, version-tracked, and
reproducible. The formula is documented in `RECOMMENDATION_EVIDENCE_MODEL.md`. Any reviewer
can verify the output from the same inputs."

### On data freshness
**Incorrect framing:** "The data might be a bit old."
**Correct framing:** "The data was ingested at RC-1 packaging — approximately 354 hours ago.
That is disclosed as a caveat on every analytics and recommendation surface."
