"""Structural check on the MATLAB inference batch.

``predict_qs_disagreement.m`` is the one registered port ``check_matlab_parity``
cannot cover. That module compares a committed artifact against a fresh Python
run, and this port has no committed artifact: its output is gitignored, because
a per-university probability table is a result to look at rather than a number
to hold still. Its Python counterpart is no help either --
``ranking_ml.serving.predict_disagreement`` scores all 1,503 QS universities
into PostgreSQL, while the port scores only the ones THE has not ranked, into a
CSV. Different contracts on purpose, so there is nothing to diff.

What can be asserted without a baseline is the *shape* of the batch, and shape
is exactly where this port went wrong. From its own header:

    An earlier version of this file carried its own copy, which had drifted: it
    matched on names alone and so trained on 820 universities instead of 1082,
    and 262 of the institutions it then "predicted" were ones THE had already
    ranked under a reviewed alias.

A model asked to predict something already observed will look confident and
mean nothing. That failure has one signature -- the scored set overlapping the
training set -- and it is visible without running a model at all.

One assertion covers it. The scored set must equal exactly the ranked QS
universities the cross-source join did not match: nothing that THE already
ranks, nothing missing, no duplicates. Set equality, no tolerances, no RNG.

    python -m ranking_ml.evaluation.check_inference_batch \\
        --batch crawlernest/crawlernest-ml/artifacts/cross_source_matlab/predicted_disagreements.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Optional

from ranking_ml.features.build_features import DEFAULT_SNAPSHOT, load_snapshot, _to_rank
from ranking_ml.features.cross_source import build_cross_source_frame

_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_BATCH = (
    _REPO_ROOT
    / "crawlernest"
    / "crawlernest-ml"
    / "artifacts"
    / "cross_source_matlab"
    / "predicted_disagreements.csv"
)

#: The column the port writes the university name into.
NAME_COLUMN = "University"

#: QS ships a handful of rows carrying a rank and no institution. The warehouse
#: writer refuses them outright -- "skip invalid university placeholder row" --
#: so a model scoring them is producing a probability about nothing. They are
#: excluded from the population and reported separately if the port emits them,
#: because "N/A appears four times" is a confusing way to say that.
PLACEHOLDER_NAMES = frozenset({"", "n/a", "na", "-", "--"})


def is_placeholder(name: str) -> bool:
    return str(name or "").strip().lower() in PLACEHOLDER_NAMES


def read_batch(path: Path) -> list[str]:
    """The universities the port scored, in file order, duplicates kept.

    Duplicates are kept rather than collapsed so the caller can report them:
    a name appearing twice means the batch was built from something other than
    a set difference, which is worth saying out loud.
    """
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or NAME_COLUMN not in reader.fieldnames:
            raise SystemExit(
                f"{path}: expected a {NAME_COLUMN!r} column, found {reader.fieldnames}"
            )
        return [str(row[NAME_COLUMN]).strip() for row in reader if row.get(NAME_COLUMN)]


def ranked_qs_names(snapshot: Optional[Path]) -> set[str]:
    """Named QS universities carrying a rank -- the population the port draws from."""
    names: set[str] = set()
    for record in load_snapshot(snapshot or DEFAULT_SNAPSHOT):
        if _to_rank(record.get("rank")) is None:
            continue
        name = str(record.get("name") or "").strip()
        if name and not is_placeholder(name):
            names.add(name)
    return names


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Assert the MATLAB inference batch is exactly the unmatched QS universities.",
    )
    parser.add_argument(
        "--batch",
        type=Path,
        default=DEFAULT_BATCH,
        help="CSV written by predict_qs_disagreement.m",
    )
    parser.add_argument(
        "--qs-snapshot", type=Path, default=None, help="override the QS snapshot"
    )
    args = parser.parse_args(argv)

    if not args.batch.is_file():
        raise SystemExit(
            f"{args.batch}: not found. Run predict_qs_disagreement.m first, or point "
            "--batch at a fresh run's output."
        )

    scored_raw = read_batch(args.batch)
    placeholders = [name for name in scored_raw if is_placeholder(name)]
    scored = [name for name in scored_raw if not is_placeholder(name)]

    population = ranked_qs_names(args.qs_snapshot)
    cross_source = build_cross_source_frame()
    matched = {
        str(name).strip()
        for name in cross_source.frame["qs_name"]
        if not is_placeholder(str(name))
    }
    expected = population - matched

    scored_set = set(scored)
    duplicated = sorted({name for name in scored if scored.count(name) > 1})
    already_ranked = sorted(scored_set & matched)
    missing = sorted(expected - scored_set)
    unknown = sorted(scored_set - population)

    print(f"QS population (named, ranked)  {len(population)}")
    print(f"matched by the join            {len(matched)}")
    print(f"expected inference batch       {len(expected)}")
    print(f"scored by the port             {len(scored)}", end="")
    print(f"  (+{len(placeholders)} placeholder)" if placeholders else "")
    print()

    problems: list[str] = []
    if already_ranked:
        problems.append(
            f"{len(already_ranked)} scored universit(ies) are already ranked by THE, so "
            "their disagreement is observed rather than predicted: "
            f"{already_ranked[:5]}"
        )
    if unknown:
        problems.append(
            f"{len(unknown)} scored name(s) are not ranked QS universities at all: {unknown[:5]}"
        )
    if missing:
        problems.append(
            f"{len(missing)} unmatched universit(ies) were left unscored: {missing[:5]}"
        )
    if duplicated:
        problems.append(f"{len(duplicated)} name(s) appear more than once: {duplicated[:5]}")
    if placeholders:
        problems.append(
            f"{len(placeholders)} placeholder row(s) were scored -- QS ships ranks with no "
            "institution attached, and a probability about one of those is a probability "
            "about nothing"
        )

    if problems:
        print(f"FAIL -- {len(problems)} problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        print()
        print(
            "The batch should be exactly the ranked QS universities the cross-source "
            "join did not match. If the join moved, re-run the port; if the port "
            "built the batch some other way, that is the bug this check exists for."
        )
        return 1

    print(
        "PASS -- the batch is exactly the ranked QS universities the join did not match."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
