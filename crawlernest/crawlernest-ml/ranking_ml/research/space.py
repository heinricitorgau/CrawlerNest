"""The experiment space: every estimator a hypothesis is allowed to name.

An :class:`ExperimentSpec` is three choices -- the model, how missing indicators
are handled, and whether the region one-hot block is read. RD-Agent's
``Hypothesis2Experiment`` turns an idea into a task for its coder; here
:func:`build_estimator` turns a spec into a fitted-ready sklearn estimator, and a
spec it cannot build is an error, not an experiment.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any, Final

from sklearn.base import BaseEstimator
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import KNNImputer, SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ranking_ml.features.schema import QS_INDICATORS
from ranking_ml.models.overall_score import RANDOM_STATE, RenormalisedWeightedScore

MODELS: Final[tuple[str, ...]] = ("linear", "ridge", "random_forest", "gradient_boosting")
MISSING_STRATEGIES: Final[tuple[str, ...]] = ("median", "knn", "renormalise")
REGION_OPTIONS: Final[tuple[bool, ...]] = (False, True)

#: The three axes a single hypothesis may change, in the order the built-in
#: proposer tries them.
AXES: Final[dict[str, tuple[Any, ...]]] = {
    "missing": MISSING_STRATEGIES,
    "model": MODELS,
    "region": REGION_OPTIONS,
}


class InvalidSpec(ValueError):
    """A spec names a component outside the space, or an impossible combination."""


@dataclass(frozen=True)
class ExperimentSpec:
    model: str
    missing: str
    region: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def key(self) -> str:
        return f"{self.model}|{self.missing}|{'region' if self.region else 'no-region'}"

    def with_change(self, axis: str, value: Any) -> "ExperimentSpec":
        return replace(self, **{axis: value})

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExperimentSpec":
        try:
            spec = cls(model=data["model"], missing=data["missing"], region=bool(data["region"]))
        except KeyError as missing_key:
            raise InvalidSpec(f"spec is missing {missing_key}") from None
        validate(spec)
        return spec


#: Where the loop starts: the model ``train_overall_score`` recommends for the
#: withheld rows. Every hypothesis is a departure from a node that descends from it.
BASELINE: Final[ExperimentSpec] = ExperimentSpec(model="linear", missing="renormalise", region=False)


def validate(spec: ExperimentSpec) -> None:
    if spec.model not in MODELS:
        raise InvalidSpec(f"unknown model {spec.model!r}; allowed: {MODELS}")
    if spec.missing not in MISSING_STRATEGIES:
        raise InvalidSpec(f"unknown missing-value strategy {spec.missing!r}; allowed: {MISSING_STRATEGIES}")
    # Renormalisation is a property of the weighted average, so it only exists
    # for the linear weighting, and that weighting reads the indicators alone.
    if spec.missing == "renormalise" and (spec.model != "linear" or spec.region):
        raise InvalidSpec("renormalise applies only to the linear model without the region block")


def is_valid(spec: ExperimentSpec) -> bool:
    try:
        validate(spec)
    except InvalidSpec:
        return False
    return True


def _imputer(strategy: str):
    if strategy == "median":
        return SimpleImputer(strategy="median")
    return KNNImputer(n_neighbors=10)


def _model(name: str):
    if name == "linear":
        return LinearRegression()
    if name == "ridge":
        return Ridge(alpha=1.0, random_state=RANDOM_STATE)
    if name == "random_forest":
        return RandomForestRegressor(n_estimators=300, min_samples_leaf=2, n_jobs=-1, random_state=RANDOM_STATE)
    return GradientBoostingRegressor(n_estimators=300, learning_rate=0.05, max_depth=3, random_state=RANDOM_STATE)


def build_estimator(spec: ExperimentSpec) -> BaseEstimator:
    validate(spec)
    if spec.missing == "renormalise":
        return RenormalisedWeightedScore()

    if spec.region:
        prepare = Pipeline([("impute", _imputer(spec.missing))])
    else:
        prepare = ColumnTransformer(
            [("indicators", _imputer(spec.missing), list(QS_INDICATORS))],
            remainder="drop",
        )
    steps: list[tuple[str, Any]] = [("prepare", prepare)]
    if spec.model == "ridge":
        steps.append(("scale", StandardScaler()))
    steps.append(("model", _model(spec.model)))
    return Pipeline(steps)
