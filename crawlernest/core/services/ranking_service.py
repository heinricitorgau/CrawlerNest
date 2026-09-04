from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from crawlernest.core.database.settings import DatabaseSettings
from crawlernest.core.dataset import DATASET_YEAR

try:
    import psycopg2
except ImportError:  # pragma: no cover
    psycopg2 = None  # type: ignore


@dataclass(slots=True)
class RankingQuery:
    # The warehouse holds one year. Defaulting to a literal here is how a
    # query silently outlives the snapshot it was written against.
    year: int = DATASET_YEAR
    scope: str = "global"
    page: int = 1
    page_size: int = 20
    search: str = ""
    country: str = ""
    region: str = ""


class RankingService:
    def __init__(self, db_settings: DatabaseSettings | None = None) -> None:
        self._db_settings = db_settings or DatabaseSettings.from_env()

    def list_rankings(self, query: RankingQuery) -> dict[str, Any]:
        if psycopg2 is None:
            raise RuntimeError("psycopg2 is required for RankingService")

        conn = psycopg2.connect(
            host=self._db_settings.host,
            port=self._db_settings.port,
            dbname=self._db_settings.database,
            user=self._db_settings.user,
            password=self._db_settings.password,
        )
        try:
            with conn.cursor() as cur:
                where_clauses = [
                    "rr.canonical_university_id IS NOT NULL",
                    "rr.universe_type = 'global'",
                    "rr.ranking_year = %s",
                ]
                params: list[Any] = [query.year]

                if query.search.strip():
                    where_clauses.append(
                        "(cu.display_name ILIKE %s OR cu.canonical_slug ILIKE %s OR COALESCE(c.country_name, '') ILIKE %s)"
                    )
                    pattern = f"%{query.search.strip()}%"
                    params.extend([pattern, pattern, pattern])

                if query.country.strip():
                    where_clauses.append(
                        "COALESCE(ac.country, c.country_name, 'Unknown') = %s"
                    )
                    params.append(query.country.strip())

                region_case = """
                    CASE
                        WHEN country IN ('United Kingdom', 'Ireland', 'France', 'Germany', 'Italy', 'Spain', 'Netherlands', 'Switzerland', 'Sweden', 'Denmark', 'Belgium', 'Austria', 'Norway', 'Finland', 'Portugal', 'Poland', 'Czech Republic') THEN 'Europe'
                        WHEN country IN ('United States', 'Canada', 'Mexico') THEN 'North America'
                        WHEN country IN ('China', 'China (mainland)', 'Hong Kong SAR', 'Japan', 'South Korea', 'Singapore', 'India', 'Taiwan', 'Malaysia', 'Thailand', 'Indonesia', 'Pakistan') THEN 'Asia'
                        WHEN country IN ('Australia', 'New Zealand') THEN 'Oceania'
                        WHEN country IN ('Brazil', 'Argentina', 'Chile', 'Colombia', 'Mexico', 'Peru') THEN 'Latin America'
                        WHEN country IN ('South Africa', 'Egypt', 'Morocco', 'Kenya', 'Nigeria', 'Ghana') THEN 'Africa'
                        ELSE 'Other'
                    END
                """
                if query.scope == "region" and query.region.strip():
                    where_clauses.append(f"{region_case} = %s")
                    params.append(query.region.strip())

                where_sql = " AND ".join(where_clauses)
                offset = max(query.page - 1, 0) * max(query.page_size, 1)

                cur.execute(
                    f"""
                    WITH admission_country AS (
                        SELECT
                            canonical_university_id,
                            MIN(country) AS country
                        FROM warehouse.admission_record
                        WHERE canonical_university_id IS NOT NULL
                        GROUP BY canonical_university_id
                    ),
                    per_university AS (
                        SELECT
                            rr.canonical_university_id,
                            cu.display_name AS university_name,
                            cu.canonical_slug AS slug,
                            COALESCE(ac.country, c.country_name, 'Unknown') AS country,
                            MIN(rr.rank_position)::INTEGER AS aggregated_rank,
                            COUNT(DISTINCT rs.source_code)::INTEGER AS source_count,
                            (ARRAY_AGG(rs.source_code ORDER BY rr.rank_position ASC, rs.source_code ASC))[1] AS primary_source,
                            MAX(rr.ranking_year)::INTEGER AS ranking_year
                        FROM warehouse.ranking_record rr
                        JOIN warehouse.canonical_university cu
                            ON cu.canonical_university_id = rr.canonical_university_id
                        LEFT JOIN admission_country ac
                            ON ac.canonical_university_id = rr.canonical_university_id
                        LEFT JOIN warehouse.countries c
                            ON c.country_id = cu.country_id
                        JOIN warehouse.ranking_source rs
                            ON rs.ranking_source_id = rr.ranking_source_id
                        WHERE {where_sql}
                        GROUP BY rr.canonical_university_id, cu.display_name, cu.canonical_slug, COALESCE(ac.country, c.country_name, 'Unknown'), c.country_name
                    ),
                    ranked AS (
                        SELECT
                            *,
                            {region_case} AS region_name,
                            ROW_NUMBER() OVER (ORDER BY aggregated_rank ASC, university_name ASC) AS global_rank,
                            ROW_NUMBER() OVER (
                                PARTITION BY {region_case}
                                ORDER BY aggregated_rank ASC, university_name ASC
                            ) AS scope_rank
                        FROM per_university
                    ),
                    counted AS (
                        SELECT COUNT(*)::INTEGER AS total_count FROM ranked
                    )
                    SELECT
                        r.canonical_university_id,
                        r.university_name,
                        r.slug,
                        r.country,
                        r.aggregated_rank,
                        r.global_rank,
                        CASE WHEN %s = 'region' THEN r.scope_rank ELSE r.global_rank END AS scope_rank,
                        GREATEST(0, 100 - r.aggregated_rank * 2)::DOUBLE PRECISION AS composite_score,
                        r.primary_source,
                        r.source_count,
                        r.ranking_year,
                        c.total_count
                    FROM ranked r
                    CROSS JOIN counted c
                    ORDER BY r.global_rank ASC
                    LIMIT %s OFFSET %s
                    """,
                    [*params, query.scope, query.page_size, offset],
                )
                rows = cur.fetchall()
        finally:
            conn.close()

        items: list[dict[str, Any]] = []
        total_count = 0
        for row in rows:
            total_count = int(row[11])
            items.append(
                {
                    "canonicalUniversityId": int(row[0]),
                    "universityName": str(row[1]),
                    "slug": str(row[2]),
                    "country": str(row[3]),
                    "aggregatedRank": int(row[4]),
                    "globalRank": int(row[5]),
                    "scopeRank": int(row[6]),
                    "compositeScore": float(row[7]),
                    "primarySource": str(row[8]),
                    "sourceCount": int(row[9]),
                    "rankingYear": int(row[10]),
                }
            )

        return {
            "items": items,
            "metadata": {
                "totalCount": total_count,
                "page": query.page,
                "pageSize": query.page_size,
            },
        }
