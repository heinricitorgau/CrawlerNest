"""The reviewed alias files must stay loadable and stay true.

``crawlernest-kb/databases/*_university_aliases_2026.json`` decide which source
name belongs to which canonical university, and 182 of the three-source rows in
the warehouse exist because of them. They are edited by hand and referenced by
id, which is the combination that rots quietly: a canonical university that is
renumbered or removed leaves an entry pointing at nothing, the seeder skips it,
and the only symptom is a university that stops carrying a rank it used to have.

The structural checks run everywhere. The warehouse checks need PostgreSQL and
opt in with ``CRAWLERNEST_RUN_PG_TESTS=1``, matching the rest of the suite:

    CRAWLERNEST_RUN_PG_TESTS=1 CRAWLERNEST_PG_PASSWORD=test \\
        python3 crawlernest/crawlernest-tests/run_tests.py
"""

from __future__ import annotations

import json
import os
import unittest
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ALIAS_DIR = REPO_ROOT / "crawlernest" / "crawlernest-kb" / "databases"
ALIAS_FILES = sorted(ALIAS_DIR.glob("*_university_aliases_*.json"))

REQUIRED_FIELDS = ("canonical_university_id", "alias_text", "canonical_slug_hint")
VALID_METHODS = {"rule", "curated"}


def _load(path: Path) -> list[dict]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise AssertionError(f"{path.name}: expected a list")
    return rows


class TestAliasFileStructure(unittest.TestCase):
    def test_alias_files_exist(self):
        # Globbing for the files means an accidental rename turns every check
        # below into a vacuous pass over an empty list.
        self.assertGreaterEqual(len(ALIAS_FILES), 2, f"no alias files in {ALIAS_DIR}")

    def test_required_fields_present(self):
        for path in ALIAS_FILES:
            for index, row in enumerate(_load(path)):
                for field in REQUIRED_FIELDS:
                    self.assertIn(field, row, f"{path.name}[{index}] lacks {field}")
                self.assertTrue(str(row["alias_text"]).strip(),
                                f"{path.name}[{index}] has an empty alias_text")

    def test_one_to_one_within_each_file(self):
        """No canonical university twice, and no source name twice.

        This is condition 3 of the matching method, held as an invariant of the
        file rather than only of the run that produced it. A hand edit that adds
        a second alias for a university it already resolves is the way a
        one-to-one guarantee gets lost after the fact.
        """
        for path in ALIAS_FILES:
            rows = _load(path)
            for field in ("canonical_university_id", "alias_text"):
                dupes = [value for value, n in Counter(r[field] for r in rows).items() if n > 1]
                self.assertEqual([], dupes, f"{path.name}: duplicate {field}: {dupes}")

    def test_curated_rows_state_their_reason(self):
        """A curated row is an assertion, so it has to say what it asserts.

        ``rule`` rows can be re-derived by re-running the generator. ``curated``
        rows cannot: they rest on a fact about the institution. Without the
        reason there is no way for a later reader to tell an informed judgement
        from a guess, and every row looks equally authoritative.
        """
        for path in ALIAS_FILES:
            for row in _load(path):
                method = row.get("method", "rule")
                self.assertIn(method, VALID_METHODS,
                              f"{path.name}: unknown method {method!r} for {row['alias_text']!r}")
                if method == "curated":
                    self.assertTrue(str(row.get("reason", "")).strip(),
                                    f"{path.name}: curated row {row['alias_text']!r} has no reason")


@unittest.skipUnless(
    os.getenv("CRAWLERNEST_RUN_PG_TESTS") == "1", "PostgreSQL integration tests are opt-in"
)
class TestAliasFilesAgainstWarehouse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg2

        cls.conn = psycopg2.connect(
            host=os.getenv("CRAWLERNEST_PG_HOST", "localhost"),
            port=int(os.getenv("CRAWLERNEST_PG_PORT", "5432")),
            dbname=os.getenv("CRAWLERNEST_PG_DATABASE", "clawer"),
            user=os.getenv("CRAWLERNEST_PG_USER", "test"),
            password=os.getenv("CRAWLERNEST_PG_PASSWORD", ""),
        )
        with cls.conn.cursor() as cur:
            cur.execute("SELECT canonical_university_id FROM warehouse.canonical_university")
            cls.canonical_ids = {int(r[0]) for r in cur.fetchall()}
        if not cls.canonical_ids:
            raise unittest.SkipTest("warehouse has no canonical universities")

    @classmethod
    def tearDownClass(cls):
        conn = getattr(cls, "conn", None)
        if conn is not None:
            conn.close()

    def test_every_canonical_id_still_exists(self):
        dangling = []
        for path in ALIAS_FILES:
            for row in _load(path):
                if int(row["canonical_university_id"]) not in self.canonical_ids:
                    dangling.append(f"{path.name}: #{row['canonical_university_id']} "
                                    f"{row['alias_text']!r}")
        self.assertEqual([], dangling,
                         f"{len(dangling)} alias rows point at canonical universities "
                         f"that no longer exist:\n  " + "\n  ".join(dangling))

    def test_alias_ids_agree_with_the_slug_hint(self):
        """The id and the name in the same row must still describe one university.

        ``canonical_slug_hint`` is there for a human reading the file, so nothing
        reads it and nothing notices when it drifts from the id beside it. If it
        drifts, every later review is done against the wrong name -- the file
        reads as if it says one thing while seeding another.
        """
        with self.conn.cursor() as cur:
            cur.execute("SELECT canonical_university_id, display_name "
                        "FROM warehouse.canonical_university")
            names = {int(r[0]): str(r[1]) for r in cur.fetchall()}

        mismatched = []
        for path in ALIAS_FILES:
            for row in _load(path):
                cid = int(row["canonical_university_id"])
                actual = names.get(cid)
                if actual is not None and actual != row["canonical_slug_hint"]:
                    mismatched.append(f"{path.name}: #{cid} file says "
                                      f"{row['canonical_slug_hint']!r}, warehouse says {actual!r}")
        self.assertEqual([], mismatched,
                         f"{len(mismatched)} rows name a different university than their id:\n  "
                         + "\n  ".join(mismatched))


if __name__ == "__main__":
    unittest.main()
