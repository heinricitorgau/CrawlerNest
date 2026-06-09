# Demo Timing Review

Phase 4 — Demo Rehearsal. Simulates 90-second, 3-minute, and 5-minute demo flows. Identifies sections that are too long, too technical, or redundant.

---

## 90-Second Version

**Goal:** Leave the judge with one thing. Pick the single most differentiated moment.

### Proposed Script

| Time | Action | Verbal |
|---|---|---|
| 0:00–0:10 | State the problem | "University rankings are opaque — you see a number, not the evidence behind it." |
| 0:10–0:20 | Open /rankings | "We have 1,499 universities, ranked from QS 2026. Each rank is computed, not scraped." |
| 0:20–0:50 | Click a top university, open explain panel | "Here is what QS says, the normalized score, the formula version, and why confidence is low — one source only." |
| 0:50–1:10 | Open /recommendations, show evidence panel | "Every recommendation shows its Evidence Chain: stored reasons, warnings, caveats. Nothing is generated." |
| 1:10–1:30 | Closing statement | "This is not the most confident system. It is the most honest one." |

### Assessment

**What works:** The university explain panel is the single strongest moment. It can carry a 90-second demo alone.

**What to cut entirely:** Analytics, agent, system-status, diagnostics, subject rankings — all cut. No curl commands.

**Risk:** No demo of analytics removes the "source disagreement" story point. The judge hears "explainability" but only sees the explain endpoint, not the broader analytics surface. Acceptable tradeoff at 90 seconds.

---

## 3-Minute Version

**Goal:** Problem → System → Explainability differentiator → Honest data posture.

### Proposed Script

| Time | Block | Content |
|---|---|---|
| 0:00–0:20 | Problem | State the three-sentence problem. No slides needed — verbal. |
| 0:20–0:50 | Rankings overview | Open /rankings. Show top 10, note 1,499 count, run one search. Do NOT show curl. |
| 0:50–1:30 | University explainability | Click one university. Show explain panel. Say: "QS rank, normalized score, formula version, confidence: low because one source." |
| 1:30–2:10 | Recommendations + evidence | Navigate to /recommendations. Enter IELTS + target rank. Open one card's "Why?" panel. Show: Reasons, Warnings, Source Coverage, Caveats. |
| 2:10–2:40 | Analytics: source disagreement | Navigate to /analytics. Show the source disagreement table. Say: "These are universities where sources disagree most. The spread is real information, not hidden." |
| 2:40–3:00 | Closing | "Every limitation is labeled. Every rank is explainable. That's the foundation for trust." |

### Assessment

**What works:** The flow moves from data → explainability → recommendation → analytics in a logical progression. The recommend + evidence panel is the emotional peak.

**Too long sections:**
- Analytics section is tight (30 seconds). Risk: if the judge asks a question here, timing collapses.

**Too technical sections:**
- The confidence score derivation (65%/35% formula) is too much detail for 3 minutes. Mention "derived from source coverage" and move on.

**Redundant sections:**
- No redundancy in this flow. Each page adds a new dimension.

**What to cut:** Agent, system-status, subject rankings, curl commands, all JSON output.

---

## 5-Minute Version

**Goal:** Full competitive demo — problem, pipeline, explainability, recommendations, analytics, operational posture, optional agent.

### Proposed Script

| Time | Block | Content |
|---|---|---|
| 0:00–0:25 | Problem statement | Verbal. The three-sentence story. |
| 0:25–0:45 | Architecture in one sentence | "Python crawlers → PostgreSQL warehouse → Spring Boot API → Next.js frontend. The data pipeline is visible at every step." |
| 0:45–1:30 | Rankings + explainability | /rankings overview. Click a university. Open explain panel. Show source_contributions, confidence. One curl command if audience is technical. |
| 1:30–2:15 | Recommendations + evidence chain | /recommendations. Enter inputs. Open evidence panel. Walk through: Reasons, Warnings, Source Coverage, Caveats. Say: "None of this is generated text." |
| 2:15–3:00 | Analytics: source disagreement + posture | /analytics. Source disagreement table. Operational posture section. "THE and ARWU are unavailable. We show that, not hide it." |
| 3:00–3:30 | System status / diagnostics | /system-status. Brief: "This is where an operator looks. Freshness, source state, aggregation run." |
| 3:30–4:00 | Agent (advisory only) | /agent. One prompt: "Explain what source disagreement means." Read the response. Highlight: "It cites the caveat, points to /analytics, and says it cannot modify data." |
| 4:00–4:30 | CI / release evidence | Run smoke_release.sh OR show the GitHub Actions badges. "This builds and validates without a live database." |
| 4:30–5:00 | Closing | "Not the most confident system. The most honest one." |

### Assessment

**What works:** The agent block at 3:30 is well-positioned — after the core product is already demonstrated. It functions as a credibility moment ("the agent knows its own limits") rather than a capability claim.

**Too long sections:**
- Agent block risks running long if the model responds slowly (Ollama) or the mock provider's response is verbose. Cap it hard at 30 seconds.
- CI/release block at 4:00–4:30 is borderline — drop it if you need 30 seconds elsewhere.

**Too technical sections:**
- One curl command max (the health check or the explain endpoint). More than one curl shifts the demo to an engineering walkthrough.
- JSON output should not appear unless the audience explicitly includes software engineers only.

**Redundant sections:**
- System status and diagnostics overlap with what analytics + health check already show. In a strict 5-minute run, system-status can be replaced with a single sentence: "The operational layer exposes freshness, source state, and pipeline history at /system-status."

**What to cut if overtime:**
- CI/release block (30 seconds saved)
- Agent block (30 seconds saved)
- One of the two analytics sub-sections

---

## Common Pitfalls Across All Versions

| Pitfall | Likely moment | Fix |
|---|---|---|
| Running curl commands live | After rankings demo | Pre-run and show output; or skip entirely for non-technical audiences |
| Reading caveats verbatim | Analytics page | Summarize in one sentence; point to the section visually |
| Explaining the 65/35 confidence formula | Recommendations evidence panel | Say "derived from source coverage" and move on |
| Getting stuck in a filter that returns unexpected results | /rankings filter | Pre-select a known-good filter (e.g., "United Kingdom") |
| Agent response is too long or generic | /agent demo | Use a suggested prompt with a predictable output; have fallback verbal ready |
| Startup failure mid-demo | Any transition | Pre-launch all tabs before the demo starts; use browser tabs not navigation |

---

## Recommended Pre-Demo State

Open all required pages in browser tabs before the demo begins:

```
Tab 1: /rankings (with top 10 loaded, one university detail pre-opened)
Tab 2: /recommendations (with inputs pre-filled)
Tab 3: /analytics (source disagreement table visible)
Tab 4: /system-status (for 5-min version)
Tab 5: /agent (for 5-min version, prompt pre-typed but not submitted)
```

Do not navigate live unless necessary. Tab switching is faster and eliminates network/load risk.

---

See also:
- [DEMO_SCRIPT_v0.1.md](DEMO_SCRIPT_v0.1.md) — detailed demo flow
- [DEMO_BROWSER_STATE.md](DEMO_BROWSER_STATE.md) — browser state preparation
- [DEMO_FAILURE_RECOVERY.md](DEMO_FAILURE_RECOVERY.md) — fallback if a service is down
- [SCREENSHOT_VALUE_REVIEW.md](SCREENSHOT_VALUE_REVIEW.md) — slide prioritization
