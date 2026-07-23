"""Characterization tests for WebContextBuilder._build_summary_facts.

These pin the exact summary-fact output for each task kind so the god-method can
be split into per-task helpers without changing behavior. Golden values were
captured from the pre-refactor implementation.
"""

from __future__ import annotations

import unittest

from crawlernest.agent.web_agent.generation.context_builder import WebContextBuilder


class TestSummaryFacts(unittest.TestCase):
    def setUp(self) -> None:
        self.cb = WebContextBuilder()

    def test_university_lookup(self) -> None:
        raw = {
            "summary": "Preview loaded.",
            "universityDisplayName": "National Taiwan University",
            "aliases": ["NTU", "台大"],
            "identitySummary": {
                "cityName": "Taipei",
                "websiteUrl": "https://ntu.edu.tw",
                "matchedBy": "name",
                "matchedValue": "NTU",
            },
            "rankingSummary": {"bestRank": 68, "bestSource": "QS"},
            "admissionSummary": {
                "countries": ["Taiwan"],
                "bestIeltsRequirement": 6.5,
                "bestToeflRequirement": 90,
            },
            "dataAvailability": {
                "missingSections": ["admission"],
                "hasRankingData": True,
                "hasAdmissionData": False,
            },
        }
        facts = self.cb._build_summary_facts(
            task_kind="university_lookup",
            user_input="where is NTU located and admission ranking",
            original_input="where is NTU located and admission ranking",
            rewritten_query=None,
            resolved_reference=None,
            raw_data=raw,
            metadata={"totalCount": 1, "page": 1, "pageSize": 10},
            focus_entity="National Taiwan University",
            long_term_memory=[],
        )
        self.assertEqual(
            facts,
            [
                "Focus entity: National Taiwan University",
                "Preview loaded.",
                "Total count: 1",
                "Page: 1, page size: 10",
                "Likely user intent: location, admission, ranking",
                "University preview available for: National Taiwan University",
                "Aliases: NTU, 台大",
                "Identity match: name = NTU",
                "Website signal: https://ntu.edu.tw",
                "Best ranking signal: rank 68 via QS",
                "Admission hints: IELTS 6.5, TOEFL 90",
                "Location signal: Taipei, Taiwan",
            ],
        )
        # The [:12] cap must hold: missing-section facts fall off the end.
        self.assertEqual(len(facts), 12)

    def test_ranking_explain(self) -> None:
        raw = {
            "summary": "Loaded 2 ranking rows.",
            "items": [
                {"universityName": "National Taiwan University", "aggregatedRank": 68, "primarySource": "QS"},
                {"universityName": "NCKU", "aggregatedRank": 220, "primarySource": "QS"},
            ],
            "topUniversities": ["National Taiwan University", "NCKU"],
        }
        facts = self.cb._build_summary_facts(
            task_kind="ranking_explain",
            user_input="why does NTU rank so high, compare vs NCKU position",
            original_input="why does NTU rank so high, compare vs NCKU position",
            rewritten_query=None,
            resolved_reference=None,
            raw_data=raw,
            metadata={"totalCount": 40, "page": 1, "pageSize": 2},
            focus_entity="National Taiwan University",
            long_term_memory=[],
        )
        self.assertEqual(
            facts,
            [
                "Focus entity: National Taiwan University",
                "Loaded 2 ranking rows.",
                "Total count: 40",
                "Page: 1, page size: 2",
                "Likely ranking intent: compare, rank_position, why_high",
                "Top matched universities: National Taiwan University, NCKU",
                "Direct match signal: National Taiwan University, aggregated rank 68, source QS",
                "Comparison candidates in current slice: National Taiwan University, NCKU",
                "Current evidence is page-level and may not cover the full result set.",
                "Strongest visible rank signal on this page: 68",
                "Use ranking evidence as support, but do not infer broader causal reasons that are not in the data.",
            ],
        )

    def test_recommendation(self) -> None:
        raw = {
            "summary": "3 recommendations.",
            "items": [
                {"universityName": "NTU", "country": "Taiwan", "category": "target", "reason": "Strong fit"},
                {"universityName": "NCKU", "country": "Taiwan", "category": "safety"},
            ],
            "profile": {"country": "Taiwan", "ielts": 6.5, "targetRank": 100},
        }
        facts = self.cb._build_summary_facts(
            task_kind="recommendation",
            user_input="recommend Taiwan universities",
            original_input="recommend Taiwan universities",
            rewritten_query="taiwan unis ielts 6.5",
            resolved_reference=None,
            raw_data=raw,
            metadata={"totalCount": 40, "page": 1, "pageSize": 2},
            focus_entity=None,
            long_term_memory=[{"content": "prefers Taiwan"}],
        )
        self.assertEqual(
            facts,
            [
                "Interpretation hint: rewritten query = taiwan unis ielts 6.5",
                "Long-term memory signals:",
                "Memory: prefers Taiwan",
                "3 recommendations.",
                "Total count: 40",
                "Page: 1, page size: 2",
                "Recommendation candidates returned: 2",
                "Countries represented in recommendation slice: Taiwan",
                "Recommendation categories present: safety, target",
                "Example recommendation reason: Strong fit",
                "Recommendation profile: country=Taiwan, ielts=6.5, targetRank=100",
                "Current recommendation evidence is page-level and may not include all candidates.",
            ],
        )


if __name__ == "__main__":
    unittest.main()
