from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from statistics import mean, pstdev
from typing import Any

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


def load_aggregated_rows_from_postgres(
    conn: Any,
    *,
    schema_name: str = "analytics",
    table_name: str = "aggregated_rankings",
) -> list[AggregatedRankingRow]:
    """Load aggregated ranking rows for the decision preview.

    This used to read warehouse.aggregated_rankings_preview, the middle table of
    a landing chain that was dropped along with warehouse.ranking_records_preview
    (see docs/migrations/RANKING_SCHEMA_CONVERGENCE.md). The published analytics
    aggregation is the surviving source, so the decision preview reads that.

    It stores less than the preview table did: there is no normalized name, no
    source count and no standard deviation. The first comes from
    canonical_university; the other two are recomputed here from
    source_ranks_json with the arithmetic the deleted chain used -- the mean of
    the per-source ranks, and their population standard deviation -- so a row
    built from analytics matches what that chain would have produced. Sources
    with a null rank are absent from the warehouse for that year and are dropped
    rather than counted; see the null-valued THE/ARWU keys described in
    CLAUDE.md.
    """
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                cu.display_name_normalized,
                ar.ranking_year,
                ar.source_ranks_json,
                ar.aggregation_method_version
            FROM {schema_name}.{table_name} ar
            JOIN warehouse.canonical_university cu
              ON cu.canonical_university_id = ar.canonical_university_id
            WHERE cu.display_name_normalized IS NOT NULL
              AND cu.display_name_normalized <> ''
            ORDER BY ar.ranking_year, ar.display_rank, cu.display_name_normalized
            """
        )
        rows = cur.fetchall()

    payload: list[AggregatedRankingRow] = []
    for row in rows:
        sources = {
            str(source_name).strip().upper(): int(rank)
            for source_name, rank in dict(row[2] or {}).items()
            if rank is not None and str(source_name).strip()
        }
        ranks = list(sources.values())
        if not ranks:
            continue
        payload.append(
            AggregatedRankingRow(
                normalized_university_name=str(row[0]),
                ranking_year=int(row[1]),
                aggregated_rank=float(mean(ranks)),
                source_count=len(ranks),
                std_deviation=float(pstdev(ranks)) if len(ranks) > 1 else 0.0,
                aggregation_method=str(row[3] or ""),
                sources=dict(sorted(sources.items())),
            )
        )
    return payload


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
