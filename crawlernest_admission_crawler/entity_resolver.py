"""Resolve admission rows to canonical universities.

This used to be an exact-match lookup of its own: lowercase the name, try
``canonical_university.display_name_normalized``, then
``university_alias.alias_normalized``, give up. Measured against the eight
checked-in admission snapshots it resolved 3 of 8, while the resolver the
ranking side already uses resolved 8 of 8 -- the misses being
``University of Melbourne`` against ``The University of Melbourne`` and
``National University of Singapore`` against
``National University of Singapore (NUS)``, exactly the shapes
``EntityResolver`` was built to handle.

So there is one resolver now, and one review path. Fuzzy matches from
admission sources land in ``warehouse.source_mapping``, surface in the same
review queue as ranking matches through ``warehouse.v_entity_mapping``, and a
reviewer's standing decision in ``warehouse.mapping_review`` outranks the
resolver here just as it does in MultiSourceRankingPipeline.

Ownership is unchanged: this reads warehouse.mapping_review and never writes
it. It writes warehouse.source_mapping, analytics.entity_resolution_event, and
the canonical columns of the admission table.
"""

from __future__ import annotations

import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from crawlernest_admission_crawler.postgres_driver import get_psycopg2
from crawlernest_admission_crawler.source_identity import (
    SOURCE_CODE,
    admission_source_entity_id,
)

# run_pipeline bootstraps these, but the package is also imported directly by
# tests and by ad-hoc scripts, where nothing has put crawlernest-core on the
# path yet.
_MODULE_ROOT = Path(__file__).resolve().parent.parent / "crawlernest" / "crawlernest-core"
if _MODULE_ROOT.is_dir() and str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from entity_resolution.repository import EntityResolutionRepository  # noqa: E402
from entity_resolution.resolver import EntityResolver, ResolverThresholds  # noqa: E402
from entity_resolution.types import EntityRecord  # noqa: E402
from multi_source.repository import MultiSourceRepository  # noqa: E402
from multi_source.reviews import apply_mapping_reviews  # noqa: E402

UNRESOLVED = "unresolved"

#: Methods that mean "a person should look at this". Mirrors the filter the
#: review queue applies, so the counts reported here and the rows a reviewer
#: sees cannot drift apart.
REVIEW_METHODS = frozenset({"fuzzy", "fuzzy_review", "embedding", "embedding_review"})


@dataclass(slots=True)
class EntityResolutionSummary:
    target_table: str
    total_rows: int
    resolved_row_count: int
    unresolved_row_count: int
    exact_match_count: int
    normalized_match_count: int
    fuzzy_match_count: int
    review_pending_count: int
    retired_mapping_count: int
    manual_review_mapping_count: int
    suspicious_mapping_count: int
    country_mismatch_mapping_count: int
    human_decision_applied_count: int


def resolve_admission_preview_entities(
    *,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
    target_schema: str = "warehouse",
    target_table: str = "admission_record",
) -> EntityResolutionSummary:
    psycopg2 = get_psycopg2()
    conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        dbname=pg_database,
        user=pg_user,
        password=pg_password,
    )
    try:
        with conn.cursor() as cur:
            rows = _load_admission_rows(cur, target_schema=target_schema, target_table=target_table)

        if not rows:
            with conn.cursor() as cur:
                mapping_stats = _load_mapping_review_stats(cur, source_names=(SOURCE_CODE,))
            return EntityResolutionSummary(
                target_table=f"{target_schema}.{target_table}",
                total_rows=0,
                resolved_row_count=0,
                unresolved_row_count=0,
                exact_match_count=0,
                normalized_match_count=0,
                fuzzy_match_count=0,
                review_pending_count=0,
                retired_mapping_count=0,
                human_decision_applied_count=0,
                **mapping_stats,
            )

        er_repo = EntityResolutionRepository(conn)
        resolver = EntityResolver(er_repo.load_canonical_profiles())
        thresholds = ResolverThresholds()

        results = [_resolve_row(resolver, row) for row in rows]

        # Human decisions outrank the resolver and are applied before anything
        # is written, for the same reason as on the ranking side: the mapping
        # upsert below would overwrite a decision stored after it.
        reviews = MultiSourceRepository(conn).load_mapping_reviews([SOURCE_CODE])
        results, review_application = apply_mapping_reviews(
            results,
            reviews,
            source_of=lambda result: result.source_name,
        )

        counts = _empty_counts()
        with conn.cursor() as cur:
            for row, result in zip(rows, results):
                _tally(counts, result)
                cur.execute(
                    f"""
                    UPDATE {target_schema}.{target_table}
                    SET canonical_university_id = %s,
                        entity_resolution_status = %s
                    WHERE id = %s
                    """,
                    (result.canonical_university_id, result.matching_method, row["id"]),
                )
        conn.commit()

        # upsert_source_mapping skips unresolved results, so nothing new is
        # written for a rejected entity. Both helpers commit for themselves.
        for row, result in zip(rows, results):
            er_repo.upsert_source_mapping(result, threshold_used=thresholds.fuzzy_review)
            er_repo.log_resolution_event(
                source_name=SOURCE_CODE,
                source_entity_id=result.source_entity_id,
                raw_name=row["university_name"],
                country_hint=row["country"],
                result=result,
            )

        # Skipping the upsert is not enough on its own: a mapping written by an
        # earlier run still sits there asserting the match the reviewer threw
        # out, and warehouse.v_entity_mapping would keep offering it for review.
        # Retiring it is how the credit is actually withdrawn -- the same move
        # MultiSourceRepository.deactivate_rejected_mappings makes for rankings.
        with conn.cursor() as cur:
            retired_count = _deactivate_rejected_mappings(cur, review_application.rejected_keys)
        conn.commit()

        with conn.cursor() as cur:
            mapping_stats = _load_mapping_review_stats(cur, source_names=(SOURCE_CODE,))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return EntityResolutionSummary(
        target_table=f"{target_schema}.{target_table}",
        total_rows=len(rows),
        resolved_row_count=counts["resolved"],
        unresolved_row_count=counts["unresolved"],
        exact_match_count=counts["exact"],
        normalized_match_count=counts["normalized"],
        fuzzy_match_count=counts["fuzzy"],
        review_pending_count=counts["review_pending"],
        retired_mapping_count=retired_count,
        human_decision_applied_count=review_application.applied,
        **mapping_stats,
    )


