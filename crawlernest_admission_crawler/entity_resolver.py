"""Resolve admission rows to canonical universities, to the rankings standard.

One resolver and one review path serve both domains. This module resolves with
the shared ``EntityResolver`` and then applies, in order, every rule the
ranking pipeline applies before it writes:

1. **Human decisions** in ``warehouse.mapping_review`` outrank the resolver
   (``apply_mapping_reviews``).
2. **A decision that did not apply** because its page came back under a new
   ``source_entity_id`` stops the run before any write
   (``refuse_reappeared_reviews``). Ingesting past it would re-credit a match a
   reviewer threw out -- or drop one a reviewer confirmed -- with no error. A
   decision whose page is simply absent is logged, never silent.
3. **An existing mapping** keeps its university: the page's URL identity
   outranks the name printed on it this time (``apply_mapping_continuity``).
   Moving a page to another university takes a remap.
4. Mappings are written to ``warehouse.source_university_mapping`` under
   ``source_code``, the same table and the same guarded upsert as QS, THE and
   ARWU. The legacy ``warehouse.source_mapping`` is neither read nor written.

Admission rows are resolved per page, not per row. One page now yields several
rows -- degree levels, programmes, intakes -- and they are one source entity:
resolving them separately could give one page two universities.

Each row keeps ``source_mapping_id``, the mapping that resolved it, or NULL when
the mapping no longer names the row's university -- the provenance rule
``ranking_record`` follows.

Ownership is unchanged: this reads warehouse.mapping_review and never writes
it. It writes warehouse.source_university_mapping,
analytics.entity_resolution_event, and the resolution columns of the admission
table.
"""

from __future__ import annotations

import logging
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable

from crawlernest_admission_crawler.postgres_driver import get_psycopg2
from crawlernest_admission_crawler.source_identity import (
    SOURCE_CODE,
    admission_entity_host,
    admission_source_entity_id,
)

# run_pipeline bootstraps these, but the package is also imported directly by
# tests and by ad-hoc scripts, where nothing has put crawlernest-core on the
# path yet.
_MODULE_ROOT = Path(__file__).resolve().parent.parent / "crawlernest" / "crawlernest-core"
if _MODULE_ROOT.is_dir() and str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from entity_resolution.repository import EntityResolutionRepository  # noqa: E402
from entity_resolution.resolver import EntityResolver  # noqa: E402
from entity_resolution.types import EntityRecord, ResolutionResult  # noqa: E402
from multi_source.continuity import MappingContinuityApplication, apply_mapping_continuity  # noqa: E402
from multi_source.repository import MultiSourceRepository  # noqa: E402
from multi_source.reviews import (  # noqa: E402
    MappingReview,
    MappingReviewApplication,
    apply_mapping_reviews,
    refuse_reappeared_reviews,
)

logger = logging.getLogger("crawlernest.admission.entity_resolver")

UNRESOLVED = "unresolved"

#: Methods that mean "a person should look at this". Mirrors the filter the
#: review queue applies, so the counts reported here and the rows a reviewer
#: sees cannot drift apart.
REVIEW_METHODS = frozenset({"fuzzy", "fuzzy_review", "embedding", "embedding_review"})


def _source_of(result: ResolutionResult) -> str:
    return result.source_name


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
    #: Source entities (pages) resolved; several rows can share one.
    entity_count: int = 0
    #: Pages kept on their existing mapping against the resolver's answer.
    held_by_existing_mapping_count: int = 0
    #: Standing decisions whose page was not in the table this run.
    unapplied_review_count: int = 0


