from __future__ import annotations

"""
Reading warehouse.rankings as multi-source input.

warehouse.ranking_record used to have two writers. The analytics bridge
derived it from warehouse.rankings by joining canonical_slug = school_slug,
stamping run_id='legacy_bridge_<year>_<source>'; the multi-source pipeline
derived it from a freshly crawled payload through the entity resolver,
stamping a run id of its own. Both ran in one `run`, in that order, so the
second pruned everything the first had written and the bridge's DO UPDATE
overwrote whatever provenance the second left behind. They agreed on all 1,499
QS universities, which is the only reason nothing was lost -- a coincidence of
coverage, not a guarantee.

This module ends that. The legacy tables stay the crawl's landing zone, and
the multi-source pipeline becomes the single writer of ranking_record, reading
its input from here and resolving it the same way it resolves THE and ARWU.
"""

from typing import Any, Optional

from .types import StandardizedRankingRecord


def load_legacy_ranking_records(
    conn: Any,
    *,
    source_code: str = "QS",
    ranking_year: int,
    ranking_type: str = "world",
    universe_type: str = "global",
    universe_key: str = "global",
) -> list[StandardizedRankingRecord]:
    """
    Read one source's rows out of warehouse.rankings, ready for ingest_records.

    Deduplicated the same way the bridge deduplicated: one row per university,
    source, year and ranking type, preferring the best rank.

    `source_entity_id` is the source's own identifier for the university, read
    from warehouse.universities.qs_profile_path. Re-keying is not free:
    warehouse.subject_ranking_record carries a foreign key to
    source_university_mapping, so QS subject rankings hang off the ids an
    earlier ingest created, and changing the scheme strands them.

    Two fallbacks behind it, in order. The id this source already has on record
    in source_university_mapping, which covers universities written before
    qs_profile_path was persisted; then school_slug, for a university neither
    knows about yet.
    """
    normalized_source = str(source_code or "QS").strip().upper()

    with conn.cursor() as cur:
        cur.execute(
            """
            WITH deduped AS (
                SELECT DISTINCT ON (
                    r.university_id, r.ranking_source, r.ranking_year, r.ranking_type
                ) r.*
                FROM warehouse.rankings r
                WHERE r.ranking_year = %(ranking_year)s
                  AND upper(r.ranking_source) = %(source_code)s
                ORDER BY
                    r.university_id,
                    r.ranking_source,
                    r.ranking_year,
                    r.ranking_type,
                    r.rank_start ASC NULLS LAST,
                    r.ranking_id DESC
            )
            SELECT
                COALESCE(
                    NULLIF(u.qs_profile_path, ''),
                    existing.source_entity_id,
                    u.school_slug
                ) AS source_entity_id,
                u.display_name,
                c.country_name,
                COALESCE(r.rank_start, r.rank_end) AS rank_position,
                r.score,
                r.source_url,
                COALESCE(NULLIF(r.ranking_type, ''), %(ranking_type)s) AS ranking_type,
                r.ranking_year,
                r.ranking_id,
                r.university_id,
                r.rank_end,
                r.metrics_json
            FROM deduped r
            JOIN warehouse.universities u
              ON u.university_id = r.university_id
            LEFT JOIN warehouse.countries c
              ON c.country_id = u.country_id
            -- Fallback for universities written before qs_profile_path was
            -- persisted: the id this source already has on record, so an
            -- ingest updates the existing mapping instead of creating a second
            -- one beside it and stranding whatever references the first.
            LEFT JOIN LATERAL (
                SELECT m.source_entity_id
                FROM warehouse.canonical_university cu
                JOIN warehouse.source_university_mapping m
                  ON m.canonical_university_id = cu.canonical_university_id
                JOIN warehouse.ranking_source rs
                  ON rs.ranking_source_id = m.ranking_source_id
                 AND rs.source_code = %(source_code)s
                WHERE cu.canonical_slug = u.school_slug
                ORDER BY m.first_seen_at ASC, m.source_mapping_id ASC
                LIMIT 1
            ) existing ON TRUE
            WHERE COALESCE(r.rank_start, r.rank_end) IS NOT NULL
            ORDER BY rank_position ASC, u.school_slug ASC
            """,
            {
                "ranking_year": int(ranking_year),
                "source_code": normalized_source,
                "ranking_type": ranking_type,
            },
        )
        rows = cur.fetchall()

    out: list[StandardizedRankingRecord] = []
    for (
        source_entity_id,
        display_name,
        country_name,
        rank_position,
        score,
        source_url,
        row_ranking_type,
        row_ranking_year,
        legacy_ranking_id,
        legacy_university_id,
        rank_end,
        metrics_json,
    ) in rows:
        entity_id = str(source_entity_id or "").strip() or str(display_name or "").strip()
        name = str(display_name or "").strip()
        if not entity_id or not name:
            continue
        out.append(
            StandardizedRankingRecord(
                source=normalized_source,
                source_entity_id=entity_id,
                university_name=name,
                country_hint=_clean(country_name),
                ranking_year=int(row_ranking_year),
                ranking_type=str(row_ranking_type or ranking_type),
                rank=None if rank_position is None else int(rank_position),
                score=None if score is None else float(score),
                source_url=_clean(source_url),
                source_version=str(row_ranking_year),
                universe_type=universe_type,
                universe_key=universe_key,
                metadata={
                    "raw_source": normalized_source,
                    "seeded_from": "warehouse.rankings",
                    # Named raw_row so the entity-review screen finds the source
                    # name and country here, as it does for THE and ARWU.
                    "raw_row": {
                        "name": name,
                        "location": _clean(country_name),
                        "rank": None if rank_position is None else str(rank_position),
                        "score": None if score is None else str(score),
                    },
                    "legacy_ranking_id": legacy_ranking_id,
                    "legacy_university_id": legacy_university_id,
                    "rank_end": rank_end,
                    "metrics_json": metrics_json or {},
                },
            )
        )
    return out


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
