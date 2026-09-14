"""The crawler records when it fetched a page, and that time reaches the warehouse.

CAVEAT_ADMISSION_DATA_STALE names a date. It can say "fetched on" only when a
row records a fetch; until now none did -- the crawler never kept the time --
so every response fell back to the undated form. These pin the time from where
the body arrives in crawlers/university_site.py, through the bridge, staging
(JSONL, SQLite, PostgreSQL) and the warehouse mapper, and the three ways it
could be quietly wrong:

* a snapshot read stamped with the time the file was opened, or with
  extracted_at, as though someone had fetched the page that day;
* a naive timestamp, which TIMESTAMPTZ reads in the session's zone (+08 on the
  development database) and can move to the neighbouring date;
* a live row with no time, which the database refuses only at the very end.

    CRAWLERNEST_RUN_PG_TESTS=1 CRAWLERNEST_PG_PASSWORD=test \\
        python3 crawlernest/crawlernest-tests/run_tests.py
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent
REPO_ROOT = PACKAGE_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from crawlernest.core.caveats import admission_stale_caveat  # noqa: E402
from crawlernest_admission_crawler.crawl_bridge import (  # noqa: E402
    _crawler_imports,
    _ensure_crawler_importable,
    crawl_admission_records,
    to_pipeline_record,
)
from crawlernest_admission_crawler.normalize import normalize_admission_records  # noqa: E402
from crawlernest_admission_crawler.validator import validate_admission_staging_rows  # noqa: E402
from crawlernest_admission_crawler.warehouse_mapper import (  # noqa: E402
    load_staging_rows_from_jsonl,
    map_staging_rows_to_warehouse_rows,
)
from crawlernest_admission_crawler.warehouse_writer import load_warehouse_preview_rows  # noqa: E402
from crawlernest_admission_crawler.writer import (  # noqa: E402
    _ingest_to_sqlite,
    write_normalized_admission_rows_to_jsonl,
)

SNAPSHOT_DIR = PACKAGE_ROOT / "crawlernest-admission-crawler" / "crawl_snapshots"
MIT_BASE = "https://gradadmissions.mit.edu"
MIT_URL = "https://gradadmissions.mit.edu/apply/english-language"
EXTRACTED_AT = datetime(2026, 9, 14, 3, 0, tzinfo=timezone.utc)
FETCHED_AT = datetime(2026, 9, 14, 2, 59, 30, tzinfo=timezone.utc)

#: Enough visible words to clear _MIN_VISIBLE_WORDS, and an IELTS figure the
#: extractor recognises so the record is usable.
PAGE = (
    "<html><body><h1>English language requirements</h1><p>"
    + "Applicants to graduate programmes must demonstrate English proficiency. " * 8
    + "The minimum IELTS score is 7.0 overall. The minimum TOEFL iBT score is 100."
    + "</p></body></html>"
)


def _crawler_class():
    _ensure_crawler_importable()
    with _crawler_imports():
        from crawlers.university_site import UniversityAdmissionCrawler
    return UniversityAdmissionCrawler


class _FakeHttpClient:
    def __init__(self, *, body=None, error=None):
        self.body = body
        self.error = error

    def get_text(self, url):
        if self.error is not None:
            raise self.error
        return self.body


def _live_crawler(**client):
    crawler = _crawler_class()(rate_limit_seconds=0.0)
    crawler.http_client = _FakeHttpClient(**client)
    return crawler


class _Crawled:
    """The shape crawlers/university_site.py returns."""

    def __init__(self, *, fetch_mode="live", fetched_at=FETCHED_AT, omit_fetch=False):
        self.university_name = "Massachusetts Institute of Technology (MIT)"
        self.source_url = MIT_URL
        self.degree_level = "postgraduate"
        self.requirements = {"IELTS": "7.0", "TOEFL": "100"}
        self.crawl_status = "success"
        self.notes = ""
        self.extraction_summary = None
        if not omit_fetch:
            self.fetch_mode = fetch_mode
            self.fetched_at = fetched_at


def _staging_row(**extra):
    row = {
        "university_name": "Massachusetts Institute of Technology (MIT)",
        "normalized_university_name": "Massachusetts Institute Of Technology (MIT)",
        "source_url": MIT_URL,
        "country": "United States",
        "ielts_requirement": 7.0,
        "toefl_requirement": 100,
        "extracted_at": EXTRACTED_AT.isoformat(),
        "degree_level": "postgraduate",
    }
    row.update(extra)
    return row


class TestTheCrawlerStampsWhatItFetched(unittest.TestCase):
    def test_a_live_fetch_records_live_and_the_time_the_body_arrived(self):
        before = datetime.now(timezone.utc)
        record = _live_crawler(body=PAGE).crawl_one(university_name="MIT", base_url=MIT_BASE, url=MIT_URL)
        after = datetime.now(timezone.utc)

        self.assertEqual("success", record.crawl_status)
        self.assertEqual("live", record.fetch_mode)
        self.assertIsNotNone(record.fetched_at.utcoffset(), "fetched_at must be timezone-aware")
        self.assertTrue(before <= record.fetched_at <= after, (before, record.fetched_at, after))

    def test_an_empty_live_body_was_still_fetched(self):
        record = _live_crawler(body="<html></html>").crawl_one(university_name="MIT", base_url=MIT_BASE, url=MIT_URL)
        self.assertEqual(("empty", "live"), (record.crawl_status, record.fetch_mode))
        self.assertIsNotNone(record.fetched_at)

    def test_a_failed_fetch_read_no_page_so_it_claims_no_fetch(self):
        for error in (
            urllib.error.HTTPError(MIT_URL, 403, "Forbidden", {}, None),
            urllib.error.URLError("connection refused"),
            TimeoutError(),
        ):
            with self.subTest(error=type(error).__name__):
                record = _live_crawler(error=error).crawl_one(university_name="MIT", base_url=MIT_BASE, url=MIT_URL)
                self.assertEqual(("unknown", None), (record.fetch_mode, record.fetched_at))

    def test_a_skipped_off_host_url_claims_no_fetch(self):
        record = _live_crawler(body=PAGE).crawl_one(
            university_name="MIT", base_url=MIT_BASE, url="https://example.com/english"
        )
        self.assertEqual(("blocked", "unknown", None), (record.crawl_status, record.fetch_mode, record.fetched_at))

    @unittest.skipUnless(SNAPSHOT_DIR.is_dir(), "checked-in snapshots are required")
    def test_a_snapshot_read_is_a_snapshot_with_no_fetch_time(self):
        """Opening the file today is not fetching the page today."""
        crawler = _crawler_class()(snapshot_dir=SNAPSHOT_DIR, rate_limit_seconds=0.0)
        crawler.http_client = _FakeHttpClient(error=AssertionError("a snapshot read must not reach the network"))
        record = crawler.crawl_one(university_name="MIT", base_url=MIT_BASE, url=MIT_URL)
        self.assertEqual(("success", "snapshot", None), (record.crawl_status, record.fetch_mode, record.fetched_at))


class TestTheBridgeCarriesItAndInventsNothing(unittest.TestCase):
    def test_a_live_record_keeps_its_fetch(self):
        record = to_pipeline_record(_Crawled(), country="United States", extracted_at=EXTRACTED_AT)
        self.assertEqual(("live", FETCHED_AT), (record.fetch_mode, record.fetched_at))

    def test_extracted_at_never_stands_in_for_a_missing_fetch_time(self):
        for crawled in (_Crawled(fetch_mode="snapshot", fetched_at=None), _Crawled(omit_fetch=True)):
            record = to_pipeline_record(crawled, country="United States", extracted_at=EXTRACTED_AT)
            self.assertIsNone(record.fetched_at)
            self.assertIn(record.fetch_mode, ("snapshot", "unknown"))

    def test_a_record_from_before_fetches_were_recorded_is_unknown(self):
        record = to_pipeline_record(_Crawled(omit_fetch=True), country="United States", extracted_at=EXTRACTED_AT)
        self.assertEqual("unknown", record.fetch_mode)

    def test_impossible_provenance_is_refused_with_the_url(self):
        for crawled, message in (
            (_Crawled(fetched_at=None), "live fetch arrived without fetched_at"),
            (_Crawled(fetched_at=datetime(2026, 9, 14, 10, 0)), "has no timezone"),
            (_Crawled(fetch_mode="cache"), "is not one of"),
        ):
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message) as caught:
                    to_pipeline_record(crawled, country="United States", extracted_at=EXTRACTED_AT)
                self.assertIn(MIT_URL, str(caught.exception))

    @unittest.skipUnless(SNAPSHOT_DIR.is_dir(), "checked-in snapshots are required")
    def test_an_offline_crawl_lands_as_snapshot_rows_without_a_fetch_date(self):
        records, _ = crawl_admission_records(snapshot_dir=SNAPSHOT_DIR)
        self.assertTrue(records)
        self.assertEqual({("snapshot", None)}, {(r.fetch_mode, r.fetched_at) for r in records})


class TestStagingCarriesIt(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _jsonl(self, rows):
        path = self.tmp / "staging.jsonl"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return path

    def test_crawl_to_jsonl_to_warehouse_row_keeps_the_instant(self):
        record = to_pipeline_record(_Crawled(), country="United States", extracted_at=EXTRACTED_AT)
        path = self.tmp / "normalized.jsonl"
        write_normalized_admission_rows_to_jsonl(normalize_admission_records([record]), path)

        result = validate_admission_staging_rows(path)
        self.assertEqual(1, result.summary.valid_row_count, result.summary.error_samples)
        self.assertEqual("2026-09-14T02:59:30+00:00", result.valid_rows[0]["fetched_at"])

        row = map_staging_rows_to_warehouse_rows(load_staging_rows_from_jsonl(path))[0]
        self.assertEqual(("live", FETCHED_AT), (row.fetch_mode, row.fetched_at))

    def test_the_validator_names_bad_provenance_against_its_line(self):
        cases = {
            "live_fetch_missing_fetched_at": _staging_row(fetch_mode="live"),
            "fetched_at_missing_timezone": _staging_row(fetch_mode="live", fetched_at="2026-09-14T10:00:00"),
            "invalid_fetched_at_isoformat": _staging_row(fetch_mode="live", fetched_at="14 Sep 2026"),
            "invalid_fetch_mode": _staging_row(fetch_mode="cache"),
        }
        for expected, row in cases.items():
            with self.subTest(expected=expected):
                result = validate_admission_staging_rows(self._jsonl([row]))
                self.assertEqual(1, result.summary.invalid_row_count)
                self.assertIn(expected, result.summary.error_samples[0]["errors"])

    def test_a_row_from_before_fetches_were_recorded_still_validates(self):
        result = validate_admission_staging_rows(self._jsonl([_staging_row()]))
        self.assertEqual(1, result.summary.valid_row_count, result.summary.error_samples)

    def test_the_mapper_and_the_preview_loader_refuse_a_naive_fetch_time(self):
        naive = _staging_row(fetch_mode="live", fetched_at="2026-09-14T10:00:00")
        with self.assertRaisesRegex(ValueError, "has no timezone"):
            map_staging_rows_to_warehouse_rows([naive])
        preview = self.tmp / "preview.json"
        for row, message in ((naive, "has no timezone"), (_staging_row(fetch_mode="live"), "needs fetched_at")):
            with self.subTest(message=message):
                preview.write_text(json.dumps([row]), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    load_warehouse_preview_rows(preview)

    def test_sqlite_staging_stores_it_and_upgrades_an_older_table(self):
        db = self.tmp / "staging.db"
        conn = sqlite3.connect(db)
        conn.execute(
            "CREATE TABLE admission_staging_records (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "university_name TEXT NOT NULL, normalized_university_name TEXT NOT NULL, source_url TEXT NOT NULL, "
            "country TEXT NULL, ielts_requirement REAL NULL, toefl_requirement INTEGER NULL, "
            "extracted_at TEXT NOT NULL, duolingo_requirement INTEGER NULL, gpa_requirement REAL NULL, "
            "application_deadline TEXT NULL, degree_level TEXT NOT NULL DEFAULT 'unknown', raw_payload TEXT NULL, "
            "UNIQUE(source_url, degree_level))"
        )
        conn.commit()
        conn.close()

        inserted, _ = _ingest_to_sqlite(db, [_staging_row(fetch_mode="live", fetched_at=FETCHED_AT.isoformat())])

        conn = sqlite3.connect(db)
        try:
            stored = conn.execute("SELECT fetched_at, fetch_mode FROM admission_staging_records").fetchall()
        finally:
            conn.close()
        self.assertEqual(1, inserted)
        self.assertEqual([(FETCHED_AT.isoformat(), "live")], stored)


class TestTheCaveatCanNowNameAFetchDate(unittest.TestCase):
    def test_a_crawler_fetch_renders_fetched_on(self):
        record = _live_crawler(body=PAGE).crawl_one(university_name="MIT", base_url=MIT_BASE, url=MIT_URL)
        caveat = admission_stale_caveat(
            fetch_dates_recorded=True,
            oldest_fetched_on=record.fetched_at.date(),
            oldest_extracted_on=record.fetched_at.date(),
        )
        self.assertIn(f"fetched on {record.fetched_at.date().isoformat()}", caveat)


@unittest.skipUnless(os.getenv("CRAWLERNEST_RUN_PG_TESTS") == "1", "PostgreSQL integration tests are opt-in")
class TestPostgresStagingAndLanding(unittest.TestCase):
    STAGING = "admission_staging_fetch_provenance_test"
    URL = "https://gradadmissions.mit.edu/crawlernest-fetch-provenance-fixture"

    @classmethod
    def setUpClass(cls):
        import psycopg2

        cls.pg = {
            "pg_host": os.getenv("CRAWLERNEST_PG_HOST", "localhost"),
            "pg_port": int(os.getenv("CRAWLERNEST_PG_PORT", "5432")),
            "pg_database": os.getenv("CRAWLERNEST_PG_DATABASE", "clawer"),
            "pg_user": os.getenv("CRAWLERNEST_PG_USER", "test"),
            "pg_password": os.getenv("CRAWLERNEST_PG_PASSWORD", ""),
        }
        cls.conn = psycopg2.connect(
            host=cls.pg["pg_host"], port=cls.pg["pg_port"], dbname=cls.pg["pg_database"],
            user=cls.pg["pg_user"], password=cls.pg["pg_password"],
        )
        cls.conn.autocommit = True

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def setUp(self):
        self._clear()
        self.addCleanup(self._clear)

    def _clear(self):
        with self.conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {self.STAGING}")
            cur.execute("DELETE FROM warehouse.admission_record WHERE source_url = %s", (self.URL,))

    def _load(self):
        from crawlernest_admission_crawler.warehouse_mapper import load_staging_rows_from_postgres

        return load_staging_rows_from_postgres(table_name=self.STAGING, **self.pg)

    def test_an_older_staging_table_reads_as_unrecorded_then_upgrades_on_ingest(self):
        from crawlernest_admission_crawler.writer import _ingest_to_postgres
        from crawlernest_admission_crawler.warehouse_writer import write_warehouse_landing_rows

        with self.conn.cursor() as cur:
            cur.execute(
                f"CREATE TABLE {self.STAGING} (id BIGSERIAL PRIMARY KEY, university_name TEXT NOT NULL, "
                "normalized_university_name TEXT NOT NULL, source_url TEXT NOT NULL, country TEXT NULL, "
                "ielts_requirement DOUBLE PRECISION NULL, toefl_requirement INTEGER NULL, "
                "extracted_at TIMESTAMPTZ NOT NULL, duolingo_requirement INTEGER NULL, "
                "gpa_requirement DOUBLE PRECISION NULL, application_deadline DATE NULL, "
                "degree_level TEXT NOT NULL DEFAULT 'unknown', raw_payload JSONB NULL, "
                "UNIQUE (source_url, degree_level))"
            )
            cur.execute(
                f"INSERT INTO {self.STAGING} (university_name, normalized_university_name, source_url, extracted_at, "
                "degree_level) VALUES ('MIT', 'MIT', %s, %s, 'undergraduate')",
                (self.URL, EXTRACTED_AT),
            )
        self.assertEqual([(None, "unknown")], [(r["fetched_at"], r["fetch_mode"]) for r in self._load()])

        # A fetch late on the 14th UTC is already the 15th in +08: the date must
        # come back as the instant that was written, not the session's reading.
        late = datetime(2026, 9, 14, 23, 30, tzinfo=timezone.utc)
        _ingest_to_postgres(
            [_staging_row(source_url=self.URL, fetch_mode="live", fetched_at=late.isoformat())],
            table_name=self.STAGING, **self.pg,
        )
        by_level = {r["degree_level"]: r for r in self._load()}
        self.assertEqual("live", by_level["postgraduate"]["fetch_mode"])
        self.assertEqual(late, datetime.fromisoformat(by_level["postgraduate"]["fetched_at"]))
        self.assertEqual("unknown", by_level["undergraduate"]["fetch_mode"])

        rows = [r for r in map_staging_rows_to_warehouse_rows(self._load()) if r.degree_level == "postgraduate"]
        write_warehouse_landing_rows(rows, **self.pg)
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT fetch_mode, fetched_at, (fetched_at AT TIME ZONE 'UTC')::date "
                "FROM warehouse.admission_record WHERE source_url = %s",
                (self.URL,),
            )
            landed = cur.fetchall()
        self.assertEqual([("live", late, late.date())], landed)
        self.assertNotEqual(late.date(), (late + timedelta(hours=8)).date(), "fixture must straddle midnight in +08")


if __name__ == "__main__":
    unittest.main()
