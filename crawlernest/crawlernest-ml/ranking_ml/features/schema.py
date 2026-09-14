"""Feature contract for the QS indicator matrix.

This module is the single source of truth for *what a feature row is*. Anything
that builds, trains on, or serves the QS feature matrix imports these names
rather than re-typing string literals, so a renamed indicator breaks loudly in
one place instead of silently producing a differently-shaped matrix.

Background on the data (measured on the QS 2026 edition, 1,504 universities):

- All nine component indicators are present on every record, but a few carry the
  string ``"n/a"`` instead of a number. Those become ``NaN`` and are imputed at
  training time; the rate is reported by :func:`missingness_report` so it never
  goes unnoticed.
- ``Overall Score`` is published only for ranks 1-705. The remaining 799 rows
  carry ``"n/a"``. That is not a data defect -- QS withholds the total for the
  tail -- and it is exactly what makes this a supervised problem: train on the
  705 labelled rows, predict the 799 unlabelled ones.
- The 2026 table also publishes ``International Student Diversity``. It is
  deliberately not in the list below: the nine indicators alone recover the
  overall score to within rounding (see the weight recovery in the model card),
  which is what an unweighted metric would look like.
- ``rank`` must never be used as a feature. QS derives the rank *from* the
  overall score, so including it leaks the target. It is carried alongside the
  matrix as an evaluation-only column (see ``RANK_COLUMN``).
"""

from __future__ import annotations

from typing import Final

#: Component indicators, in the fixed column order of the feature matrix.
#: The strings are the labels QS uses in the scraped ``table_metrics`` mapping.
QS_INDICATORS: Final[tuple[str, ...]] = (
    "Academic Reputation",
    "Employer Reputation",
    "Faculty Student Ratio",
    "Citations per Faculty",
    "International Faculty Ratio",
    "International Student Ratio",
    "International Research Network",
    "Employment Outcomes",
    "Sustainability Score",
)

#: The regression target. Numeric for ranks 1-705 in 2026, ``"n/a"`` beyond that.
TARGET_LABEL: Final[str] = "Overall Score"

#: Carried through the pipeline for evaluation but never fed to a model.
RANK_COLUMN: Final[str] = "rank"

#: Value QS uses for a withheld or unavailable number.
MISSING_TOKEN: Final[str] = "n/a"

#: Country string used when the source did not report a country.
UNKNOWN_COUNTRY: Final[str] = "N A"

#: Indicator scores are published on a 0-100 scale. Values outside this range
#: mean the parser picked up the wrong cell, so builders reject them loudly.
VALUE_MIN: Final[float] = 0.0
VALUE_MAX: Final[float] = 100.0

#: Published QS weighting, used as the non-learned baseline every model is
#: scored against. Source: QS World University Rankings 2026 methodology.
#: Keys match :data:`QS_INDICATORS`; values sum to 1.0.
QS_PUBLISHED_WEIGHTS: Final[dict[str, float]] = {
    "Academic Reputation": 0.30,
    "Employer Reputation": 0.15,
    "Faculty Student Ratio": 0.10,
    "Citations per Faculty": 0.20,
    "International Faculty Ratio": 0.05,
    "International Student Ratio": 0.05,
    "International Research Network": 0.05,
    "Employment Outcomes": 0.05,
    "Sustainability Score": 0.05,
}


def validate_contract() -> None:
    """Fail fast if the constants above drift out of agreement.

    Called at import time by the feature builder so a bad edit surfaces before
    a training run rather than inside a fold.
    """
    missing = set(QS_INDICATORS) - set(QS_PUBLISHED_WEIGHTS)
    if missing:
        raise ValueError(f"QS_PUBLISHED_WEIGHTS is missing indicators: {sorted(missing)}")
    extra = set(QS_PUBLISHED_WEIGHTS) - set(QS_INDICATORS)
    if extra:
        raise ValueError(f"QS_PUBLISHED_WEIGHTS has unknown indicators: {sorted(extra)}")
    total = sum(QS_PUBLISHED_WEIGHTS.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"QS_PUBLISHED_WEIGHTS must sum to 1.0, got {total}")
