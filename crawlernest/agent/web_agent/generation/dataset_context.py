"""How the dataset describes itself to a model.

The facts themselves -- which year is loaded, which sources are ingested -- are
warehouse facts and live in :mod:`crawlernest.core.dataset`. They are re-exported
here so an explainer has one import for "what the corpus is and what the model
must be told about it", without ``core`` ever having to import ``agent``.

What this module owns is the second half of that: the wording. A model handed a
single year of data will still write "climbing year after year" or "the latest
2027 figures", because that is what ranking prose usually sounds like. Neither
claim invents a number the faithfulness rules can catch (``faithfulness.py``
checks figures, caveats and institution names; a trend is none of those), so the
constraint has to arrive before generation rather than be caught after it.
Golden case ``faith-122`` records exactly that gap.

:func:`build_dataset_header` and :data:`DATASET_CONSTRAINTS` are what every
grounded explainer prepends and appends for that reason -- see
``GroundedExplainer._explain``, which applies both so no subclass has to.
"""

from __future__ import annotations

from crawlernest.core.dataset import DATASET_SOURCES, DATASET_YEAR

__all__ = [
    "DATASET_CONSTRAINTS",
    "DATASET_SOURCES",
    "DATASET_YEAR",
    "build_dataset_header",
]


def build_dataset_header() -> str:
    """The three-line declaration prepended to every explainer's evidence block.

    Derived from the constants rather than written out, so a dataset that gains
    a year or a source cannot leave the model reading a stale description of it.
    """
    return "\n".join(
        (
            f"Dataset year: the warehouse holds {DATASET_YEAR} ranking data and no other year.",
            f"Ingested sources: {', '.join(DATASET_SOURCES)}. Any other source is a "
            "null-valued key, not a figure.",
            "This is a single-year snapshot. Inferring any cross-year trend, movement, "
            "improvement or decline from it is forbidden.",
        )
    )


#: Appended to every explainer's response constraints by
#: :meth:`GroundedExplainer._explain`. Kept next to the header so the rule the
#: model is given and the corpus description it is given cannot drift apart.
DATASET_CONSTRAINTS = (
    f"Name no year other than {DATASET_YEAR}. No other year exists in this data, so "
    "any other year label -- an earlier edition, a later intake -- would be invented.",
    'Do not write "currently", "latest", "most recent", "up to date", "year after '
    'year", "has risen", "has improved", "held its position", or any other wording '
    "that implies time passing or a trend. One snapshot cannot show movement.",
)
