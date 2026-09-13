"""The year a caller asked for, and what to say when it is not the one we hold.

:mod:`crawlernest.core.dataset` states which ranking editions the warehouse holds.
Every query default reads :data:`DEFAULT_RANKING_YEAR` from there, so a request
naming a year outside :data:`DATASET_YEARS` does not fail -- it answers from the
default edition, or
returns an empty page, under HTTP 200 ``success`` with nothing in the response
saying the year was changed out from under it. A rehearsal turned that up: the
answer was honest about the numbers and silent about the year, which is the same
shape of omission the caveat contract exists to prevent.

An empty result has two readings and they are not equally true: "we looked and
found nothing", which blames our coverage, versus "that year was never
ingested", which is a property of the snapshot. Only the second is accurate
here. This module says so once, in wording every surface can share, rather than
leaving each caller to infer it.

Detection is deliberately wider than the query path. A year reaches the tools
through ``context`` (``year`` / ``rankingYear`` / ``ranking_year``), but a user
also types one straight into the prompt -- "QS 2025 rankings" -- where nothing
reads it at all. That request is answered from 2026 without so much as a
mismatch to notice, so the prompt is exactly the channel most worth warning
about.

Text detection is narrowed by one exclusion: a four-digit number following a
rank cue ("top 2000", "排名前 2000") is a rank threshold, not a year, and
warning about it would be a false alarm on a perfectly answerable question.
"""

from __future__ import annotations

import re
from typing import Any

from crawlernest.core.caveats import format_edition_years
from crawlernest.core.dataset import DATASET_YEARS, DEFAULT_RANKING_YEAR

__all__ = [
    "UNSUPPORTED_YEAR_WARNING_CODE",
    "YEAR_CONTEXT_KEYS",
    "build_unsupported_year_warning",
    "detect_requested_years",
    "unsupported_year_warnings",
]

#: The marker every unsupported-year warning opens with. Callers that need to
#: recognise this warning among others match on this rather than on the prose,
#: which is free to be reworded.
UNSUPPORTED_YEAR_WARNING_CODE = "UnsupportedYearWarning"

#: The context keys through which a year actually reaches the query layer --
#: ``ranking_tools.list_rankings`` reads the first, ``RecommendationService``
#: the other two. A key added there needs adding here.
YEAR_CONTEXT_KEYS = ("year", "rankingYear", "ranking_year")

#: Four-digit years, 1900-2099, not part of a longer number and not the decimal
#: half of one (so "GPA 3.2025" is not read as a year).
_YEAR_IN_TEXT = re.compile(r"(?<![\d.])(?:19|20)\d{2}(?!\d)")

#: What sits immediately before a four-digit number that makes it a rank
#: threshold rather than a year.
_RANK_CUE = re.compile(
    r"(?:top|rank(?:ed|ing)?s?|under|below|within|前|排名|名次)\s*(?:[<≤]\s*)?$",
    re.IGNORECASE,
)


def build_unsupported_year_warning(requested_year: int) -> str:
    """The warning text for one unsupported year.

    Built from :data:`DATASET_YEARS` rather than written out, so re-pointing the
    warehouse at another edition cannot leave this claiming the old one. With a
    single edition held the text is exactly what it was when that edition was a
    constant; the agent page matches on the opening words.
    """
    if len(DATASET_YEARS) == 1:
        return (
            f"{UNSUPPORTED_YEAR_WARNING_CODE}: Dataset is strictly locked to the "
            f"{DEFAULT_RANKING_YEAR} snapshot. Year {requested_year} is not available. This is not "
            f"missing or incomplete data: the warehouse holds a single-year {DEFAULT_RANKING_YEAR} "
            f"snapshot and no rows for any other year, so any result shown here describes "
            f"{DEFAULT_RANKING_YEAR} rather than {requested_year}."
        )
    held = format_edition_years(DATASET_YEARS)
    return (
        f"{UNSUPPORTED_YEAR_WARNING_CODE}: Dataset is strictly locked to the {held} "
        f"snapshots. Year {requested_year} is not available. This is not missing or "
        f"incomplete data: the warehouse holds the {held} editions and no rows for any "
        f"other year, so any result shown here describes {DEFAULT_RANKING_YEAR} rather "
        f"than {requested_year}."
    )


def _coerce_year(value: Any) -> int | None:
    """A year out of whatever a caller put in the context, or None."""
    if isinstance(value, bool):  # bool is an int; a flag is not a year.
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return int(text)
    return None


def _years_in_text(user_input: str) -> list[int]:
    if not isinstance(user_input, str):
        return []
    years: list[int] = []
    for match in _YEAR_IN_TEXT.finditer(user_input):
        if _RANK_CUE.search(user_input[: match.start()]):
            continue
        years.append(int(match.group()))
    return years


def detect_requested_years(
    *,
    context: dict[str, Any] | None = None,
    user_input: str = "",
) -> tuple[int, ...]:
    """Every year this request names, context first, de-duplicated in order."""
    years: list[int] = []
    if isinstance(context, dict):
        for key in YEAR_CONTEXT_KEYS:
            year = _coerce_year(context.get(key))
            if year is not None:
                years.append(year)
    years.extend(_years_in_text(user_input or ""))

    seen: set[int] = set()
    ordered: list[int] = []
    for year in years:
        if year not in seen:
            seen.add(year)
            ordered.append(year)
    return tuple(ordered)


def unsupported_year_warnings(
    *,
    context: dict[str, Any] | None = None,
    user_input: str = "",
) -> list[str]:
    """One warning per named year the warehouse does not hold.

    Empty for a request that names only held editions, or names no year at all --
    which is the overwhelming majority, and must stay untouched. Membership, not
    equality with the default: once a second edition is loaded, a request for it
    is answerable and warning about it would be false.
    """
    return [
        build_unsupported_year_warning(year)
        for year in detect_requested_years(context=context, user_input=user_input)
        if year not in DATASET_YEARS
    ]
