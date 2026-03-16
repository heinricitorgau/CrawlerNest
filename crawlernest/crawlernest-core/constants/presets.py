"""
Ranking presets and configurations for QS University Rankings.
"""

import json
import os
from typing import Dict, List, Tuple

# Subject ranking presets
SUBJECT_PRESETS: Dict[str, Dict[str, str]] = {
    "general": {
        "ranking_id": "3990755",
        "name": "QS World University Rankings 2025"
    }
}

# Load subject rankings from JSON file
_subject_json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "subject_ranking_ids.json")
if os.path.exists(_subject_json_path):
    with open(_subject_json_path, "r", encoding="utf-8") as f:
        _subject_data = json.load(f)
    for subject, ranking_id in _subject_data.items():
        SUBJECT_PRESETS[subject] = {
            "ranking_id": ranking_id,
            "name": f"{subject} (QS Subject)"
        }

# Ranking page URL presets
RANKING_PAGE_PRESETS: Dict[str, str] = {
    "world": "https://www.topuniversities.com/world-university-rankings",
    "sustainability": "https://www.topuniversities.com/sustainability-rankings",
    "mba": "https://www.topuniversities.com/mba-rankings/global",
    "business_analytics": "https://www.topuniversities.com/business-masters-rankings/business-analytics",
    "finance": "https://www.topuniversities.com/business-masters-rankings/finance",
    "management": "https://www.topuniversities.com/business-masters-rankings/management",
    "marketing": "https://www.topuniversities.com/business-masters-rankings/marketing",
    "supply_chain_management": "https://www.topuniversities.com/business-masters-rankings/supply-chain-management",
    "city_rankings": "https://www.topuniversities.com/city-rankings",
}

# Regional ranking presets
REGION_PAGE_PRESETS: List[Tuple[str, str]] = [
    ("Asia University Rankings", "https://www.topuniversities.com/asia-university-rankings"),
    ("Europe University Rankings", "https://www.topuniversities.com/europe-university-rankings"),
    ("Latin America & The Caribbean Rankings", "https://www.topuniversities.com/latin-america-caribbean-rankings"),
    ("Sub-Saharan Africa University Rankings 2026", "https://www.topuniversities.com/sub-saharan-africa-university-rankings"),
    ("Arab Region", "https://www.topuniversities.com/arab-region-rankings"),
]

# Subregional ranking presets
REGION_SUBREGION_PRESETS: List[Tuple[str, str]] = [
    # Asia
    ("Asia University Rankings", "https://www.topuniversities.com/asia-university-rankings"),
    ("Central Asia", "https://www.topuniversities.com/asia-university-rankings-central-asia"),
    ("Southern Asia", "https://www.topuniversities.com/asia-university-rankings-southern-asia"),
    ("Eastern Asia", "https://www.topuniversities.com/asia-university-rankings-eastern-asia"),
    ("South-eastern Asia", "https://www.topuniversities.com/asia-university-rankings-south-eastern-asia"),
    ("Western Asia", "https://www.topuniversities.com/europe-university-rankings-western-asia"),
    # Europe
    ("Europe University Rankings", "https://www.topuniversities.com/europe-university-rankings"),
    ("Northern Europe", "https://www.topuniversities.com/europe-university-rankings-northern-europe"),
    ("Western Europe", "https://www.topuniversities.com/europe-university-rankings-western-europe"),
    ("Eastern Europe", "https://www.topuniversities.com/europe-university-rankings-eastern-europe"),
    ("Southern Europe", "https://www.topuniversities.com/europe-university-rankings-southern-europe"),
    # Latin America & The Caribbean
    ("Latin America & The Caribbean Rankings", "https://www.topuniversities.com/latin-america-caribbean-rankings"),
    ("The Caribbean", "https://www.topuniversities.com/latin-america-caribbean-rankings-the-caribbean"),
    ("Central America", "https://www.topuniversities.com/latin-america-central-america-rankings"),
    ("South America", "https://www.topuniversities.com/latin-america-south-america-rankings"),
    # Arab Region
    ("Arab Region University Rankings", "https://www.topuniversities.com/arab-region-rankings"),
    # Sub-Saharan Africa
    ("Sub-Saharan Africa University Rankings 2026", "https://www.topuniversities.com/sub-saharan-africa-university-rankings"),
]
