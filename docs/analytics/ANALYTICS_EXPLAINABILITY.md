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

N and M describe one table: the global universe of the default edition, which is
what the trends and source-disagreement endpoints serve. N is the universities in
it with a rank from that source; M is the number of universities in it, counted,
not taken from the largest source. The view also holds region, regional, special
and subject universes that only QS populates, and the counts once ran across all
of them — so the caveat read "THE covers 1637 of 9862" while QS, the largest count,
looked complete and disclosed nothing.

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

The snapshot row above names a source and the editions that source covers, and a
year written into a constant is a disclosure with an expiry date — the same
failure as the old "RC-1 packaging" age. It is therefore rendered from a
template. Each language keeps exactly one copy of it, filled from its own copy of
the coverage map: `DATASET_COVERAGE` in `crawlernest/core/dataset.py`,
`DatasetScope.DATASET_COVERAGE`, and `DATASET_COVERAGE` in
`crawlernest-web/src/lib/datasetScope.ts`, whose union is the `DATASET_YEARS`
list beside each of them. `test_caveat_contract.py` checks that the three maps,
the three lists and the three templates agree. The row in the table is what the
template renders for QS today.

**The source is a slot for the same reason the years are.** It was the literal
"QS" until the 2015–2024 ARWU release. Ten of the twelve editions the warehouse
now holds carry no QS row at all, so a sentence opening "QS ranking data" could
not describe the edition a reader was looking at — and `editionCaveats(2018)`
would have printed exactly that beside a table containing no QS rank. Each
renderer therefore refuses to render a source over an edition
`DATASET_COVERAGE` does not give it: the false sentence is unwritable rather
than merely discouraged.

Template:

`{source} ranking data is a point-in-time snapshot of the {years} published tables. Figures may not reflect rankings republished since this snapshot was ingested.`

`{source}` is the sources being disclosed, in `DATASET_SOURCES` order, joined by
the same rule as the years: `ARWU`, `QS and THE`, `QS, THE and ARWU`. A response
showing one edition names the sources that edition holds; the warehouse-wide
`STANDARD_CAVEATS` names QS over QS's own editions.

`{years}` is the editions in ascending order, without duplicates, joined as
below. This table is the specification: the Python, Java and TypeScript renderers
are each tested against these rows.

<!-- year-list-rendering:start -->
| Editions held | `{years}` |
| --- | --- |
| 2026 | 2026 |
| 2025, 2026 | 2025 and 2026 |
| 2026, 2025 | 2025 and 2026 |
| 2024, 2025, 2026 | 2024, 2025 and 2026 |
| 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026 | 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025 and 2026 |
<!-- year-list-rendering:end -->

The last row is ARWU's coverage as of the 2015–2024 release, and is there because
a two-digit list is where a renderer that special-cases the last separator is
most likely to drift: every join is a comma except the final one, which is
` and `, with no serial comma before it at any length.

### Per-edition source coverage

An edition that does not hold every source says so, rather than leaving a reader
to infer it from an empty column. A missing rank inside an edition that *does*
hold the source is a different thing — that is the partial-coverage row above —
and conflating the two is what this disclosure prevents.

Template:

`The {year} edition holds {present} ranks only. No {absent} rank exists for this edition, so a position here rests on one source rather than on agreement between several.`

`{present}` and `{absent}` use the same source-list rule, except that `{absent}`
joins with `or`: "no QS and THE rank exists" reads as a claim about the pair
rather than about each of them. The disclosure is omitted for an edition holding
every source, so 2025 and 2026 do not carry it. It is rendered by
`edition_source_coverage_caveat` in Python, `AnalyticsService
.editionSourceCoverageCaveat` in Java, and `editionSourceCoverageCaveat` in
`caveatMessages.ts`.

### Admission caveats

Two disclosures travel with admission requirements wherever an API response
shows them: the university detail's `admissionRequirements.caveats`, the preview's
`admissionCaveats`, and `GET /api/v1/recommendations/explain`. The recommendation
list's `metadata.admission_caveats` carries the staleness caveat for the
universities it returns (the IELTS one names a single university, so it stays on
the explain endpoint).

| Condition | Required Caveat |
|---|---|
| No stored IELTS figure for the university at any scope, or no admission row at all (`v_admission_requirement_summary.ielts_missing`) | "No IELTS requirement was found in stored admission data for this university. Language fit cannot be assessed." |
| Any admission requirement is shown | `CAVEAT_ADMISSION_DATA_STALE`, rendered from one of the two templates below |