@dataclass(slots=True)
class AdmissionEntity:
    """One page: the unit a mapping, and a review decision, is about."""

    source_code: str
    source_entity_id: str
    university_name: str
    country: str | None
    source_url: str
    row_ids: list[int] = field(default_factory=list)
    #: Every name the page's rows printed, most common first. More than one is
    #: worth a reviewer's attention, so it travels in raw_row.
    names_seen: list[str] = field(default_factory=list)

    @property
    def key(self) -> tuple[str, str]:
        return (self.source_code, self.source_entity_id)


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
        entities = group_rows_into_entities(rows)
        source_codes = sorted({entity.source_code for entity in entities}) or [SOURCE_CODE]

        if not entities:
            with conn.cursor() as cur:
                mapping_stats = _load_mapping_review_stats(cur, source_codes=tuple(source_codes))
            return _summary(
                target_schema, target_table, rows=[], entities=[], results=[],
                review_application=MappingReviewApplication(), continuity=MappingContinuityApplication(),
                retired_count=0, mapping_stats=mapping_stats,
            )

        repo = MultiSourceRepository(conn)
        er_repo = EntityResolutionRepository(conn)
        resolver = EntityResolver(er_repo.load_canonical_profiles())
        reviews = repo.load_mapping_reviews(source_codes)

        results, review_application, continuity = decide_admission_entities(
            entities,
            resolver=resolver,
            reviews=reviews,
            existing_mappings=repo.load_active_mappings([entity.key for entity in entities]),
        )

        # Everything above only read. The first write is here, after every
        # refusal had its chance.
        repo.upsert_entity_mappings(results, source_of=_source_of)
        retired_count = repo.deactivate_rejected_mappings(review_application.rejected_keys)

        with conn.cursor() as cur:
            live = _active_mapping_ids(cur, [entity.key for entity in entities])
            for entity, result in zip(entities, results):
                cur.execute(
                    f"""
                    UPDATE {target_schema}.{target_table}
                    SET canonical_university_id = %s,
                        source_mapping_id = %s,
                        entity_resolution_status = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ANY(%s)
                    """,
                    (
                        result.canonical_university_id,
                        provenance_mapping_id(live.get(entity.key), result.canonical_university_id),
                        result.matching_method,
                        entity.row_ids,
                    ),
                )
        conn.commit()

        for entity, result in zip(entities, results):
            er_repo.log_resolution_event(
                source_name=entity.source_code,
                source_entity_id=entity.source_entity_id,
                raw_name=entity.university_name,
                country_hint=entity.country,
                result=result,
            )

        with conn.cursor() as cur:
            mapping_stats = _load_mapping_review_stats(cur, source_codes=tuple(source_codes))
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return _summary(
        target_schema, target_table, rows=rows, entities=entities, results=results,
        review_application=review_application, continuity=continuity,
        retired_count=retired_count, mapping_stats=mapping_stats,
    )


def decide_admission_entities(
    entities: list[AdmissionEntity],
    *,
    resolver: EntityResolver,
    reviews: dict[tuple[str, str], MappingReview],
    existing_mappings: dict,
) -> tuple[list[ResolutionResult], MappingReviewApplication, MappingContinuityApplication]:
    """Every decision about which university each page is, before any write.

    Pure: no database. Raises ``UnappliedReviewError`` when a standing decision
    did not apply although its page is in the batch under another id.
    """
    results = [_resolve_entity(resolver, entity) for entity in entities]

    results, review_application = apply_mapping_reviews(results, reviews, source_of=_source_of)

    refuse_reappeared_reviews(
        reviews,
        review_application,
        _review_batch(entities),
        id_handle=admission_entity_host,
    )
    if review_application.unapplied_reviews:
        # Not refused: the page is absent from the table, so nothing is
        # misattributed. Logged so it is never quiet either.
        logger.warning(
            "%s standing admission mapping review(s) had no page in this run and were not applied: %s%s",
            len(review_application.unapplied_reviews),
            ", ".join(f"{code}:{eid}" for code, eid in review_application.unapplied_reviews[:5]),
            " ..." if len(review_application.unapplied_reviews) > 5 else "",
        )

    results, continuity = apply_mapping_continuity(results, existing_mappings, source_of=_source_of)
    for conflict in continuity.conflicts:
        if conflict.resolver_canonical_university_id is None:
            continue
        logger.warning(
            "kept admission page %s %s on canonical %s; the resolver matched it to %s by %s. "
            "File a remap in warehouse.mapping_review if the resolver is right.",
            conflict.source_code,
            conflict.source_entity_id,
            conflict.kept_canonical_university_id,
            conflict.resolver_canonical_university_id,
            conflict.resolver_method,
        )
    return results, review_application, continuity


