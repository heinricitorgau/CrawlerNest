from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


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

    @property
    def ranking_type(self) -> str:
        if self.universe_type == "global":
            return "world"
        return f"{self.universe_type}:{self.universe_key}"


QS_GLOBAL = QSUniverseSpec(
    universe_type="global",
    universe_key="global",
    label="QS World University Rankings",
    ranking_id="3990755",
    ranking_page_url="https://www.topuniversities.com/university-rankings/world-university-rankings",
    fetch_details=True,
    enable_aggregation=True,
)

QS_REGION_SPECS: dict[str, QSUniverseSpec] = {
    "europe": QSUniverseSpec(
        universe_type="region",
        universe_key="europe",
        label="QS Europe University Rankings",
        ranking_id="3990755",
        ranking_page_url="https://www.topuniversities.com/europe-university-rankings",
        region_name="Europe",
    ),
    "asia": QSUniverseSpec(
        universe_type="region",
        universe_key="asia",
        label="QS Asia University Rankings",
        ranking_page_url="https://www.topuniversities.com/asia-university-rankings",
        region_name="Asia",
    ),
    "latin-america": QSUniverseSpec(
        universe_type="region",
        universe_key="latin-america",
        label="QS Latin America University Rankings",
        ranking_page_url="https://www.topuniversities.com/latin-america-university-rankings",
        region_name="Latin America",
    ),
    "arab-region": QSUniverseSpec(
        universe_type="region",
        universe_key="arab-region",
        label="QS Arab Region University Rankings",
        ranking_page_url="https://www.topuniversities.com/arab-region-university-rankings",
        region_name="Arab Region",
    ),
    "oceania": QSUniverseSpec(
        universe_type="region",
        universe_key="oceania",
        label="QS Oceania University Rankings",
        ranking_page_url="https://www.topuniversities.com/oceania-university-rankings",
        region_name="Oceania",
    ),
    "africa": QSUniverseSpec(
        universe_type="region",
        universe_key="africa",
        label="QS Africa University Rankings",
        ranking_page_url="https://www.topuniversities.com/africa-university-rankings",
        region_name="Africa",
    ),
    "north-america": QSUniverseSpec(
        universe_type="region",
        universe_key="north-america",
        label="QS North America University Rankings",
        ranking_page_url="https://www.topuniversities.com/north-america-university-rankings",
        region_name="North America",
    ),
}

QS_SUBJECT_SPECS: dict[str, QSUniverseSpec] = {
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
    "business-masters": QSUniverseSpec(
        universe_type="special",
        universe_key="business-masters",
        label="QS Business Master's Rankings",
        ranking_page_url="https://www.topuniversities.com/business-masters-rankings",
    ),
}


def get_qs_universe_spec(universe_type: str, universe_key: str) -> QSUniverseSpec:
    normalized_type = str(universe_type or "").strip().lower()
    normalized_key = str(universe_key or "").strip().lower()
    if normalized_type == "global":
        return QS_GLOBAL
    if normalized_type == "region":
        spec = QS_REGION_SPECS.get(normalized_key)
        if spec:
            return spec
    if normalized_type == "subject":
        spec = QS_SUBJECT_SPECS.get(normalized_key)
        if spec:
            return spec
    if normalized_type == "special":
        spec = QS_SPECIAL_SPECS.get(normalized_key)
        if spec:
            return spec
    raise KeyError(f"Unsupported QS universe: type={universe_type!r}, key={universe_key!r}")


def iter_all_qs_universes() -> Iterable[QSUniverseSpec]:
    yield QS_GLOBAL
    yield from QS_REGION_SPECS.values()
    yield from QS_SUBJECT_SPECS.values()
    yield from QS_SPECIAL_SPECS.values()


def iter_major_qs_universes() -> Iterable[QSUniverseSpec]:
    """Yield only the global and major regional rankings."""
    yield QS_GLOBAL
    for key in ("europe", "asia", "latin-america", "oceania", "africa"):
        spec = QS_REGION_SPECS.get(key)
        if spec:
            yield spec
