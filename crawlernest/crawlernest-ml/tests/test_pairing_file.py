"""The committed QS<->THE pairing must describe universities that exist.

``cross_source`` reads this file instead of re-deriving the join from names, so
the disagreement model trains on whatever it says. It is exported from the
warehouse by hand, which means it can go stale in two different ways:

- it can stop describing the snapshot the model trains on -- exported from a
  warehouse built on a different edition, its QS names would mostly miss and the
  training set would shrink without an error. That is what these tests catch,
  and they need no database so they run on every push;
- it can disagree with the warehouse it was exported from, which needs a
  database with THE data and is covered by
  ``crawlernest-tests/test_pairing_matches_warehouse.py``.

Neither check synchronises anything. They exist so a divergence is loud rather
than silently trained on.
"""

from __future__ import annotations

import pytest

from ranking_ml.features.build_features import load_snapshot
from ranking_ml.features.cross_source import (
    DEFAULT_PAIRING,
    build_cross_source_frame,
    load_pairing,
    load_the_snapshot,
)


@pytest.fixture(scope="module")
def pairing():
    if not DEFAULT_PAIRING.is_file():
        pytest.skip(f"no pairing file at {DEFAULT_PAIRING}")
    return load_pairing()


def test_the_pairing_file_is_present_and_not_empty(pairing):
    """A missing file is legal -- the name join still works -- but a silent
    truncation to a handful of rows is not something to discover from a metric."""
    assert len(pairing) > 500, (
        f"the pairing file holds {len(pairing)} rows; the warehouse export was 1,638. "
        "A short file would quietly shrink the training set."
    )


#: How many of the snapshot's universities the pairing has to place. The export
#: currently reaches 1,109 of 1,504. A file exported against a different QS
#: edition would land near zero here, which is the failure this guards.
MIN_SNAPSHOT_COVERAGE = 1000


def test_the_pairing_covers_the_qs_snapshot(pairing):
    """The pairing has to describe the snapshot the model trains on.

    This used to assert the stricter thing -- that *every* pairing entry names a
    snapshot university -- on the reasoning that anything else meant the file had
    been exported from a warehouse built on a different snapshot. That reasoning
    held while the canonical dimension was the world ranking and nothing else.
    It stopped holding when canonical_university was seeded from the unresolved
    log: it now covers QS's regional, subject and sustainability tables too, so
    THE legitimately matches canonical universities that the world snapshot has
    never contained, and 534 such entries are a wider dimension rather than a
    stale file.

    Coverage is the half of that assertion which still describes a real failure,
    and it describes it in the direction that actually costs something: an
    edition mismatch collapses this number, while a wider canonical set leaves
    it alone.
    """
    names = {str(record.get("name")) for record in load_snapshot()}
    covered = len(set(pairing) & names)
    assert covered >= MIN_SNAPSHOT_COVERAGE, (
        f"the pairing places only {covered} of the snapshot's {len(names)} universities, "
        f"below the floor of {MIN_SNAPSHOT_COVERAGE}. Re-export it with "
        "crawlernest/scripts/export_qs_the_pairing.py; if the export itself is this "
        "small, the warehouse and the snapshot are describing different editions."
    )


def test_every_the_name_exists_in_the_the_snapshot(pairing):
    names = {str(record.get("name")) for record in load_the_snapshot()}
    missing = sorted(set(pairing.values()) - names)
    assert not missing, (
        f"{len(missing)} pairing entries name a THE university the snapshot does not "
        f"contain, e.g. {missing[:5]}."
    )


def test_the_pairing_is_one_to_one(pairing):
    """Two QS universities pointing at one THE entity would duplicate its row
    into the training set under two labels."""
    seen: dict[str, str] = {}
    collisions = []
    for qs_name, the_name in pairing.items():
        if the_name in seen:
            collisions.append((the_name, seen[the_name], qs_name))
        seen[the_name] = qs_name
    assert not collisions, f"THE entities claimed by more than one QS university: {collisions[:5]}"


def test_the_pairing_actually_enlarges_the_join():
    """If the file stopped being used, this is what would go quiet."""
    with_file = build_cross_source_frame()
    without_file = build_cross_source_frame(pairing_path="/nonexistent-pairing.json")
    assert len(with_file.frame) > len(without_file.frame), (
        "the pairing file adds no rows over the name join, which means either it is "
        "not being read or it holds nothing the names did not already match"
    )
