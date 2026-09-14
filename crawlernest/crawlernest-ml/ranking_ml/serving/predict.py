"""Write overall-score estimates into ``analytics.ml_predictions``.

    PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python -m ranking_ml.serving.predict \\
        --pg-user test --pg-password test --pg-database clawer

    # inspect without touching the database
    ... -m ranking_ml.serving.predict --dry-run

Fits the recommended estimator on the 705 universities QS publishes an overall
score for, predicts the 799 it withholds one from, and stores each prediction
with the support distance that says how far outside the training data it sits.

Three things this deliberately does:

**It writes only to its own tables.** ``analytics.aggregated_rankings`` is never
touched. A published rank and a model's estimate of a withheld score are
different kinds of claim, and the schema keeps them apart.

**It resolves names rather than assuming them.** Snapshot names and canonical
universities are not one-to-one, because entity resolution merges variant
spellings. Rows that do not resolve are reported and skipped, never guessed at.

**It replaces its own previous run atomically.** Each run inserts a fresh
``ml_model_runs`` row and its predictions in one transaction, so a reader either
sees the whole previous run or the whole new one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from ranking_ml.evaluation.baselines import published_weight_prediction
from ranking_ml.evaluation.metrics import rank_agreement, regression_metrics
from ranking_ml.features.build_features import DEFAULT_SNAPSHOT, load_feature_matrix
from ranking_ml.models.overall_score import build_pipelines
from ranking_ml.models.support import SupportFlagger
from ranking_ml.training.train_overall_score import cross_validate_pipeline

MODEL_NAME = "qs_overall_score_estimator"
MODEL_IMPLEMENTATION = "linear_renorm"
TARGET = "qs_overall_score"
RANKING_YEAR = 2026


def normalise_name(name: object) -> str:
    """Lowercase, letters only -- the same rule used for the QS/THE join."""
    return re.sub(r"[^a-z]", "", str(name or "").lower())


def snapshot_version(path: Path) -> str:
    """Content-addressed version, so a rerun on the same data reuses the label."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return f"qs{RANKING_YEAR}-{digest}"


def collapse_to_one_row_per_university(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Keep one prediction per canonical university, and say how many were dropped.

    Entity resolution merges variant spellings, so several snapshot rows can
    resolve to the same canonical university. ``ml_predictions`` is unique on
    ``(ml_run_id, canonical_university_id, ranking_year)``, so writing the
    unmerged rows aborts the whole insert on a duplicate key.

    The first row wins. The snapshot is ordered by published rank, so that is the
    best-ranked spelling of the university rather than an arbitrary one.
    """
    before = len(frame)
    deduped = frame.drop_duplicates(subset="canonical_university_id", keep="first")
    return deduped, before - len(deduped)


def resolve_canonical_ids(connection, names: pd.Series) -> tuple[pd.Series, list[str]]:
    """Map university names to canonical ids, reporting what did not resolve.

    Returns ``(ids, unresolved_names)``; ``ids`` carries NaN where no canonical
    university matched.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT canonical_university_id, display_name FROM warehouse.canonical_university"
        )
        rows = cursor.fetchall()

    by_key: dict[str, int] = {}
    collisions: set[str] = set()
    for canonical_id, display_name in rows:
        key = normalise_name(display_name)
        if not key:
            continue
        if key in by_key:
            collisions.add(key)
            continue
        by_key[key] = int(canonical_id)

    keys = names.map(normalise_name)
    ids = keys.map(by_key)
    unresolved = sorted({name for name, key in zip(names, keys) if key not in by_key})
    if collisions:
        print(f"  [WARN] {len(collisions)} normalised names are ambiguous in the warehouse; "
              "first id kept for each")
    return ids, unresolved


