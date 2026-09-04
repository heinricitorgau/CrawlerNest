"""What is actually true about this release, for the summary generators to quote.

Five scripts under ``scripts/`` each carried their own copy of the RC-1 posture,
and all five had gone false the same way: they asserted that QS data was stale
"since RC-1 packaging", that THE and ARWU were "not available", and that subject
ranking rows were zero. The 2026-09-04 re-crawl ingested all three sources and
1,068 subject rows, so every one of those statements now describes a warehouse
that no longer exists.

Two things made that worse than ordinary stale prose.

**The lists were suppression lists.** Their surrounding text reads "expected,
documented, non-worsening -- they do not constitute an active incident". Left as
they were, a genuine THE outage tomorrow would be reported as an expected RC-1
condition and filed under nothing to do. A suppression list that outlives the
thing it suppresses does not go quiet; it starts hiding real failures.

**One entry told the presenter to deny the ML layer.** ``WHAT_NOT_TO_CLAIM``
carried "AI-powered recommendations (scoring is deterministic, no ML model
used)". Recommendation scoring is still deterministic and that part is worth
saying, but the platform now ships two models and surfaces their estimates, so
the parenthetical instructed a speaker to state something false.

## Why there are no counts in here

The old strings carried figures -- "~354 hours", "0 records" -- and a figure in a
constant is a claim with an expiry date. Everything here is phrased so it stays
true as the warehouse changes: coverage is described as partial rather than
numbered, and anything wanting real numbers should count them at the point of
use. The API already does exactly that in
``AnalyticsService.appendSourceCoverageCaveats``.

Wording is kept consistent with ``crawlernest/core/caveats.py`` and the Java
constants, though not byte-identical -- these are spoken and summary phrasings,
not the disclosure strings themselves, so ``test_caveat_contract`` does not bind
them.
"""

from __future__ import annotations

#: Conditions that are genuinely still true of this release. Anything removed
#: from here stopped being a known-acceptable condition, which means its
#: reappearance is a regression and should be reported as one.
STABLE_CONDITIONS: tuple[str, ...] = (
    "Single ranking year (2026); no year-over-year deltas are available",
    "Subject rankings are QS-only; THE and ARWU subject data is not ingested",
    "Source coverage is partial; not every university carries a rank from every source",
    "Localhost demonstration deployment; not production-scale",
)

#: ``(indicator, value, rationale)``. Present conditions with their reasons, for
#: the steadiness summary's posture table.
DEGRADED_INDICATORS: tuple[tuple[str, str, str], ...] = (
    (
        "Source coverage",
        "partial",
        "All three sources are ingested and none covers the whole table; counted per "
        "source at request time rather than asserted here",
    ),
    (
        "Single-source universities",
        "present",
        "Confidence is derived from source count, so these read low; correct, not inflated",
    ),
    (
        "Trend depth",
        "single year (2026)",
        "No prior aggregation run to difference against; no rank delta is available",
    ),
    (
        "Subject ranking sources",
        "QS only",
        "THE and ARWU subject data is not ingested",
    ),
    (
        "Model estimate support",
        "partial",
        "Some estimates fall outside the data the model was fitted on; those carry "
        "is_supported = false and are disclosed as unsupported",
    ),
    (
        "Deployment",
        "localhost",
        "Demonstration deployment; architecture is the production shape, scale is not",
    ),
)

#: Caveats that must be stated aloud during a demo.
SPOKEN_CAVEATS: tuple[str, ...] = (
    "The ranking data is a point-in-time snapshot of the 2026 published tables.",
    "QS, THE and ARWU are all ingested, with partial coverage. A university missing a "
    "rank is missing it here; that is not the source declining to rank it.",
    "Subject rankings are QS-only.",
    "Some values are model estimates produced by CrawlerNest, not published figures. "
    "They are labelled, carry a support flag, and never replace a published rank.",
    "This is a localhost demonstration. The architecture is production-ready; the scope "
    "is intentional.",
)

#: Claims that must not be made. Each says what is true in the parenthetical, so
#: the list reads as a correction rather than a prohibition.
WHAT_NOT_TO_CLAIM: tuple[str, ...] = (
    "AI-powered recommendations (recommendation scoring is deterministic; the models "
    "estimate withheld scores and disagreement risk, and do not rank anyone)",
    "Real-time data (batch ingestion only)",
    "Complete multi-source coverage (all three sources are ingested, none covers the "
    "whole table)",
    "Comprehensive subject rankings (QS only)",
    "Predictive rank forecasting (a single year; no historical depth to forecast from)",
    "AI-generated confidence scores (confidence is derived mechanically from source count)",
    "Model estimates as published figures (they estimate a score the source withheld, "
    "and are labelled as estimates everywhere they appear)",
    "Production-scale deployment (localhost demo)",
)

#: ``(label, text)`` for the demo caveat table.
DEMO_CAVEATS: tuple[tuple[str, str], ...] = (
    ("Data freshness", "Ranking data is a point-in-time snapshot of the 2026 published tables."),
    ("Source coverage", "QS, THE and ARWU are all ingested; coverage is partial for each."),
    ("Subject rankings", "QS-only; THE and ARWU subject data is not ingested."),
    ("Trend analysis", "Single year of aggregated data; year-over-year deltas not available."),
    (
        "Model estimates",
        "Estimated overall scores and disagreement probabilities are stored separately "
        "from published ranks and labelled as estimates.",
    ),
    ("Deployment", "Localhost demonstration; not production-scale."),
)
