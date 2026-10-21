"""QS's country spellings from the crawl of 2026-10-21, read as the countries the warehouse already holds.

That crawl printed "China" for "China (mainland)", "Hong Kong SAR, China" and "Macao SAR, China" for the two
SARs, and "N/A" for Northern Cyprus. Read as written, the first three split one country in two from that edition
on, and the fourth becomes a country called "N A" (ten active records already carry it, from 2026-09-04). Three
places read a country, and each is pinned here: the crawler's normalisation, the resolver's country comparison,
and the Wikipedia loader's.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent
for _p in (str(PACKAGE_ROOT / "crawlernest-core"), str(PACKAGE_ROOT / "crawlernest-jobs"), str(PACKAGE_ROOT.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import wikipedia_profile_loader as W  # noqa: E402
from crawlernest.pipeline.utils.normalization import normalize_country  # noqa: E402
from entity_resolution.resolver import EntityResolver  # noqa: E402
from entity_resolution.types import CanonicalProfile, EntityRecord  # noqa: E402


class TestCrawlerNormalisation(unittest.TestCase):
    def test_the_new_spellings_are_the_countries_the_warehouse_holds(self) -> None:
        for printed, held in (
            ("China", "China (mainland)"),
            ("Hong Kong SAR, China", "Hong Kong Sar"),
            ("Macao SAR, China", "Macau Sar"),
            ("Macao SAR", "Macau Sar"),
        ):
            with self.subTest(printed=printed):
                self.assertEqual(held, normalize_country(printed))

    def test_the_earlier_spellings_are_unchanged(self) -> None:
        for printed, held in (
            ("China (mainland)", "China (mainland)"),
            ("Hong Kong SAR", "Hong Kong Sar"),
            ("Macau SAR", "Macau Sar"),
            ("Northern Cyprus", "Northern Cyprus"),
            ("Taiwan", "Taiwan"),
        ):
            with self.subTest(printed=printed):
                self.assertEqual(held, normalize_country(printed))

    def test_not_available_is_no_country(self) -> None:
        for printed in ("N/A", "n/a", "N A"):
            with self.subTest(printed=printed):
                self.assertEqual("", normalize_country(printed))


class TestResolverCountries(unittest.TestCase):
    def _resolver(self) -> EntityResolver:
        return EntityResolver([
            CanonicalProfile(1, "University of Hong Kong", "hong kong sar", ()),
            CanonicalProfile(2, "University of Macau", "macau sar", ()),
        ])

    def test_a_sar_written_with_china_is_the_same_country(self) -> None:
        resolver = self._resolver()
        for name, country in (
            ("University of Hong Kong", "Hong Kong SAR, China"),
            ("University of Hong Kong", "Hong Kong Sar China"),
            ("University of Macau", "Macao SAR, China"),
            ("University of Macau", "Macao Sar China"),
        ):
            with self.subTest(country=country):
                result = resolver.resolve_one(EntityRecord("QS", "x", name, country))
                self.assertFalse(result.metadata["country_mismatch"])

    def test_another_country_still_is_a_mismatch(self) -> None:
        result = self._resolver().resolve_one(EntityRecord("QS", "x", "University of Hong Kong", "Singapore"))
        self.assertTrue(result.metadata["country_mismatch"])


class TestWikipediaCountries(unittest.TestCase):
    def _entity(self, country: str) -> W.Entity:
        return W.Entity("Q1", "X", [], [country], ["university"], False, "X")

    def test_a_sar_written_with_china_agrees_with_wikidata(self) -> None:
        for ours, theirs in (
            ("Hong Kong Sar China", "Hong Kong"),
            ("Hong Kong Sar China", "People's Republic of China"),
            ("Macao Sar China", "Macau"),
            ("Macao Sar", "Macau"),
        ):
            with self.subTest(ours=ours, theirs=theirs):
                self.assertTrue(W.country_agrees(self._entity(theirs), ours))

    def test_no_country_is_not_compared(self) -> None:
        self.assertIsNone(W.country_agrees(self._entity("Cyprus"), "N A"))
        self.assertIsNone(W.country_agrees(self._entity("Cyprus"), ""))


if __name__ == "__main__":
    unittest.main()
