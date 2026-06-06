# Demo Honesty Strategy

This document defines when to disclose data limitations, how to frame them, and how to avoid
both dishonest omission and excessive alarm inflation during the competition demo.

---

## The Core Tension

A competition demo faces two failure modes:

1. **Overselling**: hiding limitations to look stronger → detected by judges who ask hard questions
2. **Underselling**: leading with every caveat → loses the audience before the evidence is shown

The honest posture is neither. It is: **show the evidence, then the limits of that evidence.**

---

## Caveats That Must Be Stated Aloud (Once)

These must be spoken during the demo. Not read from a screen — spoken.

| Caveat | When to State It | Suggested Phrasing |
|---|---|---|
| QS data age | When first showing analytics | "The data was ingested at RC-1 packaging — approximately 354 hours ago." |
| THE/ARWU unavailability | When showing source coverage or operational posture | "THE and ARWU data are not available at RC-1. All rankings here are QS-sourced." |
| Single-source confidence | When showing confidence bar | "With only one source, confidence is intentionally lower. The system doesn't inflate it." |
| Localhost demo | During opening or when asked about deployment | "This is a localhost demo. The architecture is production-ready; RC-1 scope is intentional." |

---

## Caveats That Are Already Shown — Do Not Over-Repeat

These are visible on-screen in the UI. Pointing to them once is sufficient. Do not re-read
them multiple times.

| Caveat | Where It Appears | How to Handle |
|---|---|---|
| QS stale data | Data Caveats list in explain panel; analytics caveats section | Point to it once: "caveats are always present here" |
| THE unavailable | Source coverage badges; operational posture | Show visually; say it once |
| ARWU unavailable | Source coverage badges; operational posture | Show visually; say it once |
| Single-source label | Confidence reason text | Let the label do the work |
| "Not AI-generated" | Confidence bar note | Read it aloud once; don't repeat |

---

## Caveats Not to Volunteer (Unless Asked)

These are real limitations but will distract from the demo's core argument if mentioned proactively.

| Caveat | Why Not to Volunteer |
|---|---|
| Subject ranking incompleteness | Not on the core demo route; mention if subject tab is shown |
| Authentication model limitations | Not a competition differentiator; mention only if auth is questioned |
| Year-over-year trend unavailability | Visible in UI; no need to pre-explain |
| Database schema details | Too internal; not relevant to the competition argument |
| Maintenance script complexity | Not relevant to judges |

---

## Framing: Honest Without Alarming

### "The data is stale"

**Alarm framing (avoid):**
"Our data is over 350 hours old and might be inaccurate."

**Honest framing:**
"The ranking data was ingested at RC-1 packaging — approximately 350 hours ago. That's
disclosed as a caveat on every analytics and recommendation surface. When new data is ingested,
the caveats update automatically."

---

### "THE and ARWU are unavailable"

**Alarm framing (avoid):**
"We're missing two of the three major ranking sources, so our analysis is limited."

**Honest framing:**
"THE and ARWU data are not available at RC-1. The platform discloses this on the main
analytics page, in every source coverage section, and in every recommendation's evidence panel.
The confidence score reflects that gap — it is not inflated. When these sources are added,
confidence will improve and the framework is already designed to accept them."

---

### "Confidence is low"

**Alarm framing (avoid):**
"Sorry, confidence is low because we only have one data source."

**Honest framing:**
"With one source, confidence is at the lower end of the range. That's the correct answer from
the formula — not a bug. A system that gives high confidence on single-source data would be
the one to question."

---

### "This is a localhost demo"

**Alarm framing (avoid):**
"We haven't deployed this yet."

**Honest framing:**
"This is a localhost demonstration. The operational stack is complete — backend, database,
frontend, analytics pipeline. RC-1 scope is intentionally bounded; the architecture is
production-ready."

---

## Calibration Table

| Signal | Severity for Demo | Action |
|---|---|---|
| THE/ARWU unavailable | Expected, non-alarming | Disclose once; frame as intentional RC-1 scope |
| QS data ~354 hours stale | Expected, non-alarming | Disclose once; point to caveat in UI |
| Single year of aggregated data | Expected, non-alarming | Acknowledge if trends are asked about |
| Confidence "Mostly Low" | Expected, non-alarming | Explain formula; frame as honest |
| Subject data incomplete | Minor, non-alarming | Mention only if subject ranking is shown |
| Localhost deployment | Context, non-alarming | State once during opening or if asked |

---

## Anti-Patterns

| Anti-Pattern | Why It Fails |
|---|---|
| Opening with a list of caveats | Loses audience before evidence is shown |
| Apologizing for limitations | Implies they are failures, not known scoped decisions |
| Over-repeating "we don't have THE/ARWU" | Sounds like dwelling on a weakness |
| Saying "this is just a prototype" | Undersells a complete operational MVP |
| Hiding confidence scores | Removes the evidence-backed claim entirely |
| Claiming the confidence score is "good" | Invites question about inflation |
| Saying "AI-powered" for any component | False and verifiably so |

---

## Honesty Without Alarm: The Mental Model

Think of the demo as a credible analyst briefing, not a sales pitch and not a confession.

A credible analyst:
- States what is known and what is estimated
- Identifies where data is incomplete
- Does not inflate confidence to appear stronger
- Does not over-qualify to appear humble
- Answers hard questions directly when they arise

CrawlerNest's platform is designed to behave the same way. The demo should mirror that.
