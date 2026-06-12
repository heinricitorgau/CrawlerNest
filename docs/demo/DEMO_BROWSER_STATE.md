# Demo Browser State

Defines the exact browser configuration for the CrawlerNest competition demo.
Consistent browser state prevents visual surprises during the demo.

---

## Browser Choice

Use a **dedicated browser profile** or a freshly opened private/incognito window.

**Recommended:** Chrome or Chromium (predictable rendering, consistent zoom).
**Acceptable:** Firefox with default theme.
**Avoid:** Safari (occasional layout differences), Edge with Copilot sidebar enabled.

---

## Tabs to Open (in order, left to right)

| Tab # | URL | Purpose |
|---|---|---|
| 1 | `http://localhost:3000/analytics` | Demo start — disagreement + posture |
| 2 | `http://localhost:3000/recommendations` | Evidence chain demo |
| 3 | `http://localhost:3000/system-status` | Optional: data freshness |

Open all three tabs **before the demo begins** so navigation is instant.
Do not open them during the demo — tab loading is visible to the audience.

---

## Tabs NOT to Open

- Developer tools (F12 console) — unless specifically needed for a technical audience
- Any localhost port other than 3000
- `http://localhost:8080` (raw API) — not a demo surface
- Any other application, dashboard, or browser-based tool
- Personal email, calendar, messaging apps
- Previous draft or unrelated browser sessions

---

## Browser Zoom

Set zoom to **100%** (Ctrl+0 / Cmd+0).

- Lower zoom (90%, 80%): text too small, evidence labels become hard to read
- Higher zoom (110%, 125%): content clips, horizontal scroll appears
- 100% is the intended layout baseline

Verify zoom on each tab after opening — some browsers remember per-site zoom.

---

## Dark / Light Mode

**Use light mode.**

Reason: the CrawlerNest UI is designed and tested in light mode. Severity chips,
confidence badges, and availability labels are calibrated for light background contrast.

- macOS: System Preferences → Appearance → Light
- Windows: Settings → Personalization → Colors → Light
- Browser override: ensure browser is not applying a forced dark mode extension

---

## Session State

Before the demo, the session state should be:

- [ ] No login errors visible — if auth is required, log in before the session starts
- [ ] `/analytics` loads without a redirect to `/login` or an error page
- [ ] `/recommendations` loads the form without a "session expired" banner
- [ ] No stale session warnings are visible in the UI

If session expires during the demo: see [DEMO_FAILURE_RECOVERY.md](DEMO_FAILURE_RECOVERY.md).

---

## Saved Recommendation Availability

For a stable demo, pre-generate a recommendation before the demo starts:

1. On `/recommendations`, enter the standard demo profile
2. Click "Generate Recommendations"
3. Confirm results load and explain panel opens correctly
4. Leave the page in the state you want to show

This ensures that if the backend is slow during the demo, you have a visible result
ready to navigate back to.

Alternatively, if `/saved-recommendations` shows prior results, that page can serve
as a stable fallback surface.

---

## Analytics Page Preload

Before the demo begins:

1. Navigate to `http://localhost:3000/analytics`
2. Scroll slowly through the entire page once — this preloads images and layout
3. Scroll back to the top
4. Leave the tab at the top of the page, ready to scroll down during the demo

This prevents the audience seeing a "loading…" spinner during the first scroll.

---

## Cache Refresh Guidance

- Do **not** hard-refresh (Ctrl+Shift+R) during the demo — it triggers full reload
- Do **not** clear browser cache immediately before the demo — re-fetches all assets
- If you suspect a stale page, do a **soft reload** (Ctrl+R / F5) before the demo begins, not during

---

## Avoid During Demo

| Action | Why to Avoid |
|---|---|
| Opening new tabs | Visible loading, layout shift |
| Closing tabs | Risk of closing the wrong tab |
| Switching windows | Visible taskbar, alt-tab flash |
| Typing in address bar | Visible autocomplete dropdowns |
| Hard refresh | Full page reload visible to audience |
| Opening DevTools | Shifts page layout, looks unpolished |
| Scrolling too fast | Severity chips and badges need 1–2 seconds of dwell |
| Hovering over unrelated elements | Tooltips and focus rings distract |
| Zooming in/out during the demo | Layout shift, audience disorientation |

---

## Bookmark Shortcuts (Optional)

For faster navigation during Q&A, add bookmarks:

- Bookmark 1: `Analytics` → `http://localhost:3000/analytics`
- Bookmark 2: `Recommendations` → `http://localhost:3000/recommendations`
- Bookmark 3: `System Status` → `http://localhost:3000/system-status`

Enable the bookmarks bar (Ctrl+Shift+B / Cmd+Shift+B) before the demo.
