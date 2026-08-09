"""The non-learned baseline every model here is scored against.

QS publishes the weighting it uses to combine the nine indicators into the
overall score. Applying it directly is therefore not a strawman baseline like
"predict the mean" -- it is the actual documented mechanism, and a learned model
that cannot beat it has demonstrated nothing.

Keeping this in the comparison is also what makes the headline result
falsifiable: if a fitted linear model recovers coefficients close to the
published weights, that is evidence the features and target line up as claimed;
if it does not, something upstream is wrong and the discrepancy is visible
rather than absorbed into a slightly better R2.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ranking_ml.features.schema import QS_INDICATORS, QS_PUBLISHED_WEIGHTS


def published_weight_prediction(X: pd.DataFrame) -> np.ndarray:
    """Predict the overall score with QS's own published weighting.

    Missing indicator values are handled by renormalising over the weights that
    are actually available for that row, rather than imputing. A university
    missing its international-faculty score should be scored on what QS did
    publish for it, not on a median borrowed from other institutions.
    """
    indicators = X[list(QS_INDICATORS)]
    weights = np.array([QS_PUBLISHED_WEIGHTS[name] for name in QS_INDICATORS], dtype=float)

    values = indicators.to_numpy(dtype=float)
    available = np.isfinite(values)

    weighted = np.where(available, values, 0.0) @ weights
    weight_mass = available @ weights

    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(weight_mass > 0, weighted / weight_mass, np.nan)
    return out


def normalised_coefficients(coefficients: np.ndarray) -> dict[str, float]:
    """Scale fitted coefficients to sum to 1 so they compare to QS's weights.

    Only meaningful for a linear model fitted on the raw 0-100 indicator values;
    coefficients from a model fitted on standardised features do not carry the
    same interpretation.
    """
    coefficients = np.asarray(coefficients, dtype=float)
    total = coefficients.sum()
    if not np.isfinite(total) or total == 0:
        return {name: float("nan") for name in QS_INDICATORS}
    return {name: float(c / total) for name, c in zip(QS_INDICATORS, coefficients)}


def weight_recovery_table(fitted_weights: dict[str, float]) -> pd.DataFrame:
    """Fitted weighting beside QS's published weighting, with the gap."""
    rows = []
    for name in QS_INDICATORS:
        published = QS_PUBLISHED_WEIGHTS[name]
        recovered = fitted_weights.get(name, float("nan"))
        rows.append(
            {
                "indicator": name,
                "qs_published": round(published, 4),
                "recovered": round(recovered, 4),
                "abs_error": round(abs(recovered - published), 4),
            }
        )
    return pd.DataFrame(rows).sort_values("qs_published", ascending=False)
