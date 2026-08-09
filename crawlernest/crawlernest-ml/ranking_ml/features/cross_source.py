"""Join the QS and THE snapshots into one cross-source frame.

Two ranking bodies score the same universities on different criteria and reach
different conclusions. This module assembles the rows where both published a
verdict, so the disagreement can be modelled instead of asserted.

Matching is exact on a normalised name (case, punctuation and whitespace
stripped). That is deliberately conservative: it under-matches rather than
risking a wrong pairing, and every downstream number is therefore a lower bound
on the available overlap. Fuzzy matching would raise the count but would need
its own evaluation before its output could be trusted here -- the repo already
has an unresolved-entity report for exactly that problem.

THE publishes its five pillar scores numerically for all 2,191 rows. Its
*overall* score is banded for all but the top 201, which is why the label is
built from published ranks rather than from overall scores.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ranking_ml.features.build_features import DEFAULT_SNAPSHOT, load_snapshot, _to_float, _to_rank
from ranking_ml.features.schema import QS_INDICATORS

_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_THE_SNAPSHOT = _REPO_ROOT / "crawlernest" / "crawlernest-kb" / "databases" / "the_rankings_2026.json"

#: THE's five pillars, in fixed column order.
THE_PILLARS: tuple[str, ...] = (
    "scores_teaching",
    "scores_research",
    "scores_citations",
    "scores_industry_income",
    "scores_international_outlook",
)

THE_FEATURE_NAMES: tuple[str, ...] = tuple(
    "THE " + name.removeprefix("scores_").replace("_", " ") for name in THE_PILLARS
)


def normalise_name(name: Any) -> str:
    """Lowercase, letters only. Collapses 'The University of X' style variation."""
    return re.sub(r"[^a-z]", "", str(name or "").lower())


def load_the_snapshot(path: Path | str | None = None) -> list[dict[str, Any]]:
    snapshot_path = Path(path) if path else DEFAULT_THE_SNAPSHOT
    if not snapshot_path.is_file():
        raise FileNotFoundError(f"THE snapshot not found at {snapshot_path}")
    with snapshot_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    rows = payload.get("rows") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise ValueError(f"expected a list of rows in {snapshot_path}")
    return rows


@dataclass(frozen=True)
class CrossSourceFrame:
    """Universities ranked by both QS and THE, with each source's features."""

    frame: pd.DataFrame
    qs_population: int
    the_population: int

    @property
    def feature_names(self) -> list[str]:
        return list(QS_INDICATORS) + list(THE_FEATURE_NAMES)

    def features(self) -> pd.DataFrame:
        return self.frame[self.feature_names]

    def summary(self) -> str:
        return (
            f"matched {len(self.frame)} universities "
            f"(QS population {self.qs_population}, THE population {self.the_population})"
        )


def build_cross_source_frame(
    qs_path: Path | str | None = None,
    the_path: Path | str | None = None,
) -> CrossSourceFrame:
    """Inner-join QS and THE on normalised name, keeping both sides' features.

    Percentiles are computed against each source's **full** population, not the
    overlap, so a university's standing means "top x% of what QS ranked" rather
    than "top x% of the subset that happens to appear in both".
    """
    qs_records = load_snapshot(qs_path or DEFAULT_SNAPSHOT)
    the_records = load_the_snapshot(the_path)

    qs_rows = []
    for record in qs_records:
        metrics = record.get("table_metrics") or {}
        row = {"key": normalise_name(record.get("name")), "qs_name": record.get("name")}
        row["qs_rank"] = _to_rank(record.get("rank"))
        for name in QS_INDICATORS:
            row[name] = _to_float(metrics.get(name))
        qs_rows.append(row)
    qs = pd.DataFrame(qs_rows)

    the_rows = []
    for record in the_records:
        raw = (record.get("metadata") or {}).get("raw_row") or {}
        row = {"key": normalise_name(record.get("name")), "the_name": record.get("name")}
        row["the_rank"] = _to_rank(record.get("rank"))
        for pillar, label in zip(THE_PILLARS, THE_FEATURE_NAMES):
            row[label] = _to_float(raw.get(pillar))
        the_rows.append(row)
    the = pd.DataFrame(the_rows)

    qs_population = int(qs["qs_rank"].notna().sum())
    the_population = int(the["the_rank"].notna().sum())

    # Percentile within each source's own population, 0 = best.
    qs["qs_percentile"] = qs["qs_rank"].rank(method="average", pct=True)
    the["the_percentile"] = the["the_rank"].rank(method="average", pct=True)

    # Drop duplicate keys before joining so a name collision cannot fan out.
    qs = qs.drop_duplicates("key", keep="first")
    the = the.drop_duplicates("key", keep="first")

    merged = qs.merge(the, on="key", how="inner")
    merged = merged[merged["qs_rank"].notna() & merged["the_rank"].notna()].reset_index(drop=True)
    merged["percentile_gap"] = (merged["qs_percentile"] - merged["the_percentile"]).abs()
    merged["favoured_by"] = np.where(
        merged["qs_percentile"] < merged["the_percentile"], "QS", "THE"
    )

    return CrossSourceFrame(frame=merged, qs_population=qs_population, the_population=the_population)


def disagreement_label(frame: pd.DataFrame, *, quantile: float = 0.80) -> tuple[pd.Series, float]:
    """Binary disagreement label and the gap threshold that produced it.

    The threshold is a quantile of the observed gap rather than a round number,
    so the positive rate is a stated design choice (``1 - quantile``) instead of
    an accident of where a hand-picked cutoff happened to land. Sensitivity to
    this choice is reported by the training run.
    """
    threshold = float(frame["percentile_gap"].quantile(quantile))
    return (frame["percentile_gap"] > threshold).astype(int), threshold
