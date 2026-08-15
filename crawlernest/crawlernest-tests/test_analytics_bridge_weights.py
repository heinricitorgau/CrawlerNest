"""Source weights: one definition per path, and they must agree.

The weights lived in three places before this: ``default_aggregation_config()``
for the multi-source path, ``analytics_bridge.WEIGHTS`` for the run metadata, and
a third copy written as literals inside the aggregation SQL. Nothing compared
them. The SQL was the only one that decided anything, so editing either Python
copy would have changed what a run *claimed* to weight without changing what it
weighted -- a report that agrees with itself and not with the warehouse.

The SQL copy is gone; it binds ``WEIGHTS`` as parameters. These tests hold the
remaining two together, and check the properties the aggregation math relies on.
"""

from __future__ import annotations

import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CORE = os.path.join(REPO_ROOT, "crawlernest", "crawlernest-core")

# Order matters: models.py exists at both the repo root and in crawlernest-core,
# and the multi-source adapters import the core one. Core goes in front; the repo
# root is appended so `crawlernest.db.*` resolves without shadowing it.
if CORE not in sys.path:
    sys.path.insert(0, CORE)
if REPO_ROOT not in sys.path:
    sys.path.append(REPO_ROOT)

from crawlernest.db.analytics_bridge import (  # noqa: E402
    WEIGHT_ORDER,
    WEIGHTS,
    _weight_triple,
)
from ranking_aggregation import default_aggregation_config  # noqa: E402


class TestWeightDefinitionsAgree(unittest.TestCase):
    def test_the_two_paths_configure_the_same_weights(self):
        self.assertEqual(
            WEIGHTS,
            default_aggregation_config().source_weights,
            "the legacy bridge and the multi-source path would aggregate differently",
        )

    def test_the_sql_parameter_triple_follows_the_declared_order(self):
        """A reordering here would silently give THE's weight to QS."""
        self.assertEqual(WEIGHT_ORDER, ("QS", "THE", "ARWU"))
        self.assertEqual(_weight_triple(), tuple(WEIGHTS[s] for s in WEIGHT_ORDER))

    def test_every_configured_source_has_a_weight(self):
        self.assertEqual(set(WEIGHT_ORDER), set(WEIGHTS))


class TestWeightsSupportTheAggregationMath(unittest.TestCase):
    def test_weights_sum_to_one(self):
        """coverage_ratio is a fraction of the configured total, so it needs this.

        Without it a fully covered row reports a coverage ratio above or below
        1.0, and the caveats built on that number stop meaning what they say.
        """
        self.assertAlmostEqual(sum(WEIGHTS.values()), 1.0, places=9)

    def test_no_weight_is_negative(self):
        for source, weight in WEIGHTS.items():
            with self.subTest(source=source):
                self.assertGreaterEqual(weight, 0.0)

    def test_qs_carries_weight(self):
        """QS is the only ingested source; at zero weight every row drops out.

        The aggregation SQL keeps rows only ``WHERE available_weight > 0``, so a
        zero here empties analytics.aggregated_rankings rather than failing.
        """
        self.assertGreater(WEIGHTS["QS"], 0.0)


if __name__ == "__main__":
    unittest.main()
