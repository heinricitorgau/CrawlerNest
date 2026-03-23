#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = REPO_ROOT / "crawlernest-core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from ranking_aggregation import RankingRecordInput, aggregate_rankings, default_aggregation_config


def main() -> None:
    records = [
        RankingRecordInput(
            canonical_university_id=1,
            source="QS",
            year=2026,
            rank=10,
            score=None,
        ),
        RankingRecordInput(
            canonical_university_id=1,
            source="THE",
            year=2026,
            rank=25,
            score=None,
        ),
        RankingRecordInput(
            canonical_university_id=1,
            source="ARWU",
            year=2026,
            rank=40,
            score=None,
        ),
        RankingRecordInput(
            canonical_university_id=2,
            source="QS",
            year=2026,
            rank=30,
            score=None,
        ),
        RankingRecordInput(
            canonical_university_id=2,
            source="THE",
            year=2026,
            rank=28,
            score=None,
        ),
    ]

    outputs = aggregate_rankings(records, config=default_aggregation_config())
    for row in outputs:
        print(
            f"cid={row.canonical_university_id} year={row.year} rank={row.display_rank} "
            f"composite={row.composite_score} coverage={row.coverage_ratio} "
            f"source_ranks={row.source_ranks} "
            f"norm={row.source_normalized_scores} "
            f"weights={row.source_weights_used} "
            f"method={row.aggregation_method_version}"
        )


if __name__ == "__main__":
    main()
