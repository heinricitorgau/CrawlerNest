"""Tests for merging duplicate canonical universities, and for the alias guard the merge relies on.

A merge moves ranks from one university to another, so what these pin down is what it
refuses: two records a source ranks separately, a record that marks an institutional
change, and a name that would also be read as a third university.

The warehouse cases need PostgreSQL and opt in like the rest of the suite:

    CRAWLERNEST_RUN_PG_TESTS=1 CRAWLERNEST_PG_PASSWORD=test \\
        python3 crawlernest/crawlernest-tests/run_tests.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent
for _p in (str(PACKAGE_ROOT / "scripts"), str(PACKAGE_ROOT / "crawlernest-core"), str(PACKAGE_ROOT / "crawlernest-jobs"),
           str(PACKAGE_ROOT.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import merge_duplicate_canonicals as M  # noqa: E402
import wikipedia_profile_loader as W  # noqa: E402
from entity_resolution.alias_safety import alias_is_safe, has_disambiguator, resolver_keys  # noqa: E402
from entity_resolution.resolver import EntityResolver  # noqa: E402
from entity_resolution.types import CanonicalProfile, EntityRecord  # noqa: E402

SURVIVOR = "crawlernest-dupmerge-fixture-universitesi"
LOSER = "crawlernest-dupmerge-fixture-university"
THIRD = "crawlernest-dupmerge-fixture-third"
MERGED_BY = "duplicate-canonical-merge-fixture"
ENTITY = "/universities/crawlernest-dupmerge-fixture"


def _decisions(merges: list[dict], **top) -> Path:
    doc = {"decided_on": "2026-10-12", "decided_by": "test", "merged_by": MERGED_BY, "merges": merges, **top}
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(doc, handle)
    handle.close()
    return Path(handle.name)


def _merge(**overrides) -> dict:
    return {"loser_slug": LOSER, "survivor_slug": SURVIVOR, "evidence": "wikidata:Q1", "why": "same university", **overrides}


class TestDecisionFile(unittest.TestCase):
    def test_the_committed_file_loads(self) -> None:
        decisions = M.load_decisions(M.DEFAULT_DECISIONS)
        self.assertGreater(len(decisions.merges), 100)
        self.assertEqual("duplicate-canonical-merge-2026-10-12", decisions.merged_by)

    def test_a_chain_is_refused(self) -> None:
        # a -> b and b -> c would depend on the order the file is read in.
        path = _decisions([_merge(), _merge(loser_slug=SURVIVOR, survivor_slug=THIRD)])
        with self.assertRaisesRegex(ValueError, "both merged away and merged into"):
            M.load_decisions(path)

    def test_a_record_merged_twice_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "merged twice"):
            M.load_decisions(_decisions([_merge(), _merge(survivor_slug=THIRD)]))

    def test_a_merge_without_its_reason_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "evidence and its reason"):
            M.load_decisions(_decisions([_merge(why=" ")]))

    def test_an_unknown_overlap_rule_is_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown overlap rule"):
            M.load_decisions(_decisions([_merge(overlap="keep_best")]))


class TestAliasSafety(unittest.TestCase):
    NAMES = {
        1: resolver_keys("Northeastern University"),
        2: resolver_keys("Northeastern University (China)"),
        3: resolver_keys("Universität Paderborn"),
    }

    def test_a_trailing_parenthesis_is_also_the_bare_name(self) -> None:
        self.assertIn("raw:northeastern university", resolver_keys("Northeastern University (Shenyang)"))
        self.assertTrue(has_disambiguator("University of New England (Australia)"))
        self.assertFalse(has_disambiguator("University of California, Berkeley"))

    def test_another_universitys_name_is_not_a_safe_alias(self) -> None:
        # Given to the Chinese university, this alias would be reached by Boston's name first.
        self.assertIn("canonical 1", alias_is_safe("Northeastern University (Shenyang)", 2, self.NAMES))

    def test_a_name_only_this_university_has_is_safe(self) -> None:
        self.assertIsNone(alias_is_safe("University of Paderborn", 3, self.NAMES))

    def test_accents_and_transliteration_count_as_the_same_name(self) -> None:
        names = {1: resolver_keys("Universität Tübingen")}
        self.assertIsNotNone(alias_is_safe("Universitat Tubingen", 2, names))
        self.assertIsNotNone(alias_is_safe("Universitaet Tuebingen", 2, names))


class TestTitleAliases(unittest.TestCase):
    UNIVERSITIES = [
        (1, "universidad-de-sevilla", "Universidad de Sevilla", "Spain", []),
        (2, "northeastern-china", "Dongbei Daxue", "China (mainland)", []),
        (3, "northeastern", "Northeastern University", "United States", []),
        (4, "ankara-a", "Ankara Üniversitesi", "Turkey", []),
        (5, "ankara-b", "Ankara University", "Türkiye", []),
        (6, "oxford", "University of Oxford", "United Kingdom", []),
        (7, "unmatched", "Some College", "Chile", []),
        (8, "boston-tech", "Boston Tech", "United States", ["Northeastern Institute"]),
    ]
    TITLES = {
        "universidad-de-sevilla": "University of Seville",
        "northeastern-china": "Northeastern University (China)",
        "northeastern": "Northeastern University",
        "ankara-a": "Ankara University",
        "ankara-b": "Ankara University",
        "oxford": "University of Oxford",
        "boston-tech": "Northeastern Institute of Technology",
    }

    def setUp(self) -> None:
        self.rows, self.skipped = W.title_alias_rows(self.UNIVERSITIES, self.TITLES)

    def test_a_native_name_gets_its_english_title(self) -> None:
        by_id = {row["canonical_university_id"]: row for row in self.rows}
        self.assertEqual("University of Seville", by_id[1]["alias_text"])
        self.assertEqual(("Universidad de Sevilla", "rule"), (by_id[1]["canonical_slug_hint"], by_id[1]["method"]))

    def test_what_is_left_out_and_why(self) -> None:
        self.assertEqual({1, 8}, {row["canonical_university_id"] for row in self.rows})
        self.assertEqual(
            {"no_article": 1, "shared_title": 2, "disambiguated": 1, "already_a_name": 2, "collides": 0}, self.skipped
        )

    def test_a_title_two_records_share_goes_to_neither(self) -> None:
        # An unmerged duplicate: giving the title to one would decide the merge by file order.
        self.assertNotIn("Ankara University", {row["alias_text"] for row in self.rows})

    def test_a_title_that_is_another_records_name_is_left_out(self) -> None:
        universities = [*self.UNIVERSITIES, (9, "seville-college", "University of Seville", "United States", [])]
        rows, skipped = W.title_alias_rows(universities, self.TITLES)
        self.assertNotIn(1, {row["canonical_university_id"] for row in rows})
        self.assertEqual(1, skipped["collides"])


class TestCountrySpellings(unittest.TestCase):
    """THE writes "Türkiye" and "Czechia"; the records QS seeded say "Turkey" and "Czech Republic"."""

    def _resolver(self) -> EntityResolver:
        return EntityResolver([
            CanonicalProfile(1, "Akdeniz University", "turkey", ()),
            CanonicalProfile(2, "Masaryk University", "czech republic", ()),
        ])

    def test_one_country_under_two_spellings_is_not_a_mismatch(self) -> None:
        resolver = self._resolver()
        for name, country in (("Akdeniz University", "Türkiye"), ("Masaryk University", "Czechia")):
            with self.subTest(country=country):
                result = resolver.resolve_one(EntityRecord("THE", "x", name, country))
                self.assertFalse(result.metadata["country_mismatch"])
                self.assertFalse(result.metadata["suspicious_merge"])

    def test_two_countries_still_are(self) -> None:
        result = self._resolver().resolve_one(EntityRecord("THE", "x", "Akdeniz University", "Greece"))
        self.assertTrue(result.metadata["country_mismatch"])


@unittest.skipUnless(os.getenv("CRAWLERNEST_RUN_PG_TESTS") == "1", "PostgreSQL integration tests are opt-in")
class TestMergeAgainstPostgres(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import psycopg2

        cls.psycopg2 = psycopg2
        cls.dsn = {
            "host": os.getenv("CRAWLERNEST_PG_HOST", "localhost"),
            "port": int(os.getenv("CRAWLERNEST_PG_PORT", "5432")),
            "dbname": os.getenv("CRAWLERNEST_PG_DATABASE", "clawer"),
            "user": os.getenv("CRAWLERNEST_PG_USER", "test"),
            "password": os.getenv("CRAWLERNEST_PG_PASSWORD", ""),
        }

    def setUp(self) -> None:
        self.conn = self.psycopg2.connect(**self.dsn)
        self._clear()
        with self.conn.cursor() as cur:
            # An existing source, with editions no source has: a source row of the fixture's own would
            # take a value from ranking_source's smallint sequence on every run.
            cur.execute("SELECT ranking_source_id FROM warehouse.ranking_source WHERE source_code = 'QS'")
            row = cur.fetchone()
            if row is None:
                self.skipTest("the warehouse has no QS ranking source to hang fixture rows on")
            self.source_id = row[0]
            self.ids = {}
            for slug, name in ((SURVIVOR, "Dupmerge Fixture Üniversitesi"), (LOSER, "Dupmerge Fixture University"),
                               (THIRD, "Dupmerge Third University")):
                cur.execute(
                    "INSERT INTO warehouse.canonical_university (canonical_slug, display_name, display_name_normalized) "
                    "VALUES (%s, %s, lower(%s)) RETURNING canonical_university_id", (slug, name, name))
                self.ids[slug] = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO warehouse.source_university_mapping (ranking_source_id, source_code, source_entity_id, "
                "canonical_university_id, match_method, confidence_score) VALUES (%s, 'QS', %s, %s, 'exact_display', 0.99) "
                "RETURNING source_mapping_id", (self.source_id, ENTITY, self.ids[LOSER]))
            self.mapping_id = cur.fetchone()[0]
            self._rank(cur, SURVIVOR, 1901, 10)
            self._rank(cur, LOSER, 1902, 20, mapped=True)
        self.conn.commit()

    def _rank(self, cur, slug: str, year: int, rank: int, *, mapped: bool = False) -> None:
        cur.execute(
            "INSERT INTO warehouse.ranking_record (canonical_university_id, ranking_source_id, source_mapping_id, "
            "ranking_year, rank_position) VALUES (%s, %s, %s, %s, %s)",
            (self.ids[slug], self.source_id, self.mapping_id if mapped else None, year, rank))

    def tearDown(self) -> None:
        self.conn.rollback()
        self._clear()
        self.conn.close()

    def _clear(self) -> None:
        slugs = [SURVIVOR, LOSER, THIRD]
        ids = "(SELECT canonical_university_id FROM warehouse.canonical_university WHERE canonical_slug = ANY(%s))"
        with self.conn.cursor() as cur:
            for table, column in (
                ("warehouse.mapping_review", "decided_canonical_university_id"),
                ("warehouse.ranking_record", "canonical_university_id"),
                ("warehouse.source_university_mapping", "canonical_university_id"),
                ("warehouse.university_alias", "canonical_university_id"),
                ("warehouse.canonical_university", "canonical_university_id"),
            ):
                cur.execute(f"DELETE FROM {table} WHERE {column} IN {ids}", (slugs,))
            cur.execute("DELETE FROM warehouse.mapping_review WHERE source_code = 'QS' AND source_entity_id = %s", (ENTITY,))
        self.conn.commit()

    def _run(self, *, commit: bool = True, **overrides) -> dict:
        return M.merge_all(self.conn, M.load_decisions(_decisions([_merge(**overrides)])), commit=commit)

    def _one(self, sql: str, params=()) -> tuple:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
        self.conn.rollback()
        return row

    def test_rows_mapping_and_name_move_and_the_loser_stays_as_merged(self) -> None:
        result = self._run()
        self.assertEqual((1, 1, 1, 1), tuple(result["totals"][k] for k in ("merged", "ranking_rows", "mappings", "aliases_added")))
        self.assertEqual((2,), self._one("SELECT count(*) FROM warehouse.ranking_record WHERE canonical_university_id = %s",
                                         (self.ids[SURVIVOR],)))
        self.assertEqual((self.ids[SURVIVOR],), self._one(
            "SELECT canonical_university_id FROM warehouse.source_university_mapping WHERE source_mapping_id = %s",
            (self.mapping_id,)))
        self.assertEqual(("Dupmerge Fixture University",), self._one(
            "SELECT alias_text FROM warehouse.university_alias WHERE canonical_university_id = %s", (self.ids[SURVIVOR],)))
        self.assertEqual(("merged", str(self.ids[SURVIVOR]), MERGED_BY), self._one(
            "SELECT status, metadata->>'merged_into', metadata->>'merged_by' FROM warehouse.canonical_university "
            "WHERE canonical_university_id = %s", (self.ids[LOSER],)))

    def test_without_commit_nothing_is_written(self) -> None:
        result = self._run(commit=False)
        self.assertEqual(1, result["totals"]["merged"])
        self.assertEqual(("active",), self._one(
            "SELECT status FROM warehouse.canonical_university WHERE canonical_university_id = %s", (self.ids[LOSER],)))

    def test_running_it_again_does_nothing(self) -> None:
        self._run()
        again = self._run()
        self.assertEqual((0, 1), (again["totals"]["merged"], again["totals"]["already"]))

    def test_two_records_one_table_ranks_separately_are_not_merged(self) -> None:
        with self.conn.cursor() as cur:
            self._rank(cur, LOSER, 1901, 30)
        self.conn.commit()
        with self.assertRaisesRegex(M.PreconditionFailed, "rank both records"):
            self._run()
        self.assertEqual(("active",), self._one(
            "SELECT status FROM warehouse.canonical_university WHERE canonical_university_id = %s", (self.ids[LOSER],)))

    def test_an_identical_legacy_copy_is_dropped_when_the_decision_says_so(self) -> None:
        with self.conn.cursor() as cur:
            self._rank(cur, SURVIVOR, 1902, 20)  # the unmapped copy of the loser's mapped row
        self.conn.commit()
        result = self._run(overlap=M.OVERLAP_IDENTICAL_RANK)
        self.assertEqual(1, result["totals"]["legacy_duplicates_dropped"])
        self.assertEqual((self.mapping_id,), self._one(
            "SELECT source_mapping_id FROM warehouse.ranking_record WHERE canonical_university_id = %s AND ranking_year = 1902",
            (self.ids[SURVIVOR],)))

    def test_identical_rank_still_refuses_different_ranks(self) -> None:
        with self.conn.cursor() as cur:
            self._rank(cur, SURVIVOR, 1902, 21)
        self.conn.commit()
        with self.assertRaisesRegex(M.PreconditionFailed, "ranks 21 and 20"):
            self._run(overlap=M.OVERLAP_IDENTICAL_RANK)

    def test_a_decision_naming_the_loser_follows_it(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO warehouse.mapping_review (ranking_source_id, source_entity_id, reviewed_source_name, "
                "reviewed_canonical_university_id, reviewed_match_method, decision, decided_canonical_university_id, "
                "decided_by, source_code) VALUES (%s, %s, 'x', %s, 'fuzzy_review', 'confirmed', %s, 'test', 'QS')",
                (self.source_id, ENTITY, self.ids[LOSER], self.ids[LOSER]))
        self.conn.commit()
        self.assertEqual(1, self._run()["totals"]["reviews_repointed"])
        decided, note = self._one("SELECT decided_canonical_university_id, note FROM warehouse.mapping_review "
                                  "WHERE source_code = 'QS' AND source_entity_id = %s", (ENTITY,))
        self.assertEqual(self.ids[SURVIVOR], decided)
        self.assertIn("was merged into", note)

    def test_a_name_another_university_answers_to_is_not_made_an_alias(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO warehouse.university_alias (canonical_university_id, alias_text, alias_normalized) "
                        "VALUES (%s, 'Dupmerge Fixture University', 'dupmerge fixture university')", (self.ids[THIRD],))
        self.conn.commit()
        result = self._run()
        self.assertEqual((0, 1), (result["totals"]["aliases_added"], result["totals"]["aliases_withheld"]))
        self.assertEqual((0,), self._one("SELECT count(*) FROM warehouse.university_alias WHERE canonical_university_id = %s",
                                         (self.ids[SURVIVOR],)))


if __name__ == "__main__":
    unittest.main()
