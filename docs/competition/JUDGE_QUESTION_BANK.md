# Judge Question Bank

Phase 4 — Demo Rehearsal. Judge simulation from four reviewer perspectives.

---

## Perspective 1 — CS / Data Engineering Professor

### Most Likely Questions

- "What is the aggregation formula, exactly? Walk me through the weights and normalization."
- "How do you resolve the same university appearing under different names across QS, THE, and ARWU?"
- "What does your canonical entity resolution look like? Is it deterministic?"
- "Where is the data stored — what schema design did you choose and why?"
- "What happens when a new QS release changes 200 university names? How does your pipeline handle drift?"
- "How is `composite_score` computed when only one source is available?"
- "What is the `aggregation_method_version` field for, and how do you version the formula?"

### Sharpest Questions

- "You say 'multi-source aggregation' — but THE and ARWU aren't actually available. Isn't this single-source with a framework that doesn't yet have data?"
- "Your confidence score at RC-1 is always 'low' for every university because you only have QS. Doesn't that make the confidence display meaningless?"
- "The `source_ranks_json` field stores JSON in a relational database. Why not normalize that into a separate source-rank table?"
- "Your analytics view is called `v_aggregated_rankings_latest` — what does 'latest' mean when you only have one year of data?"

### Easiest Points to Challenge

- "Multi-source" positioning while only QS is present.
- "Analytics" page when single-year and single-source means very little can actually be analyzed.
- Confidence buckets that currently place every university in "low."
- Calling a mock-provider chat window an "agent."

### Easiest Misunderstandings

- Conflating the explainability API with actual AI reasoning — it is stored-data retrieval, not inference.
- Assuming the "recommendation engine" uses ML when it is deterministic arithmetic.
- Thinking "canonical matching" implies deduplication at scale when it is manual-resolve at RC-1.

---

## Perspective 2 — AI Application Competition Judge

### Most Likely Questions

- "Where exactly does AI appear in this system?"
- "What is the agent doing that a query form could not do?"
- "Why is explainability a differentiator? Every deterministic system is by definition explainable."
- "How does the confidence score compare to a proper Bayesian confidence interval?"
- "What would it take to add a real ML ranking model here?"
- "Is the recommendation 'explainability' meaningful, or just showing input fields back to the user?"

### Sharpest Questions

- "The agent is a chat box backed by a mock provider by default. How is that meaningfully different from a FAQ page?"
- "You call this an 'AI application' but the recommendation engine explicitly has no AI. What is the AI innovation here?"
- "If the agent cannot modify data, cannot call tools, and cannot run queries — what problem does it solve that a help page does not?"
- "The 'Evidence Chain' in recommendations is essentially a struct dump of stored fields. Is that what you mean by explainability?"

### Easiest Points to Challenge

- The agent being the weakest component while positioned as a differentiator.
- "Explainability" being pattern-matched to the AI-explainability trend without involving AI.
- The system being more of an ETL + CRUD application than an AI application.

### Easiest Misunderstandings

- Mistaking the demo-ready agent UI for a real reasoning agent.
- Assuming "deterministic recommendation" means it was designed to avoid AI bias (rather than simply having no ML).
- Conflating operational honesty about data gaps with a design principle — the caveats exist because data is missing, not only because transparency is valued.

---

## Perspective 3 — Software Engineering Judge

### Most Likely Questions

- "Walk me through your CI/CD pipeline. What runs on every push?"
- "How do you test the recommendation scoring logic?"
- "What does the Spring Boot to Next.js data path look like?"
- "How is PostgreSQL schema versioned?"
- "What is the `warehouse` vs `analytics` schema split for?"
- "Does the Next.js API layer add any logic or is it pure proxy?"
- "What is your test coverage for the core scoring and explainability paths?"

### Sharpest Questions

- "You have two CI workflows but neither runs against a live database. How confident are you that fixture-mode tests reflect real behavior?"
- "The `start_localhost.sh` startup script is a shell script — what happens when a port collision occurs mid-demo?"
- "Spring Boot and Next.js are two separate processes. If the Java API is down, what does the user see? Have you tested that degraded state?"
- "You have `servise_for_java` in the path name — is that a typo that's now committed to the repo and propagated into configs?"
- "The entity canonical matching is described as 'manual resolve for 4 unresolved entities.' How does that scale to the full THE/ARWU dataset?"

### Easiest Points to Challenge

- The typo in `servise_for_java` is a visible, persistent credibility issue.
- Fixture-mode CI means no end-to-end integration test with a real DB in CI.
- No evidence of formal test coverage metrics.
- Demo depends on multiple manual startup steps and local state.

### Easiest Misunderstandings

- Treating the demo bundle as a deployable artifact when it is packaged for localhost only.
- Assuming Spring Boot session persistence across restarts (sign-out-on-restart behavior is documented but easily missed).
- Thinking the analytics view is materialized when it may be a live-computed view each load.

---

## Perspective 4 — Non-Technical Judge

### Most Likely Questions

- "Who is this for? Students? Universities? Admissions consultants?"
- "How is this different from QS's own website or US News & World Report?"
- "If I wanted to use this today, what would I do?"
- "Can I trust the recommendations it gives me?"
- "How often is the data updated?"

### Sharpest Questions

- "You show me a university ranked 50 — why would I use your rank instead of the official QS rank?"
- "You keep saying the data is 'stale' and 'from one source.' If the data isn't fresh and isn't multi-source, why is the system useful now?"
- "The agent says 'I can suggest how to change the code' — so it's a developer tool, not a student tool?"
- "The 'recommendations' page has me enter a target rank and IELTS score. But who sets the IELTS minimums? Are they accurate?"

### Easiest Points to Challenge

- The gap between what the demo shows and what a real user would experience if they tried to use it today.
- Admissions data being scraped and potentially outdated — IELTS minimums are presented as evidence but sourced from crawled data.
- The localhost-only nature of the demo undermining credibility for general users.

### Easiest Misunderstandings

- Thinking the "agent" is a student-facing advisor when it is a developer-facing readonly bridge.
- Assuming "explainability" means the system can explain why Harvard is ranked first, rather than explaining the scoring math.
- Confusing "honest data posture" with the system having poor data — the posture is a design choice, not a product failure.

---

## Cross-Cutting Danger Zones

| Question type | Risk | Preparation |
|---|---|---|
| "Why only QS?" | Credibility hit if not prepared | Explain THE/ARWU unavailability clearly, note framework is ready |
| "What does the agent actually do?" | Hardest question for AI-competition judges | Be honest: advisory, readonly, demonstration of provider bridge |
| "Can I use this today?" | Non-technical judge will ask this | Honest answer: localhost demo MVP, not production-deployed |
| "How is this different from a spreadsheet?" | Could land hard | Emphasize deterministic formula, explainability API, pipeline observability |
| "What happens when QS releases 2027 data?" | Good test of pipeline design | Walk through the pipeline command and schema versioning |

---

See also:
- [COMPETITION_DEMO_NARRATIVE.md](COMPETITION_DEMO_NARRATIVE.md) — demo flow and talking points
- [DEMO_HONESTY_GUIDELINES.md](../demo/DEMO_HONESTY_GUIDELINES.md) — acceptable phrasing
- [COMPETITION_TRACK.md](COMPETITION_TRACK.md) — competition positioning
