"""The exported cross-edition ranks must still be what the warehouse holds.

``crawlernest-kb/databases/cross_edition_ranks.csv`` is the input to the MATLAB forecast experiment, exported so the
experiment does not need a database. Nothing keeps the two in step: re-ingest an edition, correct a mapping, forget the
export, and the experiment goes on reproducing a table that used to be true, with a hash that still matches the file.
This fails when they differ, which is all it is for; ``export_cross_edition_ranks.py --commit`` is what to run.

Opt-in, like the other warehouse checks, and skipped where the warehouse is too small to compare against.

    CRAWLERNEST_RUN_PG_TESTS=1 CRAWLERNEST_PG_PASSWORD=test \\
        python3 crawlernest/crawlernest-tests/run_tests.py
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "crawlernest" / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

MINIMUM_RECORDS = 1000


@unittest.skipUnless(os.getenv("CRAWLERNEST_RUN_PG_TESTS") == "1", "PostgreSQL integration tests are opt-in")
class TestCrossEditionExportMatchesWarehouse(unittest.TestCase):
    def test_the_committed_export_is_what_the_warehouse_holds(self):
        import export_cross_edition_ranks as export
        import psycopg2

        if not export.CSV_FILE.is_file():
            self.skipTest("no export committed")
        conn = psycopg2.connect(
            host=os.getenv("CRAWLERNEST_PG_HOST", "localhost"),
            port=int(os.getenv("CRAWLERNEST_PG_PORT", "5432")),
            dbname=os.getenv("CRAWLERNEST_PG_DATABASE", "clawer"),
            user=os.getenv("CRAWLERNEST_PG_USER", "test"),
            password=os.getenv("CRAWLERNEST_PG_PASSWORD", ""),
        )
        try:
            conn.set_session(readonly=True)
            with conn.cursor() as cur:
                cur.execute(export.QUERY)
                records = cur.fetchall()
        finally:
            conn.close()
        if len(records) < MINIMUM_RECORDS:
            self.skipTest(f"only {len(records)} ranking records: a scratch warehouse, nothing to compare against")
        rows, _dropped = export.build_rows(records)
        self.assertEqual(
            export.render_csv(rows),
            export.CSV_FILE.read_text(encoding="utf-8"),
            "cross_edition_ranks.csv differs from the warehouse; run export_cross_edition_ranks.py --commit "
            "and re-run the MATLAB experiment",
        )


if __name__ == "__main__":
    unittest.main()
