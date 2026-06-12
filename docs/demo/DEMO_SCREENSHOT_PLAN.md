# Demo Screenshot Plan

This document defines which screens are most worth capturing for the competition submission,
slide deck, or documentation. For each screenshot: why it matters, what must be visible,
and what should not clutter the frame.

---

## Priority 1: Essential Screenshots

These are the images that carry the core competition argument. Capture these first.

---

### Screenshot A — Source Disagreement Severity

**Page:** `/analytics` — Source Disagreement table

**Why it matters:**
This screenshot shows the platform's core differentiator: disagreement is surfaced and
classified, not hidden. No other university ranking platform in the competition is likely to
show a "High Disagreement" badge with a rank spread visible beside it.

**What must be visible:**
- At least one row with a **High** severity chip (red badge)
- The spread value (e.g., 200+) in the Spread column
- A **Low** confidence badge on the same row
- The table header row (University, Aggregated, QS, THE, ARWU, Spread, Confidence)
- University name for context

**What must NOT be visible:**
- Browser DevTools or console
- Unrelated browser tabs
- Debug error messages
- Loading spinners
- The scrollbar if possible (crop to table area)

**Crop guidance:** Crop to the Source Disagreement section header + first 4–5 table rows.

---

### Screenshot B — Operational Posture Section

**Page:** `/analytics` — Operational Posture section

**Why it matters:**
Self-disclosure of source unavailability on the main analytics page is unusual. This screenshot
proves the platform states its limitations publicly and prominently — not buried in documentation.

**What must be visible:**
- Section heading: "Operational Posture"
- Three availability badges: `QS ✓ Available`, `THE — Unavailable`, `ARWU — Unavailable`
- The explanatory note about THE/ARWU at RC-1
- "Confidence Posture" stat card with its label

**What must NOT be visible:**
- Analytics Caveats section (below — keep focus on Operational Posture)
- System status page
- Any loading states

**Crop guidance:** Crop to the Operational Posture section header + availability badges + stat cards.

---

### Screenshot C — Recommendation Explain Panel: Evidence Chain

**Page:** `/recommendations` — explain panel open on a result card

**Why it matters:**
The "Evidence Chain" heading + checkmark reasons directly refute the black-box objection.
This is the strongest screenshot for "explainability" as a competition theme.

**What must be visible:**
- "Why this recommendation?" button (showing it's clickable / open)
- **"Evidence Chain"** section heading
- At least 2–3 `✓` reason lines
- The university name and fit score above the panel
- The Data Confidence bar with percentage

**What must NOT be visible:**
- The full page including all form fields (crop to the card + explain panel)
- Multiple result cards visible (focus on one)
- Empty warning sections (omit if no warnings)

**Crop guidance:** Crop to a single result card with the explain panel open. Remove form fields above.

---

### Screenshot D — Source Coverage in Explain Panel

**Page:** `/recommendations` — explain panel, Source Coverage section

**Why it matters:**
Showing `QS ✓ Available`, `THE — Unavailable`, `ARWU — Unavailable` in the recommendation
explain panel proves that source availability is integrated into the recommendation evidence,
not just an analytics-page footnote.

**What must be visible:**
- **Source Coverage** section heading
- Three source badges with clear available/unavailable state
- The confidence reason text beneath (if present)

**What must NOT be visible:**
- The full explain panel (crop to just the Source Coverage + caveats section)
- Form fields or other page content

**Crop guidance:** Crop to just the Source Coverage and Data Caveats sections of the explain panel.

---

## Priority 2: Supporting Screenshots

These reinforce the core argument. Capture if time permits.

---

### Screenshot E — Analytics Caveats Section

**Page:** `/analytics` — Analytics Caveats

**Why it matters:**
Shows that caveats are explicit, amber-highlighted, and unconditional — not a fine-print
afterthought.

**What must be visible:**
- Section heading: "Analytics Caveats" with "Read before interpreting" subtitle
- At least 2–3 amber caveat items (QS stale, THE unavailable, ARWU unavailable)

---

### Screenshot F — Confidence Visualization Bar

**Page:** `/recommendations` — explain panel, confidence bar

**Why it matters:**
The visual bar + "Not AI-generated" note is a direct, verifiable claim that many platforms
cannot make about their confidence scores.

**What must be visible:**
- The confidence bar with fill percentage
- The percentage label on the right
- The "Not AI-generated" note below

---

### Screenshot G — Source Coverage Progress Bars

**Page:** `/analytics` — Source Coverage section

**Why it matters:**
QS at 100%, THE at 0%, ARWU at 0% with clear "Available / Unavailable" badges makes the
data posture immediately scannable.

**What must be visible:**
- All three source coverage cards
- QS: `✓ Available`, THE: `— Unavailable`, ARWU: `— Unavailable`
- Progress bars showing the coverage percentages

---

## What to Avoid in All Screenshots

| Thing to Avoid | Why |
|---|---|
| Browser console or DevTools open | Looks like debugging |
| Error messages or 500 states | Looks like a broken system |
| Loading spinners | Implies slow backend |
| Multiple tabs visible | Clutters the frame |
| Long URL bar with localhost:3000 visible | Minor but distracts from UI |
| Scrollbars visible | Crop them out if possible |
| Unrelated UI above/below the target section | Use targeted crop |

---

## Screenshot Workflow

1. Ensure backend and frontend are running
2. Navigate to the target URL
3. Allow all data to load (no spinners)
4. Use browser zoom at 100% (or 90% for wider tables)
5. Crop to the target section using screenshot tool
6. Save as PNG; filename convention: `screenshot_<letter>_<short_description>.png`
7. Store under `docs/assets/` or include in submission materials
