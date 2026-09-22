#!/usr/bin/env python3
"""Re-run the QS ingest for a year from the crawl snapshots already on disk.

A decision recorded in warehouse.mapping_review changes nothing by itself. The
pipeline applies decisions during ingestion -- ``MultiSourceRankingPipeline.
ingest_records`` calls ``apply_mapping_reviews`` before it upserts mappings and
before it credits any source to a university -- so a reviewed backlog only takes
effect on the next ingest. Re-crawling QS to get one is an hour of network
traffic for a payload that has not changed and is already saved under
``crawlernest-kb/qs_universes/<year>/<type>/<key>/raw_snapshot.json``.

This replays those snapshots through the same ingest path, one universe at a
time, with the universe columns the CLI's ``ingest-rankings`` cannot set (it
builds a QSAdapter without universe_type/universe_key, so everything it writes
lands as global/global regardless of --ranking-type).

    # what would be replayed
    ./.venv/bin/python crawlernest/scripts/reingest_qs_universes.py \
        --ranking-year 2026 --pg-password test

    # replay it
    ./.venv/bin/python crawlernest/scripts/reingest_qs_universes.py \
        --ranking-year 2026 --pg-password test --commit

Each universe gets its own timestamped run id, so prune_superseded_records
retires the rows the previous ingest wrote for that universe and nothing else:
the prune is scoped to (source, year, ranking_type, run_id).

This is a replay, not a crawl. It reproduces whatever the snapshot holds, so a
universe whose snapshot is stale stays stale -- check the dates it prints.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve()
_MODULE_ROOT = _HERE.parents[1]              # crawlernest/
_REPO_ROOT = _HERE.parents[2]

for _path in (
    _MODULE_ROOT,                             # pipeline.* package
    _MODULE_ROOT / "crawlernest-core",        # models, multi_source, entity_resolution
    _MODULE_ROOT / "crawlernest-jobs",        # qs_universe_registry
    _MODULE_ROOT / "crawlernest-analytics",
):
    if _path.is_dir() and str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from qs_universe_registry import iter_all_qs_universes  # noqa: E402
from ranking_edition import snapshot_edition_ok  # noqa: E402
from pipeline.utils.postgres import (  # noqa: E402
    build_multi_source_pipeline,
    connect_postgres,
)


def snapshot_path(root: Path, ranking_year: int, universe_type: str, universe_key: str) -> Path:
    return root / str(ranking_year) / universe_type / universe_key / "raw_snapshot.json"


def load_snapshot(path: Path) -> list[dict[str, Any]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(rows, dict):
        rows = rows.get("rows", [])
    return [row for row in rows if isinstance(row, dict)]


def edition_verified(run_status_path: Path, ranking_year: int) -> bool:
    """Replay only a snapshot whose crawl proved it read ``ranking_year``'s table.

    A replay reproduces the snapshot under the year it is asked for. Before
    ranking_edition, the 2026 global and world-slice snapshots were crawled off
    the page then serving QS 2027, so replaying them as 2026 is the mislabel.
    """
    try:
        run_status = json.loads(run_status_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return snapshot_edition_ok(run_status, ranking_year=ranking_year)


def replay_universe(pipeline: Any, spec: Any, rows: list[dict[str, Any]], ranking_year: int) -> Any:
    from models import University
    from multi_source.adapters import QSAdapter

    stamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    batch_id = f"qs-{spec.universe_type}-{spec.universe_key}-{ranking_year}-reingest-{stamp}"

    standardized = QSAdapter(
        ranking_year=ranking_year,
        ranking_type=spec.ranking_type,
        universe_type=spec.universe_type,
        universe_key=spec.universe_key,
    ).adapt([University.from_dict(row) for row in rows])

    return pipeline.ingest_records(
        standardized,
        batch_id=batch_id,
        run_label_prefix="qs_review_reingest",
        ranking_type=spec.ranking_type,
        enable_aggregation=spec.enable_aggregation,
    )


def _print_frozen_reasons(reasons: set[str]) -> None:
    """Say once why a frozen universe cannot be replayed.

    Repeating a four-line explanation per universe is how output becomes
    something people scroll past, and this one is the same sentence seven times.
    """
    for reason in sorted(r for r in reasons if r):
        print()
        print("  why the frozen universes cannot be replayed:")
        print(f"    {reason}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay saved QS crawl snapshots through the ingest pipeline")
    parser.add_argument("--ranking-year", type=int, default=2026)
    parser.add_argument(
        "--snapshot-root",
        default=str(_MODULE_ROOT / "crawlernest-kb" / "qs_universes"),
        help="Directory holding <year>/<universe_type>/<universe_key>/raw_snapshot.json",
    )
    parser.add_argument(
        "--universe", action="append", default=None,
        help="Limit to this ranking_type (e.g. regional:asia). Repeatable.",
    )
    parser.add_argument("--commit", action="store_true",
                        help="Actually ingest. Without it, only the plan is printed.")
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-database", default="clawer")
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="")
    args = parser.parse_args()

    root = Path(args.snapshot_root)
    wanted = set(args.universe) if args.universe else None

    plan: list[tuple[Any, Path, list[dict[str, Any]]]] = []
    skipped: list[str] = []
    frozen_reasons: set[str] = set()
    for spec in iter_all_qs_universes():
        if wanted is not None and spec.ranking_type not in wanted:
            continue
        path = snapshot_path(root, args.ranking_year, spec.universe_type, spec.universe_key)
        if not path.is_file():
            if spec.is_frozen:
                # "No snapshot" reads as an accident. For these it is the state
                # of the source, so the line says which date the warehouse holds
                # and the reason is printed once below rather than seven times.
                frozen_reasons.add(spec.frozen_reason or "")
                skipped.append(
                    f"{spec.ranking_type}: frozen, warehouse holds the {spec.data_frozen_at} ingest"
                )
            else:
                skipped.append(f"{spec.ranking_type}: no snapshot at {path}")
            continue
        rows = load_snapshot(path)
        if not rows:
            skipped.append(f"{spec.ranking_type}: snapshot is empty")
            continue
        if not edition_verified(path.parent / "run_status.json", args.ranking_year):
            skipped.append(
                f"{spec.ranking_type}: snapshot records no verified {args.ranking_year} edition "
                "(crawled before ranking_edition; re-crawl it)"
            )
            continue
        plan.append((spec, path, rows))

    if not plan:
        print("Nothing to replay.")
        for line in skipped:
            print(f"  skip {line}")
        _print_frozen_reasons(frozen_reasons)
        return 1

    print(f"{len(plan)} universe(s) to replay for {args.ranking_year}:")
    for spec, path, rows in plan:
        mtime = dt.datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"  {spec.ranking_type:<28} {len(rows):>5} rows   snapshot {mtime}")
    for line in skipped:
        print(f"  skip {line}")
    _print_frozen_reasons(frozen_reasons)

    if not args.commit:
        print("\nPlan only. Nothing was ingested. Re-run with --commit to apply.")
        return 0

    conn = connect_postgres(args.pg_host, args.pg_port, args.pg_database,
                            args.pg_user, args.pg_password)
    failures = 0
    try:
        # Built once: the resolver loads every canonical profile at construction,
        # and this replay never adds one, so rebuilding per universe would reread
        # the same fifteen hundred rows nineteen times.
        pipeline = build_multi_source_pipeline(conn)
        print()
        for spec, _path, rows in plan:
            try:
                summary = replay_universe(pipeline, spec, rows, args.ranking_year)
            except Exception as exc:  # one universe failing must not hide the rest
                failures += 1
                conn.rollback()
                print(f"  FAIL {spec.ranking_type}: {exc}")
                continue
            conn.commit()
            print(
                f"  ok   {spec.ranking_type:<28} "
                f"in={summary.standardized_count:>5} matched={summary.matched_count:>5} "
                f"unresolved={summary.unresolved_count:>5} written={summary.rows_written:>5}"
            )
    finally:
        conn.close()

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
