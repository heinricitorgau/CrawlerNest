"""Country to region grouping for the QS feature matrix.

The 2026 snapshot spans 107 country strings. Feeding those in as 107 one-hot
columns against 705 labelled rows would add more parameters than the training
set can support, so countries are collapsed into 12 regions.

The grouping is geographic-political and, like any such grouping, has judgement
calls rather than a single correct answer. The ones worth knowing about:

- Turkey is grouped with the Middle East / North Africa rather than Europe.
- Georgia, Armenia and Azerbaijan are grouped with Central Asia as "Caucasus and
  Central Asia" rather than split between Europe and Asia.
- Puerto Rico is grouped with Latin America rather than North America.
- Northern Cyprus is listed separately from Cyprus by the source; it is grouped
  with the Middle East, while Cyprus is grouped with Western Europe.
- ``"N A"`` is the source's own missing-country marker and maps to ``Unknown``.

Change the grouping if you disagree -- but change it here, once, and re-run the
evaluation so the effect on the metrics is visible rather than assumed.
"""

from __future__ import annotations

from typing import Final

from ranking_ml.features.schema import UNKNOWN_COUNTRY

NORTH_AMERICA: Final[str] = "North America"
LATIN_AMERICA: Final[str] = "Latin America"
WESTERN_EUROPE: Final[str] = "Western Europe"
EASTERN_EUROPE: Final[str] = "Eastern Europe"
MIDDLE_EAST_NORTH_AFRICA: Final[str] = "Middle East and North Africa"
SUB_SAHARAN_AFRICA: Final[str] = "Sub-Saharan Africa"
EAST_ASIA: Final[str] = "East Asia"
SOUTH_ASIA: Final[str] = "South Asia"
SOUTHEAST_ASIA: Final[str] = "Southeast Asia"
CENTRAL_ASIA: Final[str] = "Caucasus and Central Asia"
OCEANIA: Final[str] = "Oceania"
UNKNOWN_REGION: Final[str] = "Unknown"

