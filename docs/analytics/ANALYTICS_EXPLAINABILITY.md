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

The two source-coverage rows below are **generated from the warehouse**, not
written as constants. They previously read "THE data is not available. Analysis
reflects QS source only", which was true when written and false the day THE was
ingested for part of the table — a disclosure that is specific, confident and
wrong. `AnalyticsService.appendSourceCoverageCaveats` counts the non-null ranks
per source and emits the matching row; `SourceCoverageCaveatTest` fails if that
goes back to being a constant.

| Condition | Required Caveat |
| --- | --- |
| Source has no rows | "&lt;Source&gt; data is not available. No university carries a rank from this source." |
| Source covers part of the table | "&lt;Source&gt; covers N of M universities. A missing &lt;S&gt; rank means either that the &lt;S&gt; data ingested here does not include the university or that this platform could not match it — not that &lt;S&gt; does not rank it." |
| Source covers the whole table | *(no caveat — there is nothing undisclosed)* |
| Snapshot age | "QS ranking data is a point-in-time snapshot of the 2025 and 2026 published tables. Figures may not reflect rankings republished since this snapshot was ingested." |
| Single-year trends | "Year-over-year trend analysis requires data from multiple aggregation runs. Current coverage is a single year — no rank delta is available." |
| Multi-edition trends | "Composite ranks are not compared between editions. A university's composite position moves whenever source coverage changes, so rank movement is reported per source on each university's page instead." |
| Incomplete subject coverage | "Subject ranking data is incomplete. Subject analytics are not available in this release." |
| Response carries a modelled value | "Some values in this response are model estimates produced by CrawlerNest, not figures published by the ranking source. Estimated values are labelled as estimates, carry a support flag, and never replace a published rank." |
| Response carries an unsupported estimate | "Some estimates here fall outside the data the model was fitted on and are marked unsupported. The model has seen no comparable cases for them. That is a statement about the evidence behind the estimate, not a measurement of how wrong it is." |
| Response shows a per-source rank change | "Rank changes compare one source's published ranks between two editions. They are not changes in a composite or platform rank, a banded rank gives a range rather than a number, and no change is shown when the institution or its source entry changed between editions." |
| Response carries a disagreement probability | "Cross-source disagreement probability is a model estimate of how likely QS and THE are to disagree about a university, not an observed difference between published ranks. A probability is not a rank gap, and most scored universities carry no THE rank to compare against." |

### Year-bearing caveats

The snapshot row above names the editions the warehouse holds, and a year written
into a constant is a disclosure with an expiry date — the same failure as the old
"RC-1 packaging" age. It is therefore rendered from a template. Each language
keeps exactly one copy of it, filled from its own list of held editions:
`DATASET_YEARS` in `crawlernest/core/dataset.py`, `DatasetScope.DATASET_YEARS`,
and `DATASET_YEARS` in `crawlernest-web/src/lib/datasetScope.ts`.
`test_caveat_contract.py` checks that the three lists and the three templates
agree. The row in the table is what the template renders for the warehouse today.

Template:

`QS ranking data is a point-in-time snapshot of the {years} published tables. Figures may not reflect rankings republished since this snapshot was ingested.`

`{years}` is the held editions in ascending order, without duplicates, joined as
below. This table is the specification: the Python, Java and TypeScript renderers
are each tested against these rows.

<!-- year-list-rendering:start -->
| Editions held | `{years}` |
| --- | --- |
| 2026 | 2026 |
| 2025, 2026 | 2025 and 2026 |
| 2026, 2025 | 2025 and 2026 |
| 2024, 2025, 2026 | 2024, 2025 and 2026 |
<!-- year-list-rendering:end -->

### Model estimates

The modelling layer in `crawlernest/crawlernest-ml/` produces estimated values —
an overall score for the universities QS withholds one from, and a cross-source
disagreement probability. These are not published figures and must never be
presented as though they were.

Three rules govern them:

1. **Separate storage.** Estimates live in their own tables and never overwrite
   `composite_score` or enter `analytics.aggregated_rankings`.
2. **Conditional disclosure.** Any response carrying an estimate includes the
   caveat above. It is conditional rather than always-on: most responses contain
   nothing but published figures, and a caveat that fires when it does not apply
   trains readers to skip the array.
3. **Support, not confidence.** Each estimate carries a mechanically-derived
   support flag — distance from the data the model was fitted on — in keeping
   with the rule that confidence is derived and never assigned by hand. A
   supported estimate is one the model has seen comparable cases for; it is not
   a claim about the estimate's error.

