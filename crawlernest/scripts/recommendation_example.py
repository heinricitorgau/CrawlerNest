#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = REPO_ROOT / "crawlernest-core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from recommendation_engine import (
    RecommendationCandidate,
    RecommendationQuery,
    default_recommendation_config,
    recommend_universities,
)


def main() -> None:
    candidates = [
        RecommendationCandidate(
            canonical_university_id=1,
            university_name="University of Oxford",
            country="UK",
            ranking_year=2026,
            aggregated_rank=4,
            aggregated_score=98.7,
            coverage_ratio=1.0,
            ielts_min=7.0,
            source_ranks={"QS": 3, "THE": 1, "ARWU": 7},
            aggregation_method_version="rank_agg_v1",
        ),
        RecommendationCandidate(
            canonical_university_id=2,
            university_name="University of Birmingham",
            country="UK",
            ranking_year=2026,
            aggregated_rank=76,
            aggregated_score=84.2,
            coverage_ratio=0.75,
            ielts_min=6.5,
            source_ranks={"QS": 80, "THE": 93},
            aggregation_method_version="rank_agg_v1",
        ),
        RecommendationCandidate(
            canonical_university_id=3,
            university_name="University of Leeds",
            country="UK",
            ranking_year=2026,
            aggregated_rank=92,
            aggregated_score=81.6,
            coverage_ratio=0.75,
            ielts_min=6.0,
            source_ranks={"QS": 82, "THE": 128},
            aggregation_method_version="rank_agg_v1",
        ),
        RecommendationCandidate(
            canonical_university_id=4,
            university_name="University of Toronto",
            country="Canada",
            ranking_year=2026,
            aggregated_rank=18,
            aggregated_score=94.1,
            coverage_ratio=1.0,
            ielts_min=6.5,
            source_ranks={"QS": 17, "THE": 21, "ARWU": 24},
            aggregation_method_version="rank_agg_v1",
        ),
    ]

    query = RecommendationQuery(
        country="UK",
        ielts_score=6.5,
        target_rank=100,
        preferred_ranking_source="QS",
        limit=3,
        ranking_year=2026,
    )
    results = recommend_universities(candidates, query, config=default_recommendation_config())
    for row in results:
        print(
            f"cid={row.canonical_university_id} name={row.university_name} country={row.country} "
            f"agg_rank={row.aggregated_rank} ielts_min={row.ielts_min} score={row.matching_score:.2f}"
        )
        print(f"  explanation={row.explanation}")
        print(f"  rules={row.score_breakdown.rules_passed}")


if __name__ == "__main__":
    main()
