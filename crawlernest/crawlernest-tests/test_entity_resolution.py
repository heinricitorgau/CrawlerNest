"""Tests for entity resolution normalizer and resolver fixes.

Covers:
- Fix R1: ABBREVIATION_MAP expansion (sci, natl, coll, engr, intl)
- Fix R2: HTML entity decoding (&amp; -> &)
- Fix R3: Country-blocking non-fatal fallback
"""
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent

sys.path.insert(0, str(PACKAGE_ROOT / "crawlernest-core"))

from entity_resolution.normalizer import normalize_university_name, tokenize_for_blocking
from entity_resolution.resolver import EntityResolver, ResolverThresholds
from entity_resolution.types import CanonicalProfile, EntityRecord


class TestNormalizerR1(unittest.TestCase):
    """Fix R1: expanded ABBREVIATION_MAP."""

    def test_sci_expands_to_science(self):
        result = normalize_university_name("National Univ of Sci and Tech")
        self.assertIn("science", result)
        self.assertNotIn("sci", result.split())

    def test_natl_expands_to_national(self):
        result = normalize_university_name("Natl Taiwan University")
        self.assertIn("national", result)
        self.assertNotIn("natl", result.split())

    def test_coll_expands_to_college(self):
        result = normalize_university_name("Royal Coll of Music")
        self.assertIn("college", result)

    def test_engr_expands_to_engineering(self):
        result = normalize_university_name("School of Engr Sciences")
        self.assertIn("engineering", result)

    def test_intl_expands_to_international(self):
        result = normalize_university_name("Intl University of Tokyo")
        self.assertIn("international", result)


class TestNormalizerR2(unittest.TestCase):
    """Fix R2: HTML entity decoding."""

    def test_amp_entity_decoded(self):
        result = normalize_university_name("Science &amp; Technology University")
        # &amp; -> & -> " and " -> "and" (stopword removed)
        self.assertNotIn("amp", result.split())
        self.assertIn("science", result)
        self.assertIn("technology", result)

    def test_quoted_entity_decoded(self):
        result = normalize_university_name("Arts &amp; Crafts College")
        tokens = result.split()
        self.assertNotIn("amp", tokens)

    def test_plain_ampersand_still_works(self):
        result = normalize_university_name("Science & Technology University")
        # & -> " and " -> stopword -> removed
        self.assertIn("science", result)
        self.assertIn("technology", result)
        self.assertNotIn("&", result)


class TestResolverR3CountryFallback(unittest.TestCase):
    """Fix R3: country-blocking falls back when intersection is empty."""

    def _make_resolver(self) -> EntityResolver:
        profiles = [
            CanonicalProfile(
                canonical_university_id=1,
                display_name="ETH Zurich",
                country_hint="switzerland",  # stored as full name
                aliases=("Swiss Federal Institute of Technology",),
            ),
        ]
        return EntityResolver(profiles, thresholds=ResolverThresholds(fuzzy_accept=0.80, fuzzy_review=0.75))

    def test_country_mismatch_does_not_block_match(self):
        """When incoming country_hint='CH' doesn't match canonical 'switzerland',
        R3 ensures the token candidates are still considered via fallback."""
        resolver = self._make_resolver()
        record = EntityRecord(
            source_name="QS",
            source_entity_id="eth-zurich",
            university_name="ETH Zurich",
            country_hint="ch",  # two-letter code — won't match "switzerland" in index
        )
        result = resolver.resolve_one(record)
        # Should still resolve (exact match in alias index) regardless of country hint
        self.assertIsNotNone(result.canonical_university_id)

    def test_no_country_hint_still_resolves(self):
        resolver = self._make_resolver()
        record = EntityRecord(
            source_name="QS",
            source_entity_id="eth-zurich",
            university_name="ETH Zurich",
            country_hint=None,
        )
        result = resolver.resolve_one(record)
        self.assertIsNotNone(result.canonical_university_id)
        self.assertEqual(result.canonical_university_id, 1)

    def test_wrong_country_does_not_force_wrong_match(self):
        """Even with the fallback, the fuzzy threshold still protects precision.
        A completely different name should not match."""
        resolver = self._make_resolver()
        record = EntityRecord(
            source_name="QS",
            source_entity_id="unknown",
            university_name="University of Nowhere",
            country_hint="ch",
        )
        result = resolver.resolve_one(record)
        # Should be unresolved because fuzzy score will be too low
        self.assertIsNone(result.canonical_university_id)


if __name__ == "__main__":
    unittest.main()
