"""The QS universes this pipeline crawls, and which *kind* of ranking each one is.

Two different products, told apart by ``ranking_scope``
------------------------------------------------------
QS publishes both a world ranking and a set of standalone regional rankings, and
this pipeline wants both. They are not the same data:

``world_slice``
    The world ranking, filtered to a region. Ranks are *world* ranks -- NUS
    appears at 8, KFUPM at 101. One ranking id (the world one) serves every
    region; the region name drives a query filter. This is what every
    ``region:*`` universe has always produced, and the checked-in artifacts
    confirm it: region/asia holds NUS at rank 8, not at rank 3.

``regional_ranking``
    QS's separate publication for that region, with its own node id and its own
    1..N ranks -- QS Asia University Rankings puts HKU at 1. A different dataset
    answering a different question.

Until this field existed the registry described one model and implemented the
other: the labels and page URLs said "QS Asia University Rankings" while the
mechanism fetched a world slice. That mismatch is what let a stale world id sit
unnoticed across eleven universes, because sharing one id between regions is
correct under ``world_slice`` and wrong under ``regional_ranking``, and nothing
recorded which one was meant.

Consequences the code depends on
--------------------------------
* ``world_slice`` universes deliberately share the world ranking's id. The
  cache's "two universes cannot claim one id" check must not fire for them.
* ``regional_ranking`` universes each resolve their own id, and a shared id there
  really is a bug.
* A ``world_slice`` universe's ``ranking_page_url`` is the *world* ranking page,
  because that is the page carrying the id it needs.

``ranking_id`` stays None wherever a page can be resolved. QS changes node ids
every edition; reading the id off the page is what makes that self-healing, and
pinning one is how the previous id went stale. Pin only to freeze an edition on
purpose, and never copy an id between universes of different scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

#: The world ranking, narrowed to a region. World ranks, shared world id.
RANKING_SCOPE_WORLD_SLICE = "world_slice"
#: QS's own standalone ranking for that region. Its own id, its own 1..N ranks.
RANKING_SCOPE_REGIONAL = "regional_ranking"

WORLD_RANKING_PAGE = "https://www.topuniversities.com/university-rankings/world-university-rankings"


@dataclass(frozen=True)
class QSUniverseSpec:
    universe_type: str
    universe_key: str
    label: str
    ranking_id: str | None = None
    ranking_page_url: str | None = None
    region_name: str | None = None
    fetch_details: bool = False
    enable_aggregation: bool = True
    #: Which of the two products above this universe is. See the module docstring.
    ranking_scope: str = RANKING_SCOPE_REGIONAL

    @property
    def ranking_type(self) -> str:
        if self.universe_type == "global":
            return "world"
        return f"{self.universe_type}:{self.universe_key}"

    @property
    def is_world_slice(self) -> bool:
        return self.ranking_scope == RANKING_SCOPE_WORLD_SLICE


QS_GLOBAL = QSUniverseSpec(
    universe_type="global",
    universe_key="global",
    label="QS World University Rankings",
    ranking_page_url=WORLD_RANKING_PAGE,
    fetch_details=True,
    enable_aggregation=True,
    ranking_scope=RANKING_SCOPE_WORLD_SLICE,
)


def _world_slice(key: str, label: str, region_name: str) -> QSUniverseSpec:
    """A region cut out of the world ranking.

    The page URL is the world ranking's, not a per-region page. Several of the
    per-region URLs previously listed here now 404 -- QS restructured, and
    /africa-university-rankings, /oceania-university-rankings,
    /north-america-university-rankings and /latin-america-university-rankings are
    all gone. That did not matter while a hardcoded id was in use, and it would
    have silently broken every one of these universes the moment ids started
    being resolved from pages. The world page is the correct source for the id
    these universes actually need.
    """
    return QSUniverseSpec(
        universe_type="region",
        universe_key=key,
        label=label,
        ranking_page_url=WORLD_RANKING_PAGE,
        region_name=region_name,
        ranking_scope=RANKING_SCOPE_WORLD_SLICE,
    )


#: World-ranking slices. Keys, ranking_type values and artifact paths are
#: unchanged from before ranking_scope existed, so warehouse rows and checked-in
#: artifacts keep their meaning. Only the labels moved, to stop claiming to be
#: QS's separate regional publications.
QS_REGION_SPECS: dict[str, QSUniverseSpec] = {
    "europe": _world_slice("europe", "QS World Rankings — Europe", "Europe"),
    "asia": _world_slice("asia", "QS World Rankings — Asia", "Asia"),
    "latin-america": _world_slice("latin-america", "QS World Rankings — Latin America", "Latin America"),
    "arab-region": _world_slice("arab-region", "QS World Rankings — Arab Region", "Arab Region"),
    "oceania": _world_slice("oceania", "QS World Rankings — Oceania", "Oceania"),
    "africa": _world_slice("africa", "QS World Rankings — Africa", "Africa"),
    "north-america": _world_slice("north-america", "QS World Rankings — North America", "North America"),
}


def _regional(key: str, label: str, page_url: str, region_name: str) -> QSUniverseSpec:
    return QSUniverseSpec(
        universe_type="regional",
        universe_key=key,
        label=label,
        ranking_page_url=page_url,
        region_name=region_name,
        ranking_scope=RANKING_SCOPE_REGIONAL,
    )


#: QS's standalone regional rankings. Additive: new universe_type, so these get
#: their own ranking_type ("regional:asia") and their own artifact directories,
#: and nothing that reads "region:asia" changes meaning.
#:
#: Only the regions QS actually publishes appear here. There is no QS Oceania or
#: QS North America ranking -- they are absent from QS's own /regional-rankings
#: index -- so those two exist as world slices only. Latin America is published
#: as three separate rankings, not one.
QS_REGIONAL_SPECS: dict[str, QSUniverseSpec] = {
    "europe": _regional(
        "europe", "QS Europe University Rankings",
        "https://www.topuniversities.com/europe-university-rankings", "Europe",
    ),
    "asia": _regional(
        "asia", "QS Asia University Rankings",
        "https://www.topuniversities.com/asia-university-rankings", "Asia",
    ),
    "arab-region": _regional(
        "arab-region", "QS Arab Region University Rankings",
        "https://www.topuniversities.com/arab-region-university-rankings", "Arab Region",
    ),
    "sub-saharan-africa": _regional(
        "sub-saharan-africa", "QS Sub-Saharan Africa University Rankings",
        "https://www.topuniversities.com/sub-saharan-africa-university-rankings",
        "Sub-Saharan Africa",
    ),
    "caribbean": _regional(
        "caribbean", "QS World University Rankings: The Caribbean",
        "https://www.topuniversities.com/latin-america-caribbean-rankings", "The Caribbean",
    ),
    "central-america": _regional(
        "central-america", "QS World University Rankings: Central America",
        "https://www.topuniversities.com/latin-america-central-america-rankings",
        "Central America",
    ),
    "south-america": _regional(
        "south-america", "QS World University Rankings: South America",
        "https://www.topuniversities.com/latin-america-south-america-rankings", "South America",
    ),
}

QS_SUBJECT_SPECS: dict[str, QSUniverseSpec] = {
    # The pinned id currently answers HTTP 500. Subject specs carry no ranking
    # page, so there is nothing to re-resolve it from; fixing this needs a
    # subject page URL, which is its own piece of work.
    "engineering-technology": QSUniverseSpec(
        universe_type="subject",
        universe_key="engineering-technology",
        label="QS Engineering & Technology Rankings",
        ranking_id="4023765",
    ),
    "computer-science": QSUniverseSpec(
        universe_type="subject",
        universe_key="computer-science",
        label="QS Computer Science Rankings",
        ranking_id="4023722",
    ),
    "business-management": QSUniverseSpec(
        universe_type="subject",
        universe_key="business-management",
        label="QS Business & Management Rankings",
        ranking_id="4023720",
    ),
}

QS_SPECIAL_SPECS: dict[str, QSUniverseSpec] = {
    "sustainability": QSUniverseSpec(
        universe_type="special",
        universe_key="sustainability",
        label="QS Sustainability Rankings",
        ranking_page_url="https://www.topuniversities.com/sustainability-rankings",
    ),
    "mba": QSUniverseSpec(
        universe_type="special",
        universe_key="mba",
        label="QS Global MBA Rankings",
        ranking_page_url="https://www.topuniversities.com/mba-rankings/global",
    ),
    # QS Business Master's is a family of five specialisation rankings
    # (finance, marketing, management, business analytics, supply chain), each
    # with its own id. The parent page carries no id of its own, so this entry
    # can only ever fail to resolve. Left listed and disabled rather than
    # deleted, so the gap is visible instead of looking like an oversight.
    "business-masters": QSUniverseSpec(
        universe_type="special",
        universe_key="business-masters",
        label="QS Business Master's Rankings (family; no single ranking id)",
        ranking_page_url="https://www.topuniversities.com/business-masters-rankings",
        enable_aggregation=False,
    ),
}

_SPECS_BY_TYPE: dict[str, dict[str, QSUniverseSpec]] = {
    "region": QS_REGION_SPECS,
    "regional": QS_REGIONAL_SPECS,
    "subject": QS_SUBJECT_SPECS,
    "special": QS_SPECIAL_SPECS,
}


def get_qs_universe_spec(universe_type: str, universe_key: str) -> QSUniverseSpec:
    normalized_type = str(universe_type or "").strip().lower()
    normalized_key = str(universe_key or "").strip().lower()
    if normalized_type == "global":
        return QS_GLOBAL
    spec = _SPECS_BY_TYPE.get(normalized_type, {}).get(normalized_key)
    if spec:
        return spec
    raise KeyError(f"Unsupported QS universe: type={universe_type!r}, key={universe_key!r}")


def iter_all_qs_universes() -> Iterable[QSUniverseSpec]:
    yield QS_GLOBAL
    yield from QS_REGION_SPECS.values()
    yield from QS_REGIONAL_SPECS.values()
    yield from QS_SUBJECT_SPECS.values()
    yield from QS_SPECIAL_SPECS.values()


def iter_major_qs_universes() -> Iterable[QSUniverseSpec]:
    """Yield only the global ranking and the major world slices."""
    yield QS_GLOBAL
    for key in ("europe", "asia", "latin-america", "oceania", "africa"):
        spec = QS_REGION_SPECS.get(key)
        if spec:
            yield spec
