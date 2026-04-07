#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg2

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = REPO_ROOT / "crawlernest-core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from multi_source.repository import MultiSourceRepository
from multi_source.types import UnifiedRankingRecord
from ranking_aggregation import RankingRecordInput, default_aggregation_config
from ranking_aggregation.aggregator import aggregate_rankings
from ranking_aggregation.repository import RankingAggregationRepository


SOURCE_NAME_MAP = {
    "QS": "QS World University Rankings",
    "THE": "Times Higher Education World University Rankings",
    "ARWU": "Academic Ranking of World Universities",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed multi-source ranking tables and aggregated rankings from legacy warehouse.rankings"
    )
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--database", default="clawer")
    parser.add_argument("--user", default="test")
    parser.add_argument("--password", default="")
    parser.add_argument("--year", type=int, default=None, help="Optional single ranking year to backfill")
    parser.add_argument("--run-label", default="legacy_backfill")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    conn = psycopg2.connect(
        host=args.host,
        port=args.port,
        database=args.database,
        user=args.user,
        password=args.password,
    )
    try:
        rows = _load_legacy_rows(conn, year=args.year)
        unified_rows = _to_unified_rows(rows)
        if not unified_rows:
            print("[warn] no legacy ranking rows found for backfill")
            return 0

        ms_repo = MultiSourceRepository(conn)
        source_defs = _collect_source_defs(unified_rows)
        source_id_map = ms_repo.upsert_ranking_sources(source_defs)
        ms_repo.upsert_source_university_mappings(unified_rows, source_id_map)
        ms_repo.upsert_ranking_records(unified_rows, source_id_map)

        aggregation_inputs = [
            RankingRecordInput(
                canonical_university_id=row.canonical_university_id,
                source=row.source,
                year=row.year,
                rank=row.rank,
                score=row.score,
                metadata_json=row.metadata,
            )
            for row in unified_rows
            if row.canonical_university_id is not None
        ]
        agg_outputs = aggregate_rankings(aggregation_inputs, config=default_aggregation_config())
        agg_repo = RankingAggregationRepository(conn)

        years = sorted({row.year for row in aggregation_inputs})
        run_ids: dict[int, int] = {}
        for year in years:
            year_inputs = [r for r in aggregation_inputs if r.year == year]
            year_outputs = [r for r in agg_outputs if r.year == year]
            run_id = agg_repo.create_aggregation_run(
                year=year,
                universe_type="global",
                universe_key="global",
                config=default_aggregation_config(),
                input_record_count=len(year_inputs),
                run_label=f"{args.run_label}_{year}",
                notes="Backfilled from warehouse.rankings",
            )
            agg_repo.upsert_source_weight_config(default_aggregation_config())
            agg_repo.upsert_aggregated_rankings(run_id, year_outputs)
            agg_repo.finish_aggregation_run(run_id, len(year_outputs), status="finished")
            run_ids[year] = run_id

        print(f"[ok] seeded ranking sources: {len(source_id_map)}")
        print(f"[ok] seeded ranking records: {len(unified_rows)}")
        print(f"[ok] seeded aggregated ranking rows: {len(agg_outputs)}")
        print(f"[ok] aggregation runs by year: {run_ids}")
        return 0
    finally:
        conn.close()



def _load_legacy_rows(conn, year: int | None) -> list[tuple]:
    sql = """
        SELECT
            cul.canonical_university_id,
            u.school_slug,
            u.display_name,
            c.country_name,
            r.ranking_source,
            r.ranking_type,
            r.ranking_year,
            r.rank_start,
            r.rank_end,
            r.score,
            r.source_url,
            r.metrics_json
        FROM warehouse.rankings r
        JOIN warehouse.universities u
          ON u.university_id = r.university_id
        JOIN warehouse.canonical_university_link cul
          ON cul.university_id = u.university_id
        LEFT JOIN warehouse.countries c
          ON c.country_id = u.country_id
        WHERE (%s IS NULL OR r.ranking_year = %s)
          AND r.ranking_source IS NOT NULL
    """
    with conn.cursor() as cur:
        cur.execute(sql, (year, year))
        return cur.fetchall()



def _to_unified_rows(rows: list[tuple]) -> list[UnifiedRankingRecord]:
    out: list[UnifiedRankingRecord] = []
    for (
        canonical_university_id,
        school_slug,
        display_name,
        country_name,
        ranking_source,
        ranking_type,
        ranking_year,
        rank_start,
        rank_end,
        score,
        source_url,
        metrics_json,
    ) in rows:
        source_code = str(ranking_source or "").strip().upper()
        if not source_code:
            continue
        rank_position = rank_start or rank_end
        out.append(
            UnifiedRankingRecord(
                canonical_university_id=int(canonical_university_id),
                source=source_code,
                source_entity_id=str(school_slug),
                rank=int(rank_position) if rank_position is not None else None,
                score=float(score) if score is not None else None,
                year=int(ranking_year) if ranking_year is not None else 0,
                ranking_type=_normalize_ranking_type(ranking_type),
                matched_alias=display_name,
                confidence_score=1.0,
                matching_method="legacy_seed",
                source_url=source_url,
                source_version=None,
                metadata={
                    "legacy_rank_end": rank_end,
                    "legacy_metrics_json": metrics_json,
                },
            )
        )
    return out



def _collect_source_defs(rows: list[UnifiedRankingRecord]) -> list[tuple[str, str, str | None]]:
    out: list[tuple[str, str, str | None]] = []
    seen: set[str] = set()
    for row in rows:
        if row.source in seen:
            continue
        seen.add(row.source)
        out.append((row.source, SOURCE_NAME_MAP.get(row.source, row.source), None))
    return out


def _normalize_ranking_type(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "world"
    if text.isdigit():
        return "world"
    return text


if __name__ == "__main__":
    raise SystemExit(main())
