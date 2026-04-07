#!/usr/bin/env python3
from __future__ import annotations

"""
Example integration point:
crawler -> extractor -> normalization -> ENTITY RESOLUTION -> DB write
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = REPO_ROOT / "crawlernest-core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from entity_resolution import CanonicalProfile, EntityRecord, EntityResolver


def main() -> None:
    canonical_profiles = [
        CanonicalProfile(
            canonical_university_id=1,
            display_name="Massachusetts Institute of Technology",
            country_hint="united states",
            aliases=(
                "MIT",
                "Massachusetts Inst. of Tech",
                "麻省理工學院",
            ),
        ),
        CanonicalProfile(
            canonical_university_id=2,
            display_name="Stanford University",
            country_hint="united states",
            aliases=("Stanford", "史丹佛大學"),
        ),
    ]

    resolver = EntityResolver(canonical_profiles=canonical_profiles)

    incoming = [
        EntityRecord(
            source_name="QS",
            source_entity_id="/universities/massachusetts-institute-technology-mit",
            university_name="MIT",
            country_hint="united states",
        ),
        EntityRecord(
            source_name="THE",
            source_entity_id="inst-12345",
            university_name="Massachusetts Inst. of Tech",
            country_hint="united states",
        ),
        EntityRecord(
            source_name="ARWU",
            source_entity_id="arwu-8899",
            university_name="麻省理工學院",
            country_hint="united states",
        ),
    ]

    results = resolver.resolve_batch(incoming)
    for r in results:
        print(
            f"{r.source_name}:{r.source_entity_id} -> "
            f"canonical={r.canonical_university_id}, "
            f"alias={r.matched_alias}, "
            f"score={r.confidence_score:.4f}, "
            f"method={r.matching_method}"
        )


if __name__ == "__main__":
    main()
