"""Tests for the entity review queue (crawlernest/scripts/entity_review_candidates.py).

The queue is read by a person and decides nothing, so what these pin down is what it lists and what it
must not do: a subset of names alone is not a candidate, evidence against a pair lowers it without hiding
it, a dismissal needs its reason, and no annotator other than ``none`` exists until one is added on
purpose. The read against the warehouse needs PostgreSQL and opts in like the rest of the suite.
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
for _p in (str(PACKAGE_ROOT / "scripts"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import entity_review_candidates as E  # noqa: E402

QS, THE, ARWU = "QS", "THE", "ARWU"


def _t(source: str, year: int) -> tuple:
    return (source, year, "world", "global", "global")


def _rec(cid: int, name: str, country: str = "Italy", tables=(), qid=None) -> E.Record:
    return E.Record(cid, f"slug-{cid}", name, country, qid, frozenset(tables))


class TestNameKey(unittest.TestCase):
    def test_translations_and_accents_meet(self) -> None:
        # Pairs from the 2026-10-12 merges an equal key catches.
        for a, b in [("Hannover Medical School", "Medizinische Hochschule Hannover"),
                     ("Ankara University", "Ankara Üniversitesi"),
                     ("Autonomous University of Madrid", "Universidad Autónoma de Madrid")]:
            self.assertEqual(E.name_key(a), E.name_key(b), (a, b))

    def test_parenthesis_and_generic_words_drop(self) -> None:
        self.assertEqual(E.name_key("Universidade Federal do Ceará (UFC)"), frozenset({"federal", "ceara"}))
        self.assertEqual(E.name_key("University of the"), frozenset())

    def test_relation(self) -> None:
        k = E.name_key
        self.assertEqual(E.key_relation(k("Tampere University"), k("University of Tampere")), E.SIG_SAME_NAME_KEY)
        self.assertEqual(E.key_relation(k("North Dakota State University"), k("University of North Dakota")),
                         E.SIG_NAME_KEY_SUBSET)
        # One distinctive word on the smaller side is too little to call a subset.
        self.assertIsNone(E.key_relation(k("Ankara University"), k("Ankara Medical University")))
        self.assertIsNone(E.key_relation(frozenset(), k("Ankara University")))

    def test_recall_on_the_committed_merges(self) -> None:
        # The docstring quotes these figures; a change to the key must change them on purpose.
        path = PACKAGE_ROOT / "crawlernest-kb" / "entity_merges" / "duplicate_canonicals_2026-10-12.json"
        merges = json.loads(path.read_text(encoding="utf-8"))["merges"]
        equal = sum(E.name_key(m["loser_name"]) == E.name_key(m["survivor_name"]) != frozenset() for m in merges)
        related = sum(E.key_relation(E.name_key(m["loser_name"]), E.name_key(m["survivor_name"])) is not None
                      for m in merges)
        self.assertEqual(len(merges), 112)
        self.assertEqual(equal, 43)
        self.assertEqual(related, 56)


class TestDuplicateCandidates(unittest.TestCase):
    def test_same_key_is_listed_high_when_nothing_contradicts(self) -> None:
        a = _rec(1, "Universita degli Studi G. d'Annunzio Chieti Pescara", tables=[_t(QS, 2025), _t(ARWU, 2024)])
        b = _rec(2, "G d'Annunzio University of Chieti-Pescara")
        [c] = E.duplicate_candidates([a, b])
        self.assertEqual(c.signals, [E.SIG_SAME_NAME_KEY])
        self.assertEqual(c.priority, "high")
        self.assertEqual([r["slug"] for r in c.subject["records"]], ["slug-1", "slug-2"])
        self.assertIn("never ranked in the same year", c.evidence)

    def test_a_source_ranking_both_lowers_but_does_not_hide(self) -> None:
        a = _rec(1, "Miami University", "United States", [_t(QS, 2026)])
        b = _rec(2, "University of Miami", "United States", [_t(QS, 2026), _t(THE, 2026)])
        [c] = E.duplicate_candidates([a, b])
        self.assertEqual(c.priority, "low")
        self.assertTrue(any("lists them as two" in x for x in c.against))

    def test_lineage_is_evidence_against(self) -> None:
        a = _rec(1, "University of Tampere", "Finland", [_t(ARWU, 2018)])
        b = _rec(2, "Tampere University", "Finland", [_t(THE, 2024)])
        [c] = E.duplicate_candidates([a, b], lineage=[(1, 2, "merger")])
        self.assertEqual(c.priority, "low")
        self.assertIn("institution_lineage records a merger between them", c.against)

    def test_subset_needs_complementary_coverage(self) -> None:
        state = _rec(1, "North Dakota State University", "United States", [_t(QS, 2026)])
        und = _rec(2, "University of North Dakota", "United States", [_t(QS, 2026)])
        self.assertEqual(E.duplicate_candidates([state, und]), [])        # one source ranks both
        und2 = _rec(2, "University of North Dakota", "United States", [_t(THE, 2026)])
        [c] = E.duplicate_candidates([state, und2])
        self.assertEqual((c.signals, c.priority), ([E.SIG_NAME_KEY_SUBSET], "medium"))
        und3 = _rec(2, "University of North Dakota", "United States", [_t(THE, 2019)])
        self.assertEqual(E.duplicate_candidates([state, und3]), [])       # no shared year

    def test_shared_wikidata_and_name_key_are_one_candidate(self) -> None:
        a = _rec(1, "Ankara University", "Turkey", [_t(THE, 2026)], qid="Q1")
        b = _rec(2, "Ankara Üniversitesi", "Turkey", [_t(QS, 2026)], qid="Q1")
        [c] = E.duplicate_candidates([a, b])
        self.assertEqual(c.signals, [E.SIG_SHARED_WIKIDATA, E.SIG_SAME_NAME_KEY])
        self.assertEqual(c.priority, "high")

    def test_other_countries_are_not_compared(self) -> None:
        a = _rec(1, "University of Lagos", "Nigeria")
        b = _rec(2, "Universidad de Los Lagos", "Chile")
        self.assertEqual(E.duplicate_candidates([a, b]), [])


class TestMappingCandidates(unittest.TestCase):
    def _m(self, conf: float, **flags) -> E.FuzzyMapping:
        return E.FuzzyMapping("THE", "924", "Paris-Sorbonne University – Paris 4", "paris-sorbonne",
                              "Paris Sorbonne University", "fuzzy_review", conf, **flags)

    def test_priority(self) -> None:
        self.assertEqual(E.fuzzy_candidates([self._m(0.95, country_mismatch=True)])[0].priority, "high")
        self.assertEqual(E.fuzzy_candidates([self._m(0.83)])[0].priority, "medium")
        self.assertEqual(E.fuzzy_candidates([self._m(0.95)])[0].priority, "low")

    def test_collision_line_is_parsed(self) -> None:
        [c] = E.collision_candidates(["THE 2019: c1262 'Miami University' holds ['A', 'B']"])
        self.assertEqual(c.subject["source_entity_id"], "collision:2019:c1262")
        self.assertEqual(c.priority, "high")


class TestDismissals(unittest.TestCase):
    def _file(self, entries: list) -> Path:
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump({"dismissed": entries}, handle)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return Path(handle.name)

    def test_a_dismissal_needs_its_reason_and_shape(self) -> None:
        for bad in ({"kind": "duplicate", "slugs": ["a", "b"], "why": " "},
                    {"kind": "duplicate", "slugs": ["a", "a"], "why": "x"},
                    {"kind": "mapping", "source_code": "THE", "why": "x"},
                    {"kind": "alias", "why": "x"}):
            with self.assertRaises(ValueError, msg=bad):
                E.load_dismissed(self._file([bad]))

    def test_split_hides_dismissed_and_reports_stale(self) -> None:
        a = _rec(1, "Miami University", "United States")
        b = _rec(2, "University of Miami", "United States")
        cands = E.duplicate_candidates([a, b]) + E.fuzzy_candidates(
            [E.FuzzyMapping("QS", "x", "X", "s", "S", "fuzzy", 0.9)])
        dismissed = E.load_dismissed(self._file([
            {"kind": "duplicate", "slugs": ["slug-2", "slug-1"], "why": "two universities"},
            {"kind": "mapping", "source_code": "THE", "source_entity_id": "gone", "why": "fine"},
        ]))
        queue, hidden, stale = E.split_dismissed(cands, dismissed)
        self.assertEqual([c.kind for c in queue], [E.KIND_MAPPING])
        self.assertEqual(hidden[0]["dismissed_because"], "two universities")
        self.assertEqual([e["source_entity_id"] for e in stale], ["gone"])

    def test_committed_file_loads(self) -> None:
        entries = E.load_dismissed(E.DISMISSED_PATH)
        self.assertTrue(all(e.get("decided_by") for e in entries))


class TestReport(unittest.TestCase):
    def test_only_the_offline_annotator_exists(self) -> None:
        # A model annotator sends candidates somewhere. Adding one is a decision; this makes it a visible one.
        self.assertEqual(sorted(E.ANNOTATORS), ["none"])
        self.assertIsNone(E.NoAnnotator().annotate(E.Candidate(E.KIND_MAPPING, [], {})))

    def test_build_and_render(self) -> None:
        recs = [_rec(1, "Tampere University", "Finland", [_t(THE, 2024)]),
                _rec(2, "University of Tampere", "Finland", [_t(ARWU, 2018)])]
        report = E.build_report(recs, [], [], [], [], E.NoAnnotator(), matches_generated_at=None,
                                today="2026-11-13")
        self.assertEqual(report["counts"], {"duplicate:high": 1})
        self.assertIsNone(report["queue"][0]["model_note"])
        md = E.render_markdown(report)
        self.assertIn("Nothing here is a decision", md)
        self.assertIn("Tampere University / University of Tampere", md)


@unittest.skipUnless(os.getenv("CRAWLERNEST_RUN_PG_TESTS") == "1", "PostgreSQL integration tests are opt-in")
class TestAgainstPostgres(unittest.TestCase):
    def test_reads_only_active_records_in_a_read_only_session(self) -> None:
        import psycopg2

        conn = psycopg2.connect(host=os.getenv("CRAWLERNEST_PG_HOST", "localhost"),
                                port=int(os.getenv("CRAWLERNEST_PG_PORT", "5432")),
                                dbname=os.getenv("CRAWLERNEST_PG_DATABASE", "clawer"),
                                user=os.getenv("CRAWLERNEST_PG_USER", "test"),
                                password=os.getenv("CRAWLERNEST_PG_PASSWORD", ""))
        try:
            conn.set_session(readonly=True)
            records = E.fetch_records(conn)
            fuzzy = E.fetch_fuzzy(conn)
            lineage = E.fetch_lineage(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT canonical_slug FROM warehouse.canonical_university WHERE status <> 'active'")
                inactive = {r[0] for r in cur.fetchall()}
        finally:
            conn.close()
        self.assertFalse({r.slug for r in records} & inactive)
        report = E.build_report(records, lineage, fuzzy, [], [], E.NoAnnotator(), matches_generated_at=None,
                                today="2026-11-13")
        listed = {r["slug"] for c in report["queue"] if c["kind"] == E.KIND_DUPLICATE
                  for r in c["subject"]["records"]}
        self.assertFalse(listed & inactive)
        self.assertTrue(all(c["model_note"] is None for c in report["queue"]))


if __name__ == "__main__":
    unittest.main()