def entity_resolution_summary_to_dict(summary: EntityResolutionSummary) -> dict[str, Any]:
    return asdict(summary)


def _resolve_row(resolver: EntityResolver, row: dict[str, Any]):
    """Resolve one admission row, keeping the evidence a reviewer needs.

    ``raw_row`` is added to the metadata because the review screen reads the
    source's own name and country from ``metadata #>> '{raw_row,name}'`` and
    ``{raw_row,location}``. EntityResolver does not write those -- each source's
    own writer does -- and without them a reviewer sees a blank row and cannot
    judge the pair.
    """
    result = resolver.resolve_one(
        EntityRecord(
            source_name=SOURCE_CODE,
            source_entity_id=row["source_entity_id"],
            university_name=row["university_name"],
            country_hint=row["country"],
        )
    )
    metadata = dict(result.metadata or {})
    metadata["raw_row"] = {
        "name": row["university_name"],
        "location": row["country"],
        "source_url": row["source_url"],
    }
    return replace(result, metadata=metadata)


def _load_admission_rows(
    cur: "psycopg2.extensions.cursor",
    *,
    target_schema: str,
    target_table: str,
) -> list[dict[str, Any]]:
    """Read the rows to resolve, deriving source_entity_id where it is missing.

    The column is nullable until it becomes half of the natural key, so a row
    written before that migration still has to resolve rather than crash.
    """
    cur.execute(
        f"""
        SELECT
            id,
            source_entity_id,
            university_name,
            country,
            source_url
        FROM {target_schema}.{target_table}
        ORDER BY id ASC
        """
    )
    rows: list[dict[str, Any]] = []
    for row_id, source_entity_id, university_name, country, source_url in cur.fetchall():
        rows.append(
            {
                "id": int(row_id),
                "source_entity_id": (
                    str(source_entity_id)
                    if source_entity_id
                    else admission_source_entity_id(str(source_url or ""))
                ),
                "university_name": str(university_name or ""),
                "country": None if country is None else str(country).strip() or None,
                "source_url": str(source_url or ""),
            }
        )
    return rows


def _empty_counts() -> dict[str, int]:
    return {
        "resolved": 0,
        "unresolved": 0,
        "exact": 0,
        "normalized": 0,
        "fuzzy": 0,
        "review_pending": 0,
    }


def _tally(counts: dict[str, int], result: Any) -> None:
    method = result.matching_method
    if result.canonical_university_id is None:
        counts["unresolved"] += 1
    else:
        counts["resolved"] += 1

    if method.startswith("exact"):
        counts["exact"] += 1
    elif method.startswith("normalized"):
        counts["normalized"] += 1
    elif method.startswith("fuzzy") or method.startswith("embedding"):
        counts["fuzzy"] += 1

    if method in REVIEW_METHODS:
        counts["review_pending"] += 1


def _deactivate_rejected_mappings(
    cur: "psycopg2.extensions.cursor",
    rejected_keys: tuple[tuple[str, str], ...],
) -> int:
    """Retire the mappings a reviewer threw out. Returns how many were live."""
    retired = 0
    for source_name, source_entity_id in rejected_keys:
        cur.execute(
            """
            UPDATE warehouse.source_mapping
            SET is_active = FALSE,
                review_status = 'rejected',
                last_seen_at = CURRENT_TIMESTAMP
            WHERE source_name = %s
              AND source_entity_id = %s
              AND is_active
            """,
            (source_name, source_entity_id),
        )
        retired += cur.rowcount
    return retired


def _load_mapping_review_stats(
    cur: "psycopg2.extensions.cursor",
    *,
    source_names: tuple[str, ...],
) -> dict[str, int]:
    if not source_names:
        return {
            "manual_review_mapping_count": 0,
            "suspicious_mapping_count": 0,
            "country_mismatch_mapping_count": 0,
        }

    cur.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'warehouse'
          AND table_name = 'source_mapping'
        LIMIT 1
        """
    )
    if cur.fetchone() is None:
        return {
            "manual_review_mapping_count": 0,
            "suspicious_mapping_count": 0,
            "country_mismatch_mapping_count": 0,
        }

    cur.execute(
        """
        SELECT
            COUNT(*) FILTER (WHERE review_status = 'manual_review') AS manual_review_mapping_count,
            COUNT(*) FILTER (WHERE COALESCE((metadata ->> 'suspicious_merge')::boolean, FALSE)) AS suspicious_mapping_count,
            COUNT(*) FILTER (WHERE COALESCE((metadata ->> 'country_mismatch')::boolean, FALSE)) AS country_mismatch_mapping_count
        FROM warehouse.source_mapping
        WHERE source_name = ANY(%s)
        """,
        (list(source_names),),
    )
    row = cur.fetchone()
    return {
        "manual_review_mapping_count": 0 if row is None or row[0] is None else int(row[0]),
        "suspicious_mapping_count": 0 if row is None or row[1] is None else int(row[1]),
        "country_mismatch_mapping_count": 0 if row is None or row[2] is None else int(row[2]),
    }
