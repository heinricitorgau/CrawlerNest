"""The two ways QS's regional rankings failed to be fetched, measured 2026-09-22 and fixed here.

* The ranking endpoint was asked with only nid/page/items_per_page/tab. For the world ranking's id the server
  tolerates that; for a regional ranking's id it hangs instead of answering (45 s timeout with the short set, HTTP 200
  with 1,534 records in under a second with the full set the page itself sends, same id, same session).
* A prefetched payload taken from the ranking *page* was accepted whatever it held. QS's regional pages embed a single
  featured row, so ``regional:asia`` and ``regional:caribbean`` prefetched exactly one node while the endpoint held 1,534
  and 28, and the crawl took the fragment as the whole edition. The ingest's shrink guard was all that stood between that
  and an edition pruned to one university.
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT / "crawlernest-core"))
sys.path.insert(0, str(PACKAGE_ROOT / "crawlernest-extractors"))
sys.path.insert(0, str(PACKAGE_ROOT / "crawlernest-jobs"))

from config import Config  # noqa: E402
from fetcher import MIN_PREFETCH_ROWS, AsyncUniversityFetcher, UniversityFetcher, _prefetch_is_a_whole_page  # noqa: E402

FILTER_KEYS = (
    "region", "countries", "cities", "search", "star", "sort_by", "order_by", "program_type", "scholarship", "fee",
    "english_score", "academic_score", "mix_student", "loggedincache",
)


def nodes(n: int) -> dict:
    return {"score_nodes": [{"uniname": f"University {i}"} for i in range(n)]}


class TestTheEndpointIsAskedLikeThePageAsksIt(unittest.TestCase):
    def test_every_filter_the_page_sends_is_present_and_empty(self):
        params = Config().get_api_params()
        for key in FILTER_KEYS:
            self.assertIn(key, params, f"{key} is missing: a regional id hangs without it")
            self.assertEqual(params[key], "", key)

    def test_the_four_original_parameters_are_unchanged(self):
        config = Config()
        config.ranking_id = "3990755"
        config.page = 2
        config.items_per_page = 30
        params = config.get_api_params()
        self.assertEqual(
            {k: params[k] for k in ("nid", "page", "items_per_page", "tab")},
            {"nid": "3990755", "page": "2", "items_per_page": "30", "tab": "indicators"},
        )

    def test_a_requested_country_still_overrides_the_empty_default(self):
        config = Config()
        config.country = ["US", "CA"]
        self.assertEqual(config.get_api_params()["countries"], "US,CA")
        config.country = "TW"
        self.assertEqual(config.get_api_params()["countries"], "TW")

    def test_the_filter_names_are_a_class_constant_not_per_instance_state(self):
        self.assertEqual(tuple(Config.QS_FILTER_PARAMS), FILTER_KEYS)
        self.assertNotIn("QS_FILTER_PARAMS", Config().__dict__)

    def test_the_endpoint_request_carries_them(self):
        config = Config()
        config.ranking_id = "3990755"
        config._session_warmed = True
        fetcher = UniversityFetcher(config)
        response = MagicMock(status_code=200, headers={}, text="{}")
        response.json.return_value = nodes(12)
        with patch.object(fetcher.session, "get", return_value=response) as get:
            fetcher.fetch_rankings()
        sent = get.call_args.kwargs["params"]
        # "countries" is the one the request drops on purpose when no country was asked for: _fetch_rankings_impl pops it
        # (country_v is None). That is older than this change. Whether the endpoint still answers a regional id promptly
        # without it was not measured here; the 2026-09-22 measurement used the full set from get_api_params.
        for key in FILTER_KEYS:
            if key != "countries":
                self.assertIn(key, sent, f"{key} is missing from the request actually sent")
        self.assertNotIn("countries", sent)


class TestAPrefetchedFragmentIsNotTheRanking(unittest.TestCase):
    def test_the_boundary(self):
        self.assertEqual(MIN_PREFETCH_ROWS, 10)
        self.assertFalse(_prefetch_is_a_whole_page(nodes(MIN_PREFETCH_ROWS - 1)))
        self.assertTrue(_prefetch_is_a_whole_page(nodes(MIN_PREFETCH_ROWS)))
        self.assertTrue(_prefetch_is_a_whole_page(nodes(1534)))

    def test_the_one_row_fragment_the_regional_pages_embed_is_not_a_page(self):
        self.assertFalse(_prefetch_is_a_whole_page(nodes(1)))

    def test_nothing_usable_is_not_a_page(self):
        for payload in ({}, {"score_nodes": None}, {"score_nodes": "x"}, {"score_nodes": {}}, None, [], "x", 0):
            with self.subTest(payload=payload):
                self.assertFalse(_prefetch_is_a_whole_page(payload))

    def _fetcher(self, payload):
        config = Config()
        config.ranking_id = "3990755"
        config._session_warmed = True
        config._prefetched_payload = payload
        return UniversityFetcher(config)

    def test_a_fragment_does_not_short_circuit_the_endpoint(self):
        fetcher = self._fetcher(nodes(1))
        response = MagicMock(status_code=200, headers={}, text="{}")
        response.json.return_value = nodes(1534)
        with patch.object(fetcher.session, "get", return_value=response) as get:
            data = fetcher.fetch_rankings()
        self.assertGreater(get.call_count, 0, "the endpoint was never asked")
        self.assertEqual(len(data["score_nodes"]), 1534)
        self.assertFalse(fetcher.config._used_prefetched_payload)

    def test_a_whole_page_still_saves_the_round_trip(self):
        payload = nodes(30)
        fetcher = self._fetcher(payload)
        with patch.object(fetcher.session, "get") as get:
            data = fetcher.fetch_rankings()
        self.assertIs(data, payload)
        self.assertEqual(get.call_count, 0)
        self.assertTrue(fetcher.config._used_prefetched_payload)

    def test_a_fragment_does_not_stand_in_for_a_ranking_id_that_could_not_be_resolved(self):
        # ranking_id "0" means "the page already has the table"; a fragment is not the table.
        config = Config()
        config.ranking_id = ""
        config.ranking_year = 2026
        config.universe_type = "region"
        config.universe_key = "asia"
        config.ranking_page_url = "https://www.topuniversities.com/asia-university-rankings"
        config._prefetched_payload = nodes(1)
        fetcher = UniversityFetcher(config)
        page = MagicMock(status_code=200, headers={}, text="<html>no nid here</html>")
        with patch.object(fetcher.session, "get", return_value=page):
            try:
                fetcher._ensure_ranking_id()
            except ValueError:
                pass  # unresolved is the honest outcome; what matters is that it did not become "0"
        self.assertNotEqual(str(config.ranking_id), "0")


class RequestWasSent(BaseException):
    """Raised by the stand-in for the network call. A BaseException, so no ``except Exception`` in the fetcher hides it."""


class TestTheAsyncFetcherAppliesTheSameRule(unittest.TestCase):
    """The async crawler has its own copy of both call sites, and no other test reaches it."""

    def _fetcher(self, payload, *, ranking_id="3990755"):
        config = Config()
        config.ranking_id = ranking_id
        config._session_warmed = True
        config._prefetched_payload = payload
        fetcher = AsyncUniversityFetcher(config)
        fetcher.session = MagicMock()  # the code asserts a session exists; nothing is sent through it
        return fetcher

    def test_a_fragment_does_not_short_circuit_the_endpoint(self):
        fetcher = self._fetcher(nodes(1))
        with patch.object(fetcher, "_warm_session_for_endpoint", AsyncMock()), patch.object(
            fetcher, "_async_session_get_transient_retry", AsyncMock(side_effect=RequestWasSent)
        ):
            with self.assertRaises(RequestWasSent):
                asyncio.run(fetcher._fetch_rankings_impl(allow_cache_refresh=False))
        self.assertFalse(fetcher.config._used_prefetched_payload)

    def test_a_whole_page_still_saves_the_round_trip(self):
        payload = nodes(30)
        fetcher = self._fetcher(payload)
        send = AsyncMock(side_effect=RequestWasSent)
        with patch.object(fetcher, "_warm_session_for_endpoint", AsyncMock()), patch.object(
            fetcher, "_async_session_get_transient_retry", send
        ):
            data = asyncio.run(fetcher._fetch_rankings_impl(allow_cache_refresh=False))
        self.assertIs(data, payload)
        send.assert_not_called()
        self.assertTrue(fetcher.config._used_prefetched_payload)

    def _unresolvable(self, payload):
        fetcher = self._fetcher(payload, ranking_id="")
        fetcher.config.ranking_year = 2026
        fetcher.config.universe_type = "region"
        fetcher.config.universe_key = "asia"
        fetcher.config.ranking_page_url = "https://www.topuniversities.com/asia-university-rankings"
        return fetcher

    def test_a_fragment_does_not_stand_in_for_a_ranking_id_that_could_not_be_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            fetcher = self._unresolvable(nodes(1))
            fetcher.config.resolution_cache_path = str(Path(tmp) / "resolution_cache.json")
            with patch.object(fetcher, "_async_session_get_transient_retry", AsyncMock(side_effect=RuntimeError("no page"))):
                try:
                    resolved = asyncio.run(fetcher._ensure_ranking_id())
                except ValueError:
                    resolved = None  # unresolved is the honest outcome
        self.assertNotEqual(resolved, "0")
        self.assertNotEqual(str(fetcher.config.ranking_id), "0")

    def test_a_whole_page_is_still_taken_when_the_id_cannot_be_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            fetcher = self._unresolvable(nodes(30))
            fetcher.config.resolution_cache_path = str(Path(tmp) / "resolution_cache.json")
            with patch.object(fetcher, "_async_session_get_transient_retry", AsyncMock(side_effect=RuntimeError("no page"))):
                resolved = asyncio.run(fetcher._ensure_ranking_id())
        self.assertEqual(resolved, "0")


if __name__ == "__main__":
    unittest.main()
