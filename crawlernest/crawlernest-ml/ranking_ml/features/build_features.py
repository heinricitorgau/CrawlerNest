"""Build the QS indicator feature matrix from a crawl snapshot.

The snapshot at ``crawlernest/crawlernest-kb/databases/last_crawl_snapshot.json``
is committed to the repository, so this builder -- and therefore training and
evaluation -- runs with no database and no network. That is deliberate: CI can
verify the model without provisioning PostgreSQL.

Output shape (2026 snapshot):

    X            (1503, 9) indicators, or (1503, 21) with region one-hot
    y            1503 values, 600 numeric and 903 NaN
    rank         1503 integers, evaluation only, never a feature

Run it directly for a summary of what came out::

    PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python \\
        -m ranking_ml.features.build_features
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ranking_ml.features.regions import REGION_ORDER, region_for, unmapped_countries
from ranking_ml.features.schema import (
    MISSING_TOKEN,
    QS_INDICATORS,
    RANK_COLUMN,
    TARGET_LABEL,
    VALUE_MAX,
    VALUE_MIN,
    validate_contract,
)

validate_contract()

#: Repository root, four levels up from this file.
_REPO_ROOT = Path(__file__).resolve().parents[4]

DEFAULT_SNAPSHOT = _REPO_ROOT / "crawlernest" / "crawlernest-kb" / "databases" / "last_crawl_snapshot.json"

_NUMERIC_RE = re.compile(r"^\d+(?:\.\d+)?$")


@dataclass(frozen=True)
class FeatureMatrix:
    """A built feature matrix and everything needed to interpret it."""

    X: pd.DataFrame
    y: pd.Series
    rank: pd.Series
    university_name: pd.Series
    country: pd.Series

    @property
    def labelled_mask(self) -> pd.Series:
        """Rows where QS published an overall score (ranks 1-600)."""
        return self.y.notna()

    @property
    def feature_names(self) -> list[str]:
        return list(self.X.columns)

    def labelled(self) -> tuple[pd.DataFrame, pd.Series]:
        """The supervised training set: features and target for labelled rows."""
        mask = self.labelled_mask
        return self.X.loc[mask], self.y.loc[mask]

    def unlabelled(self) -> pd.DataFrame:
        """Rows QS withheld a score for -- the inference set."""
        return self.X.loc[~self.labelled_mask]

    def summary(self) -> str:
        n_lab = int(self.labelled_mask.sum())
        lines = [
            f"rows              {len(self.X)}",
            f"features          {self.X.shape[1]}  {self.feature_names}",
            f"labelled (train)  {n_lab}   rank range "
            f"{self.rank[self.labelled_mask].min()}-{self.rank[self.labelled_mask].max()}",
            f"unlabelled (infer){len(self.X) - n_lab}   rank range "
            f"{self.rank[~self.labelled_mask].min()}-{self.rank[~self.labelled_mask].max()}",
        ]
        return "\n".join(lines)


def _to_float(value: Any) -> float:
    """Parse a QS cell to float, mapping ``n/a`` and junk to ``NaN``.

    Values outside the published 0-100 scale are treated as missing rather than
    trusted: a number off that scale means the parser picked up the wrong cell,
    and silently training on it would be worse than dropping it.
    """
    if value is None:
        return float("nan")
    if isinstance(value, bool):
        return float("nan")
    if isinstance(value, (int, float)):
        parsed = float(value)
    else:
        text = str(value).strip()
        if not text or text.lower() == MISSING_TOKEN:
            return float("nan")
        text = text.replace(",", "")
        if not _NUMERIC_RE.match(text):
            return float("nan")
        parsed = float(text)
    if not (VALUE_MIN <= parsed <= VALUE_MAX):
        return float("nan")
    return parsed


def _to_rank(value: Any) -> float:
    """Parse the published rank. Ranges like ``901-950`` take their midpoint."""
    if value is None:
        return float("nan")
    text = str(value).strip().replace(",", "").lstrip("=+")
    if not text:
        return float("nan")
    for sep in ("-", "–", "~"):
        if sep in text:
            parts = [p.strip() for p in text.split(sep) if p.strip()]
            if len(parts) == 2 and all(_NUMERIC_RE.match(p) for p in parts):
                return (float(parts[0]) + float(parts[1])) / 2.0
            return float("nan")
    return float(text) if _NUMERIC_RE.match(text) else float("nan")


def load_snapshot(path: Path | str | None = None) -> list[dict[str, Any]]:
    """Load the crawl snapshot, which is a flat list of university records."""
    snapshot_path = Path(path) if path else DEFAULT_SNAPSHOT
    if not snapshot_path.is_file():
        raise FileNotFoundError(
            f"crawl snapshot not found at {snapshot_path}. Run the pipeline first, "
            "or pass --snapshot with an explicit path."
        )
    with snapshot_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError(f"expected a list of records in {snapshot_path}, got {type(payload).__name__}")
    return payload


def build_feature_matrix(
    records: list[dict[str, Any]],
    *,
    include_region: bool = True,
) -> FeatureMatrix:
    """Turn raw snapshot records into a :class:`FeatureMatrix`.

    ``include_region`` adds the one-hot region block. The nine indicators are
    always present and always first, so a model trained without regions reads
    the same columns as the first nine of a matrix built with them.
    """
    rows: list[dict[str, float]] = []
    targets: list[float] = []
    ranks: list[float] = []
    names: list[str] = []
    countries: list[str] = []

    for record in records:
        metrics = record.get("table_metrics") or {}
        rows.append({name: _to_float(metrics.get(name)) for name in QS_INDICATORS})
        targets.append(_to_float(metrics.get(TARGET_LABEL)))
        ranks.append(_to_rank(record.get(RANK_COLUMN)))
        names.append(str(record.get("name") or "").strip())
        countries.append(str(record.get("country") or "").strip())

    X = pd.DataFrame(rows, columns=list(QS_INDICATORS))
    country_series = pd.Series(countries, name="country")

    if include_region:
        regions = country_series.map(region_for)
        for region in REGION_ORDER:
            X[f"region={region}"] = (regions == region).astype(float)

    return FeatureMatrix(
        X=X,
        y=pd.Series(targets, name=TARGET_LABEL, dtype=float),
        rank=pd.Series(ranks, name=RANK_COLUMN, dtype=float),
        university_name=pd.Series(names, name="university_name"),
        country=country_series,
    )


def missingness_report(matrix: FeatureMatrix) -> pd.DataFrame:
    """Per-indicator missing counts, so imputation is a decision not an accident."""
    indicators = matrix.X[list(QS_INDICATORS)]
    missing = indicators.isna().sum()
    return pd.DataFrame(
        {
            "missing": missing.astype(int),
            "missing_pct": (100.0 * missing / len(indicators)).round(2),
        }
    ).sort_values("missing", ascending=False)


def load_feature_matrix(
    path: Path | str | None = None,
    *,
    include_region: bool = True,
) -> FeatureMatrix:
    """Convenience wrapper: load the snapshot and build the matrix in one call."""
    return build_feature_matrix(load_snapshot(path), include_region=include_region)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and summarise the QS feature matrix.")
    parser.add_argument("--snapshot", default=None, help="Path to last_crawl_snapshot.json")
    parser.add_argument("--no-region", action="store_true", help="Omit the region one-hot block")
    args = parser.parse_args()

    records = load_snapshot(args.snapshot)
    matrix = build_feature_matrix(records, include_region=not args.no_region)

    print(matrix.summary())
    print("\nmissing values per indicator")
    print(missingness_report(matrix).to_string())

    stray = unmapped_countries(list(matrix.country))
    if stray:
        print(f"\n[WARN] {len(stray)} country values fell back to Unknown: {stray}")
    else:
        print("\nall country values map to an explicit region")

    labelled_X, labelled_y = matrix.labelled()
    print(
        f"\ntarget on labelled rows: n={len(labelled_y)} "
        f"min={labelled_y.min():.1f} max={labelled_y.max():.1f} "
        f"mean={labelled_y.mean():.2f} std={labelled_y.std():.2f}"
    )
    assert not np.isnan(labelled_y.to_numpy()).any(), "labelled target must not contain NaN"
    assert labelled_X.shape[0] == len(labelled_y)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
