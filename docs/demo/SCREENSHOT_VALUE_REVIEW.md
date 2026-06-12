# Screenshot Value Review

Phase 4 — Demo Rehearsal. Evaluates which demo pages and states are worth capturing for slide decks, and which to avoid.

---

## Evaluation Criteria

| Criterion | Description |
|---|---|
| **Judge reads** | What does a judge see in the first 3 seconds? |
| **Value** | Why does this screenshot support the competition narrative? |
| **Avoid** | What state or framing makes this screenshot weaker? |

---

## /rankings

### Priority A — Top Rankings Table (Top 10 visible, country/score columns)

**Judge reads:** 1,499 real university rows, ranked with scores, filterable by country. Looks like a working data product.

**Value:** Establishes that the pipeline has run, the database is populated, and the UI is functional. Concrete volume (1,499 universities) is immediately credible.

**Best state:** Show top 10 rows, all columns visible, at least one country filter applied. Score column visible.

**Avoid:** Empty table state. Pagination controls cut off. Too many columns that obscure the rank and name.

---

### Priority A — University Explainability Panel (source contributions, confidence)

**Judge reads:** A specific university showing source breakdown, normalized scores, confidence level, and formula note.

**Value:** This is the core differentiator. A judge who sees this understands CrawlerNest is not just showing QS data — it is showing the reasoning behind the aggregate rank. This is the strongest single screenshot in the system.

**Best state:** A top-10 university with the explain panel open showing `source_contributions`, `formula_note`, and `confidence_label` all visible. Pick a university where the score derivation is readable.

**Avoid:** A university with all-null source fields. Screenshot where the JSON is raw and unformatted.

---

### Priority B — Search / Filter Active (e.g., filtering by "United States")

**Judge reads:** A working search/filter UI over real data.

**Value:** Shows interactive filtering, confirms the UI is live and not static.

**Avoid:** Showing a filter that returns 0 results. Showing a filter with an error state.

---

## /recommendations

### Priority A — Recommendation Cards with "Why?" Panel Open

**Judge reads:** A recommendation result with an expandable evidence panel showing Reasons, Warnings, Source Coverage, and Data Caveats.

**Value:** This is the explainability demo moment. A judge can immediately see that the confidence score has a derivation, that warnings are honest, and that caveats are unconditional. This screenshot directly counters the "black box AI" criticism.

**Best state:** At least one card fully expanded, showing all four sections: Reasons, Warnings, Source Coverage, Data Caveats. Confidence bar visible. At least one warning present (honest data posture is the differentiator, not a clean result).

**Avoid:** A result with 0 cards. A result where the "Why?" panel is collapsed. A screenshot where the confidence bar reads 100% (false precision).

---

### Priority A — Input Form + Results Together

**Judge reads:** I entered my IELTS score and target rank, and got ranked recommendations with fit scores.

**Value:** Shows the end-to-end user flow in a single screenshot. The input → output pipeline is immediately visible.

**Best state:** Input form with values entered AND results visible below. At least 3 recommendation cards visible.

**Avoid:** Form with empty inputs. A results list where all fit scores are identical.

---

### Priority B — Source Coverage Section (within the evidence panel)

**Judge reads:** "QS is available. THE: Unavailable. ARWU: Unavailable."

**Value:** Demonstrates honest data disclosure. The source gap is shown, not hidden. This directly addresses "how confident should I be in this recommendation?"

**Avoid:** Cropping this section out of the screenshot — it is a key honesty signal.

---

## /analytics

### Priority A — Source Disagreement Table (top disagreement universities visible)

**Judge reads:** Universities with large rank spreads between sources. Rank spread is a number. The meaning is immediate.

**Value:** This is the strongest analytics surface. Showing that rank disagreement is quantified and displayed directly demonstrates the "source disagreement as signal" differentiator.

**Best state:** Table visible with at least 5 rows, rank spread column clearly labeled, confidence bucket column visible.

