"""Train and evaluate the QS overall-score models.

    PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python \\
        -m ranking_ml.training.train_overall_score

Writes ``artifacts/models/overall_score.joblib`` (gitignored, rebuildable) and
``artifacts/metrics/overall_score.json`` (committed, and what CI compares
against).

The report has three parts, in order of how much they can be trusted:

1. **Cross-validated error on the 600 labelled rows.** Measures how well a model
   recovers QS's published scoring function. It is *not* an estimate of the
   error on the withheld 903 -- see the covariate-shift finding in the module
   README -- and is labelled accordingly everywhere it appears.
2. **Weight recovery.** The raw linear model's coefficients, normalised, beside
   QS's published weights. Falsifiable: either the fit lands on the documented
   weighting or it does not.
3. **Rank agreement on the 903.** Spearman between predicted score and published
   rank, reported for all unlabelled rows and again for the supported subset
   only. The scores out there are unknown; the ordering is not.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold, cross_val_predict

from ranking_ml.evaluation.baselines import (
    normalised_coefficients,
    published_weight_prediction,
    weight_recovery_table,
)
from ranking_ml.evaluation.metrics import CrossValMetrics, rank_agreement, regression_metrics
from ranking_ml.features.build_features import DEFAULT_SNAPSHOT, load_feature_matrix
from ranking_ml.features.schema import QS_INDICATORS
from ranking_ml.models.overall_score import RANDOM_STATE, build_pipelines
from ranking_ml.models.support import SupportFlagger

_REPO_ROOT = Path(__file__).resolve().parents[4]
_ML_ROOT = _REPO_ROOT / "crawlernest" / "crawlernest-ml"
DEFAULT_MODEL_DIR = _ML_ROOT / "artifacts" / "models"
DEFAULT_METRICS_DIR = _ML_ROOT / "artifacts" / "metrics"


def cross_validate_pipeline(pipeline, X: pd.DataFrame, y: pd.Series, folds: int) -> tuple[CrossValMetrics, np.ndarray]:
    """Per-fold metrics plus the out-of-fold predictions they were computed from."""
    kfold = KFold(n_splits=folds, shuffle=True, random_state=RANDOM_STATE)
    oof = cross_val_predict(pipeline, X, y, cv=kfold, n_jobs=None)

    rmses, maes, r2s = [], [], []
    for _, test_idx in kfold.split(X):
        fold = regression_metrics(y.iloc[test_idx].to_numpy(), oof[test_idx])
        rmses.append(fold.rmse)
        maes.append(fold.mae)
        r2s.append(fold.r2)

    return (
        CrossValMetrics(
            rmse_mean=float(np.mean(rmses)),
            rmse_std=float(np.std(rmses)),
            mae_mean=float(np.mean(maes)),
            mae_std=float(np.std(maes)),
            r2_mean=float(np.mean(r2s)),
            r2_std=float(np.std(r2s)),
            folds=folds,
        ),
        oof,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the QS overall-score regressor.")
    parser.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--model-dir", default=str(DEFAULT_MODEL_DIR))
    parser.add_argument("--metrics-dir", default=str(DEFAULT_METRICS_DIR))
    args = parser.parse_args()

    matrix = load_feature_matrix(args.snapshot)
    X_lab, y_lab = matrix.labelled()
    X_unlab = matrix.unlabelled()
    rank_unlab = matrix.rank.loc[~matrix.labelled_mask]

    report: dict = {
        "dataset": {
            "snapshot": str(Path(args.snapshot).relative_to(_REPO_ROOT)),
            "rows_total": int(len(matrix.X)),
            "rows_labelled": int(len(y_lab)),
            "rows_unlabelled": int(len(X_unlab)),
            "features": matrix.feature_names,
        }
    }

    # ---- 1. baseline ------------------------------------------------------
    print("=" * 78)
    print("1. BASELINE -- QS's own published weighting, no learning")
    print("=" * 78)
    baseline_pred = published_weight_prediction(X_lab)
    baseline = regression_metrics(y_lab.to_numpy(), baseline_pred)
    print(f"  {baseline}")
    report["baseline"] = {"published_weights": baseline.as_dict()}

    # ---- 2. cross-validated model comparison ------------------------------
    print()
    print("=" * 78)
    print(f"2. CROSS-VALIDATED COMPARISON ({args.folds}-fold, labelled rows only)")
    print("   Measures recovery of QS's scoring function, NOT error on the withheld 903.")
    print("=" * 78)

    cv_results: dict[str, CrossValMetrics] = {}
    for name, pipeline in build_pipelines().items():
        cv, _ = cross_validate_pipeline(pipeline, X_lab, y_lab, args.folds)
        cv_results[name] = cv
        print(f"  {name:<20} {cv}")
    report["cross_validation"] = {name: cv.as_dict() for name, cv in cv_results.items()}

    best_name = min(cv_results, key=lambda n: cv_results[n].rmse_mean)
    print(f"\n  best by CV RMSE: {best_name}")
    report["best_model"] = best_name

    # ---- 3. weight recovery ----------------------------------------------
    print()
    print("=" * 78)
    print("3. WEIGHT RECOVERY -- fitted coefficients vs QS's published weighting")
    print("=" * 78)
    linear = build_pipelines()["linear_raw"].fit(X_lab, y_lab)
    coefficients = linear.named_steps["model"].coef_
    recovered = normalised_coefficients(coefficients)
    table = weight_recovery_table(recovered)
    print(table.to_string(index=False))
    mean_abs_err = float(table["abs_error"].mean())
    print(f"\n  mean absolute weight error: {mean_abs_err:.4f}")
    report["weight_recovery"] = {
        "rows": table.to_dict(orient="records"),
        "mean_abs_error": round(mean_abs_err, 4),
        "intercept": round(float(linear.named_steps["model"].intercept_), 4),
    }

    # ---- 4. support and extrapolation ------------------------------------
    print()
    print("=" * 78)
    print("4. SUPPORT -- how much of the inference set sits inside training space")
    print("=" * 78)
    flagger = SupportFlagger().fit(X_lab)
    support_rows = [flagger.report(X_lab, "labelled (train)"), flagger.report(X_unlab, "unlabelled (infer)")]
    print(pd.DataFrame(support_rows).to_string(index=False))
    report["support"] = support_rows

    # ---- 5. external validation on the withheld rows ---------------------
    print()
    print("=" * 78)
    print("5. RANK AGREEMENT ON THE 903 -- the only external check in the shifted region")
    print("=" * 78)
    supported = flagger.is_supported(X_unlab)
    ranks = rank_unlab.to_numpy()

    # Cross-validated accuracy on the labelled rows does not decide which model
    # to use out here -- the shifted region has to be measured on its own terms.
    candidates = {
        "linear_renorm": build_pipelines()["linear_renorm"].fit(X_lab, y_lab).predict(X_unlab),
        "published_weight baseline": published_weight_prediction(X_unlab),
    }
    if best_name != "linear_renorm":
        candidates[f"{best_name} (best by CV)"] = (
            build_pipelines()[best_name].fit(X_lab, y_lab).predict(X_unlab)
        )

    agreement: dict[str, dict] = {}
    for label, predictions in candidates.items():
        agreement[label] = {
            "all_unlabelled": rank_agreement(predictions, ranks),
            "supported_only": rank_agreement(predictions[supported], ranks[supported]),
        }
        print(
            f"  {label:<28} all {agreement[label]['all_unlabelled']['spearman']:+.4f}   "
            f"supported-only {agreement[label]['supported_only']['spearman']:+.4f}"
        )
    report["rank_agreement"] = agreement

    recommended = max(candidates, key=lambda k: agreement[k]["all_unlabelled"]["spearman"])
    report["recommended_for_inference"] = recommended
    print(f"\n  recommended for the withheld rows: {recommended}")

    # ---- persist ----------------------------------------------------------
    model_dir = Path(args.model_dir)
    metrics_dir = Path(args.metrics_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)

    joblib.dump(
        {
            "cv_best_name": best_name,
            "cv_best": build_pipelines()[best_name].fit(X_lab, y_lab),
            "inference_model": build_pipelines()["linear_renorm"].fit(X_lab, y_lab),
            "support": flagger,
            "features": matrix.feature_names,
        },
        model_dir / "overall_score.joblib",
    )
    metrics_path = metrics_dir / "overall_score.json"
    metrics_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print()
    print(f"model   -> {(model_dir / 'overall_score.joblib').relative_to(_REPO_ROOT)}")
    print(f"metrics -> {metrics_path.relative_to(_REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
