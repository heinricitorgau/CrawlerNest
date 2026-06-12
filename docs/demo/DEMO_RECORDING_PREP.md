# Demo Recording Preparation

Defines how to configure, pace, and recover a CrawlerNest screen recording.
A recording serves as a submission asset and a fallback if the live demo breaks.

---

## Recording Setup

### Screen Resolution

**Target:** 1920×1080 (Full HD, 16:9).

- Lower resolutions (1280×720): text may appear soft when upscaled by recording tools
- Higher resolutions (4K): larger file, may not render clearly at video submission sizes
- If 1920×1080 is not available, 1440×900 is acceptable

Set the OS display resolution before starting the recording tool.

### Browser Window Sizing

- Window width: **1440px minimum**, ideally **1920px** (full-width viewport)
- Window height: **900px minimum**
- Maximize the window — do not record in a floating/partial window
- Hide the bookmarks bar (Ctrl+Shift+B / Cmd+Shift+B) before recording
- Zoom: **100%** (Ctrl+0 / Cmd+0)

### Recording Tool

Use any of the following:

| Tool | Platform | Notes |
|---|---|---|
| OBS Studio | All | Free, reliable, configurable |
| QuickTime Player | macOS | Built-in, screen recording mode |
| Xbox Game Bar | Windows | Win+G, simple capture |
| Kazam / SimpleScreenRecorder | Linux | Lightweight, stable |

Record the **browser window only**, not the full desktop.

---

## Recording Pacing

### General Principle

**Speak at conversation speed; move at reading speed.**

The audience needs 1–2 seconds to read a label before you scroll past it.

### Per-Section Timing

| Section | Target Duration | Key Pacing Note |
|---|---|---|
| Opening problem (spoken, no screen) | 30–45 seconds | No screen; speak slowly |
| Source Disagreement table | 30 seconds | Pause 2s on each severity chip |
| Source Coverage cards | 20 seconds | Pause on QS ✓, then THE —, ARWU — |
| Operational Posture | 15 seconds | Read confidence posture label aloud |
| Generate recommendations | 25 seconds | Do not apologize for the 3–5s delay |
| Evidence Chain | 30 seconds | Read "Evidence Chain" heading aloud; pause |
| Confidence bar | 20 seconds | Read "Not AI-generated" aloud |
| Source Coverage in explain panel | 15 seconds | Brief — the earlier context handles this |
| Data Caveats | 15 seconds | Say "These are always present" |
| Total | ~3:30 | |

---

## Narration Pacing

- Speak in **complete sentences** — avoid trailing off or half-sentences
- Pause **0.5–1 second** after pointing to each UI element before continuing
- Do not race to show every feature — 3 well-explained surfaces outweigh 7 rushed ones
- For the Evidence Chain, say: "These reasons are the scoring algorithm's stored intermediate values — not generated text."
- For the confidence bar, read the note aloud: "Not AI-generated."
- For THE/ARWU: "THE and ARWU data are not available at RC-1. The platform discloses this here."

---

## Safe Scroll Speed

| Area | Scroll Speed |
|---|---|
| Source Disagreement table | Slow — 1 row per second visible |
| Source Coverage cards | Stop at each card for 1–2 seconds |
| Operational Posture | Stop and read each chip aloud |
| Evidence Chain | Scroll slowly — read heading, pause, then reasons |
| Data Caveats | Stop completely — let the list be readable |

**Do not scroll during a spoken sentence.** Finish the sentence, then scroll.

---

## Narration Script (abbreviated)

Use this as a prompt during recording. Do not read it verbatim — adapt naturally.

```
Opening:
"University rankings are a single number that hides all the uncertainty behind it.
Sources like QS, THE, and ARWU frequently disagree by 100 to 200 positions.
CrawlerNest makes that disagreement visible — and explainable."

Source Disagreement:
"This is the source disagreement table. The spread column shows how far two sources
diverge for the same university. A spread of 200 or more is classified as High severity.
The confidence badge reflects that — Low, because the spread is high."

Operational Posture:
"The platform self-discloses its data state on the main analytics page.
QS is available. THE and ARWU are not available at RC-1. The confidence posture —
Mostly Low — reflects that. No inflation."

Recommendations:
"I'll generate a recommendation now. Country — UK. IELTS 6.5. Target rank 100.
Risk: balanced. [click] The results appear in 3 to 5 seconds."

Evidence Chain:
"I'll open the explain panel. [click] This is the Evidence Chain.
Each reason here is a stored algorithm output — not generated text.
The confidence bar is derived from source coverage and completeness. Not AI-generated."

Caveats:
"At the bottom, Data Caveats are always present — they cannot be dismissed.
THE and ARWU are not available at RC-1. The system says so on every result."
```

---

## Fallback Screenshots

Before recording, capture the Priority 1 screenshots from [SCREENSHOT_CAPTURE_WORKFLOW.md](SCREENSHOT_CAPTURE_WORKFLOW.md).

If the recording fails or the live demo environment is unavailable, present the screenshots
in a full-screen viewer or slideshow.

Navigate using arrow keys, not mouse clicks — smoother and less distracting.

---

## Offline-Safe Operation

CrawlerNest is a localhost demo by design. The application does not require:

- Internet connectivity (no external API calls during demo)
- Cloud database access (PostgreSQL runs locally)
- External CDN or asset hosting (Next.js serves all assets locally)

Before a competition day where network access is uncertain:

- [ ] Confirm the database container or process is running locally
- [ ] Confirm `npm run dev` starts without downloading packages
- [ ] Run the full startup sequence from [DEMO_PRODUCTION_RUNBOOK.md](DEMO_PRODUCTION_RUNBOOK.md) offline
- [ ] Confirm analytics and recommendations load without any network requests

If any step requires internet access, identify and fix it before the competition day.

---

## "If Demo Breaks" Recovery Guidance

### During a live recording session

1. **Stop recording immediately** — do not include the failure in the final recording
2. Identify the failure using [DEMO_FAILURE_RECOVERY.md](DEMO_FAILURE_RECOVERY.md)
3. Fix the environment, reset browser state per [DEMO_BROWSER_STATE.md](DEMO_BROWSER_STATE.md)
4. Start a new recording from the beginning
5. Keep the failed recording file in case a partial section is usable

### If you cannot fix the environment before the submission deadline

1. Present the pre-captured Priority 1 screenshots (see [SCREENSHOT_CAPTURE_WORKFLOW.md](SCREENSHOT_CAPTURE_WORKFLOW.md))
2. Narrate the screenshots as you would the live demo
3. Record the narrated screenshot walkthrough as the final submission

A narrated screenshot walkthrough is a complete and honest submission.
It demonstrates the same evidence quality as a live recording.

---

## Post-Recording Checklist

- [ ] Recording resolution is correct (1080p or 1440×900)
- [ ] Audio is audible and clear
- [ ] No personal information, passwords, or irrelevant windows appear
- [ ] Evidence Chain section is captured with "Not AI-generated" readable
- [ ] Data Caveats section is visible in the recording
- [ ] THE/ARWU Unavailable state is visible
- [ ] Total recording length is 3–5 minutes
- [ ] File is saved as MP4 or MOV (competition-friendly formats)
