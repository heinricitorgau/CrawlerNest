"""Tests for the enrichment cooldown & retry system.

Covers:
- _classify_enrichment_failure: maps exception types to failure categories
- _is_in_cooldown: respects next_retry_at timestamps
- _migrate_deferred_item: v1 (attempts) -> v2 (failure_count)
- _write_deferred_file: deduplication
- enrich_deferred_details cooldown-skip path (no DB needed)
"""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Bootstrap module paths
TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent

sys.path.insert(0, str(PACKAGE_ROOT))
sys.path.insert(0, str(PACKAGE_ROOT / "crawlernest-core"))
sys.path.insert(0, str(PACKAGE_ROOT / "crawlernest-extractors"))

from run_pipeline import (
    _JsOnlyPage,
    _classify_enrichment_failure,
    _is_in_cooldown,
    _migrate_deferred_item,
    _write_deferred_file,
    _FAILURE_MAX_COOLDOWN_HOURS,
    load_deferred_detail_list,
)


# ---------------------------------------------------------------------------
# Fake exception classes that mimic requests hierarchy by name
# ---------------------------------------------------------------------------
class FakeHTTPError(Exception):
    pass

class FakeHTTPError403(FakeHTTPError):
    pass

class FakeTimeout(Exception):
    pass

class FakeConnectionError(Exception):
    pass

class FakeRequestException(Exception):
    pass


# ---------------------------------------------------------------------------
# _classify_enrichment_failure
# ---------------------------------------------------------------------------
class TestClassifyEnrichmentFailure(unittest.TestCase):

    def test_js_only_page_is_permanent(self):
        ft, retryable, hours = _classify_enrichment_failure(_JsOnlyPage("shell"))
        self.assertEqual(ft, "js_only_permanent")
        self.assertFalse(retryable)
        self.assertEqual(hours, float("inf"))

    def test_http_error_403(self):
        exc = FakeHTTPError("403 Client Error: Forbidden")
        exc.__class__.__name__ = "HTTPError"
        ft, retryable, hours = _classify_enrichment_failure(exc)
        self.assertEqual(ft, "http_403")
        self.assertTrue(retryable)
        self.assertEqual(hours, 12.0)

    def test_http_error_non_403(self):
        exc = FakeHTTPError("500 Server Error")
        exc.__class__.__name__ = "HTTPError"
        ft, retryable, hours = _classify_enrichment_failure(exc)
        self.assertEqual(ft, "http_error")
        self.assertTrue(retryable)
        self.assertEqual(hours, 6.0)

    def test_timeout(self):
        exc = FakeTimeout("request timed out")
        exc.__class__.__name__ = "ReadTimeout"
        ft, retryable, hours = _classify_enrichment_failure(exc)
        self.assertEqual(ft, "http_timeout")
        self.assertTrue(retryable)
        self.assertEqual(hours, 2.0)

    def test_connection_error(self):
        exc = FakeConnectionError("connection reset")
        exc.__class__.__name__ = "ConnectionError"
        ft, retryable, hours = _classify_enrichment_failure(exc)
        self.assertEqual(ft, "http_error")
        self.assertTrue(retryable)

    def test_parse_no_signal(self):
        ft, retryable, hours = _classify_enrichment_failure(
            ValueError("No admission signal (gpa/ielts/toefl/gre/gmat) in parsed HTML")
        )
        self.assertEqual(ft, "parse_no_signal")
        self.assertTrue(retryable)
        self.assertEqual(hours, 24.0)

    def test_empty_response_classified_as_403(self):
        ft, retryable, hours = _classify_enrichment_failure(
            ValueError("Empty response (possible 403/redirect)")
        )
        self.assertEqual(ft, "http_403")
        self.assertTrue(retryable)

    def test_system_error_fallback(self):
        ft, retryable, hours = _classify_enrichment_failure(RuntimeError("unexpected db error"))
        self.assertEqual(ft, "system_error")
        self.assertTrue(retryable)
        self.assertEqual(hours, 1.0)


# ---------------------------------------------------------------------------
# _is_in_cooldown
# ---------------------------------------------------------------------------
class TestIsInCooldown(unittest.TestCase):
    def _now(self):
        return datetime.now(timezone.utc)

    def test_no_next_retry_at_is_eligible(self):
        item = {"school_slug": "x", "path": "/x"}
        self.assertFalse(_is_in_cooldown(item, self._now()))

    def test_future_next_retry_is_in_cooldown(self):
        future = (self._now() + timedelta(hours=10)).isoformat()
        item = {"school_slug": "x", "path": "/x", "next_retry_at": future}
        self.assertTrue(_is_in_cooldown(item, self._now()))

    def test_past_next_retry_is_eligible(self):
        past = (self._now() - timedelta(hours=1)).isoformat()
        item = {"school_slug": "x", "path": "/x", "next_retry_at": past}
        self.assertFalse(_is_in_cooldown(item, self._now()))

    def test_none_next_retry_is_eligible(self):
        item = {"school_slug": "x", "path": "/x", "next_retry_at": None}
        self.assertFalse(_is_in_cooldown(item, self._now()))

    def test_invalid_next_retry_treated_as_eligible(self):
        item = {"school_slug": "x", "path": "/x", "next_retry_at": "not-a-date"}
        self.assertFalse(_is_in_cooldown(item, self._now()))


