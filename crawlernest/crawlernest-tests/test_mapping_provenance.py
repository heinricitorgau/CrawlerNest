"""ranking_record.source_mapping_id: the backfill rule, against real SQL.

Every tier of mapping_provenance's classification is a join or a uniqueness
argument, none of which a fake exercises, so these run against PostgreSQL. They
own an isolated source, year and set of universities and remove all of it.

    CRAWLERNEST_RUN_PG_TESTS=1 CRAWLERNEST_PG_PASSWORD=test \\
        python3 crawlernest/crawlernest-tests/run_tests.py
"""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
CORE_DIR = TESTS_DIR.parent / "crawlernest-core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

#: A year no crawl covers and a source code nothing else registers.
ISOLATED_YEAR = 1899
SOURCE = "PROVTEST"
UNIVERSITIES = {
    "a": ("crawlernest-prov-fixture-a", "Provenance Fixture A"),
    "b": ("crawlernest-prov-fixture-b", "Provenance Fixture B"),
    "c": ("crawlernest-prov-fixture-c", "Provenance Fixture C"),
    "d": ("crawlernest-prov-fixture-d", "Provenance Fixture D"),
}
PAGE = "https://example.invalid/ranking-page"


@unittest.skipUnless(
    os.getenv("CRAWLERNEST_RUN_PG_TESTS") == "1", "PostgreSQL integration tests are opt-in"
)
class TestSourceMappingBackfill(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg2

        cls.conn = psycopg2.connect(
            host=os.getenv("CRAWLERNEST_PG_HOST", "localhost"),
            port=int(os.getenv("CRAWLERNEST_PG_PORT", "5432")),
            database=os.getenv("CRAWLERNEST_PG_DATABASE", "clawer"),
            user=os.getenv("CRAWLERNEST_PG_USER", "test"),
            password=os.getenv("CRAWLERNEST_PG_PASSWORD", ""),
        )

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    # -- fixture ---------------------------------------------------------------

    def setUp(self):
        self._clear()
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO warehouse.ranking_source (source_code, source_name) VALUES (%s, %s)"
                " RETURNING ranking_source_id",
                (SOURCE, "Provenance test source"),
            )
            self.source_id = cur.fetchone()[0]
            self.uni = {}
            for key, (slug, display) in UNIVERSITIES.items():
                cur.execute(
                    "INSERT INTO warehouse.canonical_university"
                    " (canonical_slug, display_name, display_name_normalized)"
                    " VALUES (%s, %s, %s) RETURNING canonical_university_id",
                    (slug, display, display.lower()),
                )
                self.uni[key] = cur.fetchone()[0]
        self.conn.commit()

        # Two entities resolve to A -- the Tsinghua-and-its-business-school shape.
        self.m_a_main = self._mapping("/p/a-main", "a", "a")
        self.m_a_school = self._mapping("/p/a-school", "a", "a school")
        # An entity a later run re-pointed at D. Its own university, so that it
        # does not also make B's mapping ambiguous.
        self.m_moved = self._mapping("/p/moved", "d", "moved")
        # The only mapping to B.
        self.m_b = self._mapping("e:b", "b", "b")
        # A reviewer's rejection, still pointing at C.
        self.m_retired = self._mapping("/p/retired", "c", "retired", active=False)

        self.r = {
            "entity_settles_ambiguity": self._record("a", "u1", "/p/a-school", "a school"),
            "entity_resolves_elsewhere": self._record("a", "u2", "/p/moved", "moved"),
            "sole_mapping_name_agrees": self._record("b", "u1", PAGE, "b"),
            "sole_mapping_name_differs": self._record("b", "u2", PAGE, "someone else"),
            "ambiguous": self._record("a", "u3", PAGE, "a"),
            "already_set": self._record("b", "u3", PAGE, "b", preset=self.m_moved),
            "no_mapping": self._record("c", "u1", PAGE, "c"),
            "entity_inactive": self._record("c", "u2", "/p/retired", "retired"),
        }
        self.conn.commit()

    def tearDown(self):
        self._clear()

    def _clear(self):
        slugs = [slug for slug, _ in UNIVERSITIES.values()]
        with self.conn.cursor() as cur:
            cur.execute(
                "DELETE FROM warehouse.ranking_record rr USING warehouse.ranking_source rs"
                " WHERE rs.ranking_source_id = rr.ranking_source_id AND rs.source_code = %s",
                (SOURCE,),
            )
            cur.execute(
                "DELETE FROM warehouse.source_university_mapping m USING warehouse.ranking_source rs"
                " WHERE rs.ranking_source_id = m.ranking_source_id AND rs.source_code = %s",
                (SOURCE,),
            )
            cur.execute("DELETE FROM warehouse.canonical_university WHERE canonical_slug = ANY(%s)", (slugs,))
            cur.execute("DELETE FROM warehouse.ranking_source WHERE source_code = %s", (SOURCE,))
        self.conn.commit()

    def _mapping(self, entity_id, uni, name, *, active=True):
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO warehouse.source_university_mapping"
                " (ranking_source_id, source_entity_id, canonical_university_id, match_method,"
                "  confidence_score, is_active, metadata)"
                " VALUES (%s, %s, %s, 'exact', 1.0, %s, %s::jsonb) RETURNING source_mapping_id",
                (self.source_id, entity_id, self.uni[uni], active, json.dumps({"normalized_name": name})),
            )
            return cur.fetchone()[0]

    def _record(self, uni, universe, url, name, *, preset=None):
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO warehouse.ranking_record"
                " (canonical_university_id, ranking_source_id, source_mapping_id, ranking_year,"
                "  ranking_type, universe_type, universe_key, rank_position, source_url, metadata, run_id)"
                " VALUES (%s, %s, %s, %s, 'world', 'test', %s, 1, %s, %s::jsonb, 'prov-test')"
                " RETURNING ranking_record_id",
                (self.uni[uni], self.source_id, preset, ISOLATED_YEAR, universe, url,
                 json.dumps({"normalized_name": name})),
            )
            return cur.fetchone()[0]

    def _linked(self, key):
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT source_mapping_id FROM warehouse.ranking_record WHERE ranking_record_id = %s",
                (self.r[key],),
            )
            return cur.fetchone()[0]

    # -- tests -----------------------------------------------------------------

    def test_classification_names_a_reason_for_every_row(self):
        from multi_source.mapping_provenance import classify

        by_basis = {
            row.basis: row
            for row in classify(self.conn, [ISOLATED_YEAR])
            if row.source_code == SOURCE
        }
        self.assertEqual(
            {
                "source_entity": 1,
                "conflict_entity_resolves_elsewhere": 1,
                "conflict_entity_inactive": 1,
                "sole_mapping_name_agrees": 2,  # one of them already set
                "unresolved_sole_mapping_name_differs": 1,
                "unresolved_ambiguous": 1,
                "unresolved_no_mapping": 1,
            },
            {basis: row.records for basis, row in by_basis.items()},
        )
        self.assertEqual(1, by_basis["sole_mapping_name_agrees"].disagrees_with_current)

    def test_backfill_links_only_on_evidence(self):
        from multi_source.mapping_provenance import backfill

        self.assertEqual(2, backfill(self.conn, [ISOLATED_YEAR]))

        self.assertEqual(self.m_a_school, self._linked("entity_settles_ambiguity"),
                         "the row's own entity settles what a join on university cannot")
        self.assertEqual(self.m_b, self._linked("sole_mapping_name_agrees"))
        for key in (
            "entity_resolves_elsewhere",
            "sole_mapping_name_differs",
            "ambiguous",
            "no_mapping",
            "entity_inactive",
        ):
            self.assertIsNone(self._linked(key), f"{key} must stay NULL: not known is not a guess")

    def test_a_value_already_set_is_never_overwritten(self):
        from multi_source.mapping_provenance import backfill

        backfill(self.conn, [ISOLATED_YEAR])
        self.assertEqual(self.m_moved, self._linked("already_set"))

    def test_a_second_pass_fills_nothing(self):
        from multi_source.mapping_provenance import backfill

        backfill(self.conn, [ISOLATED_YEAR])
        self.assertEqual(0, backfill(self.conn, [ISOLATED_YEAR]))

    def test_conflicts_are_listed_for_a_person(self):
        from multi_source.mapping_provenance import conflicts

        found = [row for row in conflicts(self.conn, [ISOLATED_YEAR]) if row[0] == SOURCE]
        self.assertEqual(
            {"conflict_entity_resolves_elsewhere", "conflict_entity_inactive"},
            {row[6] for row in found},
        )


if __name__ == "__main__":
    unittest.main()
