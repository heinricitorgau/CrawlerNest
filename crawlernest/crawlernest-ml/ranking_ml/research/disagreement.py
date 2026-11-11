"""The research loop over the cross-source disagreement classifier.

    PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python -m ranking_ml.research.disagreement --loops 20
    ... --proposer llm        # the agent's configured model proposes, inside this space

The same proposer, trace, judge, guard and holdout ledger as the overall-score loop (``loop.py``); what differs is
the space, the runner and the metric.

**The question stays one-sided.** Features are the nine QS indicators only, as in ``train_disagreement``: a
classifier handed THE's scores too is recomputing its own label (the model card's "ceiling"). No spec in this
space can name a THE feature.

**Space.** model (logistic, gradient boosting, random forest) x missing-value strategy (median, knn) x class
weighting (none, balanced). Gradient boosting takes no class weight here, so (gradient_boosting, balanced) is
invalid; a one-axis change that lands on it is repaired to class_weight "none". The baseline is the committed model,
gradient boosting with median imputation.

**Split.** The 1,136 matched universities are split once, stratified on the label at the 80th-percentile gap, into
a search set (75%) and a holdout (25%), seed 0. The gap threshold is the 80th percentile of the *search* rows'
gaps and is then applied to the holdout, so the holdout shapes neither the decisions nor the label's threshold.
(The stratification itself uses a provisional label over all rows, so which rows land in the holdout does depend
on every gap; no score or decision does.)

**Metric.** Decisions use out-of-fold PR-AUC on the search rows (5-fold stratified): the base rate is 20%, and
ROC-AUC flatters imbalanced problems (model card). The report reads the holdout once for the best node and the
baseline, through the ledger, which counts reads across runs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import KNNImputer, SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ranking_ml.features.cross_source import build_cross_source_frame
from ranking_ml.features.schema import QS_INDICATORS
from ranking_ml.research.holdout import DEFAULT_MAX_READS, HoldoutLedger
from ranking_ml.research.loop import DEFAULT_OUT_DIR, ResearchLoop
from ranking_ml.research.proposer import OneChangeProposer, Proposer
from ranking_ml.research.space import InvalidSpec, SearchSpace

RANDOM_STATE = 0
LABEL_QUANTILE = 0.80
HOLDOUT_SHARE = 0.25
SPLIT_RULE = "stratified-25pct-seed0-threshold-from-search-v1"

MODELS: Final[tuple[str, ...]] = ("gradient_boosting", "logistic", "random_forest")
MISSING_STRATEGIES: Final[tuple[str, ...]] = ("median", "knn")
CLASS_WEIGHTS: Final[tuple[str, ...]] = ("none", "balanced")
AXES: Final[dict[str, tuple[Any, ...]]] = {"model": MODELS, "missing": MISSING_STRATEGIES, "class_weight": CLASS_WEIGHTS}


@dataclass(frozen=True)
class DisagreementSpec:
    model: str
    missing: str
    class_weight: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def key(self) -> str:
        return f"{self.model}|{self.missing}|{self.class_weight}"

    def with_change(self, axis: str, value: Any) -> "DisagreementSpec":
        return replace(self, **{axis: value})

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DisagreementSpec":
        try:
            spec = cls(model=data["model"], missing=data["missing"], class_weight=data["class_weight"])
        except KeyError as missing_key:
            raise InvalidSpec(f"spec is missing {missing_key}") from None
        validate(spec)
        return spec


BASELINE: Final[DisagreementSpec] = DisagreementSpec(model="gradient_boosting", missing="median", class_weight="none")


def validate(spec: DisagreementSpec) -> None:
    if spec.model not in MODELS:
        raise InvalidSpec(f"unknown model {spec.model!r}; allowed: {MODELS}")
    if spec.missing not in MISSING_STRATEGIES:
        raise InvalidSpec(f"unknown missing-value strategy {spec.missing!r}; allowed: {MISSING_STRATEGIES}")
    if spec.class_weight not in CLASS_WEIGHTS:
        raise InvalidSpec(f"unknown class weighting {spec.class_weight!r}; allowed: {CLASS_WEIGHTS}")
    if spec.model == "gradient_boosting" and spec.class_weight == "balanced":
        raise InvalidSpec("gradient_boosting takes no class weight in this space")


def _repair(spec: DisagreementSpec, axis: str) -> DisagreementSpec | None:
    try:
        validate(spec)
        return spec
    except InvalidSpec:
        pass
    if axis != "class_weight" and spec.model == "gradient_boosting":
        return spec.with_change("class_weight", "none")
    return None


DISAGREEMENT_SPACE: Final[SearchSpace] = SearchSpace(
    name="disagreement",
    task="classifiers that predict, from QS's nine published indicators alone, whether THE will rank a university "
         "substantially differently",
    axes=AXES,
    baseline=BASELINE,
    baseline_statement="Baseline: gradient boosting with median imputation, no class weighting (the committed model).",
    baseline_reason="The model train_disagreement fits; every change is measured against it.",
    constraint='class_weight="balanced" does not exist for model="gradient_boosting"',
    spec_type=DisagreementSpec,
    validate=validate,
    repair=_repair,
)


def build_classifier(spec: DisagreementSpec) -> Pipeline:
    validate(spec)
    imputer = SimpleImputer(strategy="median") if spec.missing == "median" else KNNImputer(n_neighbors=10)
    weight = None if spec.class_weight == "none" else "balanced"
    if spec.model == "logistic":
        return Pipeline([("impute", imputer), ("scale", StandardScaler()),
                         ("model", LogisticRegression(max_iter=2000, class_weight=weight, random_state=RANDOM_STATE))])
    if spec.model == "random_forest":
        return Pipeline([("impute", imputer), ("model", RandomForestClassifier(
            n_estimators=400, min_samples_leaf=3, class_weight=weight, n_jobs=-1, random_state=RANDOM_STATE))])
    return Pipeline([("impute", imputer), ("model", GradientBoostingClassifier(
        n_estimators=300, learning_rate=0.05, max_depth=3, random_state=RANDOM_STATE))])


@dataclass
class ClassifierResult:
    """What a run measured. ``search_pr_auc`` (out of fold, search rows) is the number decisions use."""

    search_pr_auc: float
    search_roc_auc: float
    search_brier: float
    search_n: int
    search_positives: int

    metric_name = "Search PR-AUC"

    @property
    def search_score(self) -> float:
        return self.search_pr_auc

    def as_dict(self) -> dict[str, Any]:
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in self.__dict__.items()}


@dataclass(frozen=True)
class DisagreementSplit:
    X_search: pd.DataFrame
    y_search: np.ndarray
    X_holdout: pd.DataFrame
    y_holdout: np.ndarray
    threshold: float
    fingerprint: str


def split_frame(frame: pd.DataFrame) -> DisagreementSplit:
    """Search/holdout, with the label threshold taken from the search rows alone."""
    gap = frame["percentile_gap"].to_numpy()
    provisional = (gap > np.quantile(gap, LABEL_QUANTILE)).astype(int)
    idx_search, idx_holdout = train_test_split(
        np.arange(len(frame)), test_size=HOLDOUT_SHARE, stratify=provisional, random_state=RANDOM_STATE)
    threshold = float(np.quantile(gap[idx_search], LABEL_QUANTILE))
    y = (gap > threshold).astype(int)
    X = frame[list(QS_INDICATORS)].reset_index(drop=True)
    # The holdout's identity for the ledger: the rows and labels it is made of, not the files that fed them.
    digest = hashlib.sha256(
        pd.util.hash_pandas_object(frame[list(QS_INDICATORS) + ["percentile_gap"]].reset_index(drop=True)).values.tobytes()
        + idx_holdout.tobytes()
    ).hexdigest()[:16]
    return DisagreementSplit(
        X_search=X.iloc[idx_search], y_search=y[idx_search],
        X_holdout=X.iloc[idx_holdout], y_holdout=y[idx_holdout],
        threshold=threshold, fingerprint=f"{digest}:{SPLIT_RULE}",
    )


class DisagreementRunner:
    report_caveats = [
        "Features are QS's nine published indicators only; THE's scores never enter, so this predicts disagreement "
        "rather than recomputing it.",
        "The label is a gap above the 80th percentile of the search rows' QS-THE percentile gaps; it is applied "
        "unchanged to the holdout. About 20% of rows are positive, so PR-AUC is read against a ~0.20 base rate.",
        "Every probability here is a model estimate; nothing is written to the warehouse or to analytics.ml_predictions.",
    ]

    def __init__(self, split: DisagreementSplit, folds: int = 5) -> None:
        self._split = split
        self._folds = folds

    def run(self, spec: DisagreementSpec) -> ClassifierResult:
        s = self._split
        kfold = StratifiedKFold(n_splits=self._folds, shuffle=True, random_state=RANDOM_STATE)
        proba = cross_val_predict(build_classifier(spec), s.X_search, s.y_search, cv=kfold, method="predict_proba")[:, 1]
        return ClassifierResult(
            search_pr_auc=float(average_precision_score(s.y_search, proba)),
            search_roc_auc=float(roc_auc_score(s.y_search, proba)),
            search_brier=float(brier_score_loss(s.y_search, proba)),
            search_n=int(len(s.y_search)),
            search_positives=int(s.y_search.sum()),
        )

    def score_holdout(self, spec: DisagreementSpec) -> dict[str, float]:
        s = self._split
        proba = build_classifier(spec).fit(s.X_search, s.y_search).predict_proba(s.X_holdout)[:, 1]
        return {
            "pr_auc": round(float(average_precision_score(s.y_holdout, proba)), 4),
            "roc_auc": round(float(roc_auc_score(s.y_holdout, proba)), 4),
            "brier": round(float(brier_score_loss(s.y_holdout, proba)), 4),
            "n": int(len(s.y_holdout)),
            "positives": int(s.y_holdout.sum()),
            "base_rate": round(float(s.y_holdout.mean()), 4),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the research loop over the disagreement classifier.")
    parser.add_argument("--loops", type=int, default=20)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--min-delta", type=float, default=0.005,
                        help="PR-AUC a change must gain over the best node; ~280 positives make smaller gains noise")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--proposer", choices=("rule", "llm"), default="rule")
    parser.add_argument("--max-holdout-reads", type=int, default=DEFAULT_MAX_READS)
    parser.add_argument("--allow-holdout-reread", action="store_true")
    args = parser.parse_args()

    split = split_frame(build_cross_source_frame().frame)
    print(f"search {len(split.y_search)} rows ({int(split.y_search.sum())} positive), holdout {len(split.y_holdout)} "
          f"({int(split.y_holdout.sum())} positive); gap threshold {split.threshold:.4f} from the search rows")
    proposer: Proposer = OneChangeProposer(DISAGREEMENT_SPACE)
    if args.proposer == "llm":
        from ranking_ml.research.llm_proposer import llm_proposer
        from ranking_ml.research.loop import _agent_complete

        proposer = llm_proposer(_agent_complete(), DISAGREEMENT_SPACE)
    loop = ResearchLoop(DisagreementRunner(split, folds=args.folds), proposer, min_delta=args.min_delta)
    for _ in range(args.loops):
        if not loop.step():
            print("proposer exhausted the space")
            break
        i = len(loop.trace.hist) - 1
        exp, fb = loop.trace.hist[i]
        score = "error" if exp.result is None else f"{exp.result.search_score:.4f}"
        print(f"[{i:>2}] parent={exp.hypothesis.parent_index!s:>4}  {exp.spec.key():<40} "
              f"PR-AUC {score:<7} {'ACCEPT' if fb else 'reject'}  {fb.reason}")

    ledger = HoldoutLedger(Path(args.out_dir) / "holdout_ledger.json", f"disagreement:{split.fingerprint}",
                           max_reads=args.max_holdout_reads)
    report = loop.report(ledger, allow_reread=args.allow_holdout_reread)
    report["model"] = "disagreement"
    report["split"] = {"rule": SPLIT_RULE, "threshold": round(split.threshold, 4),
                       "search_rows": int(len(split.y_search)), "holdout_rows": int(len(split.y_holdout))}
    if "holdout_withheld" in report:
        print(f"\nholdout not read: {report['holdout_withheld']}")
    if "holdout" in report:
        best, base = report["holdout"]["best"], report["holdout"]["baseline"]
        print(f"\nholdout  best PR-AUC {best['pr_auc']:.4f} ROC-AUC {best['roc_auc']:.4f}  "
              f"({DisagreementSpec(**best['spec']).key()})")
        print(f"holdout  base PR-AUC {base['pr_auc']:.4f} ROC-AUC {base['roc_auc']:.4f}  "
              f"({DisagreementSpec(**base['spec']).key()})  base rate {base['base_rate']:.3f}")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"disagreement_research_{stamp}.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"report -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
