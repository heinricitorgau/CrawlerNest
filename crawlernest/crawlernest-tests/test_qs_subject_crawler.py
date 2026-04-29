import json
import tempfile
import unittest
from pathlib import Path

from crawlernest_ranking_crawler.subjects.contracts import (
    clean_qs_university_name,
    normalize_qs_subject_row,
    normalize_qs_subject_key,
    parse_rank_position,
    parse_score,
)
from crawlernest_ranking_crawler.subjects.qs_subject import fetch_qs_subject_rows


class TestQSSubjectCrawler(unittest.TestCase):
    def test_fetch_uses_local_snapshot_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            snapshot_dir = root / "2026"
            snapshot_dir.mkdir(parents=True)
            (snapshot_dir / "computer-science.json").write_text(
                json.dumps(
                    [
                        {
                            "rank": "1",
                            "name": "Massachusetts Institute of Technology (MIT)",
                            "country": "United States",
                            "score": "96.7",
                            "subject": "Computer Science and Information Systems",
                            "url": "https://example.test/qs/cs",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            rows = fetch_qs_subject_rows("computer-science", 2026, snapshot_root=root)

        self.assertEqual(1, len(rows))
        self.assertEqual("1", rows[0]["rank"])
        self.assertEqual("Massachusetts Institute of Technology (MIT)", rows[0]["name"])

    def test_normalize_qs_subject_row_contract(self):
        row = normalize_qs_subject_row(
            {
                "rank": "51-100",
                "name": "Massachusetts Institute of Technology (MIT)",
                "country": "United States",
                "score": "96.7",
                "subject": "Computer Science and Information Systems",
                "url": "https://example.test/qs/cs",
            },
            "computer-science",
            2026,
        )

        self.assertEqual("QS", row["source_code"])
        self.assertEqual("computer-science", row["subject_key"])
        self.assertEqual(2026, row["ranking_year"])
        self.assertEqual(51, row["rank_position"])
        self.assertEqual("51-100", row["rank_display"])
        self.assertEqual("Massachusetts Institute of Technology", row["university_name"])
        self.assertEqual("massachusetts institute of technology", row["university_name_normalized"])
        self.assertEqual("United States", row["country_hint"])
        self.assertEqual(96.7, row["score"])
        self.assertEqual(100.0, row["score_scale"])
        self.assertEqual(
            "qs:subject:computer-science:2026:massachusetts-institute-of-technology",
            row["source_entity_id"],
        )

    def test_subject_mapping_is_phase2_limited(self):
        self.assertEqual("electrical-engineering", normalize_qs_subject_key("Engineering - Electrical and Electronic"))
        with self.assertRaises(ValueError):
            normalize_qs_subject_key("Mathematics")

    def test_rank_and_score_parsing(self):
        self.assertEqual(51, parse_rank_position("51–100"))
        self.assertEqual(1, parse_rank_position("#1"))
        self.assertEqual(96.7, parse_score("96.7"))
        self.assertEqual(1234.5, parse_score("1,234.5"))
        self.assertIsNone(parse_score(""))

    def test_mit_parenthetical_cleanup(self):
        self.assertEqual(
            "Massachusetts Institute of Technology",
            clean_qs_university_name("Massachusetts Institute of Technology (MIT)"),
        )


if __name__ == "__main__":
    unittest.main()
