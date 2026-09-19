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
editions QS covers, and a year written into a constant is the same kind of
expiring disclosure the old "RC-1 packaging" age was. The template has one copy
per language -- ``SNAPSHOT_CAVEAT_TEMPLATE`` here, in ``AnalyticsService`` and in
``caveatMessages.ts`` -- and ``ANALYTICS_EXPLAINABILITY.md`` holds the rule for
rendering a list of years, which each language's renderer is tested against.

The source in that sentence is a slot for the same reason the years are. It was
a literal "QS" until the 2015-2024 ARWU release gave the warehouse ten editions
with no QS row in them, at which point a sentence that opens "QS ranking data"
could no longer describe the edition a reader was looking at. Which sources hold
which editions is :data:`crawlernest.core.dataset.DATASET_COVERAGE`, and
:func:`snapshot_caveat` raises rather than render a source over an edition it
does not cover -- the check that makes the false version unwritable instead of
merely discouraged.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime

from crawlernest.core.dataset import (
    DATASET_COVERAGE,
    DATASET_SOURCES,
    DATASET_YEARS,
    sources_for_year,
)

#: Byte-identical in Java, TypeScript and the explainability doc. ``{source}``
#: and ``{years}`` are replaced literally, never through str.format, so the three
#: renderers cannot disagree about escaping.
#:
#: The source used to be written into the sentence. That was safe while every
#: edition held QS, and became a false disclosure with the 2015-2024 ARWU
#: release: ten of the twelve editions hold no QS row, so a sentence beginning
#: "QS ranking data" could not describe them. Naming the source is now the
#: caller's job, and :func:`snapshot_caveat` will not let a caller name one that
#: does not cover the editions it is about.
SNAPSHOT_CAVEAT_TEMPLATE = (
    "{source} ranking data is a point-in-time snapshot of the {years} published tables. "
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


def format_sources(sources: Iterable[str], conjunction: str = "and") -> str:
    """Sources as prose, in DATASET_SOURCES order: ``ARWU``, ``QS and THE``.

    The same list rule :func:`format_edition_years` uses, so a reader meets one
    way of writing a list across every caveat. ``conjunction`` is "or" for a list
    inside a negation: "no QS and THE rank exists" reads as a claim about the
    pair, when what is meant is that neither has one.
    """
    named = [source for source in DATASET_SOURCES if source in set(sources)]
    unknown = sorted(set(sources) - set(DATASET_SOURCES))
    ordered = named + unknown
    if not ordered:
        raise ValueError("a snapshot caveat has to name at least one source")
    if len(ordered) == 1:
        return ordered[0]
    return f"{', '.join(ordered[:-1])} {conjunction} {ordered[-1]}"


def snapshot_caveat(
    source: str | Iterable[str] = "QS",
    years: Iterable[int] = DATASET_YEARS,
) -> str:
    """The snapshot disclosure for one or more sources over the editions given.

    Refuses a source that does not cover every edition named, because that is the
    disclosure this function exists to prevent: the sentence asserts that the
    named source published the named tables, and for ten of the twelve editions
    held, QS did not.
    """
    sources = (source,) if isinstance(source, str) else tuple(source)
    editions = tuple(sorted({int(year) for year in years}))
    for name in sources:
        covered = set(DATASET_COVERAGE.get(name, ()))
        missing = [year for year in editions if year not in covered]
        if missing:
            raise ValueError(
                f"{name} holds no ranks for {format_edition_years(missing)}; a snapshot "
                f"caveat naming it would claim published tables that are not in the warehouse"
            )
    return SNAPSHOT_CAVEAT_TEMPLATE.replace("{source}", format_sources(sources)).replace(
        "{years}", format_edition_years(editions)
    )


def edition_snapshot_caveat(year: int) -> str:
    """The snapshot disclosure for one edition, naming the sources that hold it.

    What a page showing a single edition should carry. For 2026 that is every
    source; for 2018 it is ARWU alone, and saying "QS" there would be the false
    sentence this whole arrangement exists to make unsayable.
    """
    sources = sources_for_year(year)
    if not sources:
        raise ValueError(f"the warehouse holds no edition {year}")
    return snapshot_caveat(sources, (year,))


#: An edition that does not hold every source says so, rather than leaving a
#: reader to infer it from an absent rank. Without this, the 2015-2024 editions
#: would present a single-source position with nothing stating that the other two
#: sources are not merely sparse here but entirely absent.
EDITION_SOURCE_COVERAGE_TEMPLATE = (
    "The {year} edition holds {present} ranks only. No {absent} rank exists for this edition, "
    "so a position here rests on one source rather than on agreement between several."
)


def edition_source_coverage_caveat(year: int) -> str | None:
    """Which sources an edition is missing, or None when it holds them all."""
    present = sources_for_year(year)
    absent = tuple(source for source in DATASET_SOURCES if source not in present)
    if not present or not absent:
        return None
    return (
        EDITION_SOURCE_COVERAGE_TEMPLATE.replace("{year}", str(year))
        .replace("{present}", format_sources(present))
        .replace("{absent}", format_sources(absent, "or"))
    )


#: Ranking data is a snapshot, and says so without naming an age. The previous
#: wording carried one and was wrong within hours of the next crawl.
#:
#: Rendered over QS's own editions rather than over DATASET_YEARS. Those were the
#: same list until the 2015-2024 ARWU release; rendering it from the union would
#: now name ten editions in which QS published nothing here. The sentence this
#: constant holds is unchanged -- which is the point: the release made it true
#: rather than rewriting it.
CAVEAT_QS_STALE = snapshot_caveat("QS", DATASET_COVERAGE["QS"])

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
#: 351 of the 787 overall-score estimates -- 45% -- sit outside the data the
#: model was fitted on, and they are systematically lower than the supported ones
#: (mean 11.8 against 18.9), which is exactly where extrapolation is least worth
#: trusting. ESTIMATED_VALUE_CAVEAT promises the reader a support flag; without
#: this one, nothing tells them the flag is set to false for almost half the rows.
#: (Counts from the 2026-09-14 run on the edition-verified QS 2026 snapshot.)
UNSUPPORTED_ESTIMATE_CAVEAT = (
    "Some estimates here fall outside the data the model was fitted on and are marked "
    "unsupported. The model has seen no comparable cases for them. That is a statement "
    "about the evidence behind the estimate, not a measurement of how wrong it is."
)

#: Carried wherever a per-source rank change is shown (rankDelta on a source
#: ranking). Movement is computed by crawlernest/core/rank_delta.py and
#: clawer.service.SourceRankDelta, source by source from printed ranks; this says
#: the three things a reader would otherwise assume the other way.
RANK_CHANGE_CAVEAT = (
    "Rank changes compare one source's published ranks between two editions. They are not "
    "changes in a composite or platform rank, a banded rank gives a range rather than a "
    "number, and no change is shown when the institution or its source entry changed "
    "between editions."
)

#: Carried by the trends surface once more than one edition is held. It pairs a
#: university's editions but deliberately reports no composite movement.
COMPOSITE_RANK_NOT_COMPARED_CAVEAT = (
    "Composite ranks are not compared between editions. A university's composite position "
    "moves whenever source coverage changes, so rank movement is reported per source on each "
    "university's page instead."
)

#: Shown when a university has no stored IELTS figure at any scope
#: (warehouse.v_admission_requirement_summary.ielts_missing), or no admission row
#: at all. Byte-identical to AnalyticsService.IELTS_MISSING_CAVEAT and to
#: CAVEAT_IELTS_MISSING in caveatMessages.ts.
CAVEAT_IELTS_MISSING = (
    "No IELTS requirement was found in stored admission data for this university. "
    "Language fit cannot be assessed."
)

#: CAVEAT_ADMISSION_DATA_STALE is a template, not a constant, because it has to
#: name a date. It used to say only that requirements "are scraped and may not
#: reflect the current year's entry conditions" -- true, and no help to a reader
#: deciding whether a figure is last month's or three years old.
#:
#: Two templates, because every admission row written so far has no fetch time:
#: runs over checked-in snapshots extract today from HTML fetched earlier, and
#: calling the extraction date a fetch date would understate the page's age.
ADMISSION_STALE_FETCHED_TEMPLATE = (
    "Admission requirements were read from university pages fetched on {date} and may not "
    "reflect the current year's entry conditions."
)

ADMISSION_STALE_UNDATED_TEMPLATE = (
    "Admission requirements were read from university pages whose fetch date was not recorded. "
    "They were extracted on {date}, the pages may be older than that, and they may not reflect "
    "the current year's entry conditions."
)


def admission_stale_caveat(
    *,
    fetch_dates_recorded: bool,
    oldest_fetched_on: date | str | None,
    oldest_extracted_on: date | str | None,
) -> str | None:
    """CAVEAT_ADMISSION_DATA_STALE for the admission rows behind a response.

    The inputs are the staleness columns of the admission views, combined over
    every university a response shows: all fetch dates recorded, the oldest fetch
    date, the oldest extraction date (UTC dates). The oldest, because a
    disclosure about the freshest row would understate the rest.

    The fetched template needs every row to carry a fetch date. Otherwise the
    undated one names the extraction date and says the fetch date is unknown.
    None when there is no admission data to disclose anything about.
    """
    if fetch_dates_recorded and oldest_fetched_on is not None:
        return ADMISSION_STALE_FETCHED_TEMPLATE.replace("{date}", _iso_date(oldest_fetched_on))
    if oldest_extracted_on is not None:
        return ADMISSION_STALE_UNDATED_TEMPLATE.replace("{date}", _iso_date(oldest_extracted_on))
    return None


def admission_caveats(summary: Mapping[str, object] | None) -> list[str]:
    """The admission caveats for one university, from its summary-view row.

    ``summary`` is a row of warehouse.v_admission_requirement_summary as a
    mapping, or None when the university has no admission row -- which is itself
    an IELTS gap.
    """
    if summary is None:
        return [CAVEAT_IELTS_MISSING]
    caveats: list[str] = []
    if summary.get("ielts_missing"):
        caveats.append(CAVEAT_IELTS_MISSING)
    stale = admission_stale_caveat(
        fetch_dates_recorded=bool(summary.get("fetch_dates_recorded")),
        oldest_fetched_on=summary.get("oldest_fetched_on"),  # type: ignore[arg-type]
        oldest_extracted_on=summary.get("oldest_extracted_on"),  # type: ignore[arg-type]
    )
    if stale:
        caveats.append(stale)
    return caveats


def _iso_date(value: date | str) -> str:
    if isinstance(value, datetime):
        raise TypeError("pass a UTC date, not a timestamp: the views already convert to UTC")
    return value.isoformat() if isinstance(value, date) else str(value)[:10]


#: The standard set every recommendation and analytics surface carries. Mirrors
#: RC1_STANDARD_CAVEATS in caveatMessages.ts and RecommendationEvidenceService.
STANDARD_CAVEATS: tuple[str, ...] = (
    CAVEAT_QS_STALE,
    CAVEAT_THE_PARTIAL,
    CAVEAT_ARWU_PARTIAL,
)


def edition_caveats(year: int) -> tuple[str, ...]:
    """The standard set for a response showing one edition.

    :data:`STANDARD_CAVEATS` describes the release, which is the wrong scope for
    one edition: it opens with QS's snapshot beside a 2018 table holding no QS
    rank, and carries a THE coverage line for an edition with no THE row to be
    partial about. ``AnalyticsService.editionCaveats`` and ``editionCaveats`` in
    caveatMessages.ts compose the same list from the same pieces.
    """
    sources = sources_for_year(year)
    if not sources:
        return STANDARD_CAVEATS
    caveats = [edition_snapshot_caveat(year)]
    coverage = edition_source_coverage_caveat(year)
    if coverage:
        caveats.append(coverage)
    # A partial-coverage line describes a source that is present and sparse, so
    # each belongs only to an edition that actually holds that source.
    if "THE" in sources:
        caveats.append(CAVEAT_THE_PARTIAL)
    if "ARWU" in sources:
        caveats.append(CAVEAT_ARWU_PARTIAL)
    return tuple(caveats)
