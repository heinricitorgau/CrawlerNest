"""Train and evaluate the cross-source disagreement classifier.

    PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python \\
        -m ranking_ml.training.train_disagreement

## The question this asks, and the one it deliberately does not

The label is built from how far apart QS and THE place the same university. Both
ranks are close to deterministic functions of their own published component
scores -- Phase 2 showed QS's overall score is a weighted sum of its nine
indicators to within 0.0008. So a classifier given *both* sources' scores is not
predicting anything; it is recomputing a quantity it was handed the inputs to.
Such a model scores well and means nothing.

The task modelled here is therefore the one-sided one:

    given only what QS published about a university,
    can we anticipate that THE will disagree?

That is a real prediction, it is not circular, and it has a use: flag contested
institutions at QS ingest time, before THE data arrives. The two-sided model is
still fitted and reported, labelled as the near-deterministic ceiling it is, so
the gap between the two is visible rather than hidden.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ranking_ml.features.cross_source import (
    THE_FEATURE_NAMES,
    build_cross_source_frame,
    disagreement_label,
)
from ranking_ml.features.schema import QS_INDICATORS

RANDOM_STATE = 0
_REPO_ROOT = Path(__file__).resolve().parents[4]
_ML_ROOT = _REPO_ROOT / "crawlernest" / "crawlernest-ml"


def build_classifiers() -> dict[str, Pipeline]:
    return {
        "logistic": Pipeline(
            [
                ("impute", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
                ("model", LogisticRegression(max_iter=2000, random_state=RANDOM_STATE)),
            ]
        ),
        "gradient_boosting": Pipeline(
            [
                ("impute", SimpleImputer(strategy="median")),
                (
                    "model",
                    GradientBoostingClassifier(
                        n_estimators=300,
                        learning_rate=0.05,
                        max_depth=3,
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        ),
    }


def evaluate(name: str, X: pd.DataFrame, y: np.ndarray, folds: int) -> dict:
    """Out-of-fold probabilities and the metrics computed from them."""
    kfold = StratifiedKFold(n_splits=folds, shuffle=True, random_state=RANDOM_STATE)
    out: dict = {}
    for model_name, pipeline in build_classifiers().items():
        proba = cross_val_predict(pipeline, X, y, cv=kfold, method="predict_proba")[:, 1]
        out[model_name] = {
            "roc_auc": round(float(roc_auc_score(y, proba)), 4),
            "pr_auc": round(float(average_precision_score(y, proba)), 4),
            "brier": round(float(brier_score_loss(y, proba)), 4),
            "_proba": proba,
        }
        print(
            f"  {name:<14} {model_name:<18} "
            f"ROC-AUC {out[model_name]['roc_auc']:.4f}   "
            f"PR-AUC {out[model_name]['pr_auc']:.4f}   "
            f"Brier {out[model_name]['brier']:.4f}"
        )
    return out


def plot_diagnostics(y: np.ndarray, proba: np.ndarray, positive_rate: float, out_path: Path) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.4))

    fpr, tpr, _ = roc_curve(y, proba)
    axes[0].plot(fpr, tpr, color="#4c72b0", lw=2, label=f"AUC = {roc_auc_score(y, proba):.3f}")
    axes[0].plot([0, 1], [0, 1], "--", color="#999", lw=1, label="chance (0.500)")
    axes[0].set_xlabel("false positive rate")
    axes[0].set_ylabel("true positive rate")
    axes[0].set_title("ROC")
    axes[0].legend(fontsize=8, loc="lower right")

    precision, recall, _ = precision_recall_curve(y, proba)
    axes[1].plot(recall, precision, color="#dd8452", lw=2,
                 label=f"AP = {average_precision_score(y, proba):.3f}")
    axes[1].axhline(positive_rate, ls="--", color="#999", lw=1,
                    label=f"chance ({positive_rate:.3f})")
    axes[1].set_xlabel("recall")
    axes[1].set_ylabel("precision")
    axes[1].set_title("Precision-recall")
    axes[1].legend(fontsize=8, loc="upper right")

    true_frac, pred_frac = calibration_curve(y, proba, n_bins=10, strategy="quantile")
    axes[2].plot(pred_frac, true_frac, "o-", color="#55a868", lw=2, label="model")
    axes[2].plot([0, 1], [0, 1], "--", color="#999", lw=1, label="perfectly calibrated")
    axes[2].set_xlabel("mean predicted probability")
    axes[2].set_ylabel("observed frequency")
    axes[2].set_title(f"Calibration (Brier = {brier_score_loss(y, proba):.3f})")
    axes[2].legend(fontsize=8, loc="upper left")

    for ax in axes:
        ax.grid(alpha=0.15)
    fig.suptitle(
        "Cross-source disagreement, predicted from QS indicators alone (out-of-fold)",
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description="Train the cross-source disagreement classifier.")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--quantile", type=float, default=0.80,
                        help="gap quantile above which a pair counts as disagreeing")
    args = parser.parse_args()

    cross = build_cross_source_frame()
    frame = cross.frame
    y_series, threshold = disagreement_label(frame, quantile=args.quantile)
    y = y_series.to_numpy()
    positive_rate = float(y.mean())

    print(cross.summary())
    print(
        f"label: percentile gap > {threshold:.4f} "
        f"({int(y.sum())} positives, {positive_rate * 100:.1f}%)"
    )

    X_qs = frame[list(QS_INDICATORS)]
    X_both = frame[list(QS_INDICATORS) + list(THE_FEATURE_NAMES)]

    report: dict = {
        "dataset": {
            "matched": int(len(frame)),
            "qs_population": cross.qs_population,
            "the_population": cross.the_population,
            "label_quantile": args.quantile,
            "gap_threshold": round(threshold, 4),
            "positives": int(y.sum()),
            "positive_rate": round(positive_rate, 4),
        }
    }

    print()
    print("=" * 78)
    print(f"CROSS-VALIDATED ({args.folds}-fold stratified, out-of-fold probabilities)")
    print("=" * 78)
    qs_only = evaluate("qs_only", X_qs, y, args.folds)
    both = evaluate("both_sources", X_both, y, args.folds)
    print("\n  'both_sources' is the near-deterministic ceiling, not a result:")
    print("  it is handed the inputs the label was computed from. 'qs_only' is the task.")

    report["qs_only"] = {k: {m: v for m, v in d.items() if not m.startswith("_")} for k, d in qs_only.items()}
    report["both_sources"] = {k: {m: v for m, v in d.items() if not m.startswith("_")} for k, d in both.items()}

    best_name = max(qs_only, key=lambda n: qs_only[n]["roc_auc"])
    report["best_qs_only"] = best_name
    print(f"\n  best one-sided model: {best_name}")

    # ---- threshold sensitivity -------------------------------------------
    print()
    print("=" * 78)
    print("THRESHOLD SENSITIVITY -- does the result survive a different cutoff?")
    print("=" * 78)
    sensitivity = []
    for quantile in (0.70, 0.80, 0.90):
        y_alt, threshold_alt = disagreement_label(frame, quantile=quantile)
        kfold = StratifiedKFold(n_splits=args.folds, shuffle=True, random_state=RANDOM_STATE)
        proba_alt = cross_val_predict(
            build_classifiers()[best_name], X_qs, y_alt.to_numpy(), cv=kfold, method="predict_proba"
        )[:, 1]
        row = {
            "quantile": quantile,
            "threshold": round(threshold_alt, 4),
            "positive_rate": round(float(y_alt.mean()), 4),
            "roc_auc": round(float(roc_auc_score(y_alt, proba_alt)), 4),
            "pr_auc": round(float(average_precision_score(y_alt, proba_alt)), 4),
        }
        sensitivity.append(row)
        print(
            f"  gap > {row['threshold']:.4f}  positives {row['positive_rate'] * 100:4.1f}%   "
            f"ROC-AUC {row['roc_auc']:.4f}   PR-AUC {row['pr_auc']:.4f}"
        )
    report["threshold_sensitivity"] = sensitivity

    # ---- which side is favoured ------------------------------------------
    favoured = frame.loc[y_series == 1, "favoured_by"].value_counts().to_dict()
    report["favoured_among_positives"] = {k: int(v) for k, v in favoured.items()}
    print()
    print(f"among disagreeing pairs, THE ranks higher for {favoured.get('THE', 0)} "
          f"and QS for {favoured.get('QS', 0)}")

    # ---- persist ----------------------------------------------------------
    figure_dir = _ML_ROOT / "artifacts" / "eda"
    metrics_dir = _ML_ROOT / "artifacts" / "metrics"
    model_dir = _ML_ROOT / "artifacts" / "models"
    for directory in (figure_dir, metrics_dir, model_dir):
        directory.mkdir(parents=True, exist_ok=True)

    figure_path = figure_dir / "disagreement_diagnostics.png"
    plot_diagnostics(y, qs_only[best_name]["_proba"], positive_rate, figure_path)

    fitted = build_classifiers()[best_name].fit(X_qs, y)
    joblib.dump({"model": fitted, "features": list(QS_INDICATORS)}, model_dir / "disagreement.joblib")

    metrics_path = metrics_dir / "disagreement.json"
    metrics_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print()
    print(f"figure  -> {figure_path.relative_to(_REPO_ROOT)}")
    print(f"model   -> {(model_dir / 'disagreement.joblib').relative_to(_REPO_ROOT)}")
    print(f"metrics -> {metrics_path.relative_to(_REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