**Avoid:** Screenshot where THE/ARWU columns are prominent and all show "N/A" — this emphasizes the data gap more than the feature.

---

### Priority B — Operational Posture / Source Availability Section

**Judge reads:** QS: available. THE: unavailable. ARWU: unavailable. Data age: visible.

**Value:** Shows self-aware operational honesty. A platform that surfaces its own gaps is a credibility differentiator. Best used in a slide that explains the competition positioning.

**Avoid:** Using this as the first or primary analytics screenshot. It communicates limitation before capability.

---

### Priority B — Ranking Trends Table (even with single-year caveat)

**Judge reads:** Year-over-year ranking movement data.

**Value:** Shows the analytics infrastructure is in place. The `singleYearOnly` honest disclosure is itself a story point.

**Avoid:** A screenshot where every trend delta is "N/A" or blank — without narration this looks like a broken feature.

---

### Optional — Confidence Distribution Chart

**Judge reads:** Most universities are "low confidence" at RC-1.

**Value:** Low. At RC-1 with single-source data this chart is not differentiating. Use only if the slide deck is specifically explaining confidence methodology.

**Avoid:** Using as a primary screenshot — it communicates data immaturity.

---

## /agent

### Priority B — Agent with Evidence-Referencing Response

**Judge reads:** A chat interface where the agent cites source caveats, suggests visiting /analytics, and discloses it cannot modify data.

**Value:** Shows the agent operates within clear boundaries and communicates operationally honest answers. A "Demo Ready Information" banner visible in the screenshot confirms the boundary is explicit.

**Best state:** A response to "What does source disagreement mean in CrawlerNest?" with the agent citing the caveat, the analytics page, and a disclaimer that it cannot modify the system.

**Avoid:** Mock provider response that is obviously generic. Any response that looks like it could have come from a vanilla ChatGPT session. The agent page with the provider set to "mock" and the response obviously placeholder text.

---

### Optional — Capability Boundary Card (Agent Cannot section)

**Judge reads:** "Agent cannot: modify code, run shell commands, write database, rerun pipeline."

**Value:** Demonstrates that the system is architecturally honest about its agent's constraints. Useful in a slide that addresses the "is this just a ChatGPT wrapper?" question.

**Avoid:** Using this as a primary agent screenshot — it emphasizes limitations before capabilities.

---

## /system-status

### Priority B — System Status Dashboard (FRESH/STALE badges visible)

**Judge reads:** A live operational dashboard with data freshness state, source availability, and diagnostics.

**Value:** Shows operational infrastructure exists behind the ranking UI. Credibility signal for technical judges.

**Best state:** All services green, freshness badges visible, aggregated count visible.

**Avoid:** A status page showing failures or errors unless you are demonstrating graceful degradation.

---

## Slide Deck Prioritization Summary

| Slot | Screenshot | Purpose |
|---|---|---|
| Slide 1 (problem) | Source disagreement table on /analytics | Show the gap: sources disagree, it matters |
| Slide 2 (solution) | Rankings table top 10 | Show the system is operational at scale |
| Slide 3 (explainability) | University explain panel | Core differentiator: derivation is visible |
| Slide 4 (recommendations) | Recommendation cards + evidence panel open | Show explainability extends to recommendations |
| Slide 5 (honesty) | Source coverage section in evidence panel | Show caveats are unconditional, not hidden |
| Slide 6 (bonus/agent) | Agent with caveat-aware response | Show advisory boundary is explicit |

---

See also:
- [SCREENSHOT_CHECKLIST_v0.1.md](SCREENSHOT_CHECKLIST_v0.1.md) — viewport and filename requirements
- [DEMO_SCRIPT_v0.1.md](DEMO_SCRIPT_v0.1.md) — demo flow steps
- [DEMO_NARRATIVE_AUDIT.md](../competition/DEMO_NARRATIVE_AUDIT.md) — narrative gaps to address in slides
