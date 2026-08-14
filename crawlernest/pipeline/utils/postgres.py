"""Shared PostgreSQL connection and multi-source pipeline construction.

Both run_pipeline.py and the extracted command modules need these, so they live
here rather than in the entry point, which would have forced the command modules
to import their own caller.

:func:`build_multi_source_pipeline` imports its collaborators inside the function
on purpose. They come from the hyphenated module directories that
``pipeline.bootstrap.bootstrap_module_paths`` puts on ``sys.path``, and that runs
partway through run_pipeline's import. Importing them at module level here would
make this module's own import order load-bearing; deferring them means it can be
imported whenever and still work, which is how the other command modules behave.
"""

from __future__ import annotations

from typing import Any, Optional

try:
    import psycopg2
except ImportError:  # pragma: no cover - reported by the caller
    psycopg2 = None  # type: ignore


def connect_postgres(
    pg_host: Optional[str],
    pg_port: int,
    pg_database: Optional[str],
    pg_user: Optional[str],
    pg_password: Optional[str],
) -> Any:
    """Open a psycopg2 connection, or explain why it cannot."""
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is required for PostgreSQL mode")
    return psycopg2.connect(
        host=pg_host,
        port=pg_port,
        database=pg_database,
        user=pg_user,
        password=pg_password,
    )


def build_multi_source_pipeline(conn: Any) -> Any:
    """Assemble the multi-source ranking pipeline against an open connection."""
    from entity_resolution import EntityResolver
    from entity_resolution.repository import EntityResolutionRepository
    from multi_source import MultiSourceRankingPipeline
    from multi_source.repository import MultiSourceRepository
    from ranking_aggregation.repository import RankingAggregationRepository

    er_repo = EntityResolutionRepository(conn)
    profiles = er_repo.load_canonical_profiles()
    if not profiles:
        raise RuntimeError(
            "No canonical university profiles found. Seed entity resolution tables before multi-source ingestion."
        )
    resolver = EntityResolver(profiles)
    return MultiSourceRankingPipeline(
        resolver=resolver,
        multi_source_repo=MultiSourceRepository(conn),
        aggregation_repo=RankingAggregationRepository(conn),
    )
