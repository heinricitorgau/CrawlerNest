"""Per-prediction support: is this row inside the region the model was trained on?

The EDA established that the 903 universities whose score QS withholds are not
drawn from the same population as the 600 it publishes -- every indicator shifts
by 0.67 to 1.91 pooled standard deviations. A model trained on the labelled rows
therefore extrapolates when it predicts the unlabelled ones, and a
cross-validated error says nothing about how wrong it is out there.

This module answers the narrower question that *can* be answered: for one row,
how far is it from the training data? The rule is deliberately mechanical and
inspectable, in keeping with the repo's policy that confidence is derived, never
assigned by hand:

    support distance = mean euclidean distance, in standardised indicator space,
                       to the k nearest training rows

    supported        = distance <= the Pth percentile of the training set's own
                       distances, computed leave-one-out

So the threshold is not a magic constant: it is the distance that P% of the
training data itself falls within. A row further out than that is flagged, and
the caller decides whether to publish the estimate or withhold it.

What this does not do: it does not estimate the error. A supported row can still
be predicted badly. It only separates "the model has seen rows like this" from
"the model has not", which is the distinction the PCA made visible.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from ranking_ml.features.schema import QS_INDICATORS

DEFAULT_NEIGHBOURS = 10
DEFAULT_PERCENTILE = 95.0


@dataclass
class SupportFlagger:
    """Distance-to-training-data flag, fitted on the labelled rows."""

    n_neighbours: int = DEFAULT_NEIGHBOURS
    percentile: float = DEFAULT_PERCENTILE

    def fit(self, X_train: pd.DataFrame) -> "SupportFlagger":
        values = X_train[list(QS_INDICATORS)].to_numpy(dtype=float)
        self._imputer = SimpleImputer(strategy="median").fit(values)
        self._scaler = StandardScaler().fit(self._imputer.transform(values))
        train_scaled = self._scaler.transform(self._imputer.transform(values))

        # k+1 neighbours because the first hit for a training row is itself.
        self._neighbours = NearestNeighbors(n_neighbors=self.n_neighbours + 1).fit(train_scaled)
        distances, _ = self._neighbours.kneighbors(train_scaled)
        self.train_distances_ = distances[:, 1:].mean(axis=1)
        self.threshold_ = float(np.percentile(self.train_distances_, self.percentile))
        return self

    def distance(self, X: pd.DataFrame) -> np.ndarray:
        """Mean distance to the k nearest training rows, one value per row."""
        values = X[list(QS_INDICATORS)].to_numpy(dtype=float)
        scaled = self._scaler.transform(self._imputer.transform(values))
        distances, _ = self._neighbours.kneighbors(scaled, n_neighbors=self.n_neighbours)
        return distances.mean(axis=1)

    def is_supported(self, X: pd.DataFrame) -> np.ndarray:
        return self.distance(X) <= self.threshold_

    def report(self, X: pd.DataFrame, label: str) -> dict[str, float]:
        distances = self.distance(X)
        supported = distances <= self.threshold_
        return {
            "set": label,
            "n": int(len(distances)),
            "supported": int(supported.sum()),
            "supported_pct": round(100.0 * float(supported.mean()), 2),
            "distance_median": round(float(np.median(distances)), 4),
            "distance_p95": round(float(np.percentile(distances, 95)), 4),
            "threshold": round(self.threshold_, 4),
        }
