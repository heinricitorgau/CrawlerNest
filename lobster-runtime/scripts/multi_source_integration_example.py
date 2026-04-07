#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = REPO_ROOT / "crawlernest-core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from entity_resolution import CanonicalProfile, EntityResolver
from multi_source.adapters import ARWUAdapter, QSAdapter, THEAdapter
from multi_source import integrate_sources
from models import University


def main() -> None:
    canonical_profiles = [
        CanonicalProfile(
            canonical_university_id=1,
            display_name="Massachusetts Institute of Technology",
            country_hint="united states",
            aliases=("MIT", "Massachusetts Inst. of Tech", "麻省理工學院"),
        ),
        CanonicalProfile(
            canonical_university_id=2,
            display_name="Stanford University",
            country_hint="united states",
            aliases=("Stanford",),
        ),
    ]
    resolver = EntityResolver(canonical_profiles)

    # QS payload uses existing University model
    qs_payload = [
        University(rank="1", name="MIT", country="United States", path="/universities/massachusetts-institute-technology-mit"),
        University(rank="2", name="Stanford University", country="United States", path="/universities/stanford-university"),
    ]
    the_payload = [
        {"id": "the:mit", "name": "Massachusetts Institute of Technology", "country": "United States", "year": 2026, "rank": 3, "score": 95.2},
        {"id": "the:stanford", "name": "Stanford", "country": "United States", "year": 2026, "rank": 4, "score": 94.9},
    ]
    arwu_payload = [
        {"id": "arwu:mit", "name": "麻省理工學院", "country": "United States", "year": 2026, "rank": 2, "score": None},
    ]

    qs_rows = QSAdapter(ranking_year=2026, ranking_type="world").adapt(qs_payload)
    the_rows = THEAdapter(default_year=2026, ranking_type="world").adapt(the_payload)
    arwu_rows = ARWUAdapter(default_year=2026, ranking_type="world").adapt(arwu_payload)

    unified_rows, diagnostics = integrate_sources(qs_rows + the_rows + arwu_rows, resolver=resolver)

    print("Diagnostics:", diagnostics)
    for row in unified_rows:
        print(
            f"canonical={row.canonical_university_id} source={row.source} "
            f"year={row.year} rank={row.rank} score={row.score} "
            f"method={row.matching_method} conf={row.confidence_score:.4f}"
        )


if __name__ == "__main__":
    main()