`CAVEAT_ADMISSION_DATA_STALE` has to name a date, so it is a template, with one
copy per language: `ADMISSION_STALE_*_TEMPLATE` in `crawlernest/core/caveats.py`,
`AnalyticsService.java` and `caveatMessages.ts`. The date is the **oldest** one
behind the response, as a UTC ISO date, taken from the staleness columns of
`warehouse.v_admission_requirement_institution` / `_summary`. When every row
records when its page was fetched:

`Admission requirements were read from university pages fetched on {date} and may not reflect the current year's entry conditions.`

When any row does not — every row written so far, since a run over checked-in
snapshots extracts today from HTML fetched earlier — the extraction date is named
and the fetch date is said to be unknown, never passed off as one:

`Admission requirements were read from university pages whose fetch date was not recorded. They were extracted on {date}, the pages may be older than that, and they may not reflect the current year's entry conditions.`

The requirement values these caveats accompany follow one rule, defined once in
those views: a university-level figure comes only from rows that apply to the
institution (`institution_minimum` or `unspecified`), for the newest intake they
state. Programme and faculty rows are counted and listed separately, never folded
into it; where rows still disagree the lowest bar is shown and `valuesDiffer` is
set.

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

#### Editions the model does not cover

The warehouse holds twelve ranking editions; the scoring job has been run over
one of them (QS 2026). So an estimate read can come back empty for two different
reasons, and only one of them is about the universities asked for:

| Situation | What the response says |
| --- | --- |
| The edition is modelled, these universities have no estimate | nothing — the empty list is the answer, and a caveat would claim a limitation the response does not have |
| The edition is not modelled | "No model estimates exist for the 2018 edition. The modelling layer has only been run over 2026, so this is a gap in what this platform modelled rather than a judgement that the 2018 edition cannot be estimated." |
| The modelling tables are absent | "No model estimates are available. The modelling layer has not been run against this database." |

Before the 2015–2024 ARWU release, `resolve_ranking_year` rejected 2018 outright
and an agent asking for 2018 estimates received a refusal it could repeat.
Holding those editions made the same request valid, so it now reaches the query
and returns zero rows: without the middle row of that table, releasing ten
editions would have converted an honest refusal into silence.

The covered editions are read from `analytics.v_ml_predictions_latest`, not
declared alongside `DATASET_YEARS`. A constant would be a second source of truth
about a table the caveat layer does not own, and the one failure worse than
silence here is telling a reader an edition was never modelled after someone has
modelled it. `MlService.covered_years()` is exempted in
`test_year_isolation_audit.py` on the ground that the edition is what the read
returns rather than what it filters on.

This disclosure is agent-side only. `getEstimatedScores` and
`getDisagreementRisk` pin `ranking_year` to `DatasetScope.defaultRankingYear()`,
so the Java endpoints cannot be asked about another edition and never need it.

### Caveat Delivery

Caveats are delivered in two places:

1. **API response** — `caveats` array in the response metadata:
   ```json
   {
     "success": true,
     "data": { ... },
     "metadata": {
       "caveats": [
         "QS (Quacquarelli Symonds) covers 1502 of 2098 universities. A missing QS rank means either that the QS data ingested here does not include the university or that this platform could not match it — not that QS does not rank it.",
         "THE (Times Higher Education) covers 1637 of 2098 universities. A missing THE rank means either that the THE data ingested here does not include the university or that this platform could not match it — not that THE does not rank it.",
         "ARWU (Academic Ranking of World Universities) covers 838 of 2098 universities. A missing ARWU rank means either that the ARWU data ingested here does not include the university or that this platform could not match it — not that ARWU does not rank it.",
         "QS ranking data is a point-in-time snapshot of the 2025 and 2026 published tables. Figures may not reflect rankings republished since this snapshot was ingested.",
         "Composite ranks are not compared between editions. A university's composite position moves whenever source coverage changes, so rank movement is reported per source on each university's page instead."
       ]
     }
   }
   ```

   The coverage counts are generated by `AnalyticsService.appendSourceCoverageCaveats`
   from `analytics.v_aggregated_rankings_latest`, so they move with the data. The figures
   above are a verbatim capture of `GET /api/v1/analytics/ranking-trends` on 2026-09-14,
   with the 2025 and 2026 editions held; treat them as an illustration of the shape, not
   a fixed baseline. `GET /api/v1/analytics/source-disagreement` carries the same three
   rows, and its `missing_source_coverage` block counts the same table (1,502 + 596,
   1,637 + 461, 838 + 1,260 of 2,098). All three sources are listed because none covers
   the whole global table; a source that did would get no caveat.

2. **Frontend** — Analytics Caveats section on the `/analytics` page,
   prominently displayed, not collapsed or hidden.

### Caveat Tone

Caveats are stated professionally and informatively. They are not apologetic.
A caveat explains what the limitation is and what the user can rely on.

**Acceptable:** "ARWU covers 838 of 2098 universities." — the number, not an
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
