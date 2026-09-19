from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from statistics import pstdev

from crawlernest_ranking_crawler.aggregator import AggregatedRankingRow
from crawlernest_ranking_crawler.explain_layer import RankingExplain
from crawlernest_ranking_crawler.trust_layer import RankingTrust


@dataclass(slots=True)
class RankingDecisionRow:
    normalized_university_name: str
    ranking_year: int
    aggregated_rank: float
    source_count: int
    std_deviation: float
    trust_score: float
    trust_level: str
    sources: dict[str, Any]
    aggregation_explain: dict[str, Any]
    trust_explain: dict[str, Any]


@dataclass(slots=True)
class DecisionWriteSummary:
    row_count: int
    inserted_row_count: int
    target_location: str
    table_name: str


def load_aggregated_rows_from_postgres(conn: Any) -> list[AggregatedRankingRow]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                normalized_university_name,
                ranking_year,
                aggregated_rank,
                source_count,
                std_deviation,
                aggregation_method,
                sources
            FROM warehouse.aggregated_rankings_preview
            ORDER BY ranking_year, aggregated_rank, normalized_university_name
            """
        )
        rows = cur.fetchall()

    payload: list[AggregatedRankingRow] = []
    for row in rows:
        payload.append(
            AggregatedRankingRow(
                normalized_university_name=str(row[0]),
                ranking_year=int(row[1]),
                aggregated_rank=float(row[2]),
                source_count=int(row[3]),
                std_deviation=float(row[4]),
                aggregation_method=str(row[5]),
                sources=dict(row[6] or {}),
            )
        )
    return payload


#: The universe the recommendation reader serves. Region, subject and special
#: universes rank a different population, and mixing them would put one
#: university in the candidate pool several times over.
WAREHOUSE_UNIVERSE_TYPE = "global"
WAREHOUSE_UNIVERSE_KEY = "global"

WAREHOUSE_AGGREGATED_SQL = """
    SELECT cu.display_name_normalized,
           v.ranking_year,
           v.display_rank,
           v.source_ranks_json,
           v.aggregation_method_version
    FROM analytics.v_aggregated_rankings_latest v
    JOIN warehouse.canonical_university cu
      ON cu.canonical_university_id = v.canonical_university_id
    WHERE v.universe_type = %s
      AND v.universe_key = %s
      AND v.display_rank IS NOT NULL
      AND cu.display_name_normalized IS NOT NULL
      AND btrim(cu.display_name_normalized) <> ''
    ORDER BY v.ranking_year, v.display_rank, cu.display_name_normalized
