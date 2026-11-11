#!/usr/bin/env python3
"""Build and verify a frozen release snapshot of the warehouse.

    release_snapshot.py build  --release v0.3-multi-year-snapshot   # pg_dump, restore into a scratch db, write manifest.json
    release_snapshot.py verify --release-dir docs/releases/<release> # check a restored database against manifest.json
    release_snapshot.py drill [--backup FILE]                        # restore a backup into a scratch db, compare every table

v0.2's restore script carried its counts as literals. That made it a check of one release, and the next release
would have overwritten it. Every release directory now holds a ``manifest.json``, and one verifier reads any of
them. ``build`` never writes a count it has not read back from a restored copy of the dump.

**A release dump carries no user data.** v0.2's dump first shipped ``warehouse.app_user`` rows (an email and a
password hash) in a public repository; it was cleaned and history rewritten on 2026-11-11. ``build`` dumps the schema
of every user table and the data of none, then refuses to write a manifest when any of them has a row in the restored
copy. ``verify`` checks the same thing. A manifest may still set ``contains_user_data`` to record such a defect
honestly; none does now.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RELEASES_DIR = REPO_ROOT / "docs" / "releases"
MANIFEST_NAME = "manifest.json"
MANIFEST_VERSION = 1

# Schema is dumped, data is not. A pattern is a pg_dump --exclude-table-data pattern.
USER_DATA_PATTERNS = (
    "warehouse.app_user",
    "warehouse.password_reset_token",
    "warehouse.saved_*",
    "desk.*",
    "agent_state.*",
)

# Each is a relation counted as a whole; a release says how many rows it had.
COUNTED_RELATIONS = (
    "analytics.aggregated_rankings",
    "analytics.ml_predictions",
    "analytics.v_ml_predictions_latest",
    "warehouse.ranking_record",
    "warehouse.subject_ranking_record",
    "warehouse.canonical_university",
    "warehouse.university_wikipedia_article",
    "warehouse.us_institution",
    "warehouse.us_institution_metric",
)


def _pg_env(args: argparse.Namespace) -> dict[str, str]:
    env = dict(os.environ)
    env.update(PGHOST=args.pg_host, PGPORT=str(args.pg_port), PGUSER=args.pg_user, PGPASSWORD=args.pg_password)
    return env


def _psql_rows(env: dict[str, str], database: str, sql: str) -> list[list[str]]:
    out = subprocess.run(
        ["psql", "-X", "-At", "-F", "\t", "-v", "ON_ERROR_STOP=1", "-d", database, "-c", sql],
        env=env, check=True, capture_output=True, text=True,
    ).stdout
    return [line.split("\t") for line in out.splitlines() if line]


def _user_tables(env: dict[str, str], database: str) -> list[str]:
    clauses = []
    for pattern in USER_DATA_PATTERNS:
        schema, table = pattern.split(".", 1)
        clauses.append(f"(table_schema = '{schema}' AND table_name LIKE '{table.replace('*', '%')}')")
    rows = _psql_rows(
        env, database,
        "SELECT table_schema || '.' || table_name FROM information_schema.tables "
        f"WHERE table_type = 'BASE TABLE' AND ({' OR '.join(clauses)}) ORDER BY 1",
    )
    return [row[0] for row in rows]


def collect_counts(env: dict[str, str], database: str) -> dict[str, Any]:
    """Everything a manifest asserts about a database, read from that database."""
    source_rows = _psql_rows(
        env, database,
        "SELECT rs.source_code, rr.ranking_year, count(*) FROM warehouse.ranking_record rr "
        "JOIN warehouse.ranking_source rs ON rs.ranking_source_id = rr.ranking_source_id "
        "GROUP BY 1, 2 ORDER BY 1, 2",
    )
    ranking_records: dict[str, dict[str, int]] = {}
    for source, year, count in source_rows:
        ranking_records.setdefault(source, {})[year] = int(count)

    aggregated: dict[str, dict[str, int]] = {}
    for year, universe, count in _psql_rows(
        env, database,
        "SELECT ranking_year, universe_type, count(*) FROM analytics.aggregated_rankings GROUP BY 1, 2 ORDER BY 1, 2",
    ):
        aggregated.setdefault(year, {})[universe] = int(count)

    relations = {}
    for relation in COUNTED_RELATIONS:
        exists = _psql_rows(env, database, f"SELECT to_regclass('{relation}') IS NOT NULL")[0][0] == "t"
        relations[relation] = int(_psql_rows(env, database, f"SELECT count(*) FROM {relation}")[0][0]) if exists else None

    user_rows = {
        table: int(_psql_rows(env, database, f"SELECT count(*) FROM {table}")[0][0])
        for table in _user_tables(env, database)
    }
    return {
        "ranking_records_by_source_year": ranking_records,
        "aggregated_rows_by_year_universe": aggregated,
        "relation_rows": relations,
        "user_data_rows": user_rows,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compare(manifest: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    """Differences between what a manifest asserts and what a database holds; empty means it matches."""
    problems: list[str] = []
    expected = manifest["counts"]
    for key in ("ranking_records_by_source_year", "aggregated_rows_by_year_universe", "relation_rows"):
        want, got = expected.get(key) or {}, actual.get(key) or {}
        if want != got:
            problems.extend(_diff(key, want, got))
    # A manifest that records a user-data defect (contains_user_data) is reported, not hidden; none does now.
    if not manifest.get("contains_user_data"):
        for table, rows in sorted((actual.get("user_data_rows") or {}).items()):
            if rows:
                problems.append(f"user data: {table} has {rows} row(s); a release holds none")
    return problems


def _diff(prefix: str, want: Any, got: Any) -> list[str]:
    if isinstance(want, dict) and isinstance(got, dict):
        out = []
        for key in sorted(set(want) | set(got), key=str):
            out.extend(_diff(f"{prefix}.{key}", want.get(key), got.get(key)))
        return out
    return [] if want == got else [f"{prefix}: expected {want}, got {got}"]


def coverage_from_counts(counts: dict[str, Any]) -> dict[str, list[int]]:
    """Editions per source the dump holds, for comparison with core/dataset.py:DATASET_COVERAGE."""
    return {
        source: sorted((int(year) for year in years), reverse=True)
        for source, years in sorted(counts["ranking_records_by_source_year"].items())
    }


def cmd_build(args: argparse.Namespace) -> int:
    env = _pg_env(args)
    release_dir = RELEASES_DIR / args.release
    if release_dir.exists() and any(release_dir.iterdir()) and not args.force:
        print(f"{release_dir} already has files; a release is never overwritten (--force to rebuild a draft)", file=sys.stderr)
        return 1
    release_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc)
    dump_path = release_dir / f"{args.pg_database}-{stamp:%Y-%m-%d}-release.dump"

    command = ["pg_dump", "-d", args.pg_database, "-Fc", "-Z9", "--no-owner", "--no-acl", "-f", str(dump_path)]
    for pattern in USER_DATA_PATTERNS:
        command.append(f"--exclude-table-data={pattern}")
    print(f"dumping {args.pg_database} -> {dump_path.relative_to(REPO_ROOT)}")
    subprocess.run(command, env=env, check=True)

    scratch = args.scratch_database
    print(f"restoring into scratch database {scratch}")
    subprocess.run(["dropdb", "--if-exists", scratch], env=env, check=True)
    subprocess.run(["createdb", scratch], env=env, check=True)
    try:
        subprocess.run(
            ["pg_restore", "-d", scratch, "--no-owner", "--no-acl", "--exit-on-error", str(dump_path)],
            env=env, check=True,
        )
        counts = collect_counts(env, scratch)
        source_counts = collect_counts(env, args.pg_database)
    finally:
        if not args.keep_scratch:
            subprocess.run(["dropdb", "--if-exists", scratch], env=env, check=False)

    leaked = {table: rows for table, rows in counts["user_data_rows"].items() if rows}
    if leaked:
        dump_path.unlink(missing_ok=True)
        print(f"refusing: the restored copy holds user data {leaked}; dump deleted", file=sys.stderr)
        return 1
    # The restored copy must agree with the live database on everything but the user tables.
    mismatches = compare({"counts": {**source_counts, "user_data_rows": {}}, "contains_user_data": True}, counts)
    if mismatches:
        dump_path.unlink(missing_ok=True)
        print("refusing: the restored copy differs from the database it was dumped from:", file=sys.stderr)
        for line in mismatches:
            print(f"  {line}", file=sys.stderr)
        return 1

    sys.path.insert(0, str(REPO_ROOT))
    from crawlernest.core.dataset import DATASET_COVERAGE  # noqa: E402

    held = coverage_from_counts(counts)
    declared = {source: sorted(years, reverse=True) for source, years in DATASET_COVERAGE.items()}
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()
    pg_dump_version = subprocess.run(["pg_dump", "--version"], capture_output=True, text=True).stdout.strip()
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "release": args.release,
        "built_at": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "built_from_commit": commit,
        "pg_dump_version": pg_dump_version,
        "database": args.pg_database,
        "dump": {"file": dump_path.name, "sha256": _sha256(dump_path), "bytes": dump_path.stat().st_size},
        "contains_user_data": False,
        "user_data_excluded": list(USER_DATA_PATTERNS),
        "dataset_coverage_declared": declared,
        # ranking_record also holds rows dataset.py does not release (a shadow ingest). They are listed, not hidden.
        "editions_held": held,
        "counts": {key: counts[key] for key in ("ranking_records_by_source_year", "aggregated_rows_by_year_universe", "relation_rows")},
    }
    (release_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {(release_dir / MANIFEST_NAME).relative_to(REPO_ROOT)}")
    for source in sorted(set(held) | set(declared)):
        extra = sorted(set(held.get(source, [])) - set(declared.get(source, [])))
        missing = sorted(set(declared.get(source, [])) - set(held.get(source, [])))
        if extra or missing:
            print(f"note: {source} held-vs-declared editions differ: held only {extra}, declared only {missing}")
    return 0


def table_row_counts(env: dict[str, str], database: str) -> dict[str, int]:
    """Exact row count of every base table outside the system schemas."""
    tables = [row[0] for row in _psql_rows(
        env, database,
        "SELECT table_schema || '.' || table_name FROM information_schema.tables "
        "WHERE table_type = 'BASE TABLE' AND table_schema NOT IN ('pg_catalog', 'information_schema') ORDER BY 1",
    )]
    if not tables:
        return {}
    union = " UNION ALL ".join(f"SELECT '{t}', count(*) FROM {t}" for t in tables)
    return {name: int(count) for name, count in _psql_rows(env, database, union)}


def cmd_drill(args: argparse.Namespace) -> int:
    """A backup is only a backup once it has been restored. Restore one into a scratch database and compare it with
    the live database table by table. The live database is read, never written; the scratch one is dropped.

    Without --backup, a fresh full dump (user tables included -- it is a backup, not a release) is written to
    .local/backups/, which is gitignored. A table that changed between the dump and the comparison shows up as a
    difference, so run it when nothing is writing.
    """
    env = _pg_env(args)
    stamp = datetime.now(timezone.utc)
    backups = REPO_ROOT / ".local" / "backups"
    reports = REPO_ROOT / ".local" / "reports" / "backup_drill"
    if args.backup:
        backup = Path(args.backup).resolve()
        if not backup.is_file():
            print(f"no such backup: {backup}", file=sys.stderr)
            return 1
    else:
        backups.mkdir(parents=True, exist_ok=True)
        backup = backups / f"crawlernest_{args.pg_database}_{stamp:%Y%m%dT%H%M%SZ}.dump"
        print(f"dumping {args.pg_database} -> {backup.relative_to(REPO_ROOT)}")
        subprocess.run(["pg_dump", "-d", args.pg_database, "-Fc", "--no-owner", "--no-acl", "-f", str(backup)],
                       env=env, check=True)

    scratch = args.scratch_database
    if scratch == args.pg_database:
        print("refusing: the scratch database is the live one", file=sys.stderr)
        return 1
    print(f"restoring {backup.name} into scratch database {scratch}")
    subprocess.run(["dropdb", "--if-exists", scratch], env=env, check=True)
    subprocess.run(["createdb", scratch], env=env, check=True)
    try:
        restore = subprocess.run(["pg_restore", "-d", scratch, "--no-owner", "--no-acl", "--exit-on-error", str(backup)],
                                 env=env, capture_output=True, text=True)
        restored = table_row_counts(env, scratch) if restore.returncode == 0 else {}
    finally:
        if not args.keep_scratch:
            subprocess.run(["dropdb", "--if-exists", scratch], env=env, check=False)
    live = table_row_counts(env, args.pg_database)

    problems: list[str] = []
    if restore.returncode != 0:
        problems.append(f"pg_restore failed: {restore.stderr.strip().splitlines()[-1] if restore.stderr.strip() else restore.returncode}")
    else:
        problems.extend(_diff("rows", live, restored))
    report = {
        "drilled_at": stamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "database": args.pg_database,
        "backup": str(backup),
        "backup_bytes": backup.stat().st_size,
        "backup_sha256": _sha256(backup),
        "tables_compared": len(live),
        "rows_live": sum(live.values()),
        "rows_restored": sum(restored.values()),
        "ok": not problems,
        "problems": problems,
    }
    reports.mkdir(parents=True, exist_ok=True)
    (reports / f"drill_{stamp:%Y%m%dT%H%M%SZ}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (reports / "latest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if problems:
        print(f"FAIL backup drill: {len(problems)} difference(s)")
        for line in problems[:50]:
            print(f"  {line}")
        return 1
    print(f"OK   backup drill: {report['tables_compared']} tables, {report['rows_restored']} rows restored and equal to live")
    if not args.backup and args.keep > 0:
        for old in prune_drill_backups(backups, args.pg_database, keep=args.keep):
            print(f"pruned {old.name}")
    return 0


def prune_drill_backups(directory: Path, database: str, *, keep: int) -> list[Path]:
    """Delete all but the newest ``keep`` dumps the drill wrote itself, and say which.

    Only ``crawlernest_<database>_<UTC stamp>.dump`` -- the drill's own name -- is ever touched: the named backups
    a loader takes before a migration (``qs_archive_pre_ingest_*``) are kept whatever their age. Called only after
    a drill passed, so the newest kept dump is one that is known to restore.
    """
    pattern = re.compile(rf"^crawlernest_{re.escape(database)}_\d{{8}}T\d{{6}}Z\.dump$")
    own = sorted((p for p in directory.glob("*.dump") if pattern.match(p.name)), key=lambda p: p.name, reverse=True)
    removed = own[max(keep, 1):]
    for path in removed:
        path.unlink()
    return removed


def cmd_verify(args: argparse.Namespace) -> int:
    release_dir = Path(args.release_dir)
    manifest = json.loads((release_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    dump_path = release_dir / manifest["dump"]["file"]
    problems = []
    if args.check_dump:
        if not dump_path.is_file():
            problems.append(f"dump missing: {dump_path}")
        elif _sha256(dump_path) != manifest["dump"]["sha256"]:
            problems.append(f"dump sha256 differs from the manifest: {dump_path.name}")
    problems.extend(compare(manifest, collect_counts(_pg_env(args), args.pg_database)))
    if manifest.get("contains_user_data"):
        print(f"WARNING: {manifest['release']} predates the no-user-data rule; its dump holds user rows ({manifest.get('user_data_note', '')})")
    if problems:
        print(f"FAIL {manifest['release']}: {len(problems)} difference(s)")
        for line in problems:
            print(f"  {line}")
        return 1
    print(f"OK   {manifest['release']} matches its manifest")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pg-host", default=os.environ.get("PGHOST", "localhost"))
    parser.add_argument("--pg-port", type=int, default=int(os.environ.get("PGPORT", "5432")))
    parser.add_argument("--pg-user", default=os.environ.get("PGUSER", "test"))
    parser.add_argument("--pg-password", default=os.environ.get("PGPASSWORD", "test"))
    parser.add_argument("--pg-database", default=os.environ.get("PGDATABASE", "clawer"))
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="dump the database and write a verified manifest")
    build.add_argument("--release", required=True)
    build.add_argument("--scratch-database", default="clawer_release_verify")
    build.add_argument("--keep-scratch", action="store_true")
    build.add_argument("--force", action="store_true")
    build.set_defaults(func=cmd_build)
    verify = sub.add_parser("verify", help="check a database against a release manifest")
    verify.add_argument("--release-dir", required=True)
    verify.add_argument("--no-check-dump", dest="check_dump", action="store_false")
    verify.set_defaults(func=cmd_verify)
    drill = sub.add_parser("drill", help="restore a backup into a scratch database and compare every table with live")
    drill.add_argument("--backup", help="an existing pg_dump custom archive; default: take a fresh one into .local/backups/")
    drill.add_argument("--scratch-database", default="clawer_backup_drill")
    drill.add_argument("--keep-scratch", action="store_true")
    drill.add_argument("--keep", type=int, default=4,
                       help="after a passing drill, keep this many of the drill's own dumps (default 4; 0 keeps all)")
    drill.set_defaults(func=cmd_drill)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
