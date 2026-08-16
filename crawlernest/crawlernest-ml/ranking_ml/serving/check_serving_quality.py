"""Measure the quality of what serving actually wrote, not just its shape.

    PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python \\
        -m ranking_ml.serving.check_serving_quality \\
        --pg-user test --pg-password test --pg-database clawer

``verify_predictions`` checks structure: both targets present, values on the
right scale, disclosure columns intact. All of that passes for a model that has
silently become useless, because a wrong number is the same shape as a right
one. This is the missing half.

## Why quality is measurable here at all

Neither model has its label available at serving time -- that is the point of
both of them. But each has something the label is a monotone function of, and
that something is published:

``qs_overall_score``
    QS withholds the score for ranks 601-1503 and publishes the rank. Rank
    orders the true score, so the rank correlation between what was served and
    what QS published is a real accuracy measure on exactly the rows that were
    served. The training run records its own expectation as
    ``metrics_json.rank_agreement_spearman``, so there is something to regress
    against rather than a number to admire.

``qs_the_disagreement``
    The label is derived from both sources' ranks, and for the universities both
    sources rank, both ranks are in the warehouse. Observed disagreement is
    therefore computable for that subset, and the served probabilities can be
    scored against it.

## What this deliberately does not do

It does not retrain, and it does not compare against the evaluation set. The
question is whether the rows in the database are any good, which is a different
question from whether the model was any good when it was fitted, and the second
has been answered by the metrics gate since Phase 2.

Support is reported split rather than pooled. A model whose supported
predictions are strong and whose unsupported ones are weak is behaving as the
support flag claims; one where the two are equal means the flag is not
measuring anything.

Exit 0 when every check passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import sys

#: Correlation is negative by construction -- a higher predicted score means a
#: better, numerically smaller, rank -- so the guard is on the magnitude.
MIN_RANK_AGREEMENT = 0.90

#: How far the served correlation may fall below what the training run recorded
#: before it counts as a regression rather than noise. Serving and evaluation
#: run on the same snapshot, so agreement should be close to exact; this is
#: slack for imputation and join differences, not for a worse model.
MAX_AGREEMENT_SHORTFALL = 0.02

#: Below this the disagreement probabilities are no better than guessing.
MIN_DISAGREEMENT_AUC = 0.60

#: A support flag that never fires, or fires on everything, is not a measurement.
MIN_SUPPORTED_FRACTION = 0.10
MAX_SUPPORTED_FRACTION = 0.999


def _fetch(cur, sql, params=None):
    cur.execute(sql, params or ())
    return cur.fetchall()


def _published_qs_ranks() -> dict[str, float]:
    """Published QS rank per university name, from the committed snapshot.

    Read from the snapshot rather than from analytics.aggregated_rankings so the
    check does not depend on the aggregation having been run. The CI serving job
    bootstraps a database, seeds canonical universities from this same snapshot
    and writes predictions -- it never builds the analytics tables, so a check
    that needed them would skip exactly where it is meant to run.
    """
    from ranking_ml.features.build_features import _to_rank, load_snapshot

    ranks: dict[str, float] = {}
    for record in load_snapshot():
        rank = _to_rank(record.get("rank"))
        name = str(record.get("name") or "").strip()
        if name and rank is not None:
            ranks[name] = float(rank)
    return ranks


def check_overall_score(cur, failures: list[str]) -> None:
    from scipy.stats import spearmanr

    published = _published_qs_ranks()
    served = _fetch(cur, """
        SELECT cu.display_name, p.predicted_value::float, p.is_supported
        FROM analytics.v_ml_predictions_latest p
        JOIN warehouse.canonical_university cu
          ON cu.canonical_university_id = p.canonical_university_id
        WHERE p.target = 'qs_overall_score'
    """)
    rows = [
        (value, published[str(name)], supported)
        for name, value, supported in served
        if str(name) in published
    ]
    print("\n### qs_overall_score — served scores against published ranks")
    if len(rows) < 100:
        failures.append(
            f"qs_overall_score: only {len(rows)} served rows join to a published QS rank; "
            "there is not enough to judge quality on"
        )
        print(f"  rows joined to a rank: {len(rows)}  -- too few")
        return

    scores = [r[0] for r in rows]
    ranks = [r[1] for r in rows]
    rho = float(spearmanr(scores, ranks).statistic)
    print(f"  rows                       {len(rows)}")
    print(f"  Spearman vs published rank {rho:+.4f}   (negative is correct)")

    if abs(rho) < MIN_RANK_AGREEMENT:
        failures.append(
            f"qs_overall_score: rank agreement |{rho:.4f}| is below {MIN_RANK_AGREEMENT}. "
            "The served scores no longer order universities the way QS does."
        )
    if rho > 0:
        failures.append(
            f"qs_overall_score: rank agreement is {rho:+.4f}, the wrong sign. A higher "
            "predicted score is coming out with a worse published rank, which means the "
            "target or the join is inverted."
        )

    recorded = _fetch(cur, """
        SELECT (metrics_json ->> 'rank_agreement_spearman')::float
        FROM analytics.ml_model_runs
        WHERE target = 'qs_overall_score'
          AND metrics_json ? 'rank_agreement_spearman'
        ORDER BY trained_at DESC LIMIT 1
    """)
    if recorded and recorded[0][0] is not None:
        expected = abs(float(recorded[0][0]))
        shortfall = expected - abs(rho)
        print(f"  the training run recorded  {expected:.4f}   shortfall {shortfall:+.4f}")
        if shortfall > MAX_AGREEMENT_SHORTFALL:
            failures.append(
                f"qs_overall_score: served agreement {abs(rho):.4f} is {shortfall:.4f} below "
                f"the {expected:.4f} the training run recorded. Serving and evaluation run "
                "on the same snapshot, so they should not disagree by this much."
            )
    else:
        print("  the training run recorded  (none) -- nothing to regress against")

    _report_support_split(rows, "qs_overall_score", failures, spearmanr)


def _report_support_split(rows, target, failures, spearmanr) -> None:
    supported = [(s, k) for s, k, ok in rows if ok]
    unsupported = [(s, k) for s, k, ok in rows if not ok]
    fraction = len(supported) / len(rows)
    print(f"  supported                  {len(supported)} of {len(rows)}  ({fraction:.1%})")

    if not MIN_SUPPORTED_FRACTION <= fraction <= MAX_SUPPORTED_FRACTION:
        failures.append(
            f"{target}: {fraction:.1%} of predictions are flagged supported. A flag that "
            "fires on almost everything or almost nothing is not measuring distance from "
            "the training data."
        )

    if len(supported) > 30 and len(unsupported) > 30:
        rho_s = abs(float(spearmanr([s for s, _ in supported], [k for _, k in supported]).statistic))
        rho_u = abs(float(spearmanr([s for s, _ in unsupported], [k for _, k in unsupported]).statistic))
        print(f"  agreement, supported       {rho_s:.4f}")
        print(f"  agreement, unsupported     {rho_u:.4f}")
        if rho_u > rho_s:
            failures.append(
                f"{target}: predictions flagged unsupported agree with published ranks "
                f"better ({rho_u:.4f}) than supported ones ({rho_s:.4f}). The support flag "
                "is pointing the wrong way."
            )


def check_disagreement(cur, failures: list[str]) -> None:
    from sklearn.metrics import roc_auc_score

    # Same reasoning as the overall-score check: the ranks come from the
    # committed snapshots and the reviewed pairing, not from the analytics
    # tables, so this runs wherever the serving jobs run.
    from ranking_ml.features.build_features import _to_rank
    from ranking_ml.features.cross_source import load_pairing, load_the_snapshot

    published_qs = _published_qs_ranks()
    the_ranks = {
        str(record.get("name") or "").strip(): float(_to_rank(record.get("rank")))
        for record in load_the_snapshot()
        if _to_rank(record.get("rank")) is not None
    }
    pairing = load_pairing()

    served = _fetch(cur, """
        SELECT cu.display_name, p.predicted_value::float
        FROM analytics.v_ml_predictions_latest p
        JOIN warehouse.canonical_university cu
          ON cu.canonical_university_id = p.canonical_university_id
        WHERE p.target = 'qs_the_disagreement'
    """)
    rows = []
    for name, value in served:
        qs_name = str(name)
        the_name = pairing.get(qs_name)
        if qs_name in published_qs and the_name in the_ranks:
            rows.append((value, published_qs[qs_name], the_ranks[the_name]))

    print("\n### qs_the_disagreement — served probabilities against observed disagreement")
    print(f"  universities both sources rank: {len(rows)}")
    if len(rows) < 100:
        print("  too few to score; skipped")
        return

    qs_ranks = sorted(r[1] for r in rows)
    the_ranks = sorted(r[2] for r in rows)

    def percentile(sorted_values, value):
        from bisect import bisect_left
        return bisect_left(sorted_values, value) / len(sorted_values)

    gaps = [abs(percentile(qs_ranks, r[1]) - percentile(the_ranks, r[2])) for r in rows]
    cutoff = sorted(gaps)[int(0.80 * len(gaps))]
    observed = [1 if g > cutoff else 0 for g in gaps]
    predicted = [r[0] for r in rows]

    positives = sum(observed)
    print(f"  observed disagreements        {positives} ({positives / len(observed):.1%}) "
          f"at gap > {cutoff:.4f}")
    if positives < 20 or positives == len(observed):
        print("  degenerate label on this subset; skipped")
        return

    auc = float(roc_auc_score(observed, predicted))
    print(f"  ROC-AUC of served probability {auc:.4f}")
    if auc < MIN_DISAGREEMENT_AUC:
        failures.append(
            f"qs_the_disagreement: served probabilities score {auc:.4f} against observed "
            f"disagreement, at or near the {0.5:.2f} of guessing. The rows in the database "
            "carry no signal even though the model was evaluated as having some."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Score the served predictions against published data.")
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="test")
    parser.add_argument("--pg-database", default="clawer")
    args = parser.parse_args()

    try:
        import psycopg2
    except ImportError:
        print("psycopg2 is required")
        return 1

    conn = psycopg2.connect(
        host=args.pg_host, port=args.pg_port, user=args.pg_user,
        password=args.pg_password, dbname=args.pg_database,
    )
    failures: list[str] = []
    try:
        with conn.cursor() as cur:
            check_overall_score(cur, failures)
            check_disagreement(cur, failures)
    finally:
        conn.close()

    print()
    if failures:
        print(f"FAIL -- {len(failures)} problem(s):")
        for failure in failures:
            print(f"  - {failure}")
        print(
            "\nThese are measured on the rows in the database, not on the evaluation set. "
            "A failure here means what is being served is worse than what was evaluated, "
            "which the metrics gate cannot see."
        )
        return 1

    print("PASS -- the served predictions agree with the published data they can be checked against.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
