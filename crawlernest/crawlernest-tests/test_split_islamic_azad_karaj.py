"""split_islamic_azad_karaj: the decision is coherent, and the prepare phase refuses before it writes.

The replay and the rewrite of rows go through the repository's own ingest and were rehearsed on a restored copy of
the database. What is pinned here is what needs no database: the decision does not contradict itself, a state it
was not made against stops the run, a person's earlier decision is never overwritten, and a dry run writes nothing.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(PACKAGE_ROOT / "crawlernest-core"), str(PACKAGE_ROOT.parent), str(PACKAGE_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.path.insert(0, str(PACKAGE_ROOT / "scripts"))
import split_islamic_azad_karaj as K  # noqa: E402

D = K.DECISION


class TestDecision(unittest.TestCase):
    def test_the_new_slug_is_clean_and_not_the_one_it_leaves(self):
        self.assertRegex(D.new_slug, r"^[a-z0-9]+(-[a-z0-9]+)*$")
        self.assertNotEqual(D.new_slug, D.expect_slug)

    def test_the_new_name_normalises_to_something_no_canonical_already_has(self):
        # A normalised name that collided with the old canonical's would let the resolver merge them again.
        self.assertNotEqual(K.base._normalize(D.new_display_name), K.base._normalize("Islamic Azad University."))

    def test_it_names_one_source_entity_and_one_edition(self):
        self.assertEqual((D.source_code, D.source_entity_id, D.ranking_year), ("THE", "587685", 2017))
        self.assertTrue(D.why.strip())

    def test_the_committed_edition_holds_the_entity_on_the_branch_name(self):
        import json

        rows = json.loads((K.base.DATABASES_DIR / f"the_rankings_{D.ranking_year}.json").read_text(encoding="utf-8"))["rows"]
        mine = [r for r in rows if str(r["id"]) == D.source_entity_id]
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0]["name"], D.source_name)

    def test_the_decider_is_named_honestly(self):
        self.assertIn("claude-code", K.DECIDED_BY)
        self.assertIn("direction", K.DECIDED_BY)


class FakeCursor:
    def __init__(self, state):
        self.state = state
        self.last = ""
        self.params = ()
        self.writes: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=()):
        self.last = " ".join(sql.split())
        self.params = params
        if self.last.startswith(("INSERT", "UPDATE")):
            self.writes.append(" ".join(self.last.split(" ")[:3]))

    def fetchone(self):
        q = self.last
        if q.startswith("INSERT INTO warehouse.canonical_university"):
            return (900001,)
        if "FROM warehouse.source_university_mapping" in q:
            return self.state["mapping"]
        if "SELECT canonical_university_id, display_name FROM warehouse.canonical_university WHERE canonical_slug" in q:
            return self.state["new_canonical"]
        if "SELECT canonical_slug, country_id FROM warehouse.canonical_university" in q:
            return self.state["origin"]
        if "SELECT country_id FROM warehouse.canonical_university" in q:
            return (50,)
        if "FROM warehouse.mapping_review" in q:
            return self.state["review"]
        raise AssertionError(f"unexpected query: {q}")


class FakeConn:
    def __init__(self, state):
        self.cur = FakeCursor(state)
        self.committed = self.rolled_back = False

    def cursor(self):
        return self.cur

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def healthy():
    return {
        "mapping": (D.expect_canonical, "fuzzy_review", 0.851, 402),
        "new_canonical": None,
        "origin": (D.expect_slug, 50),
        "review": None,
    }


class TestPrepare(unittest.TestCase):
    def test_a_dry_run_rolls_back_and_a_commit_commits(self):
        dry = FakeConn(healthy())
        self.assertFalse(K.plan_and_apply(dry, commit=False)["committed"])
        self.assertTrue(dry.rolled_back and not dry.committed)
        live = FakeConn(healthy())
        self.assertTrue(K.plan_and_apply(live, commit=True)["committed"])
        self.assertTrue(live.committed and not live.rolled_back)

    def test_it_writes_one_canonical_and_one_review_and_nothing_more(self):
        conn = FakeConn(healthy())
        K.plan_and_apply(conn, commit=True)
        self.assertEqual(conn.cur.writes, ["INSERT INTO warehouse.canonical_university",
                                           "INSERT INTO warehouse.mapping_review"])

    def test_the_review_is_a_remap_to_the_canonical_it_just_created(self):
        conn = FakeConn(healthy())
        result = K.plan_and_apply(conn, commit=True)
        self.assertEqual(result["target"], 900001)
        self.assertIn(900001, conn.cur.params)  # the INSERT INTO mapping_review was the last statement
        self.assertIn(K.DECIDED_BY, conn.cur.params)

    def test_a_canonical_that_is_not_what_it_was_decided_against_stops_the_run_before_any_write(self):
        state = healthy()
        state["origin"] = ("something-else", 50)
        conn = FakeConn(state)
        with self.assertRaises(K.base.PreconditionFailed):
            K.plan_and_apply(conn, commit=True)
        self.assertEqual(conn.cur.writes, [])
        self.assertFalse(conn.committed)

    def test_an_entity_on_an_unexpected_canonical_stops_the_run(self):
        state = healthy()
        state["mapping"] = (123, "fuzzy_review", 0.9, 402)
        conn = FakeConn(state)
        with self.assertRaises(K.base.PreconditionFailed):
            K.plan_and_apply(conn, commit=True)
        self.assertEqual(conn.cur.writes, [])

    def test_a_persons_earlier_decision_is_not_overwritten(self):
        state = healthy()
        state["review"] = ("confirmed", D.expect_canonical)
        conn = FakeConn(state)
        with self.assertRaises(K.base.PreconditionFailed):
            K.plan_and_apply(conn, commit=True)
        self.assertNotIn("INSERT INTO warehouse.mapping_review", conn.cur.writes)

    def test_a_slug_taken_by_another_university_stops_the_run(self):
        state = healthy()
        state["new_canonical"] = (5, "Some Other University")
        with self.assertRaises(K.base.PreconditionFailed):
            K.plan_and_apply(FakeConn(state), commit=True)

    def test_an_entity_on_a_third_canonical_stops_the_run_even_when_the_new_canonical_exists(self):
        # The path a half-applied or hand-edited state takes: the canonical is there, but the entity has
        # since been moved somewhere this decision knows nothing about.
        state = healthy()
        state["new_canonical"] = (777, D.new_display_name)
        state["mapping"] = (123, "fuzzy_review", 0.9, 402)
        conn = FakeConn(state)
        with self.assertRaises(K.base.PreconditionFailed):
            K.plan_and_apply(conn, commit=True)
        self.assertEqual(conn.cur.writes, [])

    def test_running_it_again_after_it_was_applied_writes_nothing(self):
        state = {
            "mapping": (777, "remapped", 1.0, 402),
            "new_canonical": (777, D.new_display_name),
            "origin": None,
            "review": ("remapped", 777),
        }
        conn = FakeConn(state)
        result = K.plan_and_apply(conn, commit=True)
        self.assertEqual(conn.cur.writes, [])
        self.assertTrue(all("already" in a for a in result["actions"]))


if __name__ == "__main__":
    unittest.main()
