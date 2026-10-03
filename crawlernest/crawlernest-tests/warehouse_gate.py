"""Decide what a warehouse drift check does when the warehouse is too small to compare against.

The three checks that hold a committed file against the live warehouse (the cross-edition export, the QS<->THE
pairing and the alias files) can only say anything on a database that holds the data. On a freshly bootstrapped
one -- every CI run -- they have nothing to compare, and skipping is correct there: treating an empty warehouse as a
mismatch would make the check loudest exactly where it knows least.

The same skip is wrong where the check is the point. Run on a developer's machine as the gate before a push, a skip
reads as a pass: a mistyped database name, a restored scratch copy, a stopped server that fell back to another
database, all exit 0 having compared nothing. ``CRAWLERNEST_REQUIRE_WAREHOUSE=1`` turns the skip into a failure, and
scripts/check_warehouse_drift.sh sets it.
"""
from __future__ import annotations

import os
import unittest

ENV = "CRAWLERNEST_REQUIRE_WAREHOUSE"


def required() -> bool:
    return os.getenv(ENV) == "1"


def too_small(reason: str) -> None:
    """Raise: a skip normally, a failure when the comparison is required. Never returns."""
    if required():
        raise AssertionError(
            f"{reason}. {ENV}=1 is set, so this is a failure rather than a skip: nothing was compared, "
            "and a drift check that compared nothing has not shown there is no drift."
        )
    raise unittest.SkipTest(reason)
