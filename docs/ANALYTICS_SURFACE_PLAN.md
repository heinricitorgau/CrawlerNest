# Analytics Surface Plan

This document plans the analytics capabilities most worth demonstrating for
the Competition Track. Each analytics item is evaluated on explainability,
implementation complexity, demo value, and operational risk.

---

## Evaluation Criteria

| Criterion | What It Means |
| --- | --- |
| **Value** | What insight does this analytics surface provide? |
| **Explainability** | Can the output be traced to source evidence? |
| **Implementation complexity** | How hard to implement with current data? |
| **Demo value** | How clearly does this showcase the platform's capabilities? |
| **Operational risk** | Risk of misleading output from limited data |

---

## Analytics Items

### 1. Source Disagreement Analysis

**Value:** Shows where QS, THE, and ARWU disagree most on the same university.
Rank spread between sources is analytically meaningful — large disagreements
indicate methodological differences between ranking bodies.

**Explainability:** High. Each disagreement is traced to source ranks: "QS ranks
MIT at 1, THE ranks it at 2, ARWU ranks it at 4. Spread = 3."

**Implementation complexity:** Low. `SourceIntelligenceService.getSourceAgreementDiagnostics()`
already implements this logic. The analytics endpoint adds honest caveats about
THE and ARWU being unavailable at RC-1.

**Demo value:** High. Showing that sources disagree — and explaining why — is a
strong differentiator from platforms that present a single number.

**Operational risk:** Medium. At RC-1 only QS data is available. THE and ARWU
are unavailable. Source disagreement analysis is effectively QS-only, which must
be disclosed. Multi-source analysis becomes available when THE/ARWU are ingested.

**Endpoint:** `GET /api/v1/analytics/source-disagreement`

---

### 2. Ranking Trend Analysis

**Value:** Shows how a university's aggregated rank has moved year over year.
Rank movement is a meaningful signal about institutional trajectory.

**Explainability:** High. Delta = current rank minus previous rank. Source counts
per year are shown. When trend data is limited (single year), this is disclosed.

**Implementation complexity:** Low-medium. Query `analytics.aggregated_rankings`
across multiple years. Join same `canonical_university_id` across years to compute
delta. If only one year exists, return `singleYearOnly: true` and no delta.

**Demo value:** Medium-high. Year-over-year movement is intuitive and relatable.
The honest `limitedCoverage` or `singleYearOnly` flag demonstrates operational
honesty rather than hiding the limitation.

**Operational risk:** Medium. At RC-1, aggregated data may be limited to a single
year (2026). Trend analysis with one year produces no delta — the endpoint returns
available data and discloses the limitation. No fake trend extrapolation.

**Endpoint:** `GET /api/v1/analytics/ranking-trends`

---

### 3. Source Coverage Analysis

**Value:** Shows which universities appear in only one source, two sources, or
all three. Single-source universities have lower confidence rankings. This
directly informs how much trust to place in an aggregated rank.

**Explainability:** High. Coverage is directly computable from `source_ranks_json`.
Each university's source count is observable, not inferred.

**Implementation complexity:** Low. Already computed as part of source agreement
diagnostics. Can be surfaced in the analytics frontend from the existing
`/api/v1/diagnostics/source-agreement` endpoint.

**Demo value:** High. Showing that some universities have robust multi-source
coverage while others rely on a single source is analytically honest and
differentiated.

**Operational risk:** Low. At RC-1, THE and ARWU are unavailable, so all
universities are effectively QS-only. The frontend discloses this. When THE/ARWU
are added, the coverage analysis becomes genuinely multi-source.

---

### 4. Country Representation Analysis

**Value:** Shows how many universities each country has in the aggregated
rankings. Useful for understanding geographic distribution and representation
gaps.

**Explainability:** High. Country count is directly derivable from
`canonical_university.country_id` joined to `v_aggregated_rankings_latest`.

**Implementation complexity:** Low. Standard GROUP BY query.

**Demo value:** Medium. Interesting for users evaluating regional coverage.
Less dramatic than source disagreement but broadly relatable.

**Operational risk:** Low. Country data is stable and well-classified.

---

### 5. Aggregation Confidence Distribution

**Value:** Shows how many universities fall into "high," "medium," and "low"
confidence tiers. Low-confidence universities have sparse source coverage.
This is a meta-signal about the quality of the overall ranking set.

**Explainability:** High. Confidence buckets are deterministic: high = 3 sources,
medium = 2 sources, low = 1 source. Formula is public.

**Implementation complexity:** Low. Confidence buckets are already computed in
`getSourceAgreementDiagnostics()`.

**Demo value:** Medium. Useful for technically-oriented reviewers. Shows that
the platform understands and discloses its own data quality.

**Operational risk:** Low. At RC-1, all universities are QS-only, so all fall
into "low" confidence. This is disclosed honestly. Confidence distribution
becomes meaningful when THE/ARWU are available.

---

## Analytics Not Planned (Non-Goals)

| Analytics Type | Why Not Planned |
| --- | --- |
| Predictive ranking forecasting | No historical depth; would require hallucination |
| ML-based university similarity | No embedding model; no training data |
| Personalized ranking weighting | Would require user behavioral model |
| Real-time ranking updates | Batch ingestion; no streaming pipeline |
| Subject ranking trend analysis | Subject data incomplete at RC-1 |
| Admission requirement correlation | Admission data not ingested at RC-1 |
| LLM-generated insight summaries | Explicitly excluded; risk of false claims |

---

## Implementation Priority Order

1. **Source Disagreement Analysis** — existing logic, add caveats, high demo value
2. **Ranking Trend Analysis** — new SQL query, honest single-year disclosure
3. **Source Coverage Analysis** — frontend display of existing data
4. **Country Representation** — low effort, adds geographic context
5. **Confidence Distribution** — already in source agreement data, show in UI

---

## Caveat Requirements

Every analytics output must include caveats. At RC-1 the required caveats are:

- `"THE and ARWU data are not available. Analysis reflects QS source only."`
- `"QS ranking data was last ingested at RC-1 packaging. Data age: ~354 hours."`
- `"Subject ranking coverage is incomplete. Subject analytics are not available."`
- For trends: `"Historical comparison requires multiple aggregation runs. Current coverage: single year."`

These caveats appear in:
1. API response metadata (`caveats` field)
2. Frontend analytics page (Analytics Caveats section)
3. Demo narrative (stated verbally)

See `docs/ANALYTICS_EXPLAINABILITY.md` for the full caveat policy.

---

## Boundary

This document plans the analytics surface. It does not commit to a delivery
timeline for items beyond Phase 1 scope. Item prioritization reflects RC-1
data posture — as additional sources are ingested, the analytics value of
items 3–5 increases significantly.
