"""Read access to the modelling layer's estimates.

Reads ``analytics.v_ml_predictions_latest`` and nothing else. The view resolves
"latest run per target" in one place (see ``crawlernest-schema/ml_postgresql.sql``),
so this service never picks a run itself.

Two properties of the view shape this code.

**Targets must be filtered, never merged.** The view holds the latest run *per
target*, so an unfiltered read returns two different quantities interleaved:
``qs_overall_score`` is a 0-100 score and ``qs_the_disagreement`` is a 0-1
probability. Sorting that by ``predicted_value`` buries every score above every
probability, and a caller that read ``predicted_value`` without checking
``target`` would compare the two as if they were the same measurement.
:meth:`MlService.fetch` therefore requires a target and rejects anything else.
``AnalyticsService`` carries the same rule as a comment; here it is an argument.

**Every row is an estimate.** ``ml_predictions.is_estimated`` has a CHECK
constraint that will not let a writer clear it, and ``is_supported`` says whether
the row sits inside the data the model was fitted on. Both are carried out of
here unconditionally, because they are what lets a consumer disclose the value
honestly -- and, concretely, what arms the ``estimate_credited_to_source`` rule
in ``agent/web_agent/generation/provenance.py``. Drop ``isEstimated`` from a row
and golden case faith-105 stops being catchable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from crawlernest.core.database.settings import DatabaseSettings
from crawlernest.core.dataset import DATASET_YEAR

try:
    import psycopg2
except ImportError:  # pragma: no cover
    psycopg2 = None  # type: ignore

#: Estimated QS overall score, 0-100, for universities QS publishes no score for.
TARGET_OVERALL_SCORE = "qs_overall_score"
#: Probability, 0-1, that QS and THE would disagree about a university.
TARGET_DISAGREEMENT = "qs_the_disagreement"

#: The only targets the modelling layer writes. Mirrors the constants in
#: AnalyticsService; test_ml_tools asserts the two lists agree.
TARGETS: tuple[str, ...] = (TARGET_OVERALL_SCORE, TARGET_DISAGREEMENT)

#: Result key each target's ``predicted_value`` is surfaced under. Separate names
#: rather than a shared ``predictedValue`` so a score and a probability cannot be
#: read out of the same field by a caller that forgot to check the target.
_VALUE_KEY = {
    TARGET_OVERALL_SCORE: "estimatedOverallScore",
    TARGET_DISAGREEMENT: "disagreementProbability",
}


@dataclass(slots=True)
class MlPredictionQuery:
    target: str
    year: int = DATASET_YEAR
    canonical_university_ids: tuple[int, ...] = ()
    limit: int = 200


class MlService:
    """Read-only access to stored model estimates."""

    def __init__(self, db_settings: DatabaseSettings | None = None) -> None:
        self._db_settings = db_settings or DatabaseSettings.from_env()

    def fetch(self, query: MlPredictionQuery) -> list[dict[str, Any]]:
        """Estimates for one target, one row per university.

        Returns ``[]`` rather than raising when the modelling tables are absent:
        a deployment that has never run the ML jobs is a normal state, and an
        agent that cannot answer "no estimates" would be unable to answer at all.
        """
        if query.target not in TARGETS:
            raise ValueError(
                f"unknown modelling target {query.target!r}; expected one of {', '.join(TARGETS)}"
            )
        if psycopg2 is None:
            raise RuntimeError("psycopg2 is required for MlService")

        conn = psycopg2.connect(
            host=self._db_settings.host,
            port=self._db_settings.port,
            dbname=self._db_settings.database,
            user=self._db_settings.user,
            password=self._db_settings.password,
        )
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('analytics.v_ml_predictions_latest') IS NOT NULL")
                row = cur.fetchone()
                if not row or not row[0]:
                    return []

                where = ["p.target = %s", "p.ranking_year = %s"]
                params: list[Any] = [query.target, query.year]
                if query.canonical_university_ids:
                    where.append("p.canonical_university_id = ANY(%s)")
                    params.append(list(query.canonical_university_ids))

                cur.execute(
                    f"""
                    SELECT p.canonical_university_id,
                           p.university_name,
                           p.slug,
                           p.country_name,
                           p.ranking_year,
                           p.target,
                           p.predicted_value,
                           p.support_distance,
                           p.is_supported,
                           p.is_estimated,
                           p.model_name,
                           p.model_version,
                           p.support_threshold
                      FROM analytics.v_ml_predictions_latest p
                     WHERE {' AND '.join(where)}
                     ORDER BY p.predicted_value DESC, p.university_name ASC
                     LIMIT %s
                    """,
                    [*params, max(query.limit, 1)],
                )
                rows = cur.fetchall()
        finally:
            conn.close()

        return [self._to_item(row) for row in rows]

    @staticmethod
    def _to_item(row: tuple[Any, ...]) -> dict[str, Any]:
        target = str(row[5])
        item: dict[str, Any] = {
            "canonicalUniversityId": int(row[0]),
            "universityName": str(row[1]),
            "slug": str(row[2]),
            "country": str(row[3]) if row[3] is not None else None,
            "rankingYear": int(row[4]),
            "target": target,
            _VALUE_KEY[target]: float(row[6]),
            "supportDistance": float(row[7]),
            # Never conditional. A consumer that has the value must also have the
            # two flags that say what kind of value it is.
            "isSupported": bool(row[8]),
            "isEstimated": bool(row[9]),
            "modelName": str(row[10]),
            "modelVersion": str(row[11]),
        }
        if row[12] is not None:
            item["supportThreshold"] = float(row[12])
        return item
