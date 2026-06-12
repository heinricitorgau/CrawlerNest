# CrawlerNest — Competition Track

This document defines CrawlerNest's positioning for competition and Dispatch-style
demo contexts. It establishes what the platform is, what it is not, and where its
genuine differentiation lies.

---

## What CrawlerNest Is Not

- **Not a generic school finder.** The platform does not surface subjective
  "best fit" recommendations based on lifestyle preferences or marketing copy.
  
- **Not a chatbot.** There is no natural language interface, LLM integration,
  or conversational recommendation flow.

- **Not a fake AI recommendation engine.** Recommendation output is deterministic,
  source-linked, and fully explainable. There is no black-box scoring, no vector
  embedding layer, and no generative ranking synthesis.

- **Not a real-time platform.** Data ingestion is batch-based. Freshness is
  honestly disclosed at every surface — API, frontend, and demo.

---

## What CrawlerNest Is

### Explainable University Intelligence Platform

CrawlerNest is an evidence-backed university intelligence system. Every ranking
displayed can be traced to its source data:

- Which ranking sources contributed (QS, THE, ARWU)
- How each source's rank was normalized and weighted
- What the rank spread across sources indicates about data confidence
- Why a university's aggregated rank is what it is

This explainability is not a feature added on top — it is the architecture.
The aggregation formula is deterministic, version-tracked, and exposed through
the `/api/v1/rankings/{id}/explain` endpoint.

### Evidence-Backed Ranking Analytics System

The analytics surface shows patterns that are directly derivable from the
ingested source data:

- Ranking trend movement across years (where historical data exists)
- Source disagreement — how much QS, THE, and ARWU differ for the same university
- Source coverage gaps — which universities appear in only one source
- Country-level representation in the ranking universe

Every analytics output includes honest disclosure of data limitations:
stale data, unavailable sources, and single-year coverage are labeled as such.

### Operationally Traceable Education Data Platform

The operational infrastructure is visible and honest:

- Freshness state is disclosed at every level (API, frontend, release bundle)
- Source availability (THE unavailable, ARWU unavailable at RC-1) is documented
  and surfaced to users, not hidden
- The maintenance posture is described in `docs/STABLE_DEGRADED_STATE.md`
- Confidence levels are derived from observable signals, not asserted

---

## Competition Differentiators

| Differentiator | What It Means |
| --- | --- |
| Full ranking explainability | Every rank can be traced to its source evidence |
| Multi-source aggregation | QS, THE, ARWU combined with transparent weighting |
| Source disagreement visibility | Where sources conflict is shown, not hidden |
| Honest caveat disclosure | Stale data, missing sources disclosed at all surfaces |
| Deterministic recommendation | No hallucinated rankings, no LLM-generated scores |
| Operational traceability | Data age, source status, aggregation run visible |
| Readonly-safe architecture | No autonomous data mutation, no self-healing |
| Session-based identity layer | Saved universities and recommendation plans for signed-in users |

---

## Competition Non-Goals

These are intentionally absent. Claiming them would be dishonest.

| Non-Goal | Why Absent |
| --- | --- |
| Real-time ranking updates | Batch ingestion; freshness is disclosed |
| THE and ARWU live data | Source files not acquired at RC-1 |
| Subject ranking completeness | MVP scope: QS global rankings only |
| Predictive ranking forecasting | No historical depth for trend prediction |
| Natural language query | No LLM integration planned |
| Personalized ML recommendations | Deterministic engine; no user behavioral model |

---

## Competition Strengths

### 1. Explainability as Architecture

Most university ranking platforms present a number without derivation. CrawlerNest
presents the number, the formula, the source contributions, the missing sources,
the normalized scores, and the confidence level — all in a single API response.

The `/api/v1/rankings/{id}/explain` endpoint is a direct expression of this.

### 2. Honest Data Posture

No claim in the platform is inflated beyond what the data supports. When THE and
ARWU are unavailable, the frontend says so. When data is stale (354h at RC-1),
the freshness endpoint says so. When coverage is limited to one source, the
confidence is "low" and that is what the user sees.

Honesty at every surface is a competitive differentiator, not a weakness.

### 3. Source Disagreement as Signal

When QS ranks a university at 50 and THE ranks it at 150, that disagreement is
itself a signal worth surfacing. CrawlerNest computes and displays rank spread,
confidence buckets, and the top universities with the largest cross-source
disagreement. This is analytically valuable information that most platforms hide.

### 4. Operational Credibility

The platform's maintenance posture — including freshness state, source availability,
and aggregation run history — is exposed through the diagnostics layer. A reviewer
or judge who asks "how do you know this data is reliable?" gets a direct, honest
answer backed by observable signals.

### 5. Deterministic and Reproducible

Given the same source data and the same aggregation method version, CrawlerNest
produces the same ranking output. There is no stochastic component, no hidden
weighting, and no output that cannot be explained.

---

## Explainability Strengths

- `GET /api/v1/rankings/{id}/explain` — per-university explanation with source
  contributions, normalized scores, weights, missing source penalties, confidence
  reasoning, and formula note
- `GET /api/v1/universities/{id}/source-comparison` — side-by-side source ranks
  for a single university
- `GET /api/v1/analytics/source-disagreement` — cross-university disagreement
  analysis with rank spread, confidence buckets, and outlier identification
- `GET /api/v1/analytics/ranking-trends` — year-over-year rank movement with
  honest `limitedCoverage` flag when historical depth is insufficient

---

## Operational Credibility Strengths

- `GET /api/v1/diagnostics/freshness` — data age and source freshness state
- `GET /api/v1/diagnostics/source-agreement` — source overlap and disagreement
- `GET /api/v1/health` — system health with source availability status
- `GET /api/v1/diagnostics/status` — full operational status summary

---

## Boundary

This document defines the competition positioning. It does not change any API
behavior, data model, or recommendation output. The positioning described here
is accurate as of RC-1 — it reflects what the system currently does, not what
it might do in a future release.

See also:
- [COMPETITION_DEMO_NARRATIVE.md](COMPETITION_DEMO_NARRATIVE.md) — demo flow and talking points
- [ANALYTICS_SURFACE_PLAN.md](../analytics/ANALYTICS_SURFACE_PLAN.md) — analytics surface planning
- [ANALYTICS_EXPLAINABILITY.md](../analytics/ANALYTICS_EXPLAINABILITY.md) — explainability requirements
- [STABLE_DEGRADED_STATE.md](../data/STABLE_DEGRADED_STATE.md) — current data posture
