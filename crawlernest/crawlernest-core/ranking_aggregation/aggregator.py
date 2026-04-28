from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from typing import Iterable, Optional

from .config import AggregationConfig, default_aggregation_config
from .types import AggregatedRankingOutput, RankingRecordInput


class RankingAggregator:
    def __init__(self, config: Optional[AggregationConfig] = None):
        self.config = config or default_aggregation_config()

    def aggregate_rankings(self, records: Iterable[RankingRecordInput]) -> list[AggregatedRankingOutput]:
        rows = [r for r in records]
        if not rows:
            return []

        by_year_and_universe: dict[tuple[int, str, str], list[RankingRecordInput]] = defaultdict(list)
        for r in rows:
            by_year_and_universe[
                (
                    int(r.year),
                    str(r.universe_type or "global").strip().lower(),
                    str(r.universe_key or "global").strip().lower(),
                )
            ].append(r)

        all_outputs: list[AggregatedRankingOutput] = []
        for (year, universe_type, universe_key), grouped_rows in sorted(by_year_and_universe.items()):
            all_outputs.extend(
                self._aggregate_single_universe(grouped_rows, year, universe_type, universe_key)
            )
        return all_outputs

    def _aggregate_single_universe(
        self,
        rows: list[RankingRecordInput],
        year: int,
        universe_type: str,
        universe_key: str,
    ) -> list[AggregatedRankingOutput]:
        grouped: dict[int, list[RankingRecordInput]] = defaultdict(list)
        for r in rows:
            grouped[int(r.canonical_university_id)].append(r)

        outputs: list[AggregatedRankingOutput] = []
        configured_weights = {
            source.upper().strip(): max(0.0, float(weight))
            for source, weight in self.config.source_weights.items()
        }
        configured_total_weight = sum(configured_weights.values()) or 1.0
        configured_sources = list(configured_weights)

        for cid, uni_rows in grouped.items():
            source_ranks: dict[str, Optional[float]] = {}
            source_norm_scores: dict[str, Optional[float]] = {}
            source_weights_used: dict[str, Optional[float]] = {}
            best_rank_by_source: dict[str, float] = {}

            for rec in uni_rows:
                source = rec.source.upper().strip()
                if source not in configured_weights:
                    continue
                rank_v = _parse_rank(rec.rank)
                if rank_v is None:
                    continue
                previous = best_rank_by_source.get(source)
                if previous is None or rank_v < previous:
                    best_rank_by_source[source] = rank_v

            weighted_sum = 0.0
            used_weight_sum = 0.0
            available_rank_count = 0
            for source in configured_sources:
                rank_v = best_rank_by_source.get(source)
                source_ranks[source] = rank_v
                norm_score = _normalize_rank_reciprocal(rank_v)
                source_norm_scores[source] = round(norm_score, 6) if norm_score is not None else None
                if rank_v is None or norm_score is None:
                    source_weights_used[source] = None
                    continue
                w = configured_weights.get(source, 0.0)
                source_weights_used[source] = w
                weighted_sum += w * norm_score
                used_weight_sum += w
                available_rank_count += 1

            composite = (weighted_sum / used_weight_sum) if used_weight_sum > 0 else None
            coverage_ratio = used_weight_sum / configured_total_weight

            outputs.append(
                AggregatedRankingOutput(
                    canonical_university_id=cid,
                    year=year,
                    universe_type=universe_type,
                    universe_key=universe_key,
                    source_ranks=source_ranks,
                    source_normalized_scores=source_norm_scores,
                    source_weights_used=source_weights_used,
                    composite_score=round(composite, 6) if composite is not None else None,
                    display_rank=None,
                    coverage_ratio=round(coverage_ratio, 6),
                    aggregation_method_version=self.config.aggregation_method_version,
                    metadata={
                        "available_rank_count": available_rank_count,
                        "configured_total_weight": configured_total_weight,
                        "used_weight_sum": round(used_weight_sum, 6),
                        "normalization": "1.0 / rank",
                    },
                )
            )

        return _assign_dense_display_rank(outputs, tie_epsilon=self.config.tie_epsilon)

    def _max_rank_by_source(self, rows: list[RankingRecordInput]) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in rows:
            source = r.source.upper().strip()
            rv = _parse_rank(r.rank)
            if rv is None:
                continue
            iv = int(round(rv))
            if iv <= 0:
                continue
            cur = out.get(source)
            if cur is None or iv > cur:
                out[source] = iv
        for source, fallback in self.config.source_rank_fallback_max.items():
            s = source.upper().strip()
            if s in out:
                out[s] = max(out[s], int(fallback))
            else:
                out[s] = int(fallback)
        return out


def aggregate_rankings(records: list[RankingRecordInput], config: Optional[AggregationConfig] = None) -> list[AggregatedRankingOutput]:
    return RankingAggregator(config=config).aggregate_rankings(records)


def _parse_rank(rank: object) -> Optional[float]:
    if rank is None:
        return None
    if isinstance(rank, (int, float)):
        v = float(rank)
        return v if v > 0 else None
    s = str(rank).strip()
    if not s:
        return None
    s = s.replace(",", "")
    # Handles "201-250", "201–250", "201~250"
    for sep in ("-", "–", "~"):
        if sep in s:
            parts = [p.strip() for p in s.split(sep) if p.strip()]
            if len(parts) == 2:
                try:
                    a = float(parts[0])
                    b = float(parts[1])
                    if a > 0 and b > 0:
                        return (a + b) / 2.0
                except Exception:
                    return None
    try:
        v = float(s)
        return v if v > 0 else None
    except Exception:
        return None


def _normalize_rank_reciprocal(rank: Optional[float]) -> Optional[float]:
    if rank is None or rank <= 0:
        return None
    return 1.0 / rank


def _assign_dense_display_rank(rows: list[AggregatedRankingOutput], tie_epsilon: float) -> list[AggregatedRankingOutput]:
    sorted_rows = sorted(
        rows,
        key=lambda r: (
            r.composite_score is None,
            -float(r.composite_score or 0.0),
            r.canonical_university_id,
        ),
    )
    out: list[AggregatedRankingOutput] = []
    cur_rank = 0
    prev_composite_score: Optional[float] = None
    for row in sorted_rows:
        if row.composite_score is None:
            out.append(replace(row, display_rank=None))
            continue
        current_composite_score = float(row.composite_score)
        if prev_composite_score is None or abs(current_composite_score - prev_composite_score) > tie_epsilon:
            cur_rank += 1
            prev_composite_score = current_composite_score
        out.append(replace(row, display_rank=cur_rank))
    return out
