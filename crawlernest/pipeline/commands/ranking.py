"""Ranking staging commands for the CrawlerNest pipeline.

Validation, ingestion, warehouse-row mapping preview, and the decision preview
for ranking records. Extracted from run_pipeline.py, where these lived
alongside every other command group.

The landing chain that once sat between the mapping preview and the decision
preview -- staging into warehouse.ranking_records_preview, aggregation into
warehouse.aggregated_rankings_preview, and entity resolution over the former --
was removed once both tables were dropped; the decision preview now reads the
published analytics aggregation directly. See
docs/migrations/RANKING_SCHEMA_CONVERGENCE.md.

Each handler takes the parsed argparse namespace and returns a process exit
code. :data:`COMMANDS` is what run_pipeline.py merges into its dispatch table.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

try:
    from pipeline.utils.artifacts import save_json_artifact
except ModuleNotFoundError:  # pragma: no cover - package import compatibility
    from ...pipeline.utils.artifacts import save_json_artifact

try:
    import psycopg2
except ImportError:  # pragma: no cover - handled by the callers
    psycopg2 = None  # type: ignore

#: Git repository root, where the crawlernest_ranking_crawler package lives.
#:
#: run_pipeline.py derives this as ``Path(__file__).resolve().parent.parent``
#: because it sits one level below the root; from this module it is three.
#: Getting it wrong imports cleanly and fails at call time, so it is computed
#: once here rather than repeated in every helper.
WORKSPACE_ROOT = Path(__file__).resolve().parents[3]


def _validate_ranking_staging(staging_file: str) -> dict[str, Any]:
    workspace_root = WORKSPACE_ROOT
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from crawlernest_ranking_crawler.validator import (  # noqa: E402
        summary_to_dict,
        validate_ranking_staging_file,
    )

    summary = validate_ranking_staging_file(Path(staging_file))
    return summary_to_dict(summary)


def _ingest_ranking_staging(
    staging_file: str,
    sqlite_db_file: str,
    *,
    allow_partial: bool,
    write_target: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    workspace_root = WORKSPACE_ROOT
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from crawlernest_ranking_crawler.ingest import (  # noqa: E402
        ingest_ranking_staging_file,
        ingest_summary_to_dict,
    )

    summary = ingest_ranking_staging_file(
        Path(staging_file),
        Path(sqlite_db_file),
        allow_partial=allow_partial,
        write_target=write_target,
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
    )
    return ingest_summary_to_dict(summary)


def _preview_ranking_warehouse_map(
    *,
    input_source: str,
    staging_input_file: str,
    staging_table: str,
    output_file: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    workspace_root = WORKSPACE_ROOT
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from crawlernest_ranking_crawler.warehouse_mapper import (  # noqa: E402
        load_staging_rows_from_jsonl,
        load_staging_rows_from_postgres,
        map_staging_rows_to_warehouse_rows,
        warehouse_rows_to_jsonable,
        write_warehouse_preview,
    )

    if input_source == "jsonl":
        staging_rows = load_staging_rows_from_jsonl(Path(staging_input_file))
        source_location = str(Path(staging_input_file))
    elif input_source == "postgres":
        staging_rows = load_staging_rows_from_postgres(
            table_name=staging_table,
            pg_host=pg_host,
            pg_port=pg_port,
            pg_database=pg_database,
            pg_user=pg_user,
            pg_password=pg_password,
        )
        source_location = f"postgresql://{pg_host}:{pg_port}/{pg_database}#{staging_table}"
    else:
        raise ValueError(f"Unsupported input source: {input_source}")

    mapped_rows = map_staging_rows_to_warehouse_rows(staging_rows)
    output_path = Path(output_file)
    write_warehouse_preview(mapped_rows, output_path)
    preview_payload = warehouse_rows_to_jsonable(mapped_rows[:5])

    return {
        "input_source": input_source,
        "source_location": source_location,
        "row_count": len(mapped_rows),
        "output_file": str(output_path),
        "preview_rows": preview_payload,
    }


def _decision_ranking_preview(
    *,
    source_schema: str,
    source_table: str,
    target_schema: str,
    target_table: str,
    output_file: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    workspace_root = WORKSPACE_ROOT
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from dataclasses import asdict  # noqa: E402

    from crawlernest_ranking_crawler.decision_writer import (  # noqa: E402
        build_decision_row,
        decision_write_summary_to_dict,
        load_aggregated_rows_from_postgres,
        write_decision_rows,
    )
    from crawlernest_ranking_crawler.explain_layer import build_explain  # noqa: E402
    from crawlernest_ranking_crawler.postgres_driver import get_psycopg2  # noqa: E402

    psycopg2 = get_psycopg2()
    conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        dbname=pg_database,
        user=pg_user,
        password=pg_password,
    )
    try:
        aggregated_rows = load_aggregated_rows_from_postgres(
            conn,
            schema_name=source_schema,
            table_name=source_table,
        )
        decision_rows = [build_decision_row(row, build_explain(row)) for row in aggregated_rows]
        output_path = Path(output_file)
        save_json_artifact(output_path, [asdict(row) for row in decision_rows])
        summary = write_decision_rows(
            decision_rows,
            conn,
            schema_name=target_schema,
            table_name=target_table,
        )
    finally:
        conn.close()

    payload = decision_write_summary_to_dict(summary)
    payload["source_location"] = f"postgresql://{pg_host}:{pg_port}/{pg_database}#{source_schema}.{source_table}"
    payload["output_file"] = str(Path(output_file))
    payload["preview_rows"] = [asdict(row) for row in decision_rows[:5]]
    return payload


def _cmd_validate_ranking_staging(args: argparse.Namespace) -> int:
    """Handler for the ``validate-ranking-staging`` command."""
    summary = _validate_ranking_staging(args.staging_input_file)
    print(
        "[validate-ranking-staging] "
        f"total={summary['total_rows']} "
        f"valid={summary['valid_row_count']} "
        f"invalid={summary['invalid_row_count']} "
        f"duplicates={summary['duplicate_row_count']}"
    )
    print(f"[validate-ranking-staging] staging_file={summary['staging_file']}")
    if summary["error_samples"]:
        print("[validate-ranking-staging] error_samples:")
        print(json.dumps(summary["error_samples"], ensure_ascii=False, indent=2))
    if summary["duplicate_samples"]:
        print("[validate-ranking-staging] duplicate_samples:")
        print(json.dumps(summary["duplicate_samples"], ensure_ascii=False, indent=2))
    return 0


def _cmd_ingest_ranking_staging(args: argparse.Namespace) -> int:
    """Handler for the ``ingest-ranking-staging`` command."""
    try:
        summary = _ingest_ranking_staging(
            args.staging_input_file,
            args.sqlite_db_file,
            allow_partial=bool(getattr(args, "allow_partial_ingest", False)),
            write_target=str(getattr(args, "write_target", "sqlite")),
            pg_host=str(getattr(args, "pg_host", "localhost")),
            pg_port=int(getattr(args, "pg_port", 5432)),
            pg_database=str(getattr(args, "pg_database", "clawer")),
            pg_user=str(getattr(args, "pg_user", "test")),
            pg_password=str(getattr(args, "pg_password", "")),
        )
    except (ValueError, RuntimeError) as exc:
        print(f"[ingest-ranking-staging] aborted: {exc}")
        validation_summary = _validate_ranking_staging(args.staging_input_file)
        print(
            "[ingest-ranking-staging] "
            f"total={validation_summary['total_rows']} "
            f"valid={validation_summary['valid_row_count']} "
            f"invalid={validation_summary['invalid_row_count']} "
            f"duplicates={validation_summary['duplicate_row_count']}"
        )
        return 1

    print(
        "[ingest-ranking-staging] "
        f"write_target={summary['write_target']} "
        f"mode={summary['mode']} "
        f"inserted={summary['inserted_row_count']} "
        f"skipped_existing={summary['skipped_existing_row_count']} "
        f"valid={summary['valid_row_count']} "
        f"invalid={summary['invalid_row_count']} "
        f"duplicates={summary['duplicate_row_count']}"
    )
    print(f"[ingest-ranking-staging] target_location={summary['target_location']}")
    print(f"[ingest-ranking-staging] table={summary['table_name']}")
    return 0


def _cmd_preview_ranking_warehouse_map(args: argparse.Namespace) -> int:
    """Handler for the ``preview-ranking-warehouse-map`` command."""
    summary = _preview_ranking_warehouse_map(
        input_source=str(args.input_source),
        staging_input_file=str(args.staging_input_file),
        staging_table=str(args.staging_table),
        output_file=str(args.output_file),
        pg_host=str(args.pg_host),
        pg_port=int(args.pg_port),
        pg_database=str(args.pg_database),
        pg_user=str(args.pg_user),
        pg_password=str(args.pg_password),
    )
    print(
        "[preview-ranking-warehouse-map] "
        f"input_source={summary['input_source']} "
        f"rows={summary['row_count']} "
        f"output={summary['output_file']}"
    )
    if summary["preview_rows"]:
        print("[preview-ranking-warehouse-map] preview_rows:")
        print(json.dumps(summary["preview_rows"], ensure_ascii=False, indent=2))
    return 0


def _cmd_decision_ranking_preview(args: argparse.Namespace) -> int:
    """Handler for the ``decision-ranking-preview`` command."""
    try:
        summary = _decision_ranking_preview(
            source_schema=str(args.source_schema),
            source_table=str(args.source_table),
            target_schema=str(args.target_schema),
            target_table=str(args.target_table),
            output_file=str(args.output_file),
            pg_host=str(args.pg_host),
            pg_port=int(args.pg_port),
            pg_database=str(args.pg_database),
            pg_user=str(args.pg_user),
            pg_password=str(args.pg_password),
        )
    except RuntimeError as exc:
        print(f"[decision-ranking-preview] aborted: {exc}")
        return 1

    print(
        f"[decision-ranking-preview] rows={summary['row_count']} "
        f"inserted={summary['inserted_row_count']}"
    )
    return 0


#: Commands this module owns, merged into run_pipeline's dispatch table.
COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "validate-ranking-staging": _cmd_validate_ranking_staging,
    "ingest-ranking-staging": _cmd_ingest_ranking_staging,
    "preview-ranking-warehouse-map": _cmd_preview_ranking_warehouse_map,
    "decision-ranking-preview": _cmd_decision_ranking_preview,
}