def group_rows_into_entities(rows: Iterable[dict[str, Any]]) -> list[AdmissionEntity]:
    """Collapse rows to pages, keeping every row id and every printed name."""
    grouped: dict[tuple[str, str], AdmissionEntity] = {}
    names: dict[tuple[str, str], Counter] = {}
    for row in rows:
        key = (row["source_code"], row["source_entity_id"])
        entity = grouped.get(key)
        if entity is None:
            entity = AdmissionEntity(
                source_code=row["source_code"],
                source_entity_id=row["source_entity_id"],
                university_name=row["university_name"],
                country=row["country"],
                source_url=row["source_url"],
            )
            grouped[key] = entity
            names[key] = Counter()
        entity.row_ids.append(int(row["id"]))
        names[key][row["university_name"]] += 1
        if entity.country is None and row["country"]:
            entity.country = row["country"]

    out: list[AdmissionEntity] = []
    for key, entity in grouped.items():
        # Most common name first; ties go to the first row read (lowest id).
        ordered = [name for name, _ in names[key].most_common()]
        entity.names_seen = ordered
        entity.university_name = ordered[0]
        out.append(entity)
    return sorted(out, key=lambda e: e.key)


def provenance_mapping_id(live: tuple[int, int] | None, canonical_university_id: int | None) -> int | None:
    """The mapping a row may name: only one that credits the row's own university.

    ``live`` is (source_mapping_id, canonical_university_id) of the page's active
    mapping. If the guarded upsert declined to move it, or a reviewer rejected
    the page, the two disagree and NULL is the honest answer -- never a link to
    a mapping that credits someone else.
    """
    if live is None or canonical_university_id is None:
        return None
    mapping_id, mapping_canonical = live
    return mapping_id if mapping_canonical == canonical_university_id else None


def entity_resolution_summary_to_dict(summary: EntityResolutionSummary) -> dict[str, Any]:
    return asdict(summary)


def _review_batch(entities: list[AdmissionEntity]) -> list[tuple[str, str, str | None]]:
    """What refuse_reappeared_reviews compares a missing decision against."""
    return [
        (entity.source_code, entity.source_entity_id, name)
        for entity in entities
        for name in entity.names_seen
    ]


def _resolve_entity(resolver: EntityResolver, entity: AdmissionEntity) -> ResolutionResult:
    """Resolve one page, keeping the evidence a reviewer needs.

    ``raw_row`` is added to the metadata because the review screen reads the
    source's own name and country from ``metadata #>> '{raw_row,name}'`` and
    ``{raw_row,location}``. EntityResolver does not write those -- each source's
    own writer does -- and without them a reviewer sees a blank row and cannot
    judge the pair.
    """
    result = resolver.resolve_one(
        EntityRecord(
            source_name=entity.source_code,
            source_entity_id=entity.source_entity_id,
            university_name=entity.university_name,
            country_hint=entity.country,
        )
    )
    metadata = dict(result.metadata or {})
    raw_row: dict[str, Any] = {
        "name": entity.university_name,
        "location": entity.country,
        "source_url": entity.source_url,
        "row_count": len(entity.row_ids),
    }
    if len(entity.names_seen) > 1:
        raw_row["names_seen"] = list(entity.names_seen)
    metadata["raw_row"] = raw_row
    return replace(result, metadata=metadata)


def _resolve_row(resolver: EntityResolver, row: dict[str, Any]) -> ResolutionResult:
    """Resolve a single row as its own page. Kept for callers that hold one row."""
    return _resolve_entity(
        resolver,
        group_rows_into_entities([{"source_code": SOURCE_CODE, **row, "id": row.get("id", 0)}])[0],
    )


