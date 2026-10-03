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

import warehouse_gate

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
            warehouse_gate.too_small("no export committed")
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
            warehouse_gate.too_small(f"only {len(records)} ranking records: a scratch warehouse, nothing to compare against")
        rows, _dropped = export.build_rows(records)
        self.assertEqual(
            export.render_csv(rows),
            export.CSV_FILE.read_text(encoding="utf-8"),
            "cross_edition_ranks.csv differs from the warehouse; run export_cross_edition_ranks.py --commit "
            "and re-run the MATLAB experiment",
        )


class TestTheExportCodeAndTheCommittedFileAgree(unittest.TestCase):
    """Runs everywhere, database or not.

    The test above holds the file against the warehouse, which only a populated database can answer. This holds it
    against the export *code*: the committed rows are turned back into what the query returns -- one record per
    ranking row, with the printed text -- and fed through ``build_rows`` and ``render_csv``. If the parser that reads a
    printed rank, or the way a row is written, changes without a re-export, the next export would differ from the
    committed file in ways nobody chose. This fails the day that change is made, instead of at the next export.
    """

    def test_the_committed_rows_survive_the_exporters_own_transformation(self):
        import csv

        import export_cross_edition_ranks as export

        self.assertTrue(export.CSV_FILE.is_file(), "the cross-edition export is not committed")
        text = export.CSV_FILE.read_text(encoding="utf-8")
        records = [
            (int(r["canonical_university_id"]), r["canonical_slug"], int(r["year"]), r["source"], r["printed"],
             r["source_kind"] == "web_archive")
            for r in csv.DictReader(text.splitlines())
        ]
        self.assertGreater(len(records), 1000, "the committed export is implausibly small")
        rows, dropped = export.build_rows(records)
        self.assertEqual(dict(dropped), {}, f"rows the exporter now refuses to parse: {dict(dropped)}")
        self.assertEqual(export.render_csv(rows), text)

    def test_the_meta_file_describes_the_csv_beside_it(self):
        import hashlib
        import json

        import export_cross_edition_ranks as export

        self.assertTrue(export.CSV_FILE.is_file() and export.META_FILE.is_file(),
                        "the cross-edition export and its meta file are not both committed")
        meta = json.loads(export.META_FILE.read_text(encoding="utf-8"))
        data = export.CSV_FILE.read_bytes().replace(b"\r\n", b"\n")
        self.assertEqual(meta["csv_sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(meta["rows"], data.count(b"\n") - 1)


if __name__ == "__main__":
    unittest.main()
