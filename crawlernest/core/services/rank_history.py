"""One university's printed rank from each source in every held edition, for the agent.

The same rules as the API's ``GET /universities/{id}/rank-history`` (``clawer.service.RankHistoryService``), so the
agent and the page cannot disagree about a gap:

- ``ranked``: the source's printed rank and its band;
- ``edition_not_held``: this warehouse holds no edition of the source that year (QS 2017). Our gap, the same for
  every university;
- ``not_in_edition``: the edition is held and this university has no rank in it here (not ingested, or not
  matched). Never "the source declined to rank it".

Nothing is computed across editions or sources. ``build_rank_history`` is pure; ``load_rank_history`` reads the
warehouse, held editions only.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from crawlernest.core.caveats import (
    CAVEAT_ARWU_PARTIAL,
    CAVEAT_THE_PARTIAL,
    RANK_HISTORY_CAVEAT,
    archive_edition_caveat,
)
from crawlernest.core.dataset import DATASET_COVERAGE, DATASET_SOURCES, DATASET_YEARS
from crawlernest.core.rank_delta import parse_rank_band, stable_source_identity

STATUS_RANKED = "ranked"
STATUS_EDITION_NOT_HELD = "edition_not_held"
STATUS_NOT_IN_EDITION = "not_in_edition"

_SQL = """
    SELECT DISTINCT ON (rs.source_code, rr.ranking_year)
           rs.source_code,
           rr.ranking_year,
           rr.rank_position,
           COALESCE(rr.metadata->>'rank_display', rr.metadata->'raw_row'->>'rank') AS rank_display,
           sm.source_entity_id,
           COALESCE((rr.metadata->>'suspicious_merge')::boolean, FALSE) AS suspicious_merge
    FROM warehouse.ranking_record rr
    JOIN warehouse.ranking_source rs ON rs.ranking_source_id = rr.ranking_source_id
    LEFT JOIN warehouse.source_university_mapping sm ON sm.source_mapping_id = rr.source_mapping_id
    WHERE rr.canonical_university_id = %s
      AND rr.ranking_year = ANY (%s)
      AND rr.ranking_type = 'world'
      AND rr.universe_type = 'global'
      AND rr.universe_key = 'global'
      AND rr.rank_position IS NOT NULL
    ORDER BY rs.source_code, rr.ranking_year, rr.rank_position ASC
"""


def build_rank_history(
    rows: Iterable[Mapping[str, Any]],
    *,
    held_years: Iterable[int] = DATASET_YEARS,
) -> dict[str, Any]:
    """The history for these warehouse rows (one per source and edition), over ``held_years``."""
    years = sorted(int(y) for y in held_years)
    by_source: dict[str, dict[int, Mapping[str, Any]]] = {}
    for row in rows:
        by_source.setdefault(str(row["source_code"]), {})[int(row["ranking_year"])] = row

    caveats: list[str] = [RANK_HISTORY_CAVEAT]
    series = []
    for source in DATASET_SOURCES:
        coverage = set(DATASET_COVERAGE.get(source, ()))
        source_rows = by_source.get(source, {})
        points = []
        previous_identity: str | None = None
        ranked = 0
        for year in years:
            if year not in coverage:
                points.append({"year": year, "status": STATUS_EDITION_NOT_HELD})
                continue
            row = source_rows.get(year)
            if row is None:
                points.append({"year": year, "status": STATUS_NOT_IN_EDITION})
                continue
            ranked += 1
            position = int(row["rank_position"])
            display = row.get("rank_display")
            band = parse_rank_band(display)
            identity = stable_source_identity(row.get("source_entity_id"))
            archived = archive_edition_caveat(source, year)
            points.append({
                "year": year,
                "status": STATUS_RANKED,
                "rankDisplay": str(display) if display else str(position),
                "rankLower": band.lower if band else position,
                "rankUpper": band.upper if band else position,
                "archived": archived is not None,
                "suspiciousMerge": bool(row.get("suspicious_merge")),
                "sourceIdentityChanged": bool(previous_identity and identity and previous_identity != identity),
            })
            if identity:
                previous_identity = identity
            if archived and archived not in caveats:
                caveats.append(archived)
        series.append({"source": source, "rankedEditions": ranked, "points": points})
    if "THE" in by_source:
        caveats.append(CAVEAT_THE_PARTIAL)
    if "ARWU" in by_source:
        caveats.append(CAVEAT_ARWU_PARTIAL)
    return {"years": years, "series": series, "caveats": caveats}


def summarize_rank_history(history: Mapping[str, Any]) -> list[str]:
    """One line per source for a prompt: every edition, with its rank or what its gap is, in the same words."""
    lines = []
    for series in history.get("series") or []:
        parts = []
        for point in series.get("points") or []:
            if point["status"] == STATUS_RANKED:
                note = " (Internet Archive capture)" if point.get("archived") else ""
                parts.append(f"{point['year']} {point['rankDisplay']}{note}")
            elif point["status"] == STATUS_EDITION_NOT_HELD:
                parts.append(f"{point['year']} no {series['source']} edition held")
            else:
                parts.append(f"{point['year']} not in the held edition")
        lines.append(f"{series['source']}: " + "; ".join(parts))
    return lines


def load_rank_history(conn: Any, canonical_university_id: int, *, held_years: Iterable[int] = DATASET_YEARS) -> dict[str, Any]:
    years = sorted(int(y) for y in held_years)
    with conn.cursor() as cur:
        cur.execute(_SQL, (int(canonical_university_id), years))
        columns = [d[0] for d in cur.description]
        rows = [dict(zip(columns, record)) for record in cur.fetchall()]
    return build_rank_history(rows, held_years=years)
