"""The caveat strings, as Python sees them.

The repo ``CLAUDE.md`` warns that caveat text lives in more than one place and
that changing one copy usually means changing all of them. There are four copies:
``AnalyticsService`` / ``RecommendationEvidenceService`` in Java,
``caveatMessages.ts`` in the frontend, ``ANALYTICS_EXPLAINABILITY.md`` as prose,
and -- from here -- Python. Java already anchors itself to the document with
``AnalyticsCaveatContractTest``; ``test_caveat_contract`` does the same for this
module and for the frontend, so the warning is enforced rather than remembered.

Why these strings needed changing at all is worth recording, because each was
true when written:

``CAVEAT_QS_STALE``
    Named a specific age ("RC-1 packaging", and in Java "approximately 354 hours
    ago") that stopped being true the moment anything was re-crawled. All three
    sources were last ingested on 2026-09-04. An age baked into a constant is a
    disclosure with an expiry date, so this one states the snapshot without
    claiming a distance from it.

``CAVEAT_THE_PARTIAL`` / ``CAVEAT_ARWU_PARTIAL``
    Previously said THE and ARWU data "is not available at RC-1". The warehouse
    now carries 1,637 THE and 838 ARWU ranks for 2026, so the old text told users
    a source was absent while the API served its figures. They now say what
    ``AnalyticsService.appendSourceCoverageCaveats`` has always said dynamically:
    coverage is partial, and a missing rank is our gap, not the source declining
    to rank.

``ESTIMATED_VALUE_CAVEAT``
    Byte-identical to ``AnalyticsService.ESTIMATED_SCORE_CAVEAT``. Anything
    reaching a user from ``analytics.ml_predictions`` must carry it -- see
    ``agent/tools/ml_tools.py``, which cannot hand back an estimate without it.

Deliberately not fixed here: ``releases/`` and ``docs/demo/`` describe the state
of a packaged demo at a point in the past. "RC-1 packaging" is the correct thing
for a historical record to say.

Year-bearing caveats are templates, not constants. ``CAVEAT_QS_STALE`` names the
editions the warehouse holds, and a year written into a constant is the same
kind of expiring disclosure the old "RC-1 packaging" age was. The template has
one copy per language -- ``SNAPSHOT_CAVEAT_TEMPLATE`` here, in
``AnalyticsService`` and in ``caveatMessages.ts`` -- and
``ANALYTICS_EXPLAINABILITY.md`` holds the rule for rendering a list of years,
which each language's renderer is tested against.
"""

from __future__ import annotations

from collections.abc import Iterable

from crawlernest.core.dataset import DATASET_YEARS

#: Byte-identical in Java, TypeScript and the explainability doc. ``{years}`` is
#: replaced literally, never through str.format, so the three renderers cannot
#: disagree about escaping.
SNAPSHOT_CAVEAT_TEMPLATE = (
    "QS ranking data is a point-in-time snapshot of the {years} published tables. "
    "Figures may not reflect rankings republished since this snapshot was ingested."
)


def format_edition_years(years: Iterable[int]) -> str:
    """Held editions as prose: ``2026``, ``2025 and 2026``, ``2024, 2025 and 2026``.

    Ascending and de-duplicated whatever order they arrive in. The rows in
    ANALYTICS_EXPLAINABILITY.md are the specification; Java and TypeScript test
    their own renderer against the same rows.
    """
    ordered = [str(year) for year in sorted({int(year) for year in years})]
    if not ordered:
        raise ValueError("a snapshot caveat has to name at least one edition")
    if len(ordered) == 1:
        return ordered[0]
    return f"{', '.join(ordered[:-1])} and {ordered[-1]}"


def snapshot_caveat(years: Iterable[int] = DATASET_YEARS) -> str:
    """The snapshot disclosure for the editions held."""
    return SNAPSHOT_CAVEAT_TEMPLATE.replace("{years}", format_edition_years(years))


#: Ranking data is a snapshot, and says so without naming an age. The previous
#: wording carried one and was wrong within hours of the next crawl. Rendered
#: from DATASET_YEARS; for the single 2026 edition it is the exact sentence this
#: constant has always held.
CAVEAT_QS_STALE = snapshot_caveat()

#: Partial coverage, phrased so absence is attributed to this platform rather
#: than to the source. Mirrors the wording AnalyticsService generates per source.
CAVEAT_THE_PARTIAL = (
    "THE (Times Higher Education) covers part of this dataset. A missing THE rank means "
    "either that the THE data ingested here does not include the university or that this "
    "platform could not match it. It does not mean THE declines to rank it."
)

CAVEAT_ARWU_PARTIAL = (
    "ARWU (Academic Ranking of World Universities) covers part of this dataset. A missing "
    "ARWU rank means either that the ARWU data ingested here does not include the "
    "university or that this platform could not match it. It does not mean ARWU declines "
    "to rank it."
)

#: Byte-identical to AnalyticsService.ESTIMATED_SCORE_CAVEAT and to the copy in
#: docs/analytics/ANALYTICS_EXPLAINABILITY.md. test_caveat_contract fails if any
#: of the three drift apart.
ESTIMATED_VALUE_CAVEAT = (
    "Some values in this response are model estimates produced by CrawlerNest, not figures "
    "published by the ranking source. Estimated values are labelled as estimates, carry a "
    "support flag, and never replace a published rank."
)

#: A disagreement probability is a second kind of estimate, and the one most
#: easily misread: it is the model's guess at whether two sources *would* differ,
#: not a difference anyone observed. For most universities scored by it, THE has
#: no rank at all, so there is no disagreement to have measured.
DISAGREEMENT_ESTIMATE_CAVEAT = (
    "Cross-source disagreement probability is a model estimate of how likely QS and THE "
    "are to disagree about a university, not an observed difference between published "
    "ranks. A probability is not a rank gap, and most scored universities carry no THE "
    "rank to compare against."
)

#: Support is a statement about the evidence behind an estimate, not its error.
#:
#: 295 of the 795 overall-score estimates -- 37% -- sit outside the data the
#: model was fitted on, and they are systematically lower than the supported ones
#: (mean 13.5 against 18.5), which is exactly where extrapolation is least worth
#: trusting. ESTIMATED_VALUE_CAVEAT promises the reader a support flag; without
#: this one, nothing tells them the flag is set to false for a third of the rows.
UNSUPPORTED_ESTIMATE_CAVEAT = (
    "Some estimates here fall outside the data the model was fitted on and are marked "
    "unsupported. The model has seen no comparable cases for them. That is a statement "
    "about the evidence behind the estimate, not a measurement of how wrong it is."
)

#: The standard set every recommendation and analytics surface carries. Mirrors
#: RC1_STANDARD_CAVEATS in caveatMessages.ts and RecommendationEvidenceService.
STANDARD_CAVEATS: tuple[str, ...] = (
    CAVEAT_QS_STALE,
    CAVEAT_THE_PARTIAL,
    CAVEAT_ARWU_PARTIAL,
)
