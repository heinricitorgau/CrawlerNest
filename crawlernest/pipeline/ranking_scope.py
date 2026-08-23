"""Scope of a ``warehouse.ranking_record`` read.

``warehouse.ranking_records_preview`` held one row per university per source per
year and no notion of a universe, so a reader could select the whole table and
get something coherent. ``warehouse.ranking_record`` is keyed
``(canonical_university_id, ranking_source_id, ranking_year, ranking_type,
universe_type, universe_key)`` -- a university appears once per source *and*
once per universe it was ranked in. A reader that wants "the world ranking"
therefore has to say so, or it silently mixes regional and global tables into
one ``MIN(rank_position)``.

Everything that summarises rankings for a university goes through the scope
defined here, so the three former copies of the filter cannot drift apart.
"""

from __future__ import annotations

#: The promoted table these readers now use.
DEFAULT_RANKING_SCHEMA = "warehouse"
DEFAULT_RANKING_TABLE = "ranking_record"

#: The one universe currently ingested. QS, THE and ARWU all land here; regional
#: and subject universes are ranked separately (subjects in
#: ``warehouse.subject_ranking_record``) and are deliberately out of scope for a
#: university-level summary.
#:
#: A SQL copy of this same predicate lives in the ``source_rank_summary`` CTE of
#: ``crawlernest-schema/recommendation_postgresql.sql`` (feeding
#: ``analytics.v_recommendation_candidates_latest``), and a Java copy in
#: ``clawer/repository/UniversityPreviewRepository.java``. A view cannot import
#: this module, so the three are kept in step by cross-reference: change one,
#: change all three.
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
    """SQL predicate pinning ``alias`` to one ranking universe.

    Emits three ``%s`` placeholders; bind :data:`DEFAULT_SCOPE_PARAMS` (or an
    explicit triple) in the same order. ``indent`` prefixes the continuation
    lines so the predicate lines up inside the caller's query.
    """
    return (
        f"{alias}.ranking_type = %s\n"
        f"{indent}AND {alias}.universe_type = %s\n"
        f"{indent}AND {alias}.universe_key = %s"
    )
