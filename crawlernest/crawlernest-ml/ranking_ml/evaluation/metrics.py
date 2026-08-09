"""Metric definitions shared by every model in this module.

One place decides what "RMSE" means here, so a number in a model card and a
number in a CI gate cannot quietly disagree.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


@dataclass(frozen=True)
class RegressionMetrics:
    """Point metrics for a regression fit."""

    rmse: float
    mae: float
    r2: float
    n: int

    def as_dict(self) -> dict[str, Any]:
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in asdict(self).items()}

    def __str__(self) -> str:
        return f"RMSE {self.rmse:6.3f}   MAE {self.mae:6.3f}   R2 {self.r2:6.4f}   (n={self.n})"


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> RegressionMetrics:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return RegressionMetrics(
        rmse=float(np.sqrt(mean_squared_error(y_true, y_pred))),
        mae=float(mean_absolute_error(y_true, y_pred)),
        r2=float(r2_score(y_true, y_pred)),
        n=int(len(y_true)),
    )


@dataclass(frozen=True)
class CrossValMetrics:
    """Mean and spread of a metric across folds.

    The spread is reported because a single averaged number hides a model that
    is excellent on four folds and broken on the fifth.
    """

    rmse_mean: float
    rmse_std: float
    mae_mean: float
    mae_std: float
    r2_mean: float
    r2_std: float
    folds: int

    def as_dict(self) -> dict[str, Any]:
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in asdict(self).items()}

    def __str__(self) -> str:
        return (
            f"RMSE {self.rmse_mean:6.3f} ± {self.rmse_std:.3f}   "
            f"MAE {self.mae_mean:6.3f} ± {self.mae_std:.3f}   "
            f"R2 {self.r2_mean:6.4f} ± {self.r2_std:.4f}"
        )


def rank_agreement(predicted_score: np.ndarray, published_rank: np.ndarray) -> dict[str, float]:
    """Spearman agreement between a predicted score and a published rank.

    A better score should mean a smaller (better) rank number, so perfect
    agreement is ``rho = -1``. The sign is flipped here so that 1.0 reads as
    perfect and the number needs no explanation in a report.

    This is the only external check available on the unlabelled rows: QS
    withholds their score but still publishes their rank, so the ordering can be
    verified even where the values cannot.
    """
    predicted_score = np.asarray(predicted_score, dtype=float)
    published_rank = np.asarray(published_rank, dtype=float)
    ok = np.isfinite(predicted_score) & np.isfinite(published_rank)
    if ok.sum() < 3:
        return {"spearman": float("nan"), "p_value": float("nan"), "n": int(ok.sum())}
    result = spearmanr(predicted_score[ok], published_rank[ok])
    return {
        "spearman": float(-result.statistic),
        "p_value": float(result.pvalue),
        "n": int(ok.sum()),
    }
