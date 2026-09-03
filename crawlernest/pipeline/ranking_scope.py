"""Scope of a ``warehouse.ranking_record`` read for a university-level summary.

``warehouse.ranking_record`` is keyed ``(canonical_university_id,
ranking_source_id, ranking_year, ranking_type, universe_type, universe_key)`` --
a university appears once per source *and* once per universe it was ever
ranked in. A reader that wants "the world ranking" has to say so, or it folds
regional, subject and special-list rows into the same aggregate.

That fold used to be silent because only ``world`` rows existed. It no longer
is: the QS crawler now also writes ``region:*`` (the world ranking sliced by
region), ``regional:*`` (QS's own standalone regional rankings), ``subject:*``
and ``special:*`` universes into this same table. Verified live in `clawer`:
MIT alone carries seven ranking_record rows spanning five different
ranking_type values, so an unscoped ``COUNT(*)``/``MIN(rank_position)`` over a
university's rows no longer describes "the world ranking" -- it describes
whatever mix of QS's other publications that university happens to appear in
too, under a label that promises the world ranking.

Everything that summarises rankings for a university goes through the scope
defined here, so the several copies of the filter (one per language, since a
SQL view cannot import this module) cannot drift apart:

- Python -- this module, used by convergence_preview.py and
  canonical_university_detail_preview.py.
- Java -- clawer/repository/UniversityPreviewRepository.java, which mirrors
  these same three literals inline (a Java method cannot import a Python
  module either).
- SQL -- the source_rank_summary CTE in
  crawlernest-schema/recommendation_postgresql.sql, which already carries this
  scope; it predates the gap this module closes and was the reference for what
  "the world ranking" concretely filters to.
"""

from __future__ import annotations

#: The promoted table these readers use.
DEFAULT_RANKING_SCHEMA = "warehouse"
DEFAULT_RANKING_TABLE = "ranking_record"

#: The world ranking only. Regional, subject and special-list universes are
#: ranked separately and are deliberately out of scope for a university-level
#: summary that promises "the world ranking".
DEFAULT_RANKING_TYPE = "world"
DEFAULT_UNIVERSE_TYPE = "global"
DEFAULT_UNIVERSE_KEY = "global"

#: Ordered to match the ``%s`` placeholders emitted by :func:`scope_predicate`.
DEFAULT_SCOPE_PARAMS: tuple[str, str, str] = (
    DEFAULT_RANKING_TYPE,
    DEFAULT_UNIVERSE_TYPE,
    DEFAULT_UNIVERSE_KEY,
)


def scope_predicate(alias: str, *, indent: str = "") -> str:
    """SQL predicate pinning ``alias`` to the world ranking.

    Emits three ``%s`` placeholders; bind :data:`DEFAULT_SCOPE_PARAMS` (or an
    explicit triple) in the same order. ``indent`` prefixes the continuation
    lines so the predicate lines up inside the caller's query.
    """
    return (
        f"{alias}.ranking_type = %s\n"
        f"{indent}AND {alias}.universe_type = %s\n"
        f"{indent}AND {alias}.universe_key = %s"
    )
