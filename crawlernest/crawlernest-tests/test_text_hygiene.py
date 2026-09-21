"""The door a source name comes through, and the two things that got past it.

Both are taken from the warehouse rather than invented:

- ``City St George's,\\xa0University of\\xa0London`` -- THE's 2026 table, whose
  no-break spaces made the name compare unequal to the canonical record it
  differs from by nothing else. It reached analytics.missing_entity_log nine
  times.
- ``University of Tennessee, Knoxville \\x96 Haslam College of Business`` -- a
  Windows-1252 en dash read as ISO-8859-1, so an unprintable C1 control ended up
  in a university's name.

The adapter tests matter as much as the function's: the cleaning is only worth
anything at the point every source passes through, and each of the three
adapters had its own copy of the name extraction.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT / "crawlernest-core"))

from text_hygiene import clean_source_text, has_control_characters  # noqa: E402

from multi_source.adapters.arwu_adapter import ARWUAdapter  # noqa: E402
from multi_source.adapters.the_adapter import THEAdapter  # noqa: E402

NBSP_NAME = "City St George's, University of London"
C1_NAME = "University of Tennessee, Knoxville  Haslam College of Business"


class TestTheTwoNamesThatGotThrough(unittest.TestCase):
    def test_no_break_spaces_become_spaces(self) -> None:
        cleaned = clean_source_text(NBSP_NAME)
        self.assertEqual("City St George's, University of London", cleaned.text)
        self.assertNotIn(" ", cleaned.text)
        self.assertTrue(cleaned.was_changed)
        self.assertTrue(any("no-break space" in c for c in cleaned.changes))

    def test_the_cleaned_name_now_equals_the_canonical_one(self) -> None:
        # The whole point: these two differed by nothing a reader can see, and
        # the resolver compared them unequal.
        canonical = "City St George's, University of London"
        self.assertNotEqual(canonical, NBSP_NAME)
        self.assertEqual(canonical, clean_source_text(NBSP_NAME).text)

    def test_a_c1_control_is_read_back_as_the_punctuation_it_was(self) -> None:
        cleaned = clean_source_text(C1_NAME)
        self.assertEqual(
            "University of Tennessee, Knoxville – Haslam College of Business", cleaned.text
        )
        self.assertFalse(has_control_characters(cleaned.text))
        self.assertTrue(any("U+0096" in c and "cp1252" in c for c in cleaned.changes))

    def test_every_cp1252_punctuation_byte_survives_as_punctuation(self) -> None:
        for control, expected in (
            ("", "‘"), ("", "’"), ("", "“"),
            ("", "”"), ("", "–"), ("", "—"),
        ):
            with self.subTest(control=control):
                self.assertEqual(f"a{expected}b", clean_source_text(f"a{control}b").text)

    def test_an_undefined_control_is_dropped_and_said_so(self) -> None:
        cleaned = clean_source_text("Name  more")
        self.assertEqual("Name more", cleaned.text)
        self.assertTrue(any("dropped undefined control U+0081" in c for c in cleaned.changes))


class TestOrdinaryNamesAreLeftAlone(unittest.TestCase):
    """The cleaning must not be the next source of damage."""

    def test_accents_and_real_punctuation_are_untouched(self) -> None:
        for name in (
            "Universidad Nacional de Tucumán",
            "Universitat Politècnica de Catalunya · BarcelonaTech (UPC)",
            "NLC «Buketov Karaganda National Research University»",
            "«KROK» University",
            "City St George’s, University of London",
            "清華大學",
            "Université Côte d’Azur",
        ):
            with self.subTest(name=name):
                cleaned = clean_source_text(name)
                self.assertEqual(name, cleaned.text)
                self.assertFalse(cleaned.was_changed, f"changed: {cleaned.changes}")

    def test_an_en_dash_that_is_already_an_en_dash_is_not_reported(self) -> None:
        name = "VSB – Technical University of Ostrava"
        self.assertEqual(name, clean_source_text(name).text)
        self.assertEqual((), clean_source_text(name).changes)

    def test_none_and_empty_are_not_errors(self) -> None:
        self.assertEqual("", clean_source_text(None).text)
        self.assertEqual("", clean_source_text("").text)
        self.assertEqual("", clean_source_text("   ").text)

    def test_zero_width_characters_go(self) -> None:
        cleaned = clean_source_text("Univer​sity")
        self.assertEqual("University", cleaned.text)
        self.assertTrue(any("zero-width" in c for c in cleaned.changes))


class TestEveryAdapterUsesTheSameDoor(unittest.TestCase):
    """One source at a time, through the real adapter, with the real row shape."""

    def test_the_adapter_cleans_the_name_and_records_it(self) -> None:
        rows = [{"id": "733856", "name": NBSP_NAME, "rank": 301, "country": "United Kingdom"}]
        record = THEAdapter(default_year=2026).adapt(rows)[0]

        self.assertEqual("City St George's, University of London", record.university_name)
        self.assertEqual("United Kingdom", record.country_hint)
        self.assertIn("name_hygiene", record.metadata)
        self.assertTrue(record.metadata["name_hygiene"])

    def test_arwu_adapter_cleans_the_name(self) -> None:
        rows = [{"id": "arwu:somewhere", "name": C1_NAME, "rank": 401}]
        record = ARWUAdapter(default_year=2026).adapt(rows)[0]

        self.assertNotIn("", record.university_name)
        self.assertIn("–", record.university_name)
        self.assertTrue(any("U+0096" in c for c in record.metadata["name_hygiene"]))

    def test_a_clean_row_carries_no_audit_line(self) -> None:
        # Conditional, like every other disclosure here: a row with nothing
        # wrong must not claim something was corrected.
        rows = [{"id": "931", "name": "Tehran University of Medical Sciences", "rank": 501}]
        record = THEAdapter(default_year=2026).adapt(rows)[0]
        self.assertNotIn("name_hygiene", record.metadata)

    def test_the_entity_id_is_not_cleaned(self) -> None:
        # An id is a key: two runs have to agree on it, so it is left exactly as
        # the source sent it even when the name beside it was corrected.
        raw_id = "arwu:place name"
        rows = [{"id": raw_id, "name": NBSP_NAME, "rank": 10}]
        record = ARWUAdapter(default_year=2026).adapt(rows)[0]
        self.assertEqual(raw_id, record.source_entity_id)
        self.assertNotIn(" ", record.university_name)


if __name__ == "__main__":
    unittest.main()