REGION_BY_COUNTRY: Final[dict[str, str]] = {
    # North America
    "United States": NORTH_AMERICA,
    "Canada": NORTH_AMERICA,
    # Latin America
    "Brazil": LATIN_AMERICA,
    "Mexico": LATIN_AMERICA,
    "Argentina": LATIN_AMERICA,
    "Chile": LATIN_AMERICA,
    "Colombia": LATIN_AMERICA,
    "Ecuador": LATIN_AMERICA,
    "Peru": LATIN_AMERICA,
    "Venezuela": LATIN_AMERICA,
    "Costa Rica": LATIN_AMERICA,
    "Uruguay": LATIN_AMERICA,
    "Cuba": LATIN_AMERICA,
    "Panama": LATIN_AMERICA,
    "Dominican Republic": LATIN_AMERICA,
    "Bolivia": LATIN_AMERICA,
    "Paraguay": LATIN_AMERICA,
    "Puerto Rico": LATIN_AMERICA,
    "Honduras": LATIN_AMERICA,
    "Guatemala": LATIN_AMERICA,
    # Western Europe
    "United Kingdom": WESTERN_EUROPE,
    "Germany": WESTERN_EUROPE,
    "Italy": WESTERN_EUROPE,
    "Spain": WESTERN_EUROPE,
    "France": WESTERN_EUROPE,
    "Netherlands": WESTERN_EUROPE,
    "Switzerland": WESTERN_EUROPE,
    "Belgium": WESTERN_EUROPE,
    "Finland": WESTERN_EUROPE,
    "Sweden": WESTERN_EUROPE,
    "Ireland": WESTERN_EUROPE,
    "Austria": WESTERN_EUROPE,
    "Portugal": WESTERN_EUROPE,
    "Greece": WESTERN_EUROPE,
    "Norway": WESTERN_EUROPE,
    "Denmark": WESTERN_EUROPE,
    "Luxembourg": WESTERN_EUROPE,
    "Iceland": WESTERN_EUROPE,
    "Malta": WESTERN_EUROPE,
    "Cyprus": WESTERN_EUROPE,
    # Eastern Europe
    "Russia": EASTERN_EUROPE,
    "Poland": EASTERN_EUROPE,
    "Czechia": EASTERN_EUROPE,
    "Romania": EASTERN_EUROPE,
    "Hungary": EASTERN_EUROPE,
    "Ukraine": EASTERN_EUROPE,
    "Slovakia": EASTERN_EUROPE,
    "Lithuania": EASTERN_EUROPE,
    "Croatia": EASTERN_EUROPE,
    "Serbia": EASTERN_EUROPE,
    "Estonia": EASTERN_EUROPE,
    "Belarus": EASTERN_EUROPE,
    "Slovenia": EASTERN_EUROPE,
    "Latvia": EASTERN_EUROPE,
    "Bulgaria": EASTERN_EUROPE,
    "Bosnia Herzegovina": EASTERN_EUROPE,
    # Middle East and North Africa
    "Turkey": MIDDLE_EAST_NORTH_AFRICA,
    "Saudi Arabia": MIDDLE_EAST_NORTH_AFRICA,
    "Egypt": MIDDLE_EAST_NORTH_AFRICA,
    "United Arab Emirates": MIDDLE_EAST_NORTH_AFRICA,
    "Jordan": MIDDLE_EAST_NORTH_AFRICA,
    "Iran": MIDDLE_EAST_NORTH_AFRICA,
    "Israel": MIDDLE_EAST_NORTH_AFRICA,
    "Lebanon": MIDDLE_EAST_NORTH_AFRICA,
    "Iraq": MIDDLE_EAST_NORTH_AFRICA,
    "Tunisia": MIDDLE_EAST_NORTH_AFRICA,
    "Bahrain": MIDDLE_EAST_NORTH_AFRICA,
    "Kuwait": MIDDLE_EAST_NORTH_AFRICA,
    "Palestinian Territories": MIDDLE_EAST_NORTH_AFRICA,
    "Qatar": MIDDLE_EAST_NORTH_AFRICA,
    "Oman": MIDDLE_EAST_NORTH_AFRICA,
    "Northern Cyprus": MIDDLE_EAST_NORTH_AFRICA,
    "Morocco": MIDDLE_EAST_NORTH_AFRICA,
    "Syria": MIDDLE_EAST_NORTH_AFRICA,
    "Libya": MIDDLE_EAST_NORTH_AFRICA,
    # Sub-Saharan Africa
    "South Africa": SUB_SAHARAN_AFRICA,
    "Ghana": SUB_SAHARAN_AFRICA,
    "Kenya": SUB_SAHARAN_AFRICA,
    "Nigeria": SUB_SAHARAN_AFRICA,
    "Ethiopia": SUB_SAHARAN_AFRICA,
    "Uganda": SUB_SAHARAN_AFRICA,
    "Sudan": SUB_SAHARAN_AFRICA,
    # First appeared in the 2026 snapshot re-crawled on 2026-09-02.
    "Tanzania": SUB_SAHARAN_AFRICA,
    # East Asia
    "China (mainland)": EAST_ASIA,
    "Japan": EAST_ASIA,
    "South Korea": EAST_ASIA,
    "Taiwan": EAST_ASIA,
    "Hong Kong Sar": EAST_ASIA,
    "Macau Sar": EAST_ASIA,
    # South Asia
    "India": SOUTH_ASIA,
    "Bangladesh": SOUTH_ASIA,
    "Pakistan": SOUTH_ASIA,
    "Sri Lanka": SOUTH_ASIA,
    # Southeast Asia
    "Malaysia": SOUTHEAST_ASIA,
    "Indonesia": SOUTHEAST_ASIA,
    "Thailand": SOUTHEAST_ASIA,
    "Vietnam": SOUTHEAST_ASIA,
    "Philippines": SOUTHEAST_ASIA,
    "Singapore": SOUTHEAST_ASIA,
    "Brunei": SOUTHEAST_ASIA,
    # Caucasus and Central Asia
    "Kazakhstan": CENTRAL_ASIA,
    "Kyrgyzstan": CENTRAL_ASIA,
    "Azerbaijan": CENTRAL_ASIA,
    "Uzbekistan": CENTRAL_ASIA,
    "Georgia": CENTRAL_ASIA,
    "Armenia": CENTRAL_ASIA,
    # Oceania
    "Australia": OCEANIA,
    "New Zealand": OCEANIA,
    # Source's own missing marker
    UNKNOWN_COUNTRY: UNKNOWN_REGION,
}

#: Fixed column order for region one-hot encoding, so a matrix built today has
#: the same layout as one built after a re-crawl that happens to drop a region.
REGION_ORDER: Final[tuple[str, ...]] = (
    NORTH_AMERICA,
    LATIN_AMERICA,
    WESTERN_EUROPE,
    EASTERN_EUROPE,
    MIDDLE_EAST_NORTH_AFRICA,
    SUB_SAHARAN_AFRICA,
    EAST_ASIA,
    SOUTH_ASIA,
    SOUTHEAST_ASIA,
    CENTRAL_ASIA,
    OCEANIA,
    UNKNOWN_REGION,
)


def region_for(country: str | None) -> str:
    """Region for *country*, or ``Unknown`` if it is blank or unmapped.

    Unmapped countries are not an error here -- a re-crawl can legitimately add
    one. :func:`unmapped_countries` is the check that surfaces them.
    """
    if not country or not str(country).strip():
        return UNKNOWN_REGION
    return REGION_BY_COUNTRY.get(str(country).strip(), UNKNOWN_REGION)


def unmapped_countries(countries: list[str]) -> list[str]:
    """Countries in *countries* that have no explicit region mapping.

    Used by the feature builder to report silent ``Unknown`` fallbacks after a
    re-crawl, rather than letting a new country quietly join the Unknown bucket.
    """
    seen = {str(c).strip() for c in countries if c and str(c).strip()}
    return sorted(seen - set(REGION_BY_COUNTRY))
