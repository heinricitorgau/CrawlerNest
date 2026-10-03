"""warehouse_gate: a skip stays a skip by default and becomes a failure only when the comparison is required."""
from __future__ import annotations

import os
import unittest
from unittest import mock

import warehouse_gate as gate


class TestGate(unittest.TestCase):
    def test_by_default_a_small_warehouse_is_a_skip(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(gate.ENV, None)
            with self.assertRaises(unittest.SkipTest):
                gate.too_small("only 0 ranking records")

    def test_when_required_it_is_a_failure_that_says_why(self):
        with mock.patch.dict(os.environ, {gate.ENV: "1"}):
            with self.assertRaises(AssertionError) as caught:
                gate.too_small("only 0 ranking records")
        self.assertIn("only 0 ranking records", str(caught.exception))
        self.assertIn(gate.ENV, str(caught.exception))

    def test_only_the_exact_value_one_requires_it(self):
        for value in ("", "0", "true", "yes"):
            with self.subTest(value=value), mock.patch.dict(os.environ, {gate.ENV: value}):
                with self.assertRaises(unittest.SkipTest):
                    gate.too_small("small")

    def test_a_skip_is_not_an_assertion_failure_and_the_reverse(self):
        self.assertFalse(issubclass(unittest.SkipTest, AssertionError))


class TestTheThreeDriftChecksUseIt(unittest.TestCase):
    """The gate protects nothing if a check still calls skipTest directly for the same condition."""

    FILES = ("test_cross_edition_export_matches_warehouse.py", "test_alias_files.py", "test_pairing_matches_warehouse.py")

    def test_each_check_asks_the_gate_when_the_warehouse_is_too_small(self):
        from pathlib import Path

        here = Path(__file__).resolve().parent
        for name in self.FILES:
            source = (here / name).read_text(encoding="utf-8")
            self.assertIn("warehouse_gate", source, f"{name} does not use warehouse_gate")
            for needle in ("skipTest(", "raise unittest.SkipTest("):
                self.assertNotIn(needle, source, f"{name} still skips on its own with {needle}")


if __name__ == "__main__":
    unittest.main()
