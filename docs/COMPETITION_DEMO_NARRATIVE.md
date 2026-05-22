# Competition Demo Narrative

This document defines the demo flow, talking points, and required disclosures
for the CrawlerNest Competition Track presentation. It also defines what must
NOT be claimed and what is intentionally limited at RC-1.

---

## The Problem

University rankings are opaque. A student or advisor looking at a ranking sees
a number — but not why it is that number, which sources contributed, how much
those sources agree, or how confident the aggregated rank is.

This opacity matters because:
- Different ranking bodies (QS, THE, ARWU) often disagree significantly
- A university ranked 50 by one source and 150 by another is in an uncertain
  position — but that uncertainty is invisible in a single published number
- Historical rank movement requires access to multiple years of data from
  multiple sources, which is not typically surfaced in a usable form

---

## What CrawlerNest Solves

CrawlerNest makes university ranking data transparent and traceable:

1. **Multi-source aggregation with explainability.** A single aggregated rank
   is computed from QS, THE, and ARWU using a documented, deterministic formula.
   Every rank can be unpacked to show source contributions, normalized scores,
   weights, and confidence level.

2. **Source disagreement as signal.** When sources disagree, that disagreement
   is surfaced — not hidden. The analytics surface shows which universities
   have the largest cross-source rank spread and why.

3. **Honest data posture.** The platform discloses what it does not have:
   stale data, unavailable sources, and incomplete coverage are labeled as such
   at every surface — API, frontend, and demo.

---

## Demo Flow

### Step 1: Open the Rankings Page

Show the global rankings page at `http://localhost:3000/`. Point out:
- 1,499 aggregated universities from QS source
- Filter by country, region, year
- The aggregated rank is computed, not scraped

### Step 2: Explain a Specific University

Click on a top university. Show the source comparison:
- Navigate to the university detail or use `GET /api/v1/universities/{id}/source-comparison`
- Demonstrate: "This rank is not just a number — it's derived from X sources.
  Here is what each source says, how their scores were normalized, and how much
  they agree."

### Step 3: Open the Analytics Page

Navigate to `/analytics`. Walk through:

**Ranking Trends:**
- "We can see how universities have moved year over year [IF multi-year data
  available]. Where only one year of data exists, we show that honestly —
  we do not extrapolate or project."

**Source Disagreement:**
- "These are the universities where QS and the available sources disagree most.
  A large rank spread is itself meaningful information — it tells you that
  confidence in the aggregated rank is lower."

**Source Coverage:**
- "At RC-1, THE and ARWU data are not yet available. Every university in this
  dataset has QS coverage. When THE and ARWU are added, source agreement
  analysis becomes meaningfully multi-source."

**Analytics Caveats:**
- Read the caveats section directly to the audience. Do not skip it.
- "We show you exactly what limitations this data has. That is a feature,
  not a weakness."

### Step 4: Show the Diagnostics Layer

Navigate to `/system-status` or `/data-quality`. Point out:
- Data freshness state and last ingestion timestamp
- Source availability status
- Aggregation run history

"You can see exactly when the data was last updated and what the operational
state of the pipeline is. This is operational credibility — we do not hide
the infrastructure behind the numbers."

---

## Key Talking Points

- "Every rank is explainable. We can show you the formula, the sources, and
  the weights for any university in the system."

- "We surface disagreement. When QS says 50 and THE says 150, we show both
  numbers and tell you the spread is 100. That uncertainty is real information."

- "We are honest about what we do not have. THE and ARWU are not available
  in this release. We say so clearly rather than pretending the data is complete."

- "This is not AI-generated ranking synthesis. The formula is deterministic,
  version-tracked, and public. You can reproduce any output given the same
  source data."

- "The confidence level is derived from source coverage — not asserted. One
  source = low confidence. Three sources = high confidence. The system tells
  you which is which."

---

## What NOT to Claim

These claims would be dishonest at RC-1. Do not make them.

| Claim | Why Not |
| --- | --- |
| "Data is fully up to date." | QS data is ~354 hours stale. THE/ARWU not available. |
| "We cover all major ranking sources." | THE and ARWU are not available at RC-1. |
| "AI-powered recommendations." | The recommendation engine is deterministic; no ML model is used. |
| "Predictive ranking forecasting." | No historical depth for trend prediction at RC-1. |
| "Real-time data." | Batch ingestion; no streaming pipeline. |
| "Subject rankings are comprehensive." | Subject data is incomplete at RC-1. |
| "Multi-source agreement analysis." | At RC-1, only QS is available — all universities are single-source. |

---

## What Is Intentionally Limited at RC-1

These are not failures — they are scoped limitations that the platform
discloses honestly.

| Limitation | What Is Available Instead |
| --- | --- |
| THE data unavailable | QS global rankings fully ingested (1,499 universities) |
| ARWU data unavailable | Aggregation framework ready for ARWU when available |
| Subject rankings incomplete | Global rankings complete and aggregated |
| Single-year aggregated data | Year-over-year trend analysis available when second year runs |
| Localhost-only deployment | Full operational stack, not a mock |
| Limited historical depth | Historical evidence preserved in snapshot system |

---

## Required Caveats During Demo

These must be stated verbally during any demo presentation. They are not optional.

1. "The ranking data was ingested at RC-1 packaging and has not been refreshed.
   Data age is approximately 354 hours."

2. "THE and ARWU data are not available in this demo. Source agreement analysis
   and multi-source confidence assessment will improve when these sources are added."

3. "Subject ranking coverage is incomplete. Subject analytics are not available
   in this release."

4. "This is a localhost demonstration. The architecture is production-ready but
   the deployment is not production-scale."

See `docs/DEMO_HONESTY_GUIDELINES.md` for acceptable and unacceptable phrasing.

---

## Closing Statement

"CrawlerNest is not the most confident university ranking platform you will see
today. It is the most honest one. Every limitation is labeled. Every rank is
explainable. Every caveat is stated. That operational honesty is the foundation
for building something that earns trust — rather than something that looks
impressive until someone asks a hard question."

---

## Boundary

This document defines the demo narrative. It does not constrain what the
audience can ask. If asked a question the platform cannot honestly answer,
say so. Improvising claims beyond what the data supports violates the
operational honesty principle this platform is built on.

See also:
- [COMPETITION_TRACK.md](COMPETITION_TRACK.md) — competition positioning
- [ANALYTICS_EXPLAINABILITY.md](ANALYTICS_EXPLAINABILITY.md) — explainability requirements
- [DEMO_HONESTY_GUIDELINES.md](DEMO_HONESTY_GUIDELINES.md) — required phrasing guidance
- [STABLE_DEGRADED_STATE.md](STABLE_DEGRADED_STATE.md) — current data posture
