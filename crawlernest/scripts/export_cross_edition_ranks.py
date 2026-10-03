#!/usr/bin/env python3
"""
Export every world-ranking rank the warehouse holds, one row per university, source and edition.

The cross-edition forecasting experiment (crawlernest-ml/matlab/run_cross_edition_forecast.m and
its Python parity check) reads this file instead of the database, for the reason the QS<->THE
pairing is a file: a model that trains against a table nobody can inspect cannot be reproduced.

    # show what would change; writes nothing
    ./.venv/bin/python crawlernest/scripts/export_cross_edition_ranks.py --pg-password test

    # write it
    ./.venv/bin/python crawlernest/scripts/export_cross_edition_ranks.py --pg-password test --commit

## What a row says

``rank_lo`` and ``rank_hi`` are the interval the source *printed*: "85" is [85, 85], "=196" is
[196, 196], "201-210" is [201, 210], "1401+" is [1401, open]. They come from the printed text, not
from ``ranking_record.rank_position``, because that column means different things across the
warehouse: the lower bound for ARWU, THE and the archive-sourced QS editions, but a per-row ordinal
for QS 2025 and 2026, which QS's endpoint hands out distinct for every row even inside a band. A
file mixing the two would turn a band into a precision the source never published. Rows whose
printed rank cannot be parsed are dropped and counted in the metadata file, not guessed.

``source_kind`` is ``web_archive`` for the QS editions read from Internet Archive captures and
``live`` for everything crawled directly. The capture dates are in ``DATASET_ARCHIVE_EDITIONS``.

The file is what the warehouse says today, including whatever false merges it still holds; the
entity repair of 2026-10-03 is described in docs/data/ENTITY_SPLIT_2026-10-03.md. A university that
is two universities in the warehouse is one series here.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (REPO_ROOT,):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from crawlernest.core.rank_delta import parse_rank_band  # noqa: E402

DATABASES = REPO_ROOT / "crawlernest" / "crawlernest-kb" / "databases"
CSV_FILE = DATABASES / "cross_edition_ranks.csv"
META_FILE = DATABASES / "cross_edition_ranks.meta.json"

COLUMNS = ("canonical_university_id", "canonical_slug", "year", "source", "rank_lo", "rank_hi", "printed", "source_kind")

QUERY = """
SELECT rr.canonical_university_id,
       cu.canonical_slug,
       rr.ranking_year,
       rs.source_code,
       CASE WHEN rs.source_code = 'QS' THEN rr.metadata->>'rank_display'
            ELSE rr.metadata->'raw_row'->>'rank' END AS printed,
       (rr.source_version LIKE 'web_archive:%%') AS is_archive
FROM warehouse.ranking_record rr
JOIN warehouse.ranking_source rs ON rs.ranking_source_id = rr.ranking_source_id
JOIN warehouse.canonical_university cu ON cu.canonical_university_id = rr.canonical_university_id
WHERE rr.universe_type = 'global' AND rr.ranking_type = 'world'
  AND rr.ranking_year BETWEEN 2015 AND 2026
ORDER BY rs.source_code, rr.ranking_year, rr.canonical_university_id
"""


def build_rows(records: list[tuple]) -> tuple[list[dict[str, Any]], Counter]:
    """CSV rows from query records, and what was dropped and why."""
    dropped: Counter = Counter()
    rows: list[dict[str, Any]] = []
    for canonical_id, slug, year, source, printed, is_archive in records:
        band = parse_rank_band(printed)
        if band is None:
            dropped[f"{source} {year}: no parseable printed rank"] += 1
            continue
        rows.append(
            {
                "canonical_university_id": int(canonical_id),
                "canonical_slug": slug,
                "year": int(year),
                "source": source,
                "rank_lo": band.lower,
                "rank_hi": "" if band.upper is None else band.upper,
                "printed": str(printed).strip(),
                "source_kind": "web_archive" if is_archive else "live",
            }
        )
    return rows, dropped


def render_csv(rows: list[dict[str, Any]]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def build_meta(rows: list[dict[str, Any]], dropped: Counter, text: str, database: str) -> dict[str, Any]:
    per = Counter((r["source"], r["year"]) for r in rows)
    return {
        "exported_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "database": database,
        "csv_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "rows": len(rows),
        "rows_per_source_year": {f"{s} {y}": n for (s, y), n in sorted(per.items())},
        "dropped": dict(sorted(dropped.items())),
        "columns": list(COLUMNS),
        "rank_semantics": (
            "rank_lo and rank_hi are the interval the source printed (parsed from the printed text, "
            "not from ranking_record.rank_position); rank_hi is empty for an open-ended band such as 1401+"
        ),
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--commit", action="store_true", help="write the files; without it only the difference is shown")
    parser.add_argument("--pg-host", default="localhost")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-database", default="clawer")
    parser.add_argument("--pg-user", default="test")
    parser.add_argument("--pg-password", default="")
    args = parser.parse_args(argv)

    import psycopg2

    conn = psycopg2.connect(host=args.pg_host, port=args.pg_port, dbname=args.pg_database, user=args.pg_user,
                            password=args.pg_password)
    try:
        conn.set_session(readonly=True)
        with conn.cursor() as cur:
            cur.execute(QUERY)
            records = cur.fetchall()
    finally:
        conn.close()

    rows, dropped = build_rows(records)
    text = render_csv(rows)
    current = CSV_FILE.read_text(encoding="utf-8") if CSV_FILE.exists() else None
    same = current == text
    print(f"{len(rows)} rows from {len(records)} warehouse records; dropped {sum(dropped.values())}")
    for reason, count in sorted(dropped.items()):
        print(f"  dropped {count}: {reason}")
    print("identical to the committed file" if same else "DIFFERS from the committed file" if current else "no committed file yet")
    if not args.commit:
        print("Plan only. Nothing was written. Re-run with --commit to write.")
        return 0
    if same:
        return 0
    CSV_FILE.write_text(text, encoding="utf-8")
    META_FILE.write_text(json.dumps(build_meta(rows, dropped, text, args.pg_database), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {CSV_FILE.relative_to(REPO_ROOT)} and {META_FILE.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
