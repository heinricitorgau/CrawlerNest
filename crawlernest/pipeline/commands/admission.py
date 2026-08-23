"""Admission staging commands for the CrawlerNest pipeline.

Validation, ingestion, warehouse preview and entity resolution for admission
records. Extracted from run_pipeline.py, where these lived alongside every other
command group.

Each handler takes the parsed argparse namespace and returns a process exit
code. :data:`COMMANDS` is what run_pipeline.py merges into its dispatch table.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

#: Git repository root, where the crawlernest_admission_crawler package lives.
#:
#: run_pipeline.py derives this as ``Path(__file__).resolve().parent.parent``
#: because it sits one level down; from this module it is three. Getting that
#: wrong imports cleanly and fails at call time, so it is computed once here
#: rather than repeated in every helper.
WORKSPACE_ROOT = Path(__file__).resolve().parents[3]


def _ensure_workspace_on_path() -> None:
    """Put the repository root on sys.path for the deferred crawler imports."""
    if str(WORKSPACE_ROOT) not in sys.path:
        sys.path.insert(0, str(WORKSPACE_ROOT))


def _validate_admission_staging(staging_file: str) -> dict[str, Any]:
    workspace_root = WORKSPACE_ROOT
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from crawlernest_admission_crawler.validator import (  # noqa: E402
        summary_to_dict,
        validate_admission_staging_file,
    )

    summary = validate_admission_staging_file(Path(staging_file))
    return summary_to_dict(summary)


def _ingest_admission_staging(
    staging_file: str,
    sqlite_db_file: str,
    *,
    allow_partial: bool,
    write_target: str,
    staging_table: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    workspace_root = WORKSPACE_ROOT
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from crawlernest_admission_crawler.writer import (  # noqa: E402
        ingest_admission_staging_file,
        ingest_summary_to_dict,
    )

    summary = ingest_admission_staging_file(
        Path(staging_file),
        Path(sqlite_db_file),
        allow_partial=allow_partial,
        write_target=write_target,
        staging_table=staging_table,
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
    )
    return ingest_summary_to_dict(summary)


def _preview_admission_warehouse_map(
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

    from crawlernest_admission_crawler.warehouse_mapper import (  # noqa: E402
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


def _write_admission_warehouse_preview(
    *,
    input_source: str,
    preview_input_file: str,
    staging_input_file: str,
    staging_table: str,
    landing_schema: str,
    landing_table: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    workspace_root = WORKSPACE_ROOT
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from crawlernest_admission_crawler.warehouse_mapper import (  # noqa: E402
        load_staging_rows_from_jsonl,
        load_staging_rows_from_postgres,
        map_staging_rows_to_warehouse_rows,
    )
    from crawlernest_admission_crawler.warehouse_writer import (  # noqa: E402
        load_warehouse_preview_rows,
        warehouse_landing_summary_to_dict,
        write_warehouse_landing_rows,
    )

    if input_source == "preview-json":
        rows = load_warehouse_preview_rows(Path(preview_input_file))
    elif input_source == "jsonl":
        rows = map_staging_rows_to_warehouse_rows(load_staging_rows_from_jsonl(Path(staging_input_file)))
    elif input_source == "postgres":
        rows = map_staging_rows_to_warehouse_rows(
            load_staging_rows_from_postgres(
                table_name=staging_table,
                pg_host=pg_host,
                pg_port=pg_port,
                pg_database=pg_database,
                pg_user=pg_user,
                pg_password=pg_password,
            )
        )
    else:
        raise ValueError(f"Unsupported input source: {input_source}")

    summary = write_warehouse_landing_rows(
        rows,
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
        schema_name=landing_schema,
        table_name=landing_table,
    )
    return warehouse_landing_summary_to_dict(summary)


def _resolve_admission_entities(
    *,
    target_schema: str,
    target_table: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    workspace_root = WORKSPACE_ROOT
    if str(workspace_root) not in sys.path:
        sys.path.insert(0, str(workspace_root))

    from crawlernest_admission_crawler.entity_resolver import (  # noqa: E402
        entity_resolution_summary_to_dict,
        resolve_admission_preview_entities,
    )

    summary = resolve_admission_preview_entities(
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
        target_schema=target_schema,
        target_table=target_table,
    )
    return entity_resolution_summary_to_dict(summary)


def _get_unresolved_admission_entities(
    *,
    target_schema: str,
    target_table: str,
    limit: int,
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

    from crawlernest_admission_crawler.unresolved_report import (  # noqa: E402
        get_unresolved_admission_entities,
        unresolved_rows_to_dicts,
        write_unresolved_report,
    )

    rows = get_unresolved_admission_entities(
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
        target_schema=target_schema,
        target_table=target_table,
        limit=limit,
    )
    if output_file:
        write_unresolved_report(rows, Path(output_file))

    return {
        "target_table": f"{target_schema}.{target_table}",
        "row_count": len(rows),
        "rows": unresolved_rows_to_dicts(rows),
        "output_file": output_file,
    }


def _refresh_admission_resolution(
    *,
    target_schema: str,
    target_table: str,
    limit: int,
    output_file: str,
    pg_host: str,
    pg_port: int,
    pg_database: str,
    pg_user: str,
    pg_password: str,
) -> dict[str, Any]:
    full_summary_limit = 1_000_000

    before_summary = _get_unresolved_admission_entities(
        target_schema=target_schema,
        target_table=target_table,
        limit=full_summary_limit,
        output_file="",
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
    )

    resolution_summary = _resolve_admission_entities(
        target_schema=target_schema,
        target_table=target_table,
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
    )

    after_full_summary = _get_unresolved_admission_entities(
        target_schema=target_schema,
        target_table=target_table,
        limit=full_summary_limit,
        output_file="",
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
    )
    after_display_summary = _get_unresolved_admission_entities(
        target_schema=target_schema,
        target_table=target_table,
        limit=limit,
        output_file=output_file,
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
    )

    before_unresolved_count = sum(int(row["occurrence_count"]) for row in before_summary["rows"])
    after_unresolved_count = sum(int(row["occurrence_count"]) for row in after_full_summary["rows"])

    return {
        "target_table": before_summary["target_table"],
        "before_unresolved_count": before_unresolved_count,
        "before_distinct_university_count": before_summary["row_count"],
        "after_unresolved_count": after_unresolved_count,
        "after_distinct_university_count": after_full_summary["row_count"],
        "resolved_row_count": resolution_summary["resolved_row_count"],
        "unresolved_row_count": resolution_summary["unresolved_row_count"],
        "exact_match_count": resolution_summary["exact_match_count"],
        "normalized_match_count": resolution_summary["normalized_match_count"],
        "fuzzy_match_count": resolution_summary["fuzzy_match_count"],
        "review_pending_count": resolution_summary["review_pending_count"],
        "retired_mapping_count": resolution_summary["retired_mapping_count"],
        "human_decision_applied_count": resolution_summary["human_decision_applied_count"],
        "display_rows": after_display_summary["rows"],
        "output_file": after_display_summary["output_file"],
    }


def _cmd_validate_admission_staging(args: argparse.Namespace) -> int:
    """Handler for the ``validate-admission-staging`` command."""
    summary = _validate_admission_staging(args.staging_input_file)
    print(
        "[validate-admission-staging] "
        f"total={summary['total_rows']} "
        f"valid={summary['valid_row_count']} "
        f"invalid={summary['invalid_row_count']} "
        f"duplicates={summary['duplicate_row_count']}"
    )
    print(f"[validate-admission-staging] staging_file={summary['staging_file']}")
    if summary["error_samples"]:
        print("[validate-admission-staging] error_samples:")
        print(json.dumps(summary["error_samples"], ensure_ascii=False, indent=2))
    if summary["duplicate_samples"]:
        print("[validate-admission-staging] duplicate_samples:")
        print(json.dumps(summary["duplicate_samples"], ensure_ascii=False, indent=2))
    return 0


def _cmd_ingest_admission_staging(args: argparse.Namespace) -> int:
    """Handler for the ``ingest-admission-staging`` command."""
    try:
        summary = _ingest_admission_staging(
            args.staging_input_file,
            args.sqlite_db_file,
            allow_partial=bool(getattr(args, "allow_partial_ingest", False)),
            write_target=str(getattr(args, "write_target", "sqlite")),
            staging_table=str(getattr(args, "staging_table", "admission_staging_records")),
            pg_host=str(getattr(args, "pg_host", "localhost")),
            pg_port=int(getattr(args, "pg_port", 5432)),
            pg_database=str(getattr(args, "pg_database", "clawer")),
            pg_user=str(getattr(args, "pg_user", "test")),
            pg_password=str(getattr(args, "pg_password", "")),
        )
    except (ValueError, RuntimeError) as exc:
        print(f"[ingest-admission-staging] aborted: {exc}")
        validation_summary = _validate_admission_staging(args.staging_input_file)
        print(
            "[ingest-admission-staging] "
            f"total={validation_summary['total_rows']} "
            f"valid={validation_summary['valid_row_count']} "
            f"invalid={validation_summary['invalid_row_count']} "
            f"duplicates={validation_summary['duplicate_row_count']}"
        )
        return 1

    print(
        "[ingest-admission-staging] "
        f"write_target={summary['write_target']} "
        f"mode={summary['mode']} "
        f"inserted={summary['inserted_row_count']} "
        f"skipped_existing={summary['skipped_existing_row_count']} "
        f"valid={summary['valid_row_count']} "
        f"invalid={summary['invalid_row_count']} "
        f"duplicates={summary['duplicate_row_count']}"
    )
    print(f"[ingest-admission-staging] target_location={summary['target_location']}")
    print(f"[ingest-admission-staging] table={summary['table_name']}")
    return 0


def _cmd_preview_admission_warehouse_map(args: argparse.Namespace) -> int:
    """Handler for the ``preview-admission-warehouse-map`` command."""
    summary = _preview_admission_warehouse_map(
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
        "[preview-admission-warehouse-map] "
        f"input_source={summary['input_source']} "
        f"rows={summary['row_count']} "
        f"output={summary['output_file']}"
    )
    if summary["preview_rows"]:
        print("[preview-admission-warehouse-map] preview_rows:")
        print(json.dumps(summary["preview_rows"], ensure_ascii=False, indent=2))
    return 0


def _cmd_write_admission_warehouse_preview(args: argparse.Namespace) -> int:
    """Handler for the ``write-admission-warehouse-preview`` command."""
    try:
        summary = _write_admission_warehouse_preview(
            input_source=str(args.input_source),
            preview_input_file=str(args.preview_input_file),
            staging_input_file=str(args.staging_input_file),
            staging_table=str(args.staging_table),
            landing_schema=str(args.landing_schema),
            landing_table=str(args.landing_table),
            pg_host=str(args.pg_host),
            pg_port=int(args.pg_port),
            pg_database=str(args.pg_database),
            pg_user=str(args.pg_user),
            pg_password=str(args.pg_password),
        )
    except RuntimeError as exc:
        print(f"[write-admission-warehouse-preview] aborted: {exc}")
        return 1

    print(
        "[write-admission-warehouse-preview] "
        f"rows={summary['row_count']} "
        f"inserted={summary['inserted_row_count']} "
        f"updated={summary['updated_row_count']}"
    )
    print(f"[write-admission-warehouse-preview] target={summary['target_location']}")
    print(f"[write-admission-warehouse-preview] table={summary['table_name']}")
    return 0


def _cmd_resolve_admission_entities(args: argparse.Namespace) -> int:
    """Handler for the ``resolve-admission-entities`` command."""
    try:
        summary = _resolve_admission_entities(
            target_schema=str(args.target_schema),
            target_table=str(args.target_table),
            pg_host=str(args.pg_host),
            pg_port=int(args.pg_port),
            pg_database=str(args.pg_database),
            pg_user=str(args.pg_user),
            pg_password=str(args.pg_password),
        )
    except RuntimeError as exc:
        print(f"[resolve-admission-entities] aborted: {exc}")
        return 1

    print(
        "[resolve-admission-entities] "
        f"total={summary['total_rows']} "
        f"resolved={summary['resolved_row_count']} "
        f"no_canonical={summary['unresolved_row_count']} "
        f"exact={summary['exact_match_count']} "
        f"normalized={summary['normalized_match_count']} "
        f"fuzzy={summary['fuzzy_match_count']} "
        f"awaiting_review={summary['review_pending_count']} "
        f"retired={summary['retired_mapping_count']} "
        f"human_decisions_applied={summary['human_decision_applied_count']}"
    )
    print(f"[resolve-admission-entities] target={summary['target_table']}")
    return 0


def _cmd_unresolved_admission_entities(args: argparse.Namespace) -> int:
    """Handler for the ``unresolved-admission-entities`` command."""
    try:
        summary = _get_unresolved_admission_entities(
            target_schema=str(args.target_schema),
            target_table=str(args.target_table),
            limit=int(args.limit),
            output_file=str(args.output_file),
            pg_host=str(args.pg_host),
            pg_port=int(args.pg_port),
            pg_database=str(args.pg_database),
            pg_user=str(args.pg_user),
            pg_password=str(args.pg_password),
        )
    except RuntimeError as exc:
        print(f"[unresolved-admission-entities] aborted: {exc}")
        return 1

    print(
        "[unresolved-admission-entities] "
        f"target={summary['target_table']} "
        f"rows={summary['row_count']}"
    )
    if summary["rows"]:
        print("normalized_university_name | occurrence_count")
        for row in summary["rows"]:
            print(f"{row['normalized_university_name']} | {row['occurrence_count']}")
    else:
        print("No unresolved admission entities found.")
    if summary["output_file"]:
        print(f"[unresolved-admission-entities] output={summary['output_file']}")
    return 0


def _cmd_refresh_admission_resolution(args: argparse.Namespace) -> int:
    """Handler for the ``refresh-admission-resolution`` command."""
    try:
        summary = _refresh_admission_resolution(
            target_schema=str(args.target_schema),
            target_table=str(args.target_table),
            limit=int(args.limit),
            output_file=str(args.output_file),
            pg_host=str(args.pg_host),
            pg_port=int(args.pg_port),
            pg_database=str(args.pg_database),
            pg_user=str(args.pg_user),
            pg_password=str(args.pg_password),
        )
    except RuntimeError as exc:
        print(f"[refresh-admission-resolution] aborted: {exc}")
        return 1

    print(
        "[refresh-admission-resolution] "
        f"target={summary['target_table']} "
        f"before_unresolved={summary['before_unresolved_count']} "
        f"after_unresolved={summary['after_unresolved_count']} "
        f"before_distinct={summary['before_distinct_university_count']} "
        f"after_distinct={summary['after_distinct_university_count']} "
        f"resolved={summary['resolved_row_count']} "
        f"no_canonical={summary['unresolved_row_count']} "
        f"exact={summary['exact_match_count']} "
        f"normalized={summary['normalized_match_count']} "
        f"fuzzy={summary['fuzzy_match_count']} "
        f"awaiting_review={summary['review_pending_count']} "
        f"retired={summary['retired_mapping_count']} "
        f"human_decisions_applied={summary['human_decision_applied_count']}"
    )
    if summary["display_rows"]:
        print("normalized_university_name | occurrence_count")
        for row in summary["display_rows"]:
            print(f"{row['normalized_university_name']} | {row['occurrence_count']}")
    else:
        print("No unresolved admission entities found.")
    if summary["output_file"]:
        print(f"[refresh-admission-resolution] output={summary['output_file']}")
    return 0


#: Commands this module owns, merged into run_pipeline's dispatch table.
COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "validate-admission-staging": _cmd_validate_admission_staging,
    "ingest-admission-staging": _cmd_ingest_admission_staging,
    "preview-admission-warehouse-map": _cmd_preview_admission_warehouse_map,
    "write-admission-warehouse-preview": _cmd_write_admission_warehouse_preview,
    "resolve-admission-entities": _cmd_resolve_admission_entities,
    "unresolved-admission-entities": _cmd_unresolved_admission_entities,
    "refresh-admission-resolution": _cmd_refresh_admission_resolution,
}
