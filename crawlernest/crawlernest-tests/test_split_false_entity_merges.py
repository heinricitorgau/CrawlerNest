"""split_false_entity_merges: the decision table is coherent, and the prepare phase refuses before it writes.

The phases that rewrite rows go through the repository's own ingest and were rehearsed on a restored copy of
the database; what is pinned here is what can be pinned without one: the decisions do not contradict each
other, a state the decision was not made against stops the run, and a dry run writes nothing.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(PACKAGE_ROOT / "crawlernest-core"), str(PACKAGE_ROOT.parent), str(PACKAGE_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

sys.path.insert(0, str(PACKAGE_ROOT / "scripts"))
import split_false_entity_merges as S  # noqa: E402


class TestDecisionTable(unittest.TestCase):
    def test_new_canonicals_have_distinct_clean_slugs(self):
        slugs = [n.slug for n in S.NEW_CANONICALS]
        self.assertEqual(len(slugs), len(set(slugs)))
        for slug in slugs:
            self.assertRegex(slug, r"^[a-z0-9]+(-[a-z0-9]+)*$")
        self.assertNotIn(S.RENAME.slug, slugs)
        self.assertEqual(len({n.key for n in S.NEW_CANONICALS}), len(S.NEW_CANONICALS))

    def test_the_ohio_canonical_takes_the_slug_the_rename_frees(self):
        ohio = next(n for n in S.NEW_CANONICALS if n.key == "miami_ohio")
        self.assertEqual(ohio.slug, S.RENAME.expect_slug)
        self.assertNotEqual(S.RENAME.slug, S.RENAME.expect_slug)

    def test_every_remap_moves_an_entity_somewhere_else(self):
        keys = {n.key for n in S.NEW_CANONICALS}
        seen = set()
        for remap in S.REMAPS:
            self.assertNotIn((remap.source_code, remap.source_entity_id), seen)
            seen.add((remap.source_code, remap.source_entity_id))
            if isinstance(remap.target, str):
                self.assertIn(remap.target, keys)
            else:
                self.assertNotEqual(remap.target, remap.expect_canonical)
            self.assertTrue(remap.why.strip())

    def test_a_rejection_names_a_canonical_this_script_creates(self):
        keys = {n.key for n in S.NEW_CANONICALS}
        for reject in S.REJECTS:
            self.assertIn(reject.would_match, keys)
            self.assertNotIn((reject.source_code, reject.source_entity_id),
                             {(r.source_code, r.source_entity_id) for r in S.REMAPS})

    def test_new_canonicals_borrow_a_country_from_a_canonical_that_is_not_new(self):
        for spec in S.NEW_CANONICALS:
            self.assertIsInstance(spec.country_from, int)

    def test_the_decider_is_named_honestly(self):
        self.assertIn("claude-code", S.DECIDED_BY)
        self.assertIn("direction", S.DECIDED_BY)


class TestAffectedYears(unittest.TestCase):
    def write(self, directory: Path, year: int, ids: list[str]):
        rows = [{"id": i, "name": f"u{i}"} for i in ids]
        (directory / f"the_rankings_{year}.json").write_text(json.dumps({"rows": rows}), encoding="utf-8")

    def test_only_editions_that_mention_a_remapped_entity_are_replayed(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            self.write(d, 2016, ["1", "131462"])
            self.write(d, 2017, ["2", "3"])
            self.write(d, 2023, ["624081"])
            # A rejected entity (Irkutsk) needs its review on record, not a replay of its editions.
            self.write(d, 2025, ["624069"])
            self.assertEqual(S.affected_the_years(d), [2016, 2023])

    def test_the_committed_files_give_the_editions_the_repair_was_rehearsed_on(self):
        self.assertEqual(S.affected_the_years(), list(range(2016, 2025)))


class FakeCursor:
    """Answers the queries plan_and_apply makes from a table, and records every write."""

    def __init__(self, state):
        self.state = state
        self.last = ""
        self.writes: list[str] = []
        self._next_id = 900000

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=()):
        self.last = " ".join(sql.split())
        self.params = params
        words = self.last.split(" ")
        if words[0] == "UPDATE":
            self.writes.append(f"UPDATE {words[1]}")
        elif words[0] == "INSERT":
            self.writes.append(f"INSERT {words[2]}")

    def fetchone(self):
        q = self.last
        if q.startswith("INSERT INTO warehouse.canonical_university"):
            self._next_id += 1
            return (self._next_id,)
        if "FROM warehouse.canonical_university WHERE canonical_university_id" in q and "canonical_slug, display_name" in q:
            return self.state["canonical_1262"]
        if "SELECT canonical_university_id, display_name FROM warehouse.canonical_university WHERE canonical_slug" in q:
            return None
        if "SELECT country_id FROM warehouse.canonical_university" in q:
            return (1,)
        if "FROM warehouse.canonical_university_link" in q:
            return (1262,)
        if "FROM warehouse.source_university_mapping" in q and "is_active" in q and "match_method" in q:
            expect = self.state["expect_by_id"].get(self.params[1])
            return (expect, "fuzzy_review", 0.85, 402)
        if "FROM warehouse.source_university_mapping" in q and "IS NOT NULL" in q:
            return None
        if "FROM warehouse.mapping_review" in q:
            return None
        if "FROM warehouse.ranking_source" in q:
            return (402,)
        raise AssertionError(f"unexpected query: {q}")


class FakeConn:
    def __init__(self, state):
        self.cur = FakeCursor(state)
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cur

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def healthy_state():
    return {
        "canonical_1262": (S.RENAME.expect_slug, S.RENAME.expect_name),
        "expect_by_id": {r.source_entity_id: r.expect_canonical for r in S.REMAPS},
    }


class TestPrepare(unittest.TestCase):
    def test_a_dry_run_rolls_back_and_a_commit_commits(self):
        dry = FakeConn(healthy_state())
        result = S.plan_and_apply(dry, commit=False)
        self.assertTrue(dry.rolled_back and not dry.committed)
        self.assertFalse(result["committed"])
        live = FakeConn(healthy_state())
        self.assertTrue(S.plan_and_apply(live, commit=True)["committed"])
        self.assertTrue(live.committed and not live.rolled_back)

    def test_it_writes_what_the_decision_says_and_nothing_more(self):
        conn = FakeConn(healthy_state())
        S.plan_and_apply(conn, commit=True)
        writes = conn.cur.writes
        self.assertEqual(writes.count("INSERT warehouse.canonical_university"), len(S.NEW_CANONICALS))
        self.assertEqual(writes.count("INSERT warehouse.mapping_review"), len(S.REMAPS) + len(S.REJECTS))
        self.assertEqual(writes.count("UPDATE warehouse.canonical_university"), 1)  # the rename
        self.assertEqual(writes.count("UPDATE warehouse.canonical_university_link"), 1)
        self.assertEqual(len(writes), len(S.NEW_CANONICALS) + len(S.REMAPS) + len(S.REJECTS) + 2)

    def test_a_canonical_that_is_not_in_the_expected_state_stops_the_run_before_any_write(self):
        state = healthy_state()
        state["canonical_1262"] = ("miami-university", "Something Else")
        conn = FakeConn(state)
        with self.assertRaises(S.PreconditionFailed):
            S.plan_and_apply(conn, commit=True)
        self.assertEqual(conn.cur.writes, [])
        self.assertFalse(conn.committed)

    def test_an_entity_on_an_unexpected_canonical_stops_the_run(self):
        state = healthy_state()
        state["expect_by_id"]["624081"] = 999999
        conn = FakeConn(state)
        with self.assertRaises(S.PreconditionFailed):
            S.plan_and_apply(conn, commit=True)
        self.assertFalse(conn.committed)

    def test_the_normalised_names_use_the_current_rule_not_the_one_that_dropped_accents(self):
        # 381 canonicals once stored "cole normale sup rieure"; the rule today folds accents.
        self.assertEqual(S._normalize("École normale supérieure Paris-Saclay"), "ecole normale superieure paris saclay")
        self.assertNotRegex(S._normalize("École normale supérieure Paris-Saclay"), r"\s[a-z]\s")


if __name__ == "__main__":
    unittest.main()
