"""
Constants package for QS University Rankings crawler.

Provides presets, country codes, and regional groupings.
"""

from .presets import (
    SUBJECT_PRESETS,
    RANKING_PAGE_PRESETS,
    REGION_PAGE_PRESETS,
    REGION_SUBREGION_PRESETS,
)

from .countries import (
    COUNTRY_CODES,
    COUNTRY_ALIASES,
    get_available_countries,
)

from .regions import (
    REGION_COUNTRIES,
    COUNTRY_NAME_ALIASES,
    COUNTRY_SLUG_ALIASES,
    UNIVERSITY_COUNTRY_HINTS,
)

__all__ = [
    # Presets
    "SUBJECT_PRESETS",
    "RANKING_PAGE_PRESETS",
    "REGION_PAGE_PRESETS",
    "REGION_SUBREGION_PRESETS",
    # Countries
    "COUNTRY_CODES",
    "COUNTRY_ALIASES",
    "get_available_countries",
    # Regions
    "REGION_COUNTRIES",
    "COUNTRY_NAME_ALIASES",
    "COUNTRY_SLUG_ALIASES",
    "UNIVERSITY_COUNTRY_HINTS",
]
