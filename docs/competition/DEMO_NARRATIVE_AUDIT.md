# Demo Narrative Audit

> **RC-1 Historical Baseline (2026-05).** This audit records the demo narrative
> and limitations observed at the RC-1 packaging point in May 2026. References
> to QS-only coverage, unavailable THE/ARWU data, or the then-current agent
> behavior are preserved as historical evidence and are superseded by the
> current 2026 Live competition documents.

Phase 4 — Demo Rehearsal. Evaluates whether the current demo narrative answers the key questions a competition judge needs answered.

---

## Audit Checklist

### 1. Why was this built?

**Current narrative coverage:** Partial.

The narrative opens with "university rankings are opaque" and "students see a number, not the evidence." This frames the problem clearly for a data-oriented judge. However, the *personal or institutional motivation* for building CrawlerNest is missing from the demo flow. The narrative explains the domain problem but not why this team specifically chose it.

**Gap:** No answer to "why did you build this and not something else?" A competition judge will ask.

**Recommendation:** Add one sentence to the opening: a concrete context for why this problem was chosen — whether academic, personal, or analytical.

---

### 2. What is the problem?

**Current narrative coverage:** Strong.

The three-sentence story in COMPETITION_STORYTELLING.md is accurate and focused:
- Rankings are opaque.
- Disagreement between sources is invisible.
- Honest uncertainty is more useful than false precision.

The problem is clearly stated and supported by the analytics surface (source disagreement) and the recommendation explainability panel.

**Gap:** The problem statement does not distinguish between "student" and "researcher/developer" use cases. The system demo flow targets a technical audience more than a student audience, but the problem statement frames a student need. This misalignment can confuse non-technical judges.

---

### 3. Why do existing solutions do this poorly?

**Current narrative coverage:** Weak.

The narrative gestures at "most platforms present a number without derivation" but does not name or demonstrate a concrete comparison. A judge unfamiliar with QS's own website will not know whether CrawlerNest is genuinely differentiated or describing a gap that doesn't exist.

**Gap:** No direct "here is what QS shows vs. what we show" comparison. No citation of a specific pain point in existing tools.

**Recommendation:** One slide or 20-second verbal: "QS shows you rank 50. The underlying data shows QS ranks MIT at 1 and THE ranks it at 2. That spread is invisible on QS's own platform. We show it."

---

### 4. What is the method?

**Current narrative coverage:** Strong on architecture, weak on narrative form.

The pipeline is well-documented. The explain API is technically detailed. The recommendation evidence model is precise. A software engineering judge will find everything they need.

However, the method is never described in a single concrete sentence that a non-technical judge can remember. The current narrative dives into endpoints and JSON structures before establishing what the system fundamentally does.

**Gap:** No one-sentence method summary suitable for a non-technical judge.

**Recommendation:** Lead with: "We crawl ranking sources, normalize them into a shared schema, aggregate with a documented formula, and expose both the result and the evidence through a public API."

---

### 5. Explainability value

**Current narrative coverage:** Strong.

The recommendation explain panel, the `/api/v1/rankings/{id}/explain` endpoint, and the source comparison API are all clearly motivated and demonstrated. The COMPETITION_DEMO_NARRATIVE.md script includes the verbatim phrasing: "This rank is not just a number — it's derived from X sources."

The evidence chain visualization differentiates CrawlerNest from systems that return recommendations with no derivation.

**Gap:** The word "explainability" is used in an AI-safety/XAI sense by many competition judges. CrawlerNest's explainability is stored-data transparency, not model interpretability. If the judge expects LIME, SHAP, or attention-weight explanations, the current narrative will seem like mislabeling.

**Recommendation:** Disambiguate early: "By explainability we mean: you can see every stored input, the formula that produced the output, and the specific data gaps that lower confidence. This is not ML interpretability — it is data lineage."

---

### 6. Agent's role

**Current narrative coverage:** Unclear and potentially misleading.

The current demo flow (COMPETITION_DEMO_NARRATIVE.md) does not include a clear step for the agent. The agent is documented separately in AGENT_DEMO_EVALUATION.md and AGENT_MODEL_INTEGRATION.md but its role in the competition narrative is undefined.

The agent is a readonly advisory bridge. Its default is a mock provider. Its best use case during a demo is showing the system knows its own boundaries. It does not recommend, does not query the database, and does not run tools.

**Gap:** No clear answer to "what does the agent contribute to the demo value proposition?"

**Recommendation:** Either (a) assign the agent a single specific demo moment ("We ask the agent to explain source disagreement — and it correctly states the caveat, the page to visit, and that it cannot modify data"), or (b) explicitly classify it as a bonus section and not part of the main narrative.

---

### 7. What will judges remember?

**Current narrative coverage:** The closing statement is strong: "CrawlerNest is not the most confident university ranking platform. It is the most honest one."

This is memorable, defensible, and differentiated. It is the right closing.

**Risk:** If the demo spends too long on curl commands, JSON output, and API endpoints, the judge will remember "technical demo that showed me JSON" rather than the closing statement. The narrative architecture leads with infrastructure and closes with philosophy — but judges form impressions in the first 90 seconds.

**Gap:** No strong opening hook before the first technical step. The demo currently starts with a health check.

**Recommendation:** Open with the three-sentence problem statement (from COMPETITION_STORYTELLING.md) before any commands or browser actions.

---

## Scores

| Dimension | Score | Reason |
|---|---|---|
| **Clarity** | 6/10 | Strong technical clarity; weak narrative clarity for non-technical judges |
| **Technical depth** | 8/10 | Full API coverage, documented formulas, CI evidence |
| **Explainability** | 7/10 | Correctly implemented; risks being misread as AI interpretability |
| **Credibility** | 9/10 | Honest caveat posture is a genuine strength; risk of over-caveating |
| **Competition impact** | 6/10 | Memorable closing; weak opening; agent role undefined; no competitor comparison |

**Overall: 7.2 / 10**

---

## Priority Gaps to Fix Before Competition

1. **No clear opening hook.** Start with the problem statement before any technical demonstration.
2. **Agent role undefined in the main narrative.** Assign it a moment or move it to bonus.
3. **"Why existing tools fail" is vague.** Add one concrete comparison.
4. **Explainability disambiguation needed.** Clarify "stored-data transparency, not ML interpretability" early.
5. **Method summary missing.** Add one sentence a non-technical judge can retain.

---

See also:
- [COMPETITION_DEMO_NARRATIVE.md](COMPETITION_DEMO_NARRATIVE.md) — step-by-step demo flow
- [COMPETITION_STORYTELLING.md](COMPETITION_STORYTELLING.md) — storytelling framework
- [JUDGE_QUESTION_BANK.md](JUDGE_QUESTION_BANK.md) — anticipated judge questions
- [DEMO_TIMING_REVIEW.md](../demo/DEMO_TIMING_REVIEW.md) — timing analysis
