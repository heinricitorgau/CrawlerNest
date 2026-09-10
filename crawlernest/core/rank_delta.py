"""How far a university moved between two ranking editions, when that is knowable.

The warehouse holds one year today (:data:`crawlernest.core.dataset.DATASET_YEAR`),
so every delta this module computes right now is withheld with reason
``single_year_dataset``. It exists so that the arithmetic, and the rules for when
the arithmetic may not be done, are settled and tested before a second year is
ingested -- not improvised under the pressure of one.

Four facts about the data decide the shape of it. Each was checked against the
warehouse on 2026-09-10, not assumed.

**Most non-QS ranks are bands, not positions.** ARWU publishes exact positions to
100 and bands after that; 743 of its 838 global rows are banded ("101-150" ...
"901-1000"). THE's bands start at 201 and its ties are written "=98"; nearly all
of its 1,637 rows are one or the other. ``ranking_record.rank_position`` stores a
band's lower bound. Subtracting lower bounds reports a university that stayed in
"201-250" as unchanged when it may have moved 49 places either way, and one that
crossed a single band boundary as having moved exactly 50. So banded ranks get
an interval, never a number: the delta lies in ``[delta_min, delta_max]``, and a
direction is reported only when every point in that interval agrees on it.

**Delta is per source, never on the composite.** ``display_rank`` in
``v_aggregated_rankings_latest`` is a ROW_NUMBER over the universities *this
platform holds* that year, and ``composite_score`` depends on which sources
covered each university. Both move when coverage moves. A composite delta
between a QS-only year and a QS+THE+ARWU year would mostly measure our ingest,
and would be reported as the university's.

**Absence is our gap.** A university with a 2026 QS row and no 2025 QS row has
``no_prior_row``, which says nothing about whether QS ranked it in 2025 -- only
that we hold no row for it. The repo-wide rule on missing source ranks applies
to missing years too.

**Identity has to survive the year boundary.** ARWU's source ids embed the year
(``arwu:2026:aalto-university``); so do QS subject ids. Comparing raw ids across
years would call every ARWU university a different entity. Continuity is judged
on :func:`stable_source_identity`, which drops the year segment, and a delta is
withheld when that identity differs -- two different source entities resolving
to one canonical university across years is either a rename or a false merge,
and this module cannot tell which.

Sign convention, fixed here and nowhere else: ``rank_delta = current - prior``.
A negative delta means a smaller rank number, i.e. the university moved *up*.
Because that inversion is easy to read backwards, :attr:`RankDelta.direction`
states it in words -- ``"up"`` / ``"down"`` / ``"unchanged"`` /
``"indeterminate"`` -- and callers should render that rather than re-deriving it
from the sign. The words are deliberately not "improved" or "declined": a rank
moving is a fact about a table, not a verdict on a university, and
``dataset_context.DATASET_CONSTRAINTS`` already bars the model from that
vocabulary.

Nothing here reads the database or knows about caveat prose. Reasons are
machine codes; turning them into disclosures is the API layer's job, and has to
happen in all four places caveat strings live (see ``core/caveats.py``).
"""

from __future__ import annotations

import re
from collections.abc import Collection
from dataclasses import dataclass, replace

from crawlernest.core.dataset import DATASET_YEAR

__all__ = [
    "DIRECTION_DOWN",
    "DIRECTION_INDETERMINATE",
    "DIRECTION_UNCHANGED",
    "DIRECTION_UP",
    "REASON_BANDED",
    "REASON_ENTITY_CHANGED",
    "REASON_NO_CURRENT_ROW",
    "REASON_NO_PRIOR_ROW",
    "REASON_SINGLE_YEAR_DATASET",
    "REASON_SUSPICIOUS_MERGE",
    "RankBand",
    "RankDelta",
    "RankObservation",
    "compute_rank_delta",
    "parse_rank_band",
    "stable_source_identity",
]

DIRECTION_UP = "up"
DIRECTION_DOWN = "down"
DIRECTION_UNCHANGED = "unchanged"
DIRECTION_INDETERMINATE = "indeterminate"

#: The warehouse does not hold the prior year at all. The dataset-level case,
#: and today the only one: every call returns this until a second year exists.
REASON_SINGLE_YEAR_DATASET = "single_year_dataset"
#: The prior year is ingested but we hold no row for this university and
#: source. Our gap -- not a statement that the source did not rank it.
REASON_NO_PRIOR_ROW = "no_prior_row"
REASON_NO_CURRENT_ROW = "no_current_row"
#: One or both ranks are bands. Not a withholding: the interval is reported,
#: only the single number is not.
REASON_BANDED = "banded"
#: Different source entities resolved to this canonical university in the two
#: years. A rename and a false merge look identical from here.
REASON_ENTITY_CHANGED = "entity_changed"
#: Entity resolution already flagged the match in one of the years.
REASON_SUSPICIOUS_MERGE = "suspicious_merge"

#: "14", "=98" (a tie), "101-150" with a hyphen or an en dash, "1501+".
_EXACT = re.compile(r"^=?\s*(\d+)$")
_BAND = re.compile(r"^(\d+)\s*[-–—]\s*(\d+)$")
_OPEN = re.compile(r"^(\d+)\s*\+$")

#: A ":2026:" segment inside a source id. Any id carrying the year is, by
#: construction, not an identity that survives into the next year.
_YEAR_SEGMENT = re.compile(r":(?:19|20)\d{2}(?=:)")


