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
        max_rank_by_source = self._max_rank_by_source(rows)
        grouped: dict[int, list[RankingRecordInput]] = defaultdict(list)
        for r in rows:
            grouped[int(r.canonical_university_id)].append(r)

        outputs: list[AggregatedRankingOutput] = []
        configured_total_weight = sum(max(0.0, float(w)) for w in self.config.source_weights.values()) or 1.0

        for cid, uni_rows in grouped.items():
            source_ranks: dict[str, Optional[float]] = {}
            source_norm_scores: dict[str, Optional[float]] = {}
            source_weights_used: dict[str, float] = {}

            for rec in uni_rows:
                source = rec.source.upper().strip()
                rank_v = _parse_rank(rec.rank)
                source_ranks[source] = rank_v

                rank_norm = None
                if rank_v is not None:
                    max_rank = max_rank_by_source.get(source)
                    if max_rank is None:
                        max_rank = self.config.source_rank_fallback_max.get(source, 1000)
                    rank_norm = _normalize_rank_to_100(rank_v, max_rank)

                score_norm = _normalize_score_to_100(
                    source=source,
                    score=rec.score,
                    score_scales=self.config.source_score_scales,
                )

                if rank_norm is not None and score_norm is not None:
                    blend = min(1.0, max(0.0, float(self.config.score_rank_blend)))
                    norm = blend * score_norm + (1.0 - blend) * rank_norm
                else:
                    norm = score_norm if score_norm is not None else rank_norm

                source_norm_scores[source] = round(norm, 6) if norm is not None else None
                if norm is not None:
                    source_weights_used[source] = max(0.0, float(self.config.source_weights.get(source, 0.0)))

            weighted_sum = 0.0
            used_weight_sum = 0.0
            for source, norm_score in source_norm_scores.items():
                if norm_score is None:
                    continue
                w = source_weights_used.get(source, 0.0)
                if w <= 0:
                    continue
                weighted_sum += w * norm_score
                used_weight_sum += w

            # Graceful missing handling:
            # divide only by used weights (not all configured weights),
            # so schools missing one source are not automatically penalized.
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
                        "configured_total_weight": configured_total_weight,
                        "used_weight_sum": round(used_weight_sum, 6),
                        "max_rank_by_source": max_rank_by_source,
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


def _normalize_rank_to_100(rank: float, max_rank: int) -> Optional[float]:
    if rank <= 0 or max_rank <= 0:
        return None
    # rank=1 => near 100, rank=max_rank => near 0
    score = 100.0 * (max_rank - rank + 1.0) / max_rank
    return min(100.0, max(0.0, score))


def _normalize_score_to_100(source: str, score: Optional[float], score_scales: dict[str, float]) -> Optional[float]:
    if score is None:
        return None
    try:
        s = float(score)
    except Exception:
        return None
    if s < 0:
        return None
    scale = score_scales.get(source)
    if scale is not None and scale > 0:
        return min(100.0, max(0.0, (s / scale) * 100.0))
    # Heuristic fallback when source scale unknown.
    if s <= 1.0:
        return s * 100.0
    if s <= 100.0:
        return s
    return None


def _assign_dense_display_rank(rows: list[AggregatedRankingOutput], tie_epsilon: float) -> list[AggregatedRankingOutput]:
    sorted_rows = sorted(
        rows,
        key=lambda r: (r.composite_score is None, -(r.composite_score or 0.0), r.canonical_university_id),
    )
    out: list[AggregatedRankingOutput] = []
    cur_rank = 0
    prev_score: Optional[float] = None
    for row in sorted_rows:
        if row.composite_score is None:
            out.append(replace(row, display_rank=None))
            continue
        if prev_score is None or abs((row.composite_score or 0.0) - prev_score) > tie_epsilon:
            cur_rank += 1
            prev_score = row.composite_score
        out.append(replace(row, display_rank=cur_rank))
    return out