def main() -> int:
    parser = argparse.ArgumentParser(description="Write overall-score estimates to PostgreSQL.")
    parser.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="test")
    parser.add_argument("--pg-database", default="clawer")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true", help="Compute everything, write nothing")
    args = parser.parse_args()

    snapshot_path = Path(args.snapshot)
    matrix = load_feature_matrix(snapshot_path)
    X_lab, y_lab = matrix.labelled()
    X_unlab = matrix.unlabelled()
    unlabelled_index = (~matrix.labelled_mask).to_numpy()

    print(matrix.summary())

    # ---- fit -------------------------------------------------------------
    model = build_pipelines()[MODEL_IMPLEMENTATION].fit(X_lab, y_lab)
    flagger = SupportFlagger().fit(X_lab)

    predictions = model.predict(X_unlab)
    distances = flagger.distance(X_unlab)
    supported = distances <= flagger.threshold_

    # ---- metrics stored alongside the estimates --------------------------
    cv, _ = cross_validate_pipeline(build_pipelines()[MODEL_IMPLEMENTATION], X_lab, y_lab, args.folds)
    baseline = regression_metrics(y_lab.to_numpy(), published_weight_prediction(X_lab))
    ranks = matrix.rank.loc[~matrix.labelled_mask].to_numpy()
    agreement = rank_agreement(predictions, ranks)

    metrics = {
        **cv.as_dict(),
        "rank_agreement_spearman": round(agreement["spearman"], 4),
        "supported_fraction": round(float(supported.mean()), 4),
    }
    print(f"\ncross-validated on the labelled rows: {cv}")
    print(f"baseline (QS published weights):      {baseline}")
    print(f"rank agreement on the withheld rows:  spearman {agreement['spearman']:+.4f}")
    print(f"supported:                            {int(supported.sum())} of {len(predictions)}")

    frame = pd.DataFrame(
        {
            "university_name": matrix.university_name[unlabelled_index].to_numpy(),
            "predicted_value": np.round(predictions, 4),
            "support_distance": np.round(distances, 6),
            "is_supported": supported,
        }
    )

    if args.dry_run:
        print("\n--dry-run: nothing written. First 5 rows that would be stored:")
        print(frame.head().to_string(index=False))
        return 0

    try:
        import psycopg2
        from psycopg2.extras import execute_values
    except ImportError:
        print("ERROR psycopg2 is required to write predictions; install requirements.txt", file=sys.stderr)
        return 2

    connection = psycopg2.connect(
        host=args.pg_host,
        port=args.pg_port,
        dbname=args.pg_database,
        user=args.pg_user,
        password=args.pg_password,
    )

    try:
        ids, unresolved = resolve_canonical_ids(connection, frame["university_name"])
        frame["canonical_university_id"] = ids
        resolved = frame[frame["canonical_university_id"].notna()].copy()
        resolved["canonical_university_id"] = resolved["canonical_university_id"].astype(int)

        # Rows and names are different counts and it matters which is reported:
        # several snapshot rows can share a name, and entity resolution merges
        # some names onto one canonical university.
        # Rows and names are different counts and it matters which is reported:
        # several snapshot rows can share a name, and entity resolution merges
        # some names onto one canonical university.
        dropped_rows = len(frame) - len(resolved)
        print(
            f"\nresolved {len(resolved)} of {len(frame)} rows to canonical ids "
            f"({dropped_rows} rows dropped, {len(unresolved)} distinct names unmatched)"
        )
        if unresolved:
            preview = ", ".join(unresolved[:5])
            print(f"  unmatched names (first 5): {preview}")

        resolved, merged = collapse_to_one_row_per_university(resolved)
        if merged:
            print(f"  {merged} rows resolved onto a university already covered; "
                  "kept the best-ranked spelling of each")

        if resolved.empty:
            print("ERROR nothing resolved; refusing to write an empty run", file=sys.stderr)
            return 1

        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO analytics.ml_model_runs (
                        model_name, model_version, target, training_rows, inference_rows,
                        feature_names_json, metrics_json, baseline_metrics_json,
                        support_threshold, notes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING ml_run_id
                    """,
                    (
                        MODEL_NAME,
                        snapshot_version(snapshot_path),
                        TARGET,
                        int(len(y_lab)),
                        int(len(resolved)),
                        json.dumps(list(X_lab.columns)),
                        json.dumps(metrics),
                        json.dumps(baseline.as_dict()),
                        float(flagger.threshold_),
                        "Estimates for universities whose overall score QS withholds "
                        f"(ranks {int(ranks.min())} and below). Cross-validated error "
                        "describes recovery of QS's scoring function on the labelled rows, "
                        "not error on these.",
                    ),
                )
                ml_run_id = cursor.fetchone()[0]

                execute_values(
                    cursor,
                    """
                    INSERT INTO analytics.ml_predictions (
                        ml_run_id, canonical_university_id, ranking_year,
                        predicted_value, support_distance, is_supported
                    ) VALUES %s
                    """,
                    [
                        (
                            ml_run_id,
                            int(row.canonical_university_id),
                            RANKING_YEAR,
                            float(row.predicted_value),
                            float(row.support_distance),
                            bool(row.is_supported),
                        )
                        for row in resolved.itertuples()
                    ],
                )

        print(f"\nwrote ml_run_id={ml_run_id} with {len(resolved)} predictions")
    finally:
        connection.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
