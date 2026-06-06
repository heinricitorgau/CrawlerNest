# Demo Failure Recovery Guide

Step-by-step recovery for common failures during a CrawlerNest competition demo.
Each section: what you see, what to say to the audience, what to do.

**Core principle:** Stay calm. The audience follows the presenter's energy.
A confident recovery is a demonstration of operational maturity — not a weakness.

---

## Failure 1 — Backend Down (No API Response)

**Symptom:** The recommendations page shows a connection error, spinner never resolves,
or the analytics table shows "Error loading data."

**What to say:**
> "The backend is initializing — let me give it a moment while I describe what we're seeing."

**What to do:**

1. Switch to Terminal A (backend terminal) without showing it to the audience
2. Check if the Spring Boot process exited — restart if necessary:
   ```bash
   cd crawlernest/servise_for_java
   ./mvnw -Dmaven.test.skip=true spring-boot:run
   ```
3. Wait ~20 seconds for startup
4. Soft-reload the page (Ctrl+R / F5 — not hard refresh)
5. If backend restarts successfully: continue the demo from where you stopped
6. If backend cannot restart within 60 seconds: switch to fallback screenshots

**Fallback:** Open Priority 1 screenshots from [SCREENSHOT_CAPTURE_WORKFLOW.md](SCREENSHOT_CAPTURE_WORKFLOW.md).
Navigate with arrow keys. Speak to each screenshot using the core sentence from [DEMO_ROUTE.md](DEMO_ROUTE.md).

---

## Failure 2 — Frontend Refresh Issue (Page Won't Load)

**Symptom:** Blank page, "localhost refused to connect", or a Next.js build error.

**What to say:**
> "I'll refresh this — the application is fully local, no network dependency."

**What to do:**

1. Check Terminal B (frontend terminal) — is `npm run dev` still running?
2. If the dev server crashed, restart:
   ```bash
   cd crawlernest/crawlernest-web
   npm run dev
   ```
3. Wait for "Ready on http://localhost:3000"
4. Reload the tab
5. If frontend recovers: continue demo normally
6. If frontend cannot restart: use fallback screenshots

**Fallback:** Open screenshot C (Evidence Chain) and screenshot B (Operational Posture).
These two alone cover the core demo argument.

---

## Failure 3 — Stale Session / Session Expired

**Symptom:** The recommendations page redirects to `/login`, or shows a "session expired" banner.

**What to say:**
> "The session timed out — this is a standard auth behaviour on localhost. Let me log back in."

**What to do:**

1. Navigate to the login page if redirected — log in with demo credentials
2. Return to `/recommendations` after login
3. Regenerate recommendations if the page is blank
4. Continue from the recommendations step of the demo

**Prevention:** See [DEMO_PRODUCTION_RUNBOOK.md](DEMO_PRODUCTION_RUNBOOK.md) Step 5 — verify session before the demo starts.

---

## Failure 4 — Analytics Page Unavailable / Empty Table

**Symptom:** The Source Disagreement table is empty, shows a "No data" message, or the
analytics page returns an API error.

**What to say:**
> "Let me show you this surface from a screenshot — the live data is the same system."

**What to do:**

1. Check that the backend is responding:
   ```bash
   curl -s "http://localhost:8080/api/v1/diagnostics/source-agreement" | head -5
   ```
2. If the API responds but the UI is empty, try a soft reload (Ctrl+R)
3. If the API is not responding, restart the backend (see Failure 1)
4. If recovery takes more than 30 seconds: use screenshot A (Source Disagreement)

**Key message to preserve:** "Sources disagree — we classify the spread as High, Medium, or Low.
The severity chip is derived from the raw spread number — not from AI."

This message can be delivered while pointing to a screenshot.

---

## Failure 5 — Missing Source (QS shows 0 records)

**Symptom:** The analytics page shows QS as Unavailable or the recommendation engine returns
no results for any profile.

**What to say:**
> "The source count is showing zero — this is a data state we'd investigate post-demo.
> Let me show you the expected posture from a prepared screenshot."

**What to do:**

1. Do not attempt to rerun ingestion pipelines during the demo — this takes 10–30 minutes
2. Switch to fallback screenshots immediately
3. Note the failure for post-demo investigation (check database connection, snapshot)

**This failure is rare in a stable environment.** It requires a database issue or a corrupted
snapshot. Prevention: confirm source count before the demo per [DEMO_PRODUCTION_RUNBOOK.md](DEMO_PRODUCTION_RUNBOOK.md) Step 4.

---

## Failure 6 — Browser Lag / Slow Rendering

**Symptom:** Pages load slowly, scrolling is choppy, or UI elements take more than 3 seconds
to appear.

**What to say:**
> "The system is loading — the full data set is local, no cloud latency."

**What to do:**

1. Close unneeded browser tabs if any were opened
2. Wait — do not click repeatedly or reload
3. If lag persists, soft reload the tab (Ctrl+R)
4. If the system is broadly unresponsive, check if another process is consuming CPU/memory
5. As a last resort, use the pre-loaded tab (if it was cached before the demo)

**Prevention:** Run a full dry-run of the demo 30 minutes before to warm up the browser cache.

---

## Failure 7 — Recommendations Not Generating

**Symptom:** Click "Generate Recommendations" and the spinner never resolves, or the results
section stays blank.

**What to say:**
> "The recommendation engine is processing. While it loads, let me describe the evidence
> structure we'll see in the explain panel."

**What to do:**

1. Wait up to 10 seconds — the first generation after startup can be slow
2. Check that the backend is running (Terminal A should show recent request logs)
3. If no request appears in the backend log, the frontend is not reaching the backend —
   check CORS or port configuration (unusual in a stable environment)
4. If results appear but slowly: proceed normally once they load
5. If results do not appear after 15 seconds: use screenshot C (Evidence Chain)

**Describe while waiting:** "The Evidence Chain will show stored algorithm outputs — not
generated text. The confidence score is derived from source coverage completeness. Not AI."

---

## Failure 8 — Local Environment Mismatch

**Symptom:** Frontend and backend started but features appear differently than expected.
For example: the Operational Posture section is missing, the confidence bar is not visible,
or the Evidence Chain heading is absent.

**What to do:**

1. Confirm the correct branch is checked out: `git status`
2. Confirm the frontend is the latest build — restart `npm run dev`
3. Confirm the backend compiled cleanly — look for warnings in the backend terminal
4. If the environment cannot be brought to a consistent state before the demo:
   - Use fallback screenshots taken from the known-good environment
   - State: "The recording was captured from the stable environment — this is the same codebase."

---

## General Recovery Principles

| Principle | Application |
|---|---|
| Narrate while recovering | Fill silence with context — "While this loads, I'll describe..." |
| No apologies | "We're seeing a recovery moment" not "Sorry, this is broken" |
| Switch to screenshots early | If recovery takes >30 seconds, switch — do not burn demo time |
| Stay on the argument | The demo argument (evidence, transparency, honesty) holds even with screenshots |
| Caveats still apply | Even in fallback mode, state the required verbal caveats |

---

## Fallback Priority Order

If the live demo cannot continue:

1. **Priority 1 screenshots** — cover disagreement, posture, evidence, caveats
2. **Narrate the evidence from memory** — the core argument is: "sources disagree, we show it; evidence is stored data, not generated; caveats are unconditional"
3. **Use the competition demo summary** — `reports/competition_demo_summary.md` has the elevator pitch, differentiators, and required caveats in printable form

A demo that uses fallback screenshots and delivers the core argument clearly is a
complete and credible demonstration.