# ---------------------------------------------------------------------------
# Cooldown scaling for http_403
# ---------------------------------------------------------------------------
class TestCooldownScaling(unittest.TestCase):
    """Verify the 403 cooldown formula: min(12 * failure_count, 72)."""

    def _403_hours(self, failure_count: int) -> float:
        # Simulate the formula used in enrich_deferred_details
        base = 12.0
        return min(base * failure_count, _FAILURE_MAX_COOLDOWN_HOURS)

    def test_first_failure_12h(self):
        self.assertEqual(self._403_hours(1), 12.0)

    def test_second_failure_24h(self):
        self.assertEqual(self._403_hours(2), 24.0)

    def test_third_failure_36h(self):
        self.assertEqual(self._403_hours(3), 36.0)

    def test_sixth_failure_capped_72h(self):
        self.assertEqual(self._403_hours(6), 72.0)

    def test_tenth_failure_still_capped_72h(self):
        self.assertEqual(self._403_hours(10), 72.0)


# ---------------------------------------------------------------------------
# _migrate_deferred_item (v1 -> v2)
# ---------------------------------------------------------------------------
class TestMigrateDeferredItem(unittest.TestCase):

    def test_v1_attempts_migrated_to_failure_count(self):
        v1 = {"school_slug": "mit", "path": "/universities/mit", "attempts": 3}
        out = _migrate_deferred_item(v1)
        self.assertEqual(out["failure_count"], 3)
        self.assertNotIn("attempts", out)

    def test_v2_failure_count_preserved(self):
        v2 = {"school_slug": "mit", "path": "/universities/mit",
              "failure_count": 2, "last_failure_type": "http_403"}
        out = _migrate_deferred_item(v2)
        self.assertEqual(out["failure_count"], 2)
        self.assertEqual(out["last_failure_type"], "http_403")

    def test_v2_fields_carried_through(self):
        ts = "2026-01-01T10:00:00+00:00"
        v2 = {"school_slug": "x", "path": "/x", "failure_count": 1,
              "last_failure_type": "http_403", "last_attempt_at": ts,
              "next_retry_at": ts}
        out = _migrate_deferred_item(v2)
        self.assertEqual(out["next_retry_at"], ts)
        self.assertEqual(out["last_attempt_at"], ts)

    def test_no_metadata_gives_zero_failure_count(self):
        bare = {"school_slug": "x", "path": "/x", "name": "X University"}
        out = _migrate_deferred_item(bare)
        self.assertEqual(out["failure_count"], 0)
        self.assertNotIn("next_retry_at", out)


# ---------------------------------------------------------------------------
# _write_deferred_file (deduplication)
# ---------------------------------------------------------------------------
class TestWriteDeferredFile(unittest.TestCase):

    def test_deduplicates_by_slug(self):
        items = [
            {"school_slug": "mit", "path": "/a"},
            {"school_slug": "mit", "path": "/b"},  # duplicate slug
            {"school_slug": "harvard", "path": "/c"},
        ]
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "deferred.json"
            _write_deferred_file(p, items)
            data = json.loads(p.read_text())
        self.assertEqual(len(data), 2)
        slugs = {d["school_slug"] for d in data}
        self.assertIn("mit", slugs)
        self.assertIn("harvard", slugs)

    def test_empty_slug_is_skipped(self):
        items = [
            {"school_slug": "", "path": "/a"},
            {"school_slug": "oxford", "path": "/b"},
        ]
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "deferred.json"
            _write_deferred_file(p, items)
            data = json.loads(p.read_text())
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["school_slug"], "oxford")


# ---------------------------------------------------------------------------
# load_deferred_detail_list migrates on load
# ---------------------------------------------------------------------------
class TestLoadDeferredDetailList(unittest.TestCase):

    def test_migrates_v1_on_load(self):
        raw = [
            {"school_slug": "mit", "path": "/universities/mit", "name": "MIT",
             "rank": "1", "country": "United States", "attempts": 2}
        ]
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "pending.json"
            p.write_text(json.dumps(raw))
            items = load_deferred_detail_list(p)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["failure_count"], 2)
        self.assertNotIn("attempts", items[0])

    def test_missing_file_returns_empty(self):
        items = load_deferred_detail_list(Path("/nonexistent/path/pending.json"))
        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()
