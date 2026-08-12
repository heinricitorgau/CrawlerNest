"""Exploratory analysis of the QS indicator matrix.

Produces the figures and the numbers that Phase 2 modelling decisions rest on::

    PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python -m ranking_ml.eda.run_eda

Written as a script rather than a notebook so it reruns identically in CI and
its output can be diffed. The figures land in ``artifacts/eda/``.

The question this analysis exists to answer is not "are the indicators
correlated" -- of course they are -- but **how far the 903 unlabelled rows sit
from the 600 labelled ones**. Training on ranks 1-600 and predicting ranks
601-1503 is extrapolation, not interpolation, and the size of that gap decides
how much the Phase 2 error estimates can be trusted.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from ranking_ml.features.build_features import (
    DEFAULT_SNAPSHOT,
    load_feature_matrix,
    missingness_report,
)
from ranking_ml.features.schema import QS_INDICATORS, TARGET_LABEL

_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUT = _REPO_ROOT / "crawlernest" / "crawlernest-ml" / "artifacts" / "eda"


def _prepared_indicators(X: pd.DataFrame) -> pd.DataFrame:
    """Indicators only, median-imputed, for analyses that cannot take NaN."""
    indicators = X[list(QS_INDICATORS)]
    imputed = SimpleImputer(strategy="median").fit_transform(indicators)
    return pd.DataFrame(imputed, columns=list(QS_INDICATORS), index=indicators.index)


def plot_correlation(matrix, out_dir: Path) -> Path:
    """Indicator correlation on the labelled rows, with the target included."""
    X_lab, y_lab = matrix.labelled()
    frame = _prepared_indicators(X_lab).copy()
    frame[TARGET_LABEL] = y_lab.to_numpy()
    corr = frame.corr(method="pearson")

    fig, ax = plt.subplots(figsize=(9, 7.5))
    im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr)), corr.columns, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(corr)), corr.columns, fontsize=8)
    for i in range(len(corr)):
        for j in range(len(corr)):
            value = corr.iloc[i, j]
            ax.text(
                j, i, f"{value:.2f}",
                ha="center", va="center", fontsize=6.5,
                color="white" if abs(value) > 0.55 else "black",
            )
    ax.set_title(
        f"QS indicator correlation, labelled rows only (n={len(y_lab)})",
        fontsize=11, pad=12,
    )
    fig.colorbar(im, ax=ax, shrink=0.8, label="Pearson r")
    fig.tight_layout()
    path = out_dir / "correlation_heatmap.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_pca(matrix, out_dir: Path) -> tuple[Path, PCA]:
    """PCA of all 1,503 rows, labelled and unlabelled drawn separately."""
    indicators = _prepared_indicators(matrix.X)
    scaled = StandardScaler().fit_transform(indicators)
    pca = PCA(n_components=2, random_state=0)
    coords = pca.fit_transform(scaled)
    labelled = matrix.labelled_mask.to_numpy()

    fig, ax = plt.subplots(figsize=(8.5, 6.5))
    ax.scatter(
        coords[~labelled, 0], coords[~labelled, 1],
        s=9, alpha=0.45, c="#b0b7c3",
        label=f"rank 601-1503, score withheld (n={int((~labelled).sum())})",
    )
    scatter = ax.scatter(
        coords[labelled, 0], coords[labelled, 1],
        s=14, alpha=0.85, c=matrix.rank[labelled], cmap="viridis",
        label=f"rank 1-600, score published (n={int(labelled.sum())})",
    )
    ax.set_xlabel(f"PC1 ({pca.explained_variance_ratio_[0] * 100:.1f}% variance)")
    ax.set_ylabel(f"PC2 ({pca.explained_variance_ratio_[1] * 100:.1f}% variance)")
    ax.set_title("QS universities in indicator space: training set vs inference set", fontsize=11)
    ax.legend(loc="best", fontsize=8, framealpha=0.9)
    fig.colorbar(scatter, ax=ax, label="published QS rank")
    ax.grid(alpha=0.15)
    fig.tight_layout()
    path = out_dir / "pca_scatter.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path, pca


def covariate_shift(matrix) -> pd.DataFrame:
    """Per-indicator distance between the labelled and unlabelled populations.

    ``standardised_gap`` is the difference in means expressed in pooled standard
    deviations (Cohen's d). Anything past roughly 0.8 is a large shift and means
    a cross-validated error on the labelled rows understates the error the model
    will actually make on the unlabelled ones.

    Returned at full precision. Rounding belongs to whoever displays the number,
    not to the function that computes it -- a rounded return value cannot be
    compared against an independent implementation, which is exactly what
    ``check_matlab_parity`` needs to do.
    """
    indicators = _prepared_indicators(matrix.X)
    labelled = matrix.labelled_mask.to_numpy()
    rows = []
    for name in QS_INDICATORS:
        a = indicators.loc[labelled, name].to_numpy()
        b = indicators.loc[~labelled, name].to_numpy()
        pooled = np.sqrt(((a.var(ddof=1) * (len(a) - 1)) + (b.var(ddof=1) * (len(b) - 1))) / (len(a) + len(b) - 2))
        rows.append(
            {
                "indicator": name,
                "labelled_mean": float(a.mean()),
                "unlabelled_mean": float(b.mean()),
                "standardised_gap": float((a.mean() - b.mean()) / pooled) if pooled else float("nan"),
            }
        )
    return pd.DataFrame(rows).sort_values("standardised_gap", key=abs, ascending=False)


def correlation_with_target(matrix) -> pd.DataFrame:
    """Pearson correlation of each indicator with the target, labelled rows only.

    Full precision, for the same reason as :func:`covariate_shift`.
    """
    X_lab, y_lab = matrix.labelled()
    prepared = _prepared_indicators(X_lab)
    target = pd.Series(y_lab.to_numpy(), index=X_lab.index)
    correlations = prepared.corrwith(target)
    return (
        pd.DataFrame({"indicator": correlations.index, "pearson_r": correlations.to_numpy()})
        .sort_values("pearson_r", ascending=False)
        .reset_index(drop=True)
    )


def plot_target_distribution(matrix, out_dir: Path) -> Path:
    _, y_lab = matrix.labelled()
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.hist(y_lab, bins=40, color="#4c72b0", alpha=0.85, edgecolor="white")
    ax.set_xlabel(f"{TARGET_LABEL} (published, ranks 1-600)")
    ax.set_ylabel("universities")
    ax.set_title(
        f"Target distribution: n={len(y_lab)}, mean={y_lab.mean():.1f}, "
        f"std={y_lab.std():.1f}, right-skewed toward the top of the table",
        fontsize=10,
    )
    ax.grid(alpha=0.15, axis="y")
    fig.tight_layout()
    path = out_dir / "target_distribution.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run EDA on the QS indicator matrix.")
    parser.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    matrix = load_feature_matrix(args.snapshot)
    print(matrix.summary())

    missing = missingness_report(matrix)
    print("\n--- missingness ---")
    print(missing.to_string())

    correlations = correlation_with_target(matrix)
    print("\n--- indicator correlation with Overall Score (labelled rows) ---")
    print(correlations.round(3).to_string(index=False))

    shift = covariate_shift(matrix)
    print("\n--- covariate shift, labelled vs unlabelled (Cohen's d) ---")
    print(shift.round(4).to_string(index=False))

    # Written at full precision so an independent implementation can be checked
    # against them -- see ranking_ml.evaluation.check_matlab_parity.
    correlations.to_csv(out_dir / "correlation_with_target.csv", index=False)
    shift.to_csv(out_dir / "covariate_shift.csv", index=False)
    missing.reset_index(names="indicator").to_csv(out_dir / "missingness.csv", index=False)

    paths = [
        plot_correlation(matrix, out_dir),
        plot_target_distribution(matrix, out_dir),
    ]
    pca_path, pca = plot_pca(matrix, out_dir)
    paths.append(pca_path)
    print(
        f"\nPCA: PC1 {pca.explained_variance_ratio_[0] * 100:.1f}%, "
        f"PC2 {pca.explained_variance_ratio_[1] * 100:.1f}%, "
        f"cumulative {pca.explained_variance_ratio_[:2].sum() * 100:.1f}%"
    )
    print("\nfigures written:")
    for path in paths:
        print(f"  {path.relative_to(_REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