@dataclass(frozen=True, slots=True)
class RankBand:
    """A published rank as a closed or half-open interval of positions.

    ``upper`` is ``None`` for an open-ended band ("1501+"). An exact rank is a
    band whose bounds coincide.
    """

    lower: int
    upper: int | None

    @property
    def is_exact(self) -> bool:
        return self.upper == self.lower


def parse_rank_band(value: str | int | None) -> RankBand | None:
    """The band a source's rank display denotes, or ``None`` if it denotes none.

    Unparseable input returns ``None`` rather than raising: this reads
    ``metadata.raw_row.rank`` from rows already in the warehouse, and one odd
    string must withhold one delta, not fail a page.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return RankBand(value, value) if value > 0 else None

    text = str(value).strip()
    if match := _EXACT.match(text):
        position = int(match.group(1))
        return RankBand(position, position) if position > 0 else None
    if match := _BAND.match(text):
        lower, upper = int(match.group(1)), int(match.group(2))
        return RankBand(lower, upper) if 0 < lower <= upper else None
    if match := _OPEN.match(text):
        lower = int(match.group(1))
        return RankBand(lower, None) if lower > 0 else None
    return None


def stable_source_identity(source_entity_id: str | None) -> str | None:
    """A source entity id with any embedded year removed.

    ``arwu:2026:aalto-university`` and ``arwu:2025:aalto-university`` are the
    same ARWU entity; QS paths and THE numeric ids carry no year and pass
    through unchanged.
    """
    if source_entity_id is None:
        return None
    return _YEAR_SEGMENT.sub("", source_entity_id.strip()) or None


@dataclass(frozen=True, slots=True)
class RankObservation:
    """One source's rank for one university in one edition."""

    year: int
    source: str
    band: RankBand | None
    source_entity_id: str | None = None
    suspicious_merge: bool = False


@dataclass(frozen=True, slots=True)
class RankDelta:
    """The movement between two editions, or why there is none to report.

    ``rank_delta`` is set only when both ranks are exact. ``delta_min`` and
    ``delta_max`` bound the movement whenever it is bounded at all; either is
    ``None`` on an unbounded side. ``reason`` explains every ``None``.
    """

    source: str
    current_year: int
    prior_year: int
    rank_delta: int | None = None
    delta_min: int | None = None
    delta_max: int | None = None
    direction: str | None = None
    reason: str | None = None


def _direction(delta_min: int | None, delta_max: int | None, exact: int | None) -> str:
    if exact is not None:
        if exact < 0:
            return DIRECTION_UP
        if exact > 0:
            return DIRECTION_DOWN
        return DIRECTION_UNCHANGED
    # Only when the whole interval agrees. [-49, 49] -- the same band both
    # years -- is the common case, and it genuinely says nothing.
    if delta_max is not None and delta_max < 0:
        return DIRECTION_UP
    if delta_min is not None and delta_min > 0:
        return DIRECTION_DOWN
    return DIRECTION_INDETERMINATE


def compute_rank_delta(
    current: RankObservation,
    prior: RankObservation | None,
    *,
    prior_year: int,
    ingested_years: Collection[int] = (DATASET_YEAR,),
) -> RankDelta:
    """Movement from ``prior_year`` to ``current.year`` for one source.

    ``ingested_years`` defaults to what :mod:`crawlernest.core.dataset` says the
    warehouse holds, so today's answer is derived from the same constant every
    query default reads -- and changes when it does, not when someone remembers.
    """
    if prior_year >= current.year:
        raise ValueError(f"prior_year {prior_year} must precede {current.year}")
    if prior is not None:
        if prior.year != prior_year:
            raise ValueError(f"prior observation is for {prior.year}, not {prior_year}")
        if prior.source != current.source:
            # Cross-source comparison is a different question with a different
            # answer; refusing it here keeps it from being asked by accident.
            raise ValueError(f"cannot compare {current.source} with {prior.source}")

    withheld = RankDelta(source=current.source, current_year=current.year, prior_year=prior_year)

    if prior_year not in ingested_years:
        return replace(withheld, reason=REASON_SINGLE_YEAR_DATASET)
    if current.band is None:
        return replace(withheld, reason=REASON_NO_CURRENT_ROW)
    if prior is None or prior.band is None:
        return replace(withheld, reason=REASON_NO_PRIOR_ROW)
    if current.suspicious_merge or prior.suspicious_merge:
        return replace(withheld, reason=REASON_SUSPICIOUS_MERGE)
    current_identity = stable_source_identity(current.source_entity_id)
    prior_identity = stable_source_identity(prior.source_entity_id)
    if current_identity is not None and prior_identity is not None and current_identity != prior_identity:
        return replace(withheld, reason=REASON_ENTITY_CHANGED)

    c, p = current.band, prior.band
    # Interval subtraction: [c_lo, c_hi] - [p_lo, p_hi] = [c_lo - p_hi, c_hi - p_lo],
    # with an open upper bound making that side unbounded.
    delta_min = None if p.upper is None else c.lower - p.upper
    delta_max = None if c.upper is None else c.upper - p.lower

    if c.is_exact and p.is_exact:
        exact = c.lower - p.lower
        return replace(
            withheld,
            rank_delta=exact,
            delta_min=exact,
            delta_max=exact,
            direction=_direction(exact, exact, exact),
        )
    return replace(
        withheld,
        delta_min=delta_min,
        delta_max=delta_max,
        direction=_direction(delta_min, delta_max, None),
        reason=REASON_BANDED,
    )
