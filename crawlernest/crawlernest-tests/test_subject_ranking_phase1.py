import unittest
from pathlib import Path

from crawlernest_ranking_crawler.subjects.contracts import (
    NormalizedSubjectRankingRow,
    build_source_entity_id,
    normalize_qs_subject_key,
    normalized_qs_subject_row_from_raw,
    parse_rank_position,
)


class TestSubjectRankingPhase1(unittest.TestCase):
    def test_qs_subject_contract_accepts_only_phase1_subjects(self):
        self.assertEqual("computer-science", normalize_qs_subject_key("Computer Science and Information Systems"))
        self.assertEqual("electrical-engineering", normalize_qs_subject_key("Engineering - Electrical and Electronic"))
        with self.assertRaises(ValueError):
            normalize_qs_subject_key("Mathematics")

    def test_rank_range_preserves_display_and_uses_lower_bound_for_sorting(self):
        row = normalized_qs_subject_row_from_raw(
            {
                "subject": "Computer Science and Information Systems",
                "ranking_year": 2026,
                "rank": "51-100",
                "university_name": "Example University",
                "country_hint": "United States",
                "score": "",
            },
            canonical_university_id=123,
        )

        self.assertEqual(row.rank_display, "51-100")
        self.assertEqual(row.rank_position, 51)
        self.assertEqual(row.subject_key, "computer-science")
        self.assertIsNone(row.score)

    def test_normalized_row_rejects_non_qs_source(self):
        with self.assertRaises(ValueError):
            NormalizedSubjectRankingRow(
                source_code="THE",
                subject_key="computer-science",
                ranking_year=2026,
                rank_position=1,
                rank_display="1",
                university_name="Example University",
                university_name_normalized="example university",
                country_hint=None,
                canonical_university_id=1,
            )

    def test_source_entity_id_is_stable(self):
        self.assertEqual(
            "qs:subject:computer-science:2026:massachusetts-institute-of-technology",
            build_source_entity_id(
                subject_key="Computer Science",
                ranking_year=2026,
                university_name_normalized="massachusetts institute of technology",
            ),
        )

    def test_subject_schema_does_not_touch_global_aggregation_schema(self):
        schema_path = Path(__file__).resolve().parents[1] / "crawlernest-schema" / "subject_ranking_postgresql.sql"
        sql = schema_path.read_text(encoding="utf-8").lower()

        self.assertIn("warehouse.subject_ranking_record", sql)
        self.assertIn("warehouse.canonical_university", sql)
        self.assertIn("warehouse.ranking_source", sql)
        self.assertNotIn("analytics.aggregated_rankings", sql)
        self.assertNotIn("analytics.v_aggregated_rankings_latest", sql)

    def test_parse_rank_position_handles_empty_rank(self):
        self.assertIsNone(parse_rank_position(""))
        self.assertEqual(1, parse_rank_position("#1"))


if __name__ == "__main__":
    unittest.main()
