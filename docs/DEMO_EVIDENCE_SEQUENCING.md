# Demo Evidence Sequencing

This document defines the order in which evidence should be revealed during the competition demo.
The goal is to build understanding progressively — starting from the problem, moving to data,
then to explainability, then to honesty — without overwhelming judges with technical context first.

---

## Core Principle

**Show the problem before the solution. Show the data before the interpretation.**

A judge who sees a "High Disagreement" chip before understanding what disagreement means will
miss the point. A judge who first understands that ranking sources disagree, then sees the chip,
will understand immediately.

---

## Evidence Revelation Sequence

### Level 0 — The Problem (Spoken, No Screen)

Before any screen is shown, establish why this matters.

1. "University rankings are a single number that hides all the uncertainty behind it."
2. "Sources like QS, THE, and ARWU often disagree by 100–200 positions."
3. "Students making multi-year decisions cannot interrogate the data they are relying on."

**Goal:** Prime the audience to look for disagreement signals when they appear.

**Timing:** 30–45 seconds. Spoken only.

---

### Level 1 — Raw Disagreement Evidence (Screen: /analytics disagreement table)

Show: The source disagreement table with raw spread values.

1. First: point to the spread column — raw numbers
2. Then: point to the severity chip — "High" classification
3. Then: point to the confidence badge — "Low" consequence

**Why this order:**
If you show the chip before the number, the chip looks like a decoration. If you show the
number first (200 positions), the chip becomes an interpretation of the number — which is
what it actually is.

**Evidence revealed:** Raw rank spread → severity classification → confidence consequence

---

### Level 2 — Source Availability Evidence (Screen: /analytics source coverage)

Show: Source coverage cards with availability badges.

1. First: show QS ✓ Available + 100% bar
2. Then: show THE — Unavailable + 0% bar
3. Then: ARWU — Unavailable + 0% bar

**Why this order:**
Show the available source first — it establishes what "covered" looks like. Then show
unavailable sources so the contrast is visible. If you show unavailable first, it looks like
a failure before the judge understands the reference state.

**Evidence revealed:** Available source baseline → unavailable sources → coverage gap

---

### Level 3 — Operational Posture Evidence (Screen: /analytics operational posture)

Show: Operational Posture section.

1. First: source availability chips (QS ✓, THE —, ARWU —)
2. Then: Confidence Posture label ("Mostly Low")
3. Do NOT expand into system-status at this point

**Why this order:**
The Operational Posture section summarizes what was just shown in Source Coverage. It is a
synthesis step — so it comes after the raw evidence, not before.

**Evidence revealed:** Source state → confidence posture → "the system knows"

---

### Level 4 — Recommendation Generation (Screen: /recommendations)

Show: Form → click Generate → see reach/target/safety results.

1. Enter profile quickly (20 seconds)
2. Click Generate
3. Wait for results — do not apologize for the 3-5 second delay
4. Point to the three buckets: reach / target / safety

**Why this order:**
The recommendation results are meaningless without first understanding that they are derived
from real data and explain themselves. But they must be generated before the explain panel
can be shown. So: generate first, explain second.

**Evidence revealed:** Input profile → output buckets → "now let's see how this was derived"

---

### Level 5 — Recommendation Evidence Chain (Screen: explain panel)

Show: "Why this recommendation?" → Evidence Chain

1. First: the Evidence Chain heading
2. Then: each ✓ reason (derived from stored scoring values)
3. Then: any ⚠ warning (data gap disclosure)
4. Then: dimensions grid (Ranking Fit, Risk Fit, Language Fit, Data Confidence scores)

**Why this order:**
The heading "Evidence Chain" sets expectation that what follows is a log of evidence steps.
The reasons are then read as evidence. If reasons appear first without the heading, they
read as chatbot output — not stored data.

**Evidence revealed:** Evidence provenance label → stored reasons → warnings → dimension scores

---

### Level 6 — Confidence Derivation (Screen: confidence bar)

Show: Confidence bar + "Not AI-generated" note

1. First: the bar fill (visual)
2. Then: the percentage (numeric)
3. Then: "Derived from source coverage and data completeness. Not AI-generated."

**Why this order:**
The visual bar creates attention. The percentage gives the precise value. The note explains
the source. If the note comes first, it sounds defensive. If it comes after the visual, it
sounds like documentation.

**Evidence revealed:** Visual signal → numeric value → derivation note

---

### Level 7 — Source Coverage in Evidence (Screen: explain panel, source coverage)

Show: Source Coverage chips in the explain panel

1. QS ✓ Available
2. THE — Unavailable
3. ARWU — Unavailable

**Why this order:**
Same as Level 2 — available first, then unavailable, so the contrast is visible.

**Context note:** This is the same information as Level 2, but now attached to a specific
recommendation. The judge sees: "The same source gap I saw in analytics is reflected here
in this specific recommendation's evidence."

---

### Level 8 — Unconditional Caveats (Screen: explain panel, data caveats)

Show: Data Caveats section

1. Point to caveat list (QS stale, THE unavailable, ARWU unavailable)
2. Say: "These are always present — not optional."

**Why last:**
Caveats that appear before evidence feel like excuses. Caveats that appear after evidence
feel like intellectual honesty. The judge has already seen the platform working; the caveats
confirm that the platform knows its own limits.

---

## Anti-Patterns to Avoid

| Anti-Pattern | Problem | Better Approach |
|---|---|---|
| Show caveats at the start | Looks like pre-emptive excuse-making | Show caveats after evidence |
| Show technical endpoints first | Loses non-technical audience | Show UI first; endpoints are "how it works" |
| Show confidence before showing sources | Confidence without context is a number | Show sources first, then confidence |
| Show operational posture without source coverage | Posture summarizes coverage; needs context | Coverage before posture |
| Read every ✓ reason aloud | Loses the structure in detail | Say "these are stored algorithm outputs" then point |
| Apologize for missing THE/ARWU | Frames it as a failure | Frame it as "we disclose it; that's the feature" |

---

## Pacing Note

The sequence above spans approximately 3–4 minutes. Each level should be visited briefly and
moved on from. A common failure mode is spending too much time at Level 1 (the table) and
running out of time before reaching the explain panel (Level 5), which is the most impactful
evidence.

**Target time per level:**

| Level | Target Duration |
|---|---|
| 0. Problem (spoken) | 45 seconds |
| 1. Disagreement table | 30 seconds |
| 2. Source coverage | 20 seconds |
| 3. Operational posture | 15 seconds |
| 4. Generate recommendations | 25 seconds |
| 5. Evidence chain | 30 seconds |
| 6. Confidence bar | 20 seconds |
| 7. Source coverage in evidence | 15 seconds |
| 8. Caveats | 15 seconds |
| **Total** | **~3:35** |
