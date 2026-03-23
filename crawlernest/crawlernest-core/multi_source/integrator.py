from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from entity_resolution import EntityRecord, EntityResolver, normalize_university_name

from .types import StandardizedRankingRecord, UnifiedRankingRecord

logger = logging.getLogger("MultiSourceIntegrator")


@dataclass(frozen=True)
class IntegrationDiagnostics:
    total_records: int
    unique_resolution_keys: int
    duplicate_resolution_saves: int
    unresolved_count: int
    by_source_count: dict[str, int]


class MultiSourceIntegrator:
    """
    Integrates standardized ranking rows from multiple sources by:
    1) batching entity-resolution calls on de-duplicated keys
    2) producing unified rows linked by canonical_university_id
    3) preserving source-specific rank/score (no overwrite)
    """

    def __init__(self, resolver: EntityResolver):
        self.resolver = resolver

    def integrate_sources(self, records: Iterable[StandardizedRankingRecord]) -> tuple[list[UnifiedRankingRecord], IntegrationDiagnostics]:
        rows = list(records)
        if not rows:
            diag = IntegrationDiagnostics(0, 0, 0, 0, {})
            return [], diag

        # Deduplicate resolution calls by normalized name + country hint.
        key_to_rows: dict[tuple[str, str], list[StandardizedRankingRecord]] = defaultdict(list)
        for r in rows:
            norm = normalize_university_name(r.university_name)
            country = (r.country_hint or "").strip().lower()
            key_to_rows[(norm, country)].append(r)

        resolution_inputs: list[EntityRecord] = []
        key_order: list[tuple[str, str]] = []
        for idx, ((norm, country), grouped_rows) in enumerate(key_to_rows.items(), start=1):
            sample = grouped_rows[0]
            key_order.append((norm, country))
            resolution_inputs.append(
                EntityRecord(
                    source_name="MULTI_SOURCE",
                    source_entity_id=f"resolve-key:{idx}",
                    university_name=sample.university_name,
                    country_hint=sample.country_hint,
                    metadata={"resolution_key": (norm, country)},
                )
            )

        resolution_results = self.resolver.resolve_batch(resolution_inputs)
        key_to_resolution = {k: v for k, v in zip(key_order, resolution_results)}

        unified: list[UnifiedRankingRecord] = []
        unresolved = 0
        by_source: dict[str, int] = defaultdict(int)
        for r in rows:
            by_source[r.source] += 1
            norm = normalize_university_name(r.university_name)
            country = (r.country_hint or "").strip().lower()
            resolved = key_to_resolution.get((norm, country))
            if resolved is None or resolved.canonical_university_id is None:
                unresolved += 1
            unified.append(
                UnifiedRankingRecord(
                    canonical_university_id=resolved.canonical_university_id if resolved else None,
                    source=r.source,
                    source_entity_id=r.source_entity_id,
                    rank=r.rank,
                    score=r.score,
                    year=r.ranking_year,
                    ranking_type=r.ranking_type,
                    matched_alias=resolved.matched_alias if resolved else None,
                    confidence_score=resolved.confidence_score if resolved else 0.0,
                    matching_method=resolved.matching_method if resolved else "unresolved",
                    source_url=r.source_url,
                    source_version=r.source_version,
                    metadata={
                        **dict(r.metadata or {}),
                        **(dict(resolved.metadata) if resolved and resolved.metadata else {}),
                    },
                )
            )

        diag = IntegrationDiagnostics(
            total_records=len(rows),
            unique_resolution_keys=len(key_to_rows),
            duplicate_resolution_saves=len(rows) - len(key_to_rows),
            unresolved_count=unresolved,
            by_source_count=dict(by_source),
        )
        logger.info(
            "Integration summary: total=%s unique_keys=%s unresolved=%s duplicate_saves=%s by_source=%s",
            diag.total_records,
            diag.unique_resolution_keys,
            diag.unresolved_count,
            diag.duplicate_resolution_saves,
            diag.by_source_count,
        )
        return unified, diag


def integrate_sources(
    records: Iterable[StandardizedRankingRecord],
    resolver: EntityResolver,
) -> tuple[list[UnifiedRankingRecord], IntegrationDiagnostics]:
    return MultiSourceIntegrator(resolver=resolver).integrate_sources(records)