"""


def aggregated_rows_from_warehouse_records(records: Any) -> list[AggregatedRankingRow]:
    """Decision-layer rows for the editions the warehouse actually holds.

    The preview loader below reads ``warehouse.aggregated_rankings_preview``, which
    is built from the sample artifact and holds two demo universities. The reader
    that consumes the decision table serves real recommendations, so these rows
    come from the aggregated rankings themselves.

    Two fields are taken rather than recomputed: ``aggregated_rank`` is the
    published composite position (the reader falls back to it for a global rank, so
    a mean of source ranks would contradict the rank shown everywhere else), and
    ``aggregation_method`` is the version that produced it. ``std_deviation`` is the
    spread of the source ranks, as in ``aggregator.aggregate_rankings`` -- the trust
    layer reads it, and it is not stored per row.

    A university with no per-source rank is skipped: the reader takes its source
    ranks from here, and a row with none would enter the candidate pool claiming no
    sources at all. Names are the join key, so the first row of a repeated
    (name, year) wins -- ordered by rank, that is the better-placed one, and the
    table's own UNIQUE constraint would otherwise drop an arbitrary one.
    """
    rows: list[AggregatedRankingRow] = []
    seen: set[tuple[str, int]] = set()
    for record in records:
        name = str(record[0] or "").strip()
        ranking_year = _safe_int(record[1], default=0)
        if not name or ranking_year == 0:
            continue
        key = (name, ranking_year)
        if key in seen:
            continue

        sources: dict[str, int] = {}
        for source, rank in dict(_as_mapping(record[3])).items():
            if rank is None:
                continue
            source_name = str(source).strip().upper()
            if source_name:
                sources[source_name] = int(rank)
        if not sources:
            continue

        seen.add(key)
        ranks = list(sources.values())
        rows.append(
            AggregatedRankingRow(
                normalized_university_name=name,
                ranking_year=ranking_year,
                aggregated_rank=float(_safe_float(record[2], default=0.0)),
                source_count=len(ranks),
                std_deviation=float(pstdev(ranks)) if len(ranks) > 1 else 0.0,
                aggregation_method=str(record[4] or "rank_agg_v1"),
                sources=dict(sorted(sources.items())),
            )
        )
    return rows


def load_aggregated_rows_from_warehouse(
    conn: Any,
    *,
    universe_type: str = WAREHOUSE_UNIVERSE_TYPE,
    universe_key: str = WAREHOUSE_UNIVERSE_KEY,
) -> list[AggregatedRankingRow]:
    with conn.cursor() as cur:
        cur.execute(WAREHOUSE_AGGREGATED_SQL, (universe_type, universe_key))
        records = cur.fetchall()
    return aggregated_rows_from_warehouse_records(records)


def _as_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    return json.loads(str(value))


def _safe_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_decision_row(row: Any, explain: RankingExplain) -> RankingDecisionRow:
    aggregation_explain = asdict(explain.aggregation)
    trust_explain = asdict(explain.trust)
    return RankingDecisionRow(
        normalized_university_name=str(_get_field(row, "normalized_university_name") or "").strip(),
        ranking_year=_safe_int(_get_field(row, "ranking_year"), default=0),
        aggregated_rank=round(_safe_float(_get_field(row, "aggregated_rank"), default=0.0), 6),
        source_count=_safe_int(_get_field(row, "source_count"), default=0),
        std_deviation=round(_safe_float(_get_field(row, "std_deviation"), default=0.0), 6),
        trust_score=round(_safe_float(explain.trust.trust_score, default=0.0), 6),
        trust_level=str(explain.trust.trust_level),
        sources=dict(sorted((_get_field(row, "sources") or {}).items())),
        aggregation_explain=aggregation_explain,
        trust_explain=trust_explain,
    )


def write_decision_rows(
    rows: list[RankingDecisionRow],
    conn: Any,
    *,
    schema_name: str = "warehouse",
    table_name: str = "ranking_decision_preview",
) -> DecisionWriteSummary:
    inserted_row_count = 0
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {schema_name}.{table_name} (
                    id BIGSERIAL PRIMARY KEY,
                    normalized_university_name TEXT NOT NULL,
                    ranking_year INTEGER NOT NULL,
                    aggregated_rank DOUBLE PRECISION NOT NULL,
                    source_count INTEGER NOT NULL,
                    std_deviation DOUBLE PRECISION NOT NULL,
                    trust_score DOUBLE PRECISION NOT NULL,
                    trust_level TEXT NOT NULL,
                    sources JSONB NOT NULL,
                    aggregation_explain JSONB NOT NULL,
                    trust_explain JSONB NOT NULL,
                    UNIQUE (normalized_university_name, ranking_year)
                )
                """
            )

            for row in rows:
                cur.execute(
                    f"""
                    INSERT INTO {schema_name}.{table_name} (
                        normalized_university_name,
                        ranking_year,
                        aggregated_rank,
                        source_count,
                        std_deviation,
                        trust_score,
                        trust_level,
                        sources,
                        aggregation_explain,
                        trust_explain
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
                    ON CONFLICT (normalized_university_name, ranking_year)
                    DO NOTHING
                    """,
                    (
                        row.normalized_university_name,
                        row.ranking_year,
                        row.aggregated_rank,
                        row.source_count,
                        row.std_deviation,
                        row.trust_score,
                        row.trust_level,
                        json.dumps(row.sources, ensure_ascii=False),
                        json.dumps(row.aggregation_explain, ensure_ascii=False),
                        json.dumps(row.trust_explain, ensure_ascii=False),
                    ),
                )
                inserted_row_count += cur.rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    dsn_parameters = conn.get_dsn_parameters()
    host = dsn_parameters.get("host", "localhost")
    port = dsn_parameters.get("port", "5432")
    database = dsn_parameters.get("dbname") or dsn_parameters.get("database") or ""
    return DecisionWriteSummary(
        row_count=len(rows),
        inserted_row_count=inserted_row_count,
        target_location=f"postgresql://{host}:{port}/{database}#{schema_name}.{table_name}",
        table_name=f"{schema_name}.{table_name}",
    )


def decision_write_summary_to_dict(summary: DecisionWriteSummary) -> dict[str, Any]:
    return asdict(summary)


def ranking_trust_to_dict(trust: RankingTrust) -> dict[str, Any]:
    return asdict(trust)


def _get_field(row: Any, field_name: str) -> Any:
    if isinstance(row, dict):
        return row.get(field_name)
    return getattr(row, field_name)


def _safe_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