def _load_admission_rows(
    cur: "psycopg2.extensions.cursor",
    *,
    target_schema: str,
    target_table: str,
) -> list[dict[str, Any]]:
    """Read the rows to resolve, deriving source_entity_id where it is missing."""
    cur.execute(
        f"""
        SELECT
            id,
            source_code,
            source_entity_id,
            university_name,
            country,
            source_url
        FROM {target_schema}.{target_table}
        ORDER BY id ASC
        """
    )
    rows: list[dict[str, Any]] = []
    for row_id, source_code, source_entity_id, university_name, country, source_url in cur.fetchall():
        rows.append(
            {
                "id": int(row_id),
                "source_code": str(source_code or SOURCE_CODE),
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


def _active_mapping_ids(
    cur: "psycopg2.extensions.cursor",
    keys: list[tuple[str, str]],
) -> dict[tuple[str, str], tuple[int, int]]:
    """(source_mapping_id, canonical_university_id) of each page's active mapping."""
    if not keys:
        return {}
    cur.execute(
        """
        SELECT m.source_code, m.source_entity_id, m.source_mapping_id, m.canonical_university_id
        FROM warehouse.source_university_mapping m
        JOIN unnest(%s::text[], %s::text[]) AS k(source_code, source_entity_id)
          ON k.source_code = m.source_code
         AND k.source_entity_id = m.source_entity_id
        WHERE m.is_active
        """,
        ([code for code, _ in keys], [entity_id for _, entity_id in keys]),
    )
    return {
        (str(code), str(entity_id)): (int(mapping_id), int(canonical_id))
        for code, entity_id, mapping_id, canonical_id in cur.fetchall()
    }


def _summary(
    target_schema: str,
    target_table: str,
    *,
    rows: list[dict[str, Any]],
    entities: list[AdmissionEntity],
    results: list[ResolutionResult],
    review_application: MappingReviewApplication,
    continuity: MappingContinuityApplication,
    retired_count: int,
    mapping_stats: dict[str, int],
) -> EntityResolutionSummary:
    counts = _empty_counts()
    for entity, result in zip(entities, results):
        for _ in entity.row_ids:
            _tally(counts, result)
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
        entity_count=len(entities),
        held_by_existing_mapping_count=len(continuity.conflicts),
        unapplied_review_count=len(review_application.unapplied_reviews),
        **mapping_stats,
    )


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


def _load_mapping_review_stats(
    cur: "psycopg2.extensions.cursor",
    *,
    source_codes: tuple[str, ...],
) -> dict[str, int]:
    """Review-queue figures for these sources, from the unified mapping table.

    ``manual_review_mapping_count`` is the active fuzzy or embedding mappings
    with no standing decision -- what the review queue offers. It used to count
    warehouse.source_mapping.review_status = 'manual_review', a column the
    unified table does not have and the queue never read.
    """
    empty = {
        "manual_review_mapping_count": 0,
        "suspicious_mapping_count": 0,
        "country_mismatch_mapping_count": 0,
    }
    if not source_codes:
        return empty
    cur.execute(
        """
        SELECT
            COUNT(*) FILTER (
                WHERE m.is_active
                  AND m.match_method = ANY(%s)
                  AND r.mapping_review_id IS NULL
            ),
            COUNT(*) FILTER (WHERE m.is_active AND m.metadata ->> 'suspicious_merge' = 'true'),
            COUNT(*) FILTER (WHERE m.is_active AND m.metadata ->> 'country_mismatch' = 'true')
        FROM warehouse.source_university_mapping m
        LEFT JOIN warehouse.mapping_review r
          ON r.source_code = m.source_code
         AND r.source_entity_id = m.source_entity_id
        WHERE m.source_code = ANY(%s)
        """,
        (sorted(REVIEW_METHODS), list(source_codes)),
    )
    row = cur.fetchone()
    if row is None:
        return empty
    return {
        "manual_review_mapping_count": int(row[0] or 0),
        "suspicious_mapping_count": int(row[1] or 0),
        "country_mismatch_mapping_count": int(row[2] or 0),
    }
