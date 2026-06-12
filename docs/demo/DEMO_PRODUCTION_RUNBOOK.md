# Demo Production Runbook

Step-by-step environment preparation for the CrawlerNest competition demo.
Follow this in order. Total estimated preparation time: **15–20 minutes**.

---

## Estimated Preparation Timeline

| Stage | Task | Duration |
|---|---|---|
| T-20 min | Environment startup | 5 min |
| T-15 min | Backend and frontend health check | 3 min |
| T-12 min | Browser preparation | 3 min |
| T-9 min | Session and data verification | 3 min |
| T-6 min | Pre-demo dry run (first stop only) | 3 min |
| T-3 min | Final caveat and posture check | 2 min |
| T-0 | Demo begins | — |

---

## Step 1 — Environment Startup

**Estimated time: 5 minutes**

Open two terminals. Keep them visible but behind the browser during the demo.

### Terminal A — Backend

```bash
cd crawlernest/servise_for_java
./mvnw -Dmaven.test.skip=true spring-boot:run
```

Wait for:
```
Started CrawlerApplication in X.XXX seconds
```

Backend is ready at `http://localhost:8080`.

### Terminal B — Frontend

```bash
cd crawlernest/crawlernest-web
npm run dev
```

Wait for:
```
✓ Ready on http://localhost:3000
```

Frontend is ready at `http://localhost:3000`.

---

## Step 2 — Backend Health Check

**Estimated time: 1 minute**

```bash
curl -s "http://localhost:8080/api/v1/health" | head -1
curl -s "http://localhost:8080/api/v1/diagnostics/source-agreement" | head -5
```

Expected: HTTP 200, JSON response with `"status"` field present.

If health check fails: see [DEMO_FAILURE_RECOVERY.md](DEMO_FAILURE_RECOVERY.md) — backend recovery.

---

## Step 3 — Frontend Browser Preparation

**Estimated time: 3 minutes**

Open a clean browser window (or use a dedicated demo profile).
See [DEMO_BROWSER_STATE.md](DEMO_BROWSER_STATE.md) for the full browser configuration.

Open these tabs **in this order** (left to right):

1. `http://localhost:3000/analytics` — confirm disagreement table loads
2. `http://localhost:3000/recommendations` — confirm form loads
3. `http://localhost:3000/system-status` — confirm status page loads

Do not open `/saved-recommendations` yet — wait until session is verified (Step 5).

---

## Step 4 — Analytics Page Verification

**Estimated time: 1 minute**

On `http://localhost:3000/analytics`:

- [ ] Source Disagreement table is visible and has rows
- [ ] At least one row has a **High** severity chip (orange/red)
- [ ] Source Coverage section shows: `QS ✓ Available`, `THE — Unavailable`, `ARWU — Unavailable`
- [ ] Operational Posture section shows confidence posture label (e.g. "Mostly Low")
- [ ] Analytics Caveats section is visible
- [ ] No console errors (press F12, check Console tab)

If the disagreement table is empty: see [DEMO_FAILURE_RECOVERY.md](DEMO_FAILURE_RECOVERY.md) — analytics unavailable.

---

## Step 5 — Session and Saved Recommendation Preparation

**Estimated time: 2 minutes**

If the demo uses a saved recommendation to avoid generating live:

1. Navigate to `http://localhost:3000/recommendations`
2. Confirm the form loads with Country / Score / Target Rank / Risk fields
3. Enter the standard demo profile:
   - Country: `United Kingdom`
   - IELTS Score: `6.5`
   - Target Rank: `100`
   - Risk Tolerance: `balanced`
4. Click **Generate Recommendations**
5. Wait for results (3–5 seconds)
6. Click **"Why this recommendation?"** on the first result card
7. Confirm Evidence Chain, confidence bar, Source Coverage, and Data Caveats are all visible
8. Navigate to `http://localhost:3000/saved-recommendations` and confirm any saved records load

If recommendations fail to generate: see [DEMO_FAILURE_RECOVERY.md](DEMO_FAILURE_RECOVERY.md) — backend down.

---

## Step 6 — Caveat Visibility Verification

**Estimated time: 1 minute**

On the recommendations explain panel, confirm:

- [ ] **Evidence Chain** heading is visible above the ✓ reasons
- [ ] **Data Confidence** bar is present with percentage
- [ ] Text "Not AI-generated" appears below the confidence bar
- [ ] **Source Coverage** chips show QS ✓ / THE — / ARWU —
- [ ] **Data Caveats** section is present at the bottom of the explain panel
- [ ] Caveats include: QS stale data, THE unavailable, ARWU unavailable

If any caveat is missing: do not proceed — see [DEMO_FAILURE_RECOVERY.md](DEMO_FAILURE_RECOVERY.md).

---

## Step 7 — Operational Posture Verification

**Estimated time: 1 minute**

Return to `http://localhost:3000/analytics`, scroll to **Operational Posture** section:

- [ ] **Source Availability** chips show: `QS ✓ Available`, `THE — Unavailable`, `ARWU — Unavailable`
- [ ] **Confidence Posture** label is present (e.g. "Mostly Low")
- [ ] **Freshness Detail** link is present (→ `/system-status`)
- [ ] Operational Posture section renders above Analytics Caveats

If Operational Posture is blank: check that the backend `/api/v1/diagnostics/source-agreement` responds.

---

## Step 8 — Final Pre-Demo Check

**Estimated time: 2 minutes**

- [ ] Both terminals (backend, frontend) are running — no error output in the last 60 seconds
- [ ] Browser zoom is set to 100% (Ctrl+0 / Cmd+0)
- [ ] Unrelated tabs are closed
- [ ] Screen recorder or window is ready (if recording)
- [ ] Notes or script doc is open on a separate screen (not visible to the audience)
- [ ] `docs/DEMO_ROUTE.md` is open for reference

---

## Failure Recovery

If anything fails during preparation, consult:

- [DEMO_FAILURE_RECOVERY.md](DEMO_FAILURE_RECOVERY.md) — per-failure recovery guide
- [DEMO_DATA_FREEZE.md](DEMO_DATA_FREEZE.md) — why not to rerun data pipelines before demo

---

## What NOT to Do Before the Demo

- Do not rerun `smoke_release.sh` immediately before the demo — it modifies report files
- Do not rerun ingestion or crawl pipelines — stale data is expected and caveat-covered
- Do not run `./mvnw test` immediately before the demo — adds startup noise
- Do not reset the database — saved recommendations and cached data will be lost
- Do not change `npm run dev` to `npm run build && npm run start` unless pre-tested
