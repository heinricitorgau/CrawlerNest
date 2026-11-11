"""The agent's rank history: the same statuses as GET /universities/{id}/rank-history, and the words a prompt gets.

The page and the agent must not disagree about a gap: "no QS 2017 edition held" is our gap for every university;
"not in the held edition" is about this one. Neither is the source declining to rank it.
"""

from __future__ import annotations

import os
import unittest
from unittest import mock

from crawlernest.agent.web_agent.generation.university_lookup_explainer import UniversityLookupExplainer
from crawlernest.core.caveats import CAVEAT_THE_PARTIAL, RANK_HISTORY_CAVEAT, archive_edition_caveat
from crawlernest.core.dataset import DATASET_YEARS
from crawlernest.core.services import rank_history as rh
from crawlernest.core.services.university_service import UniversityService


def _row(source, year, position, display=None, entity=None):
    return {"source_code": source, "ranking_year": year, "rank_position": position, "rank_display": display,
            "source_entity_id": entity, "suspicious_merge": False}


def _point(history, source, year):
    series = next(s for s in history["series"] if s["source"] == source)
    return next(p for p in series["points"] if p["year"] == year)


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.history = rh.build_rank_history(
            [
                _row("THE", 2026, 201, "201–250", "the:a"),
                _row("THE", 2024, 180, "180", "the:a"),
                _row("THE", 2025, 170, "170", "the:b"),
                _row("QS", 2023, 100, "=100", "qs:2023:x"),
                _row("QS", 2024, 90, "90", "qs:2024:x"),
            ],
            held_years=[2017, 2023, 2024, 2025, 2026],
        )

    def test_every_point_says_what_it_is(self):
        self.assertEqual([2017, 2023, 2024, 2025, 2026], self.history["years"])
        self.assertEqual("edition_not_held", _point(self.history, "QS", 2017)["status"])
        self.assertEqual("not_in_edition", _point(self.history, "QS", 2026)["status"])
        self.assertEqual("not_in_edition", _point(self.history, "ARWU", 2026)["status"])
        banded = _point(self.history, "THE", 2026)
        self.assertEqual(("ranked", 201, 250, "201–250"), (banded["status"], banded["rankLower"], banded["rankUpper"], banded["rankDisplay"]))
        self.assertEqual(100, _point(self.history, "QS", 2023)["rankLower"])

    def test_archive_editions_and_changed_entries_are_marked(self):
        self.assertTrue(_point(self.history, "QS", 2023)["archived"])
        self.assertFalse(_point(self.history, "QS", 2024)["sourceIdentityChanged"])  # the year segment is not identity
        self.assertTrue(_point(self.history, "THE", 2025)["sourceIdentityChanged"])
        self.assertEqual(RANK_HISTORY_CAVEAT, self.history["caveats"][0])
        self.assertIn(archive_edition_caveat("QS", 2023), self.history["caveats"])
        self.assertIn(CAVEAT_THE_PARTIAL, self.history["caveats"])

    def test_the_prompt_lines_name_every_gap_in_the_same_words(self):
        lines = rh.summarize_rank_history(self.history)
        qs = next(line for line in lines if line.startswith("QS:"))
        self.assertIn("2017 no QS edition held", qs)
        self.assertIn("2023 =100 (Internet Archive capture)", qs)
        self.assertIn("2026 not in the held edition", qs)
        self.assertNotIn("declin", " ".join(lines))

    def test_the_statuses_are_the_apis(self):
        # Spelled as in clawer.service.RankHistoryService and the web types.
        self.assertEqual(("ranked", "edition_not_held", "not_in_edition"),
                         (rh.STATUS_RANKED, rh.STATUS_EDITION_NOT_HELD, rh.STATUS_NOT_IN_EDITION))


class LookupTest(unittest.TestCase):
    def test_the_lookup_carries_the_history_and_every_caveat(self):
        preview = mock.MagicMock()
        history = rh.build_rank_history([_row("THE", 2026, 1, "1")], held_years=[2025, 2026])
        with mock.patch("crawlernest.core.services.university_service.build_canonical_university_detail_preview",
                        return_value=preview), \
                mock.patch("crawlernest.core.services.university_service.detail_preview_to_dict",
                           return_value={"canonical_university_id": 3, "admission_caveats": ["admission caveat"]}), \
                mock.patch.object(UniversityService, "_rank_history", return_value=history):
            data = UniversityService().get_detail_preview(canonical_university_id=3)
        self.assertIs(history, data["rank_history"])
        self.assertEqual("admission caveat", data["caveats"][0])
        self.assertIn(RANK_HISTORY_CAVEAT, data["caveats"])

    def test_the_explainer_puts_the_history_in_its_evidence(self):
        history = rh.build_rank_history([_row("THE", 2026, 1, "1")], held_years=[2025, 2026])
        evidence = UniversityLookupExplainer()._build_evidence_block(
            preview={"university_display_name": "Alpha University", "rank_history": history}, caveats=[])
        self.assertIn("rank history", evidence)
        self.assertIn("THE: 2025 not in the held edition; 2026 1", evidence)


@unittest.skipUnless(os.getenv("CRAWLERNEST_RUN_PG_TESTS") == "1", "PostgreSQL integration tests are opt-in")
class WarehouseTest(unittest.TestCase):
    def test_a_ranked_university_reads_held_editions_only(self):
        import psycopg2

        conn = psycopg2.connect(
            host=os.getenv("CRAWLERNEST_PG_HOST", "localhost"), port=int(os.getenv("CRAWLERNEST_PG_PORT", "5432")),
            dbname=os.getenv("CRAWLERNEST_PG_DATABASE", "clawer"), user=os.getenv("CRAWLERNEST_PG_USER", "test"),
            password=os.getenv("CRAWLERNEST_PG_PASSWORD", "test"),
        )
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT canonical_university_id FROM warehouse.ranking_record "
                            "WHERE universe_type = 'global' AND rank_position IS NOT NULL LIMIT 1")
                found = cur.fetchone()
            if found is None:
                self.skipTest("the warehouse holds no global rank")
            history = rh.load_rank_history(conn, found[0])
        finally:
            conn.close()
        self.assertEqual(sorted(DATASET_YEARS), history["years"])
        statuses = {p["status"] for s in history["series"] for p in s["points"]}
        self.assertIn("ranked", statuses)
        self.assertLessEqual(statuses, {"ranked", "edition_not_held", "not_in_edition"})


if __name__ == "__main__":
    unittest.main()
