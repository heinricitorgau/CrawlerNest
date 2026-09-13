"""How the dataset, and the evidence in front of the model, are described to it.

The facts themselves -- which editions are loaded, which sources are ingested --
are warehouse facts and live in :mod:`crawlernest.core.dataset`. They are
re-exported here so an explainer has one import for "what the corpus is and what
the model must be told about it", without ``core`` ever having to import
``agent``.

What this module owns is the second half of that: the wording. A model handed
ranking rows will still write "climbing year after year" or "the latest 2027
figures", because that is what ranking prose usually sounds like. Neither claim
invents a number the faithfulness rules can catch (``faithfulness.py`` checks
figures, caveats and institution names; a trend is none of those), so the
constraint has to arrive before generation rather than be caught after it.
Golden case ``faith-122`` records exactly that gap.

## Derived from the evidence, not from a count of years

The rules used to be written against the warehouse: "name no year other than
2026", "one snapshot cannot show movement". Both are true only while one edition
is loaded, and the obvious generalisation -- relax them once a second edition
exists -- is the wrong one. A second edition in the warehouse says nothing about
whether *these rows* compare two editions. Unlocking trend wording on a dataset
flag would let a model describe movement for a university whose rows carry no
comparison at all.

So both rules are computed from the rows being explained:

- **Years.** The model may name the years the rows carry (``rankingYear``, and
  the editions a rank-change field compares). Rows that carry none fall back to
  the editions the warehouse holds.
- **Movement.** A claim about time is allowed only when a row carries a
  rank-change field whose direction is determinate -- ``rankDelta`` with
  ``direction`` of ``up``, ``down`` or ``unchanged``, the vocabulary of
  :mod:`crawlernest.core.rank_delta`. ``indeterminate``, a withheld delta, or no
  field at all shows no movement, whatever the warehouse holds.

For today's evidence -- 2026 rows, no rank-change field, one edition loaded -- the
header and the rules render to exactly the text they had as constants.
:data:`DATASET_CONSTRAINTS` and :func:`build_dataset_header` with no argument are
that rendering, and golden tests pin it.

:func:`build_dataset_header` and :func:`dataset_constraints` are what every
grounded explainer prepends and appends -- see ``GroundedExplainer._explain``,
which passes its rows so no subclass has to.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from crawlernest.core.caveats import format_edition_years
from crawlernest.core.dataset import (
    DATASET_SOURCES,
    DATASET_YEAR,
    DATASET_YEARS,
    DEFAULT_RANKING_YEAR,
)
from crawlernest.core.rank_delta import DIRECTION_DOWN, DIRECTION_UNCHANGED, DIRECTION_UP

__all__ = [
    "DATASET_CONSTRAINTS",
    "DATASET_SOURCES",
    "DATASET_YEAR",
    "DATASET_YEARS",
    "DEFAULT_RANKING_YEAR",
    "EvidenceScope",
    "RANK_CHANGE_FIELD",
    "build_dataset_header",
    "dataset_constraints",
    "evidence_scope",
]

#: The row field a rank comparison has to arrive in for the model to be allowed
#: to describe movement. A dict, or a list of dicts (one per source), each with a
#: ``direction``. Phase 4's API field has to use this name, or this module has to
#: learn the new one -- until then a delta in any other field is invisible here,
#: which fails closed.
RANK_CHANGE_FIELD = "rankDelta"

#: Directions that state a movement (or its absence) rather than withholding one.
DETERMINATE_DIRECTIONS = frozenset({DIRECTION_UP, DIRECTION_DOWN, DIRECTION_UNCHANGED})

_ROW_YEAR_FIELDS = ("rankingYear", "ranking_year")
_CHANGE_YEAR_FIELDS = ("currentYear", "current_year", "priorYear", "prior_year")


@dataclass(frozen=True, slots=True)
class EvidenceScope:
    """What a set of evidence rows lets a model say about time."""

    #: Years the model may name, newest first.
    years: tuple[int, ...]
    #: Whether any row carries a determinate rank-change field.
    shows_movement: bool
    #: Whether ``years`` came from the rows rather than from the warehouse.
    years_from_evidence: bool


def _as_year(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 1900 <= value <= 2099 else None
    if isinstance(value, str) and value.strip().isdigit():
        return _as_year(int(value.strip()))
    return None


def _rank_changes(row: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    value = row.get(RANK_CHANGE_FIELD)
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, list):
        return [entry for entry in value if isinstance(entry, Mapping)]
    return []


def evidence_scope(items: Iterable[Any] | None = None) -> EvidenceScope:
    """The years and the movement the rows actually carry."""
    years: set[int] = set()
    shows_movement = False
    for row in items or ():
        if not isinstance(row, Mapping):
            continue
        for key in _ROW_YEAR_FIELDS:
            year = _as_year(row.get(key))
            if year is not None:
                years.add(year)
        for change in _rank_changes(row):
            for key in _CHANGE_YEAR_FIELDS:
                year = _as_year(change.get(key))
                if year is not None:
                    years.add(year)
            if change.get("direction") in DETERMINATE_DIRECTIONS:
                shows_movement = True

    from_evidence = bool(years)
    nameable = years if from_evidence else set(DATASET_YEARS)
    return EvidenceScope(
        years=tuple(sorted(nameable, reverse=True)),
        shows_movement=shows_movement,
        years_from_evidence=from_evidence,
    )


def _single_edition_loaded() -> bool:
    return len(DATASET_YEARS) == 1


def build_dataset_header(items: Iterable[Any] | None = None) -> str:
    """The three-line declaration prepended to every explainer's evidence block.

    Line one describes the warehouse; line three describes what *these rows* can
    show. Derived rather than written out, so neither a dataset that gains an
    edition nor evidence that gains a comparison leaves the model reading a stale
    description.
    """
    scope = evidence_scope(items)
    if _single_edition_loaded():
        holdings = (
            f"Dataset year: the warehouse holds {DATASET_YEARS[0]} ranking data and no other year."
        )
    else:
        holdings = (
            f"Dataset years: the warehouse holds {format_edition_years(DATASET_YEARS)} "
            "ranking data and no other year."
        )

    if scope.shows_movement:
        temporal = (
            "Some rows carry a rank-change field. Movement between editions may be stated "
            "only where a row carries one, and only in the direction it gives."
        )
    elif _single_edition_loaded():
        temporal = (
            "This is a single-year snapshot. Inferring any cross-year trend, movement, "
            "improvement or decline from it is forbidden."
        )
    else:
        temporal = (
            "No row in this evidence carries a rank-change field. Inferring any cross-year "
            "trend, movement, improvement or decline from it is forbidden."
        )

    return "\n".join(
        (
            holdings,
            f"Ingested sources: {', '.join(DATASET_SOURCES)}, with partial coverage. A "
            "university missing a rank from one of them is missing it here; that is not "
            "the source declining to rank it.",
            temporal,
        )
    )


_TIME_WORDING = (
    'Do not write "currently", "latest", "most recent", "up to date", "year after '
    'year", "has risen", "has improved", "held its position", or any other wording '
    "that implies time passing or a trend."
)


def dataset_constraints(items: Iterable[Any] | None = None) -> tuple[str, ...]:
    """The year rule and the movement rule for these rows.

    Appended to every explainer's response constraints by
    :meth:`GroundedExplainer._explain`. Kept next to the header so the rules the
    model is given and the description it is given cannot drift apart.
    """
    scope = evidence_scope(items)

    if scope.years == DATASET_YEARS and _single_edition_loaded():
        year_rule = (
            f"Name no year other than {DATASET_YEARS[0]}. No other year exists in this data, so "
            "any other year label -- an earlier edition, a later intake -- would be invented."
        )
    else:
        year_rule = (
            f"Name no year other than {format_edition_years(scope.years)}. No other year "
            "appears in this evidence, so any other year label -- an earlier edition, a later "
            "intake -- would be invented."
        )

    if scope.shows_movement:
        movement_rule = (
            "State a movement between editions only for a row that carries a rank-change "
            "field, only for the source and editions that field names, and only in the "
            'direction it gives. A row whose direction is "indeterminate", or that carries '
            'no such field, shows no movement. Say a rank moved "up" or "down"; never say a '
            'university "improved" or "declined", and do not write "currently", "latest", '
            '"most recent" or "up to date".'
        )
    elif _single_edition_loaded():
        movement_rule = f"{_TIME_WORDING} One snapshot cannot show movement."
    else:
        movement_rule = (
            f"{_TIME_WORDING} No row here carries a rank-change field, so this evidence "
            "cannot show movement."
        )

    return (year_rule, movement_rule)


#: The rules for evidence that carries no year and no comparison. Kept as a
#: constant for callers that have no rows to pass; with one edition loaded it is
#: byte-identical to the constant it replaces.
DATASET_CONSTRAINTS = dataset_constraints()
