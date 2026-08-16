"""The exported QS<->THE pairing must still agree with the warehouse.

``crawlernest-kb/databases/qs_the_pairing_2026.json`` is the warehouse's answer
to "which QS university is which THE university", exported by hand so the ML
jobs can read it without a database. Nothing keeps the two in step. Re-ingest
THE, correct a match, forget the export, and the disagreement model goes on
training against the pairing that used to be true -- silently, because a stale
join produces a plausible number rather than an error.

This does not synchronise them. It fails when they differ, which is the point.

Skipped where the warehouse has no THE rows -- a freshly bootstrapped database
has nothing to compare against, and treating that as a mismatch would make the
check fire loudest exactly where it knows least.

    CRAWLERNEST_RUN_PG_TESTS=1 CRAWLERNEST_PG_PASSWORD=test \\
        python3 crawlernest/crawlernest-tests/run_tests.py
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PAIRING_FILE = REPO_ROOT / "crawlernest" / "crawlernest-kb" / "databases" / "qs_the_pairing_2026.json"

#: Below this, the warehouse is a scratch or partially loaded database rather
#: than one the export could reasonably be compared against.
MINIMUM_WAREHOUSE_PAIRS = 100


@unittest.skipUnless(
    os.getenv("CRAWLERNEST_RUN_PG_TESTS") == "1", "PostgreSQL integration tests are opt-in"
)
class TestPairingMatchesWarehouse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg2

        if not PAIRING_FILE.is_file():
            raise unittest.SkipTest(f"no pairing file at {PAIRING_FILE}")

        dsn = {
            "host": os.getenv("CRAWLERNEST_PG_HOST", "localhost"),
            "port": int(os.getenv("CRAWLERNEST_PG_PORT", "5432")),
            "database": os.getenv("CRAWLERNEST_PG_DATABASE", "clawer"),
            "user": os.getenv("CRAWLERNEST_PG_USER", "test"),
            "password": os.getenv("CRAWLERNEST_PG_PASSWORD", ""),
        }
        conn = psycopg2.connect(**dsn)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT cu.display_name, rr.metadata #>> '{raw_row,name}'
                    FROM warehouse.ranking_record rr
                    JOIN warehouse.ranking_source rs USING (ranking_source_id)
                    JOIN warehouse.canonical_university cu USING (canonical_university_id)
                    WHERE rs.source_code = 'THE'
                """)
                cls.warehouse = {str(a): str(b) for a, b in cur.fetchall() if b}
        finally:
            conn.close()

        if len(cls.warehouse) < MINIMUM_WAREHOUSE_PAIRS:
            raise unittest.SkipTest(
                f"warehouse holds {len(cls.warehouse)} THE pairs, too few to compare "
                "an export against"
            )

        cls.exported = {
            str(row["qs_name"]): str(row["the_name"])
            for row in json.loads(PAIRING_FILE.read_text(encoding="utf-8"))
        }

    def test_the_export_covers_the_same_universities(self):
        only_file = sorted(set(self.exported) - set(self.warehouse))
        only_warehouse = sorted(set(self.warehouse) - set(self.exported))
        self.assertEqual(
            (only_file, only_warehouse),
            ([], []),
            "the pairing export and the warehouse disagree about which universities "
            f"have a THE rank. Only in the file: {only_file[:5]}. Only in the "
            f"warehouse: {only_warehouse[:5]}. Re-export before trusting ML metrics.",
        )

    def test_no_university_is_paired_to_a_different_entity(self):
        changed = [
            (qs, self.exported[qs], self.warehouse[qs])
            for qs in set(self.exported) & set(self.warehouse)
            if self.exported[qs] != self.warehouse[qs]
        ]
        self.assertEqual(
            changed, [],
            "the export pairs universities to different THE entities than the "
            f"warehouse does: {changed[:5]}",
        )


if __name__ == "__main__":
    unittest.main()