The caveat string has a single definition per language:
`AnalyticsService.ESTIMATED_SCORE_CAVEAT` (Java, referenced by
`AnalyticsController` and `RecommendationEvidenceService` rather than repeated),
`ESTIMATED_VALUE_CAVEAT` in `crawlernest/core/caveats.py` (Python), and
`CAVEAT_MODEL_ESTIMATE` in `caveatMessages.ts` (frontend). Two tests hold them
together: `AnalyticsCaveatContractTest` reads this document and fails if the text
here drifts from the Java constant, and `test_caveat_contract.py` checks all four
copies against each other.

A disagreement probability carries a second caveat as well. The general one says
a value is an estimate; it does not cover the specific misreading, which is that
"0.99 disagreement" sounds like an observed conflict. Most universities the
classifier scores carry no THE rank for anything to have conflicted with.

The Python read path enforces the pairing structurally rather than by
convention: `agent/tools/ml_tools.py` returns rows and caveats in one
`EstimateEvidence` object and has no method that yields bare rows. Every row also
keeps `isEstimated`, which is what arms the `estimate_credited_to_source` rule in
`provenance.py` — golden case faith-105 is unfaithful in a way no faithfulness
rule reaches, and that flag is the only reason it is caught.

### Caveat Delivery

Caveats are delivered in two places:

1. **API response** — `caveats` array in the response metadata:
   ```json
   {
     "success": true,
     "data": { ... },
     "metadata": {
       "caveats": [
         "THE (Times Higher Education) covers 1637 of 9530 universities. A missing THE rank means either that the THE data ingested here does not include the university or that this platform could not match it — not that THE does not rank it.",
         "ARWU (Academic Ranking of World Universities) covers 838 of 9530 universities. A missing ARWU rank means either that the ARWU data ingested here does not include the university or that this platform could not match it — not that ARWU does not rank it.",
         "QS ranking data is a point-in-time snapshot of the 2026 published tables. Figures may not reflect rankings republished since this snapshot was ingested.",
         "Year-over-year trend analysis requires data from multiple aggregation runs. Current coverage is a single year — no rank delta is available."
       ]
     }
   }
   ```

   The two coverage counts are generated by `AnalyticsService.appendSourceCoverageCaveats`
   from `analytics.v_aggregated_rankings_latest`, so they move with the data. The figures
   above are a verbatim capture of `GET /api/v1/analytics/ranking-trends` against the
   2026-09-04 ingest; treat them as an illustration of the shape, not a fixed baseline.
   QS is absent from the list because it covers the whole table — 9,530 of 9,530 — and a
   source with nothing undisclosed gets no caveat.

2. **Frontend** — Analytics Caveats section on the `/analytics` page,
   prominently displayed, not collapsed or hidden.

### Caveat Tone

Caveats are stated professionally and informatively. They are not apologetic.
A caveat explains what the limitation is and what the user can rely on.

**Acceptable:** "ARWU covers 838 of 9530 universities." — the number, not an
adjective, and the reader can see how much weight to give it.

**Not acceptable:** "Sorry, we don't have much ARWU data." (too informal, and
"much" is not a quantity)

**Not acceptable:** "THE does not rank this university." — when the truth is that
we did not ingest it or could not match it. A missing rank has three possible
causes: the source does not rank the university, the snapshot ingested here does
not reach it, or entity resolution failed. Two of the three are ours, and
naming the third moves our gap onto the institution.

ARWU makes this concrete, and the balance has shifted three times. The first
snapshot held that source's top 30, so almost every absence was the second cause;
a caveat offering only the third would have been wrong about nearly all of them.
The snapshot then reached 897 rows, and the second cause receded. It now holds
all 1,000 rows ARWU publishes, which retires that cause entirely: every absence
is now either a university ARWU does not rank or one this platform failed to
match, and 291 of the 1,000 entities are still unmatched. The wording names both
of ours because which one dominates changes with the data — it has changed three
times here — and a caveat that must be rewritten every time the data moves is one
that will eventually be wrong. This is the same failure the agent's provenance
checker guards in generated text.

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
| `GET /api/v1/analytics/estimated-scores` | Model-estimated overall scores with `is_estimated`, per-row support flag and distance, the model run that produced them, and the model-estimate caveat |
| `GET /api/v1/analytics/disagreement-risk` | Modelled probability that THE places a university differently from QS, with the same per-row disclosure plus a caveat stating that a probability is not a finding |
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
- [COMPETITION_TRACK.md](../competition/COMPETITION_TRACK.md) — competition positioning and differentiators
- [ANALYTICS_SURFACE_PLAN.md](ANALYTICS_SURFACE_PLAN.md) — analytics surface planning
- [DEMO_HONESTY_GUIDELINES.md](../demo/DEMO_HONESTY_GUIDELINES.md) — required demo disclosure
