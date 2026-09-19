"""What the warehouse actually contains, stated once so nothing has to guess.

Two facts about this release are load-bearing and were, until now, re-asserted
independently by every caller that needed them: which editions the warehouse
holds, and which sources are actually in it. They are one fact now --
:data:`DATASET_COVERAGE` -- because as of the 2015-2024 ARWU release the answer
to the first depends on which source is being asked about.

The second fact changed and nothing noticed. QS was the only ingested source for
most of this project's life, and a good deal of prose still says so -- the repo
``CLAUDE.md`` among it. As of the 2026-09-04 ingest the warehouse also carries
1,637 THE and 838 ARWU ranks for 2026. Coverage is partial and QS remains far the
largest, but "QS only" is no longer a true thing to tell a user or a model, which
is why :data:`DATASET_SOURCES` is read from here rather than written out wherever
it is needed.

Stating them here rather than in each service fixes the default-year drift. Each
caller that needed a year picked its own: a literal ``2026`` in ``RankingQuery``,
another in ``ranking_tools``, and ``datetime.now().year`` in
``recommendation_service`` -- which silently starts querying a year the warehouse
has no rows for the moment the wall clock rolls over, returning an empty result
that looks like a data problem rather than a code one. A constant cannot do that.

These are warehouse facts, so they live in ``core`` and the agent layer reads
them from here -- ``agent`` imports ``core`` and never the reverse. How the facts
are described *to a model* is a generation concern and lives in
``agent/web_agent/generation/dataset_context.py``, which re-exports both names
alongside the prose it builds from them.

Changing :data:`DATASET_YEARS` is therefore a data-migration step, not an edit: it
re-points every query default and rewrites what the model is told the corpus
contains.

Two questions used to share one constant, and they stop agreeing the moment a
second edition is loaded, so they are separate names now:

- *Which year does a query use when the caller names none?* That is
  :data:`DEFAULT_RANKING_YEAR`, one year.
- *Does the warehouse hold this year?* That is membership in
  :data:`DATASET_YEARS`. Writing it as ``year != DEFAULT_RANKING_YEAR`` would,
  after a 2025 ingest, warn a user that the 2025 data they are looking at does
  not exist.

With one edition loaded both give the answers the single constant gave.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

#: Which editions each source actually covers, newest first.
#:
#: This is the fact a flat list of years cannot state, and it stopped being
#: optional with the 2015-2024 ARWU release. ARWU reaches back to 2015; QS and
#: THE begin at 2025. The snapshot caveat names QS and rendered from
#: :data:`DATASET_YEARS`, so extending the years alone would have told every
#: reader that ten editions holding no QS row at all are "a snapshot of the QS
#: published tables" -- a specific, confident, false disclosure, the kind
#: ``docs/analytics/ANALYTICS_EXPLAINABILITY.md`` exists to prevent.
#:
#: A source belongs to a year here once the warehouse serves its ranks for that
#: year: the same standard :data:`DATASET_SOURCES` applies to sources overall.
DATASET_COVERAGE: Mapping[str, tuple[int, ...]] = MappingProxyType(
    {
        "QS": (2026, 2025),
        "THE": (2026, 2025),
        "ARWU": (2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015),
    }
)

#: Every ranking edition the warehouse holds, newest first. Membership here is
#: what "we have that year" means; nothing else should decide it.
#:
#: Derived from :data:`DATASET_COVERAGE` rather than written out, so the union
#: cannot drift from the per-source truth underneath it. Java and TypeScript
#: hold the same list as a literal and ``test_caveat_contract`` pins all three
#: together, which is what keeps a literal safe there.
#:
#: 2025 released 2026-09-14, after its shadow ingest was audited unreachable from
#: every serving surface. Every 2025 and 2026 world-ranking row was crawled
#: through crawlernest-jobs/ranking_edition.py, which proves the edition from the
#: page that names it -- the check whose absence had stored the QS 2027 table as
#: 2026. 2015-2024 released 2026-09-20 to the same standard: every row came from
#: crawlernest-jobs/arwu_crawler.py carrying verify_arwu_page_url edition proof,
#: and each edition was audited servable through the crawlernest.dataset.years
#: override before this constant moved.
DATASET_YEARS: tuple[int, ...] = tuple(
    sorted({year for years in DATASET_COVERAGE.values() for year in years}, reverse=True)
)

#: The year a query uses when the caller names none: the newest edition held.
DEFAULT_RANKING_YEAR: int = max(DATASET_YEARS)

#: Alias of :data:`DEFAULT_RANKING_YEAR`, from when there was only one year to
#: name. Kept so existing imports keep working; new code should say which of the
#: two questions above it is asking.
DATASET_YEAR = DEFAULT_RANKING_YEAR


def resolve_ranking_year(requested: int | None) -> int | None:
    """The edition a serving read should use, or ``None`` when it should read nothing.

    No year requested reads the default edition. A held year reads that year. Any
    other year -- including one loaded but not yet released, a shadow ingest --
    reads nothing, so the caller returns an empty result instead of querying.
    ``clawer.service.DatasetScope.resolveRankingYear`` is the same rule in Java.

    Operator tooling (``run_pipeline``) is not a serving read and may query a
    shadow edition on purpose; it resolves only ``None``.
    """
    if requested is None:
        return DEFAULT_RANKING_YEAR
    return requested if requested in DATASET_YEARS else None

#: Ranking sources actually ingested, largest coverage first. This tuple is what
#: is loaded, not what is anticipated: a source belongs here once the warehouse
#: holds ranks from it, and coverage being partial is not a reason to omit it --
#: claiming a source is absent while the API serves its figures is the worse
#: error of the two.
#:
#: "Largest coverage" is by rows, not by editions: QS is still the widest source
#: in the table it appears in, while ARWU is the only one reaching back to 2015.
#: :data:`DATASET_COVERAGE` is what says which is which.
DATASET_SOURCES = ("QS", "THE", "ARWU")


def sources_for_year(year: int) -> tuple[str, ...]:
    """The sources holding ranks for an edition, in :data:`DATASET_SOURCES` order.

    Empty for an edition the warehouse does not hold. ``DatasetScope.sourcesFor``
    in Java and ``sourcesForYear`` in TypeScript are the same rule; each surface
    needs it to describe the edition it is showing rather than the release as a
    whole.
    """
    return tuple(source for source in DATASET_SOURCES if year in DATASET_COVERAGE.get(source, ()))


def years_for_source(source: str) -> tuple[int, ...]:
    """The editions one source covers, newest first. Empty for an unknown source."""
    return DATASET_COVERAGE.get(source, ())
