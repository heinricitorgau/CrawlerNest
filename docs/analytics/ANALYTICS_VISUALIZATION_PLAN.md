# Analytics Visualization Plan

CrawlerNest Phase 3 defines which analytics and explainability visualizations are most valuable
for competition demonstration and why. Each visualization is evaluated on five axes.

## Design Principles

- **Data-first**: every visualization shows real stored data, not synthetic inference
- **Explainability-first**: the source of every number is visible or stated
- **Operational honesty**: limitations are shown alongside data, not suppressed
- **Conservative UI**: no flashy animations, no AI-aesthetic, no enterprise telemetry look
- **Evidence-backed**: every visualization links back to a source in the database

---

## 1. Rank Delta Visualization

**What:** Year-over-year rank movement for aggregated universities — upward/downward colored chips
(green = rank improved, red = rank worsened) with the delta value.

**Value:** Demonstrates multi-year aggregation capability and trend signal extraction.

**Explainability:** Delta is computed from `analytics.aggregated_rankings` rows across years.
Shown only when two years of data exist; never synthesized from a single year.

**Competition Impact:** High — shows the platform can surface trend signals that raw ranking lists
don't surface.

**Implementation Complexity:** Low — data already returned by `/api/analytics/ranking-trends`;
`DeltaChip` renders the green/red badge.

**Operational Honesty:** When only one year exists, `single_year_only: true` triggers a
"Historical comparison is currently limited." banner. No fake trend is synthesized.

---

## 2. Source Disagreement Severity

**What:** Rank spread between sources classified as High / Medium / Low severity, rendered as
colored chips in the analytics disagreement table.

**Value:** Converts a raw spread number into a human-readable signal about how much confidence
to place in the aggregated rank.

**Explainability:** Severity derived deterministically from spread value:
- ≥ 200 rank positions → High disagreement
- ≥ 50 rank positions → Medium disagreement
- < 50 rank positions → Low disagreement

Formula is in `src/lib/analyticsPresentation.ts` (`spreadToSeverity`). Reviewable by inspection.

**Competition Impact:** High — judges can immediately see which universities have uncertain
consensus rather than reading raw numbers.

**Implementation Complexity:** Low — purely frontend; `spreadToSeverity()` + `severityConfig()`.

**Operational Honesty:** At RC-1 with only QS data, high spread is largely a single-source
artifact. The Operational Posture section states this explicitly.

---

## 3. Source Coverage and Availability

**What:** Per-source availability badges (QS ✓ Available, THE — Unavailable, ARWU — Unavailable)
visible on the analytics source coverage section and on each recommendation explain panel.

**Value:** Makes the single-source limitation explicitly visible rather than hidden in a footnote.

**Explainability:** Derived from `covered_pct` in `/api/analytics/source-disagreement`. If
`covered_pct = 0`, the source is shown as Unavailable.

**Competition Impact:** Very High — operational honesty is a key differentiator of this platform.

**Implementation Complexity:** Low — CSS badge toggle; no backend change required.

**Operational Honesty:** THE and ARWU are shown as "Unavailable" with an explanatory note that
this is an RC-1 limitation, not a permanent state.

---

## 4. Confidence Visualization

**What:** Visual confidence bar in the recommendation explain panel showing `dataConfidence` as a
percentage bar with a labeled score.

**Value:** Turns a bare percentage into a visually scannable signal that distinguishes high vs.
low confidence at a glance.

**Explainability:** Confidence derived from source coverage completeness (65%) + source agreement
(35%). Formula is documented in `docs/RECOMMENDATION_EVIDENCE_MODEL.md`. Not AI-generated.

**Competition Impact:** High — removes the "black box" perception of confidence scores.

**Implementation Complexity:** Low — a CSS bar rendered from `explain.dimensions.dataConfidence`.

**Operational Honesty:** Label explicitly states "Derived from source coverage and data
completeness. Not AI-generated."

---

## 5. Recommendation Evidence Chain

**What:** Section heading "Evidence Chain" on the recommendation explain panel, grouping stored
reason strings and warning signals under an explicit evidence label.

**Value:** Makes explicit that each reason comes from stored database values, not a generative
model.

**Explainability:** Each reason string is produced by the scoring algorithm from stored DB values;
none are synthesized at display time.

**Competition Impact:** Medium-High — reframes the explain panel as a traceable evidence log
rather than a chatbot output.

**Implementation Complexity:** Low — UI label change only; no logic change.

**Operational Honesty:** Warnings surface data gaps (e.g., IELTS missing) rather than
suppressing them.

---

## 6. Operational Posture Surface

**What:** A dedicated section on the analytics page showing:
- Source availability (QS/THE/ARWU availability badges)
- Confidence distribution posture (Mostly High / Mixed / Mostly Low)
- Pointer to `/system-status` for freshness detail

**Value:** Demonstrates that the platform is self-aware about its limitations — it knows what
data it has and doesn't have, and states this publicly.

**Explainability:** Source availability from `missing_source_coverage` response.
Confidence posture from `confidence_buckets`. No synthetic inference.

**Competition Impact:** Very High — differentiates the platform from systems that simply show
confident-looking dashboards without disclosing data quality.

**Implementation Complexity:** Low — renders existing API data in a structured format.

**Operational Honesty:** Explicitly shows THE and ARWU as "Unavailable" with an explanatory note.

---

## 7. Analytics Caveats Visibility

**What:** Amber-highlighted caveat list at the bottom of the analytics page, sourced from API
response envelopes.

**Value:** Forces the demo audience to encounter data limitations before drawing conclusions.

**Explainability:** Caveats come from the backend response metadata, not hardcoded in the
frontend.

**Competition Impact:** Medium — validates the platform's honest data posture.

**Implementation Complexity:** Already implemented — section exists.

**Operational Honesty:** Caveats are shown unconditionally, not behind a toggle.

---

## Deferred Visualizations

These are intentionally out of scope for RC-1 and Phase 3:

| Visualization | Reason Deferred |
|---|---|
| Multi-source rank agreement scatter plot | Requires THE/ARWU data (not available at RC-1) |
| Year-over-year trend lines | Requires second year of aggregated data |
| Subject ranking comparison chart | Subject data incomplete at RC-1 |
| Real-time freshness gauge | Requires streaming pipeline (batch only at RC-1) |
| Predictive rank forecast | No historical depth; would synthesize fake data |
| AI-generated insight summaries | Violates evidence-backed principle |

---

## Consistency Implementation

All visualizations use shared helpers from `src/lib/analyticsPresentation.ts`:

| Helper | Purpose |
|---|---|
| `confidenceConfig(level)` | Badge color + bar fill + approximate percentage |
| `spreadToSeverity(spread)` | Convert rank spread number to High/Medium/Low |
| `severityConfig(severity)` | Badge colors for severity level |
| `sourceAvailabilityConfig(available)` | Badge colors + icon for availability |
| `stalenessLabel(ageHours)` | Human-readable freshness description |
| `stalenessBadgeCls(ageHours)` | Badge CSS for freshness state |
| `confidencePostureLabel(buckets)` | Derives posture label from confidence distribution |
