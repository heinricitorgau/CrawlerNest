"""Universes the source has stopped serving, and the date their data stands at.

QS's standalone regional rankings -- ``regional:*`` -- were last ingested on
2026-09-04. On 2026-09-22 a re-crawl established that no path this crawler has
still returns them: the REST endpoint 404s, the ranking page embeds no
score_nodes, and ``/rankings/endpoint`` answers for the world ranking's id
(1,000 rows) but times out for a regional one. A crawl now parses a single row
off the rendered page, and the ingest's shrink guard refuses that batch rather
than pruning 1,533 rows down to 1.

That last part is the behaviour worth protecting, and it already has tests. What
did not exist is a record of *why* a re-crawl produces nothing, in a form the
next person meets rather than has to rediscover -- which is what these assert.

Nothing serves these rows, so this is deliberately not a caveat: the analytics
surfaces filter to ``universe_type = 'global'``, and the one parameterised read
takes ``region`` (the world slice), never ``regional``. A disclosure about data
no reader can reach is the kind that teaches people to skip the array.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT / "crawlernest-jobs"))
sys.path.insert(0, str(PACKAGE_ROOT / "crawlernest-core"))

import qs_universe_registry as reg  # noqa: E402

FROZEN_DATE = "2026-09-04"


class TestTheStandaloneRegionalFamilyIsMarkedFrozen(unittest.TestCase):
    def test_every_standalone_regional_universe_carries_the_date(self) -> None:
        for key, spec in sorted(reg.QS_REGIONAL_SPECS.items()):
            with self.subTest(universe=spec.ranking_type):
                self.assertTrue(spec.is_frozen, f"{spec.ranking_type} lost its frozen marker")
                self.assertEqual(FROZEN_DATE, spec.data_frozen_at)
                self.assertTrue(spec.frozen_reason)

    def test_the_reason_names_what_was_measured(self) -> None:
        # Not "QS changed something": the three paths that were tried, so the
        # next person can re-test them rather than repeat the search.
        reason = reg.REGIONAL_FROZEN_REASON
        for evidence in ("404", "score_nodes", "/rankings/endpoint", "shrink guard"):
            with self.subTest(evidence=evidence):
                self.assertIn(evidence, reason)

    def test_the_world_slice_family_is_not_marked(self) -> None:
        # region:* rides the world ranking's id and still crawls -- 562 rows for
        # asia on 2026-09-22. Marking it would be false.
        for spec in reg.iter_all_qs_universes():
            if spec.ranking_scope == reg.RANKING_SCOPE_WORLD_SLICE:
                with self.subTest(universe=spec.ranking_type):
                    self.assertFalse(spec.is_frozen)
                    self.assertIsNone(spec.data_frozen_at)

    def test_no_other_family_is_marked_by_accident(self) -> None:
        frozen = {s.ranking_type for s in reg.iter_all_qs_universes() if s.is_frozen}
        expected = {s.ranking_type for s in reg.QS_REGIONAL_SPECS.values()}
        self.assertEqual(expected, frozen)

    def test_a_frozen_universe_is_still_a_real_universe(self) -> None:
        # Frozen describes the source, not the record: these keep their page,
        # their scope and their place in the registry, because the warehouse
        # still holds their rows and a future fix should find them here.
        for spec in reg.QS_REGIONAL_SPECS.values():
            with self.subTest(universe=spec.ranking_type):
                self.assertFalse(spec.is_world_slice)
                self.assertTrue(spec.ranking_page_url)
                self.assertTrue(spec.ranking_type.startswith("regional:"))


if __name__ == "__main__":
    unittest.main()
