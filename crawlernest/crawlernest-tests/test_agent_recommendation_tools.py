from __future__ import annotations

import unittest
from typing import Any

from crawlernest.agent.tools.recommendation_tools import RecommendationTools


class CapturingRecommendationService:
    def __init__(self) -> None:
        self.profile: dict[str, Any] | None = None

    def recommend(self, profile: dict[str, Any]) -> dict[str, Any]:
        self.profile = profile
        return {
            "items": [
                {
                    "universityName": "National Taiwan University",
                    "country": profile.get("country"),
                }
            ],
            "metadata": {
                "country": profile.get("country"),
                "country_policy": profile.get("country_policy"),
                "country_preference_mode": profile.get("country_preference_mode"),
            },
        }


class TestAgentRecommendationTools(unittest.TestCase):
    def test_taiwan_recommendation_prompt_sets_hard_filter_payload(self) -> None:
        service = CapturingRecommendationService()
        tools = RecommendationTools(service=service)  # type: ignore[arg-type]

        response = tools.recommend(
            {},
            "Recommend Taiwan universities for IELTS 6.5 and target rank 100",
        )

        assert service.profile is not None
        self.assertEqual(service.profile["country"], "Taiwan")
        self.assertEqual(service.profile["countryPolicy"], "hard_filter")
        self.assertEqual(service.profile["country_policy"], "hard_filter")
        self.assertEqual(service.profile["country_preference_mode"], "hard_filter")
        self.assertEqual(service.profile["ielts"], 6.5)
        self.assertEqual(service.profile["targetRank"], 100)
        names = [item["universityName"] for item in response["items"]]
        self.assertNotIn("Massachusetts Institute of Technology", names)
        self.assertNotIn("Harvard University", names)
        self.assertNotIn("University of Oxford", names)

    def test_taiwan_country_aliases_map_to_same_country_key(self) -> None:
        tools = RecommendationTools(service=CapturingRecommendationService())  # type: ignore[arg-type]

        prompts = [
            "Recommend Taiwan universities",
            "Recommend Taiwanese universities",
            "Recommend universities in Taiwan",
            "Recommend Taiwan schools",
            "推薦台灣大學",
            "推薦臺灣大學",
            "推薦國立台灣大學",
            "推薦國立臺灣大學",
        ]

        for prompt in prompts:
            with self.subTest(prompt=prompt):
                merged = tools._merge_prompt_context({}, prompt)
                self.assertEqual(merged["country"], "Taiwan")
                self.assertEqual(merged["countryPolicy"], "hard_filter")
                self.assertEqual(merged["country_preference_mode"], "hard_filter")


if __name__ == "__main__":
    unittest.main()
