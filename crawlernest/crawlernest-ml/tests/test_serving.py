"""Serving-path tests that need no database.

The write path is exercised end to end by the ml-serving CI job against a
throwaway PostgreSQL. These cover the one piece that job cannot reach: the
collapse of several snapshot rows onto one canonical university.

That collapse is what real entity resolution produces -- the warehouse holds
1,499 canonical universities for 1,503 snapshot rows -- but the CI database is
seeded one row per distinct name, so nothing there merges. Without these tests
the guard would be code nobody runs until a real warehouse breaks the insert.
"""

from __future__ import annotations

import pandas as pd

from ranking_ml.serving.predict import collapse_to_one_row_per_university, normalise_name
from ranking_ml.serving.seed_canonical_from_snapshot import normalise_display_name, slugify


def _frame(rows):
    return pd.DataFrame(rows, columns=["canonical_university_id", "university_name", "predicted_value"])


def test_duplicate_canonical_ids_are_collapsed():
    """The insert is unique on canonical id, so duplicates must not reach it."""
    frame = _frame([
        (10, "Best Spelling University", 90.0),
        (11, "Another University", 80.0),
        (10, "Variant Spelling University", 70.0),
    ])
    deduped, merged = collapse_to_one_row_per_university(frame)

    assert merged == 1
    assert list(deduped["canonical_university_id"]) == [10, 11]


def test_the_kept_row_is_the_first_one():
    """The snapshot is rank-ordered, so first means best-ranked, not arbitrary."""
    frame = _frame([
        (10, "Best Spelling University", 90.0),
        (10, "Variant Spelling University", 70.0),
    ])
    deduped, _ = collapse_to_one_row_per_university(frame)

    assert list(deduped["university_name"]) == ["Best Spelling University"]
    assert list(deduped["predicted_value"]) == [90.0]


def test_nothing_is_dropped_when_every_id_is_distinct():
    frame = _frame([(1, "A University", 1.0), (2, "B University", 2.0)])
    deduped, merged = collapse_to_one_row_per_university(frame)

    assert merged == 0
    assert len(deduped) == 2


def test_empty_input_is_handled():
    deduped, merged = collapse_to_one_row_per_university(_frame([]))
    assert merged == 0
    assert deduped.empty


# ── the seeder's name handling ───────────────────────────────────────────────

def test_slug_and_normalised_name_agree_with_the_resolver():
    """Whatever the seeder writes must be findable by the resolver's rule."""
    name = "Ca' Foscari University of Venice"
    assert slugify(name) == "ca-foscari-university-of-venice"
    assert normalise_display_name(name) == "ca foscari university of venice"
    # The resolver matches on letters only, from display_name.
    assert normalise_name(name) == "cafoscariuniversityofvenice"


def test_placeholder_names_share_a_slug():
    """Why the seeder skips them: they all collapse onto one invented entity."""
    assert slugify("N/A") == slugify("n/a") == "n-a"
