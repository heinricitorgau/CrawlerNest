"""Tests for the identity an admission row is reviewed under.

The same reduction is written twice -- here in Python, and as a backfill in
crawlernest-schema/admission_postgresql.sql. These cases pin the Python side so
a drift between the two shows up as a failure rather than as review decisions
that quietly stop applying.
"""
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent.parent

# crawlernest_admission_crawler lives at the repository root, which run_tests.py
# does not put on sys.path -- it adds the crawlernest/crawlernest-* module dirs.
sys.path.insert(0, str(REPO_ROOT))

from crawlernest_admission_crawler.source_identity import (  # noqa: E402
    admission_source_entity_id,
)


class TestSchemeAndCase(unittest.TestCase):
    def test_https_scheme_is_dropped(self):
        self.assertEqual(
            "www.ox.ac.uk/admissions/graduate",
            admission_source_entity_id("https://www.ox.ac.uk/admissions/graduate"),
        )

    def test_http_scheme_is_dropped(self):
        self.assertEqual(
            "www.ox.ac.uk/admissions/graduate",
            admission_source_entity_id("http://www.ox.ac.uk/admissions/graduate"),
        )

    def test_host_and_path_are_lowercased(self):
        self.assertEqual(
            "www.ox.ac.uk/admissions/graduate",
            admission_source_entity_id("HTTPS://WWW.OX.AC.UK/Admissions/Graduate"),
        )

    def test_surrounding_whitespace_is_ignored(self):
        self.assertEqual(
            "www.ox.ac.uk/admissions",
            admission_source_entity_id("  https://www.ox.ac.uk/admissions  "),
        )


class TestTrailingSlash(unittest.TestCase):
    def test_trailing_slash_is_stripped(self):
        self.assertEqual(
            "nusgs.nus.edu.sg/admissions/english-language",
            admission_source_entity_id("https://nusgs.nus.edu.sg/admissions/english-language/"),
        )

    def test_a_url_with_and_without_it_are_the_same_entity(self):
        self.assertEqual(
            admission_source_entity_id("https://nusgs.nus.edu.sg/admissions/"),
            admission_source_entity_id("https://nusgs.nus.edu.sg/admissions"),
        )

    def test_bare_host_reduces_to_the_host(self):
        self.assertEqual("www.mit.edu", admission_source_entity_id("https://www.mit.edu/"))


class TestQueryAndFragment(unittest.TestCase):
    def test_query_string_is_dropped(self):
        self.assertEqual(
            "study.unimelb.edu.au/admissions",
            admission_source_entity_id("https://study.unimelb.edu.au/admissions?utm_source=qs"),
        )

    def test_fragment_is_dropped(self):
        self.assertEqual(
            "study.unimelb.edu.au/admissions",
            admission_source_entity_id("https://study.unimelb.edu.au/admissions#ielts"),
        )

    def test_slash_before_a_query_is_still_stripped(self):
        self.assertEqual(
            "study.unimelb.edu.au/admissions",
            admission_source_entity_id("https://study.unimelb.edu.au/admissions/?page=2"),
        )


class TestIdentityIsNameFree(unittest.TestCase):
    def test_two_pages_of_one_university_are_distinct_entities(self):
        taught = admission_source_entity_id(
            "https://www.ucl.ac.uk/prospective-students/graduate/taught-degrees/english-language-requirements"
        )
        research = admission_source_entity_id(
            "https://www.ucl.ac.uk/prospective-students/graduate/research-degrees/english-language-requirements"
        )
        self.assertNotEqual(taught, research)

    def test_long_urls_are_not_truncated(self):
        # _url_to_slug in the crawler caps at 80 characters because it is
        # naming a file. Truncating here would collide two pages that share a
        # prefix, merging their review decisions.
        self.assertEqual(
            "example.edu/" + "a" * 200,
            admission_source_entity_id("https://example.edu/" + "a" * 200),
        )

    def test_two_pages_sharing_a_long_prefix_stay_distinct(self):
        prefix = "https://example.edu/" + "a" * 100
        self.assertNotEqual(
            admission_source_entity_id(prefix + "/taught"),
            admission_source_entity_id(prefix + "/research"),
        )


class TestEmptyInput(unittest.TestCase):
    def test_empty_string_reduces_to_empty(self):
        self.assertEqual("", admission_source_entity_id(""))

    def test_none_reduces_to_empty(self):
        self.assertEqual("", admission_source_entity_id(None))


if __name__ == "__main__":
    unittest.main()
