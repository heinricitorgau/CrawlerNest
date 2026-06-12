# Screenshot Capture Workflow

Defines which screens to capture, what must be visible in each, and how to capture them cleanly.
Screenshots serve as fallback evidence if the live demo cannot run, and as competition submission assets.

---

## Capture Setup

Before taking screenshots:

1. Browser zoom: **100%** (Ctrl+0 / Cmd+0)
2. Browser window width: **1440px** minimum (full HD landscape preferred: 1920×1080)
3. Light mode enabled (see [DEMO_BROWSER_STATE.md](DEMO_BROWSER_STATE.md))
4. Both backend and frontend running
5. Standard demo profile pre-loaded on `/recommendations`
6. No DevTools open, no notification banners, no browser extensions visible

---

## Priority 1 — Essential Captures (Take These First)

### A. Source Disagreement Table (`/analytics`)

**Capture purpose:** Show that CrawlerNest quantifies and classifies rank spread — not a feature most ranking tools offer.

**Must be visible:**
- At least one row with a **High** severity chip (orange/amber background)
- The raw spread number in that row (e.g. "215")
- The **Low** confidence badge beside the high-spread row
- Section heading "Source Disagreement" visible at the top of the table

**Avoid:**
- Do not scroll so far that the heading is cut off
- Do not show rows with only "Low" severity — at least one High must be visible
- Do not include the browser address bar in the capture

**Crop guidance:** Top of section heading → bottom of table, no wider than the content card.

**Suggested browser size:** Full-width viewport, table naturally fits at 1440px.

---

### B. Operational Posture Section (`/analytics`)

**Capture purpose:** Demonstrate system self-disclosure — source availability and confidence posture on the main analytics page.

**Must be visible:**
- `QS ✓ Available` chip (green/emerald)
- `THE — Unavailable` chip (slate/gray)
- `ARWU — Unavailable` chip (slate/gray)
- **Confidence Posture** label (e.g. "Mostly Low")
- Section heading "Operational Posture" visible

**Avoid:**
- Do not crop before the section heading
- Do not show a state where THE or ARWU appear as Available (they are not at RC-1)

**Crop guidance:** "Operational Posture" heading → end of posture card, including availability chips and confidence label.

---

### C. Recommendation Evidence Chain (`/recommendations`)

**Capture purpose:** Show the Evidence Chain — stored algorithm outputs, not generated text. This is the core explainability differentiator.

**Must be visible:**
- "Evidence Chain" heading label above the ✓ reason list
- At least 2 ✓ reasons (e.g. "Rank within target range", "Language requirement met")
- **Data Confidence** bar (filled, with percentage)
- "Derived from source coverage and data completeness. Not AI-generated." text
- **Source Coverage** chips (QS ✓, THE —, ARWU —)

**Avoid:**
- Do not capture while the explain panel is loading (spinner visible)
- Do not capture if the confidence bar is at 0% with no fill
- Do not show any ⚠ warnings unless they are clearly readable (not cropped)

**Crop guidance:** From "Why this recommendation?" heading to end of Data Caveats section.

---

### D. Data Caveats (Unconditional) (`/recommendations` explain panel)

**Capture purpose:** Prove that caveats appear unconditionally — not suppressible, not hidden by a clean result.

**Must be visible:**
- "Data Caveats" section heading
- At least 3 caveat bullet points:
  - QS data ingested ~354 hours ago
  - THE data not available at RC-1
  - ARWU data not available at RC-1

**Avoid:**
- Do not crop so that the heading is cut off
- Do not show an empty Data Caveats section

**Crop guidance:** "Data Caveats" heading → last caveat bullet, tight crop.

---

## Priority 2 — Supporting Captures (Take These After Priority 1)

### E. Source Coverage Cards (`/analytics`)

**Capture purpose:** Reinforce the source availability story at a higher level than the posture section.

**Must be visible:**
- QS card with "Available" badge and 100% coverage bar
- THE card with "Unavailable" badge and 0% bar
- ARWU card with "Unavailable" badge and 0% bar

**Crop guidance:** "Source Coverage" section heading → end of the three coverage cards.

---

### F. Confidence Bar Close-Up (`/recommendations` explain panel)

**Capture purpose:** Isolate the confidence bar + "Not AI-generated" note for use in slide decks.

**Must be visible:**
- "Data Confidence" label
- Filled bar (colored portion)
- Percentage value (e.g. "65%")
- "Not AI-generated." note below the bar

**Crop guidance:** Tight crop — just the confidence bar component, no surrounding content.

---

### G. Analytics Overview (full page) (`/analytics`)

**Capture purpose:** Establish overall page structure — disagreement, coverage, posture, caveats in one view.

**Must be visible:**
- Section headings for: Source Disagreement, Source Coverage, Operational Posture, Analytics Caveats
- Page is scrolled to show at least two sections simultaneously

**Crop guidance:** Full viewport, no browser chrome.

---

## What to Avoid in All Screenshots

| Anti-Pattern | Problem |
|---|---|
| Browser address bar visible | Distracting, clutters the image |
| DevTools panel open | Makes the UI look half-broken |
| Loading spinners | Implies instability |
| Empty tables or sections | Removes the demonstration value |
| Windows taskbar or dock visible | Unprofessional, distracts from content |
| Notification popups | System noise, unpredictable |
| Mouse cursor in center of text | Covers content, looks accidental |
| Browser bookmarks bar visible | Clutters the top of the image |

---

## Screenshot Workflow

1. Set up browser per [DEMO_BROWSER_STATE.md](DEMO_BROWSER_STATE.md)
2. Navigate to each target page and scroll to the required section
3. Pause 2 seconds for any animations or loading indicators to settle
4. Use OS screenshot tool or browser full-page capture:
   - macOS: `Cmd+Shift+4` (region select) or `Cmd+Shift+5` (window/region options)
   - Windows: `Win+Shift+S` (region select) or Snipping Tool
   - Linux: `gnome-screenshot -a` (area select) or `scrot -s`
5. Save as PNG (lossless) to a named folder: `screenshots/demo-[date]/`
6. Name files descriptively: `A-source-disagreement.png`, `B-operational-posture.png`, etc.
7. Review each capture: check for required elements before moving on

---

## Fallback Use in Demo

If the live demo environment fails, these screenshots can be shown directly:

- Open screenshots in a full-screen image viewer or slideshow
- Navigate using arrow keys — smoother than browser tab switching
- Speak to each screenshot using the core sentence from [DEMO_ROUTE.md](DEMO_ROUTE.md)
- Refer to [DEMO_FAILURE_RECOVERY.md](DEMO_FAILURE_RECOVERY.md) for the full fallback procedure
