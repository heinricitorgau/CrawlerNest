from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from crawlernest_ranking_crawler.aggregator import AggregatedRankingRow


@dataclass(slots=True)
class AggregationWriteSummary:
    row_count: int
    written_row_count: int
    target_location: str
    table_name: str


def write_aggregated_rows(
    rows: list[AggregatedRankingRow],
    conn: Any,
    *,
    schema_name: str = "warehouse",
    table_name: str = "aggregated_rankings_preview",
) -> AggregationWriteSummary:
    written_row_count = 0
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
                aggregation_method TEXT NOT NULL,
                sources JSONB NOT NULL,
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
                    aggregation_method,
                    sources
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (normalized_university_name, ranking_year)
                DO NOTHING
                """,
                (
                    row.normalized_university_name,
                    row.ranking_year,
                    row.aggregated_rank,
                    row.source_count,
                    row.std_deviation,
                    row.aggregation_method,
                    json.dumps(row.sources, ensure_ascii=False),
                ),
            )
            written_row_count += cur.rowcount

    conn.commit()
    dsn_parameters = conn.get_dsn_parameters()
    host = dsn_parameters.get("host", "localhost")
    port = dsn_parameters.get("port", "5432")
    database = dsn_parameters.get("dbname") or dsn_parameters.get("database") or ""
    return AggregationWriteSummary(
        row_count=len(rows),
        written_row_count=written_row_count,
        target_location=f"postgresql://{host}:{port}/{database}#{schema_name}.{table_name}",
        table_name=f"{schema_name}.{table_name}",
    )


def aggregation_write_summary_to_dict(summary: AggregationWriteSummary) -> dict[str, Any]:
    return asdict(summary)
