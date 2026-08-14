"""Write cross-source disagreement probabilities into ``analytics.ml_predictions``.

    PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python \\
        -m ranking_ml.serving.predict_disagreement \\
        --pg-user test --pg-password test --pg-database clawer

    # compute everything, write nothing
    ... -m ranking_ml.serving.predict_disagreement --dry-run

Fits the one-sided classifier on the 820 universities QS and THE both rank, then
scores **every** university QS ranks -- including the ones THE has never covered.
That asymmetry is the point of the model: the probability is useful precisely
where there is no THE verdict to compare against, so a contested institution can
be flagged at QS ingest time rather than after a second source arrives.

Two things this shares with the overall-score job and one it does not.

Shared: predictions land in their own table, never in
``analytics.aggregated_rankings``, and every row carries a support distance so no
consumer can surface a probability without the means to say how far outside the
training data it sits.

Different: the training set is the 820-row overlap rather than a slice of the
ranking table, so it is worth checking where the other 683 universities sit
relative to it. They sit inside it. 96.8% of all 1,503 rows fall within the
training support, against 72.8% for the overall-score model, because the overlap
spans the QS distribution rather than clustering at one end of it the way the
published-score cutoff does. The looser coupling to rank is what makes this
model's coverage the better of the two.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from ranking_ml.features.build_features import DEFAULT_SNAPSHOT, load_feature_matrix
from ranking_ml.features.cross_source import build_cross_source_frame, disagreement_label
from ranking_ml.features.schema import QS_INDICATORS
from ranking_ml.models.support import SupportFlagger
from ranking_ml.serving.predict import (
    collapse_to_one_row_per_university,
    normalise_name,
    resolve_canonical_ids,
)
from ranking_ml.training.train_disagreement import RANDOM_STATE, build_classifiers

MODEL_NAME = "qs_the_disagreement_classifier"
MODEL_IMPLEMENTATION = "gradient_boosting"
TARGET = "qs_the_disagreement"
RANKING_YEAR = 2026
LABEL_QUANTILE = 0.80


def snapshot_version(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return f"qs{RANKING_YEAR}-{digest}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Write disagreement probabilities to PostgreSQL.")
    parser.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="test")
    parser.add_argument("--pg-database", default="clawer")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    snapshot_path = Path(args.snapshot)

    # ---- training set: the QS n THE overlap --------------------------------
    cross = build_cross_source_frame(snapshot_path)
    y_series, threshold = disagreement_label(cross.frame, quantile=LABEL_QUANTILE)
    X_train = cross.frame[list(QS_INDICATORS)]
    y_train = y_series.to_numpy()
    print(cross.summary())
    print(f"label: percentile gap > {threshold:.4f} "
          f"({int(y_train.sum())} positives, {y_train.mean() * 100:.1f}%)")

    # ---- inference set: every university QS ranks ---------------------------
    matrix = load_feature_matrix(snapshot_path)
    X_all = matrix.X[list(QS_INDICATORS)]
    print(f"scoring {len(X_all)} QS universities, {len(X_train)} of which are in the overlap")

    model = build_classifiers()[MODEL_IMPLEMENTATION].fit(X_train, y_train)
    probabilities = model.predict_proba(X_all)[:, 1]

    flagger = SupportFlagger().fit(X_train)
    distances = flagger.distance(X_all)
    supported = distances <= flagger.threshold_

    # ---- metrics stored beside the predictions -----------------------------
    kfold = StratifiedKFold(n_splits=args.folds, shuffle=True, random_state=RANDOM_STATE)
    oof = cross_val_predict(
        build_classifiers()[MODEL_IMPLEMENTATION], X_train, y_train, cv=kfold, method="predict_proba"
    )[:, 1]
    metrics = {
        "roc_auc": round(float(roc_auc_score(y_train, oof)), 4),
        "pr_auc": round(float(average_precision_score(y_train, oof)), 4),
        "brier": round(float(brier_score_loss(y_train, oof)), 4),
        "folds": args.folds,
        "label_quantile": LABEL_QUANTILE,
        "gap_threshold": round(threshold, 4),
        "supported_fraction": round(float(supported.mean()), 4),
    }
    baseline = {
        "roc_auc": 0.5,
        "pr_auc": round(float(y_train.mean()), 4),
        "note": "chance: ROC-AUC 0.5, PR-AUC equal to the positive rate",
    }
    print(f"\nout-of-fold on the overlap: ROC-AUC {metrics['roc_auc']:.4f}  "
          f"PR-AUC {metrics['pr_auc']:.4f}  (chance PR-AUC {baseline['pr_auc']:.4f})")
    print(f"supported: {int(supported.sum())} of {len(X_all)} "
          f"({supported.mean() * 100:.1f}%)")

    frame = pd.DataFrame({
        "university_name": matrix.university_name.to_numpy(),
        "predicted_value": np.round(probabilities, 4),
        "support_distance": np.round(distances, 6),
        "is_supported": supported,
    })

    if args.dry_run:
        print("\n--dry-run: nothing written. Highest-risk rows that would be stored:")
        print(frame.nlargest(5, "predicted_value").to_string(index=False))
        return 0

    try:
        import psycopg2
        from psycopg2.extras import execute_values
    except ImportError:
        print("ERROR psycopg2 is required to write predictions", file=sys.stderr)
        return 2

    connection = psycopg2.connect(
        host=args.pg_host, port=args.pg_port, dbname=args.pg_database,
        user=args.pg_user, password=args.pg_password,
    )

    try:
        ids, unresolved = resolve_canonical_ids(connection, frame["university_name"])
        frame["canonical_university_id"] = ids
        resolved = frame[frame["canonical_university_id"].notna()].copy()
        resolved["canonical_university_id"] = resolved["canonical_university_id"].astype(int)
        dropped_rows = len(frame) - len(resolved)
        print(f"\nresolved {len(resolved)} of {len(frame)} rows to canonical ids "
              f"({dropped_rows} rows dropped, {len(unresolved)} distinct names unmatched)")
        if unresolved:
            print(f"  unmatched names (first 5): {', '.join(unresolved[:5])}")

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
                        int(len(y_train)),
                        int(len(resolved)),
                        json.dumps(list(QS_INDICATORS)),
                        json.dumps(metrics),
                        json.dumps(baseline),
                        float(flagger.threshold_),
                        "Probability that THE places this university substantially "
                        "differently from QS, predicted from QS indicators alone. Trained on "
                        "the 820-university overlap; most scored rows sit outside it, which "
                        "is what the support flag reports.",
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
                        (ml_run_id, int(r.canonical_university_id), RANKING_YEAR,
                         float(r.predicted_value), float(r.support_distance), bool(r.is_supported))
                        for r in resolved.itertuples()
                    ],
                )
        print(f"\nwrote ml_run_id={ml_run_id} with {len(resolved)} predictions")
    finally:
        connection.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
