"""Check what the serving jobs actually wrote.

    PYTHONPATH=crawlernest/crawlernest-ml ./.venv/bin/python \\
        -m ranking_ml.serving.verify_predictions \\
        --pg-user test --pg-password test --pg-database clawer

Running a serving job to exit 0 only proves it did not crash. This checks the
rows: that both targets are present, that each value is on the scale its target
implies, that the disclosure columns say what they must, and that the view the
API reads returns one run per target rather than a pile of them.

The scale check is the one that matters most. A 0-1 probability and a 0-100
score share a column, so a job writing to the wrong target, or a view returning
two targets at once, shows up here as a value in the wrong range rather than as
a plausible-looking number in the API.

Exit 0 when every check passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import sys

EXPECTED = {
    "qs_overall_score": {"low": 0.0, "high": 100.0, "min_rows": 500},
    "qs_the_disagreement": {"low": 0.0, "high": 1.0, "min_rows": 500},
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the rows the serving jobs wrote.")
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="test")
    parser.add_argument("--pg-database", default="clawer")
    args = parser.parse_args()

    try:
        import psycopg2
    except ImportError:
        print("ERROR psycopg2 is required", file=sys.stderr)
        return 2

    failures: list[str] = []
    connection = psycopg2.connect(
        host=args.pg_host, port=args.pg_port, dbname=args.pg_database,
        user=args.pg_user, password=args.pg_password,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT target, model_name, count(*),
                       min(predicted_value), max(predicted_value),
                       bool_and(is_estimated), count(*) FILTER (WHERE support_distance IS NULL)
                  FROM analytics.v_ml_predictions_latest
                 GROUP BY target, model_name
                 ORDER BY target
            """)
            rows = cursor.fetchall()

            print(f"{'target':<24} {'rows':>6} {'min':>10} {'max':>10}  model")
            seen = set()
            for target, model, count, low, high, estimated, null_support in rows:
                print(f"{target:<24} {count:>6} {float(low):>10.4f} {float(high):>10.4f}  {model}")
                seen.add(target)
                spec = EXPECTED.get(target)
                if spec is None:
                    failures.append(f"{target}: unexpected target in the view")
                    continue
                if count < spec["min_rows"]:
                    failures.append(f"{target}: only {count} rows, expected at least {spec['min_rows']}")
                if not (spec["low"] <= float(low) and float(high) <= spec["high"]):
                    failures.append(
                        f"{target}: values [{float(low):.4f}, {float(high):.4f}] fall outside "
                        f"[{spec['low']}, {spec['high']}] -- wrong target, or two targets merged"
                    )
                if not estimated:
                    failures.append(f"{target}: some rows have is_estimated false")
                if null_support:
                    failures.append(f"{target}: {null_support} rows have no support_distance")

            for target in EXPECTED:
                if target not in seen:
                    failures.append(f"{target}: no rows written")

            # One run per target, which is what the API's "latest" depends on.
            cursor.execute("""
                SELECT target, count(DISTINCT model_version), count(DISTINCT model_name)
                  FROM analytics.v_ml_predictions_latest GROUP BY target
            """)
            for target, versions, models in cursor.fetchall():
                if versions != 1 or models != 1:
                    failures.append(
                        f"{target}: the view exposes {models} models / {versions} versions; "
                        "it should expose exactly the latest run"
                    )

            # Estimates must never have leaked into the published table.
            cursor.execute("""
                SELECT count(*) FROM analytics.aggregated_rankings a
                 WHERE EXISTS (SELECT 1 FROM analytics.ml_predictions p
                                WHERE p.canonical_university_id = a.canonical_university_id
                                  AND p.predicted_value = a.composite_score)
            """)
            leaked = cursor.fetchone()[0]
            if leaked:
                failures.append(
                    f"{leaked} aggregated_rankings rows carry a composite_score equal to a "
                    "model prediction; estimates must not reach the published table"
                )
    finally:
        connection.close()

    print()
    if failures:
        print(f"FAIL -- {len(failures)} problem(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("PASS -- both targets written, values on the right scales, disclosure columns intact.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
