# Analytics Explainability

This document defines the explainability requirements for all CrawlerNest
analytics outputs. Every analytics surface — API response, frontend display,
or demo narrative — must meet these requirements.

---

## Core Requirements

### 1. Explainable

Every analytics output must be traceable to its source evidence. The user
must be able to understand how the output was derived without needing access
to internal systems.

**Required for each analytics output:**
- What data was used (source, year, universe scope)
- What computation was applied (formula, aggregation method)
- What the output means in plain terms

**Not acceptable:**
- "Confidence score: 0.87" without explaining what 0.87 means
- "University ranked 45" without showing which sources contributed
- "High agreement" without showing the rank spread

### 2. Evidence-Backed

Every analytics claim must be derivable from ingested source records.

**Acceptable:**
- "QS ranks MIT at 1. THE ranks MIT at 2. Rank spread = 1."
- "Only QS data is available for this university. Confidence: low."
- "Year-over-year rank delta: +12 (moved from 45 to 57)."

**Not acceptable:**
- "Based on trends, this university is likely to improve next year."
- "This university has strong research output." (unless sourced from a ranking criterion)
- "Confidence: high" based on factors not traceable to source data

### 3. Reproducible

Given the same source data and the same aggregation method version, the
analytics output must be identical. There must be no stochastic component,
random sampling, or session-dependent variation.

**Required:**
- Aggregation method version is available in API responses
- Source data timestamp is included in API responses
- Output is deterministic for the same inputs

### 4. Source-Linked

Each analytics output must identify which ranking sources contributed.

**Required:**
- List of contributing sources (e.g., `["QS"]`)
- List of missing sources (e.g., `["THE", "ARWU"]`)
- Caveat when coverage is incomplete

---

## Caveat Policy

Caveats are not optional. They are the honesty contract for analytics output.

### Required Caveats at RC-1

| Condition | Required Caveat |
| --- | --- |
| THE unavailable | "THE (Times Higher Education) data is not available. Analysis reflects QS source only." |
| ARWU unavailable | "ARWU (Academic Ranking of World Universities) data is not available. Analysis reflects QS source only." |
| Stale data | "QS ranking data was last ingested at RC-1 packaging (approximately 354 hours ago). Data may not reflect the current published rankings." |
| Single-year trends | "Year-over-year trend analysis requires data from multiple aggregation runs. Current data covers a single year — no rank delta is available." |
| Incomplete subject coverage | "Subject ranking data is incomplete. Subject analytics are not available in this release." |

### Caveat Delivery

Caveats are delivered in two places:

1. **API response** — `caveats` array in the response metadata:
   ```json
   {
     "success": true,
     "data": { ... },
     "metadata": {
       "caveats": [
         "THE and ARWU data not available — QS source only.",
         "Single-year coverage — no rank delta available."
       ]
     }
   }
   ```

2. **Frontend** — Analytics Caveats section on the `/analytics` page,
   prominently displayed, not collapsed or hidden.

### Caveat Tone

Caveats are stated professionally and informatively. They are not apologetic.
A caveat explains what the limitation is and what the user can rely on.

**Acceptable:** "THE and ARWU data are not available in this release. Source
agreement analysis reflects QS rankings only. Multi-source comparison will
be available when THE and ARWU are ingested."

**Not acceptable:** "Sorry, we don't have THE and ARWU data." (too informal)

**Not acceptable:** Omitting the caveat because the presentation audience
might react negatively.

---

## What Analytics Must Not Do

### No Black-Box Scoring

Analytics outputs must not include scores, indexes, or confidence levels that
cannot be traced to a documented formula. If a score appears, the formula must
be disclosed in the same response or linked.

### No Fake Confidence

Confidence levels must be derived from observable signals:
- "high" = 3 major sources available
- "medium" = 2 major sources available
- "low" = 1 major source available (or fewer)

Adjusting confidence levels to look better before demos is explicitly prohibited.
See `docs/MAINTENANCE_DISCIPLINE.md` §4 for the rationale.

### No Hallucinated Analytics

Analytics must not include:
- Trend projections without actual historical data
- "Predicted" rankings not grounded in source data
- Quality assessments derived from proxies not in the data
- LLM-generated summaries of ranking patterns

### No Hidden Weighting Changes

The aggregation formula must remain stable between analytics runs. Changing
weights to make a particular university rank better for a demo violates the
reproducibility requirement.

---

## Analytics Explainability Endpoints

| Endpoint | Explainability Features |
| --- | --- |
| `GET /api/v1/analytics/ranking-trends` | Source counts per year, rank delta, `singleYearOnly` flag, data age, caveats |
| `GET /api/v1/analytics/source-disagreement` | Rank spread, confidence buckets, source overlap, missing source coverage, caveats |
| `GET /api/v1/rankings/{id}/explain` | Per-source contribution, weights, normalized scores, missing source penalties, confidence reasoning |
| `GET /api/v1/universities/{id}/source-comparison` | Side-by-side source ranks, confidence, rank spread |
| `GET /api/v1/diagnostics/freshness` | Data age, freshness state, last ingestion timestamp |

---

## Boundary

This document defines explainability requirements. It does not implement any
enforcement mechanism. Compliance is maintained through code review and the
audit trail in git history.

Non-compliance indicators (things to flag in review):
- A score field with no formula reference
- A `confidence` field set manually rather than derived
- An analytics output with no `caveats` field
- A trend projection without underlying historical data

See also:
- [COMPETITION_TRACK.md](COMPETITION_TRACK.md) — competition positioning and differentiators
- [ANALYTICS_SURFACE_PLAN.md](ANALYTICS_SURFACE_PLAN.md) — analytics surface planning
- [DEMO_HONESTY_GUIDELINES.md](DEMO_HONESTY_GUIDELINES.md) — required demo disclosure
