#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Python-only crawler engine launcher (crawl + normalize + write + query)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run crawler pipeline with Python engine only")
    run_parser.add_argument("--limit", type=int, default=200)
    run_parser.add_argument("--workers", type=int, default=1)
    run_parser.add_argument("--request-delay", type=float, default=10.0)
    run_parser.add_argument("--write-batch-size", type=int, default=200)
    run_parser.add_argument("--ranking-id", default="3990755")
    run_parser.add_argument("--db-type", choices=["postgres"], default="postgres")
    run_parser.add_argument("--pg-host", default="localhost")
    run_parser.add_argument("--pg-port", type=int, default=5432)
    run_parser.add_argument("--pg-database", default="clawer")
    run_parser.add_argument("--pg-user", default="test")
    run_parser.add_argument("--pg-password", default="")
    run_parser.add_argument("--use-async", action="store_true")
    run_parser.add_argument("--rankings-only", action="store_true")
    run_parser.add_argument("--resource-guard", action="store_true")
    run_parser.add_argument("--resume", action="store_true")

    query_parser = subparsers.add_parser("query", help="Query rankings from Python-managed DB")
    query_parser.add_argument("keyword")
    query_parser.add_argument("--limit", type=int, default=20)
    query_parser.add_argument("--db-type", choices=["postgres"], default="postgres")
    query_parser.add_argument("--pg-host", default="localhost")
    query_parser.add_argument("--pg-port", type=int, default=5432)
    query_parser.add_argument("--pg-database", default="clawer")
    query_parser.add_argument("--pg-user", default="test")
    query_parser.add_argument("--pg-password", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    pipeline = repo_root / "run_pipeline.py"

    base_cmd = [sys.executable, str(pipeline)]
    if args.command == "run":
        cmd = [
            *base_cmd,
            "run",
            "--limit",
            str(args.limit),
            "--workers",
            str(args.workers),
            "--request-delay",
            str(args.request_delay),
            "--write-batch-size",
            str(max(1, args.write_batch_size)),
            "--ranking-id",
            str(args.ranking_id),
            "--db-type",
            str(args.db_type),
            "--pg-host",
            str(args.pg_host),
            "--pg-port",
            str(args.pg_port),
            "--pg-database",
            str(args.pg_database),
            "--pg-user",
            str(args.pg_user),
            "--pg-password",
            str(args.pg_password),
        ]
        if args.use_async:
            cmd.append("--use-async")
        if args.rankings_only:
            cmd.append("--rankings-only")
        if args.resource_guard:
            cmd.append("--resource-guard")
        if args.resume:
            cmd.append("--resume")
    else:
        cmd = [
            *base_cmd,
            "query",
            str(args.keyword),
            "--limit",
            str(args.limit),
            "--db-type",
            str(args.db_type),
            "--pg-host",
            str(args.pg_host),
            "--pg-port",
            str(args.pg_port),
            "--pg-database",
            str(args.pg_database),
            "--pg-user",
            str(args.pg_user),
            "--pg-password",
            str(args.pg_password),
        ]

    proc = subprocess.run(cmd, cwd=str(repo_root))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
