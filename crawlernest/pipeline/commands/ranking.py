"""Ranking staging commands for the CrawlerNest pipeline.

Validation, ingestion, warehouse preview and write, aggregation and decision
previews, and entity resolution for ranking records. Extracted from
run_pipeline.py, where these lived alongside every other command group.

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


def _write_ranking_warehouse_preview(
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

    from crawlernest_ranking_crawler.warehouse_mapper import (  # noqa: E402
        load_staging_rows_from_jsonl,
        load_staging_rows_from_postgres,
        map_staging_rows_to_warehouse_rows,
    )
    from crawlernest_ranking_crawler.warehouse_writer import (  # noqa: E402
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


def _aggregate_ranking_preview(
    *,
    input_source: str,
    preview_input_file: str,
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

    from crawlernest_ranking_crawler.aggregation_writer import (  # noqa: E402
        aggregation_write_summary_to_dict,
        write_aggregated_rows,
    )
    from crawlernest_ranking_crawler.aggregator import (  # noqa: E402
        aggregate_rankings,
        aggregated_rows_to_jsonable,
    )
    from crawlernest_ranking_crawler.postgres_driver import get_psycopg2  # noqa: E402
    from crawlernest_ranking_crawler.warehouse_mapper import (  # noqa: E402
        load_staging_rows_from_postgres,
        map_staging_rows_to_warehouse_rows,
    )
    from crawlernest_ranking_crawler.warehouse_writer import load_warehouse_preview_rows  # noqa: E402

    if input_source == "preview-json":
        source_rows = load_warehouse_preview_rows(Path(preview_input_file))
        source_location = str(Path(preview_input_file))
    elif input_source == "postgres":
        staging_rows = load_staging_rows_from_postgres(
            table_name=f"{source_schema}.{source_table}",
            pg_host=pg_host,
            pg_port=pg_port,
            pg_database=pg_database,
            pg_user=pg_user,
            pg_password=pg_password,
        )
        source_rows = map_staging_rows_to_warehouse_rows(staging_rows)
        source_location = f"postgresql://{pg_host}:{pg_port}/{pg_database}#{source_schema}.{source_table}"
    else:
        raise ValueError(f"Unsupported input source: {input_source}")

    aggregated_rows = aggregate_rankings(source_rows)
    output_path = Path(output_file)
    save_json_artifact(output_path, aggregated_rows_to_jsonable(aggregated_rows))

    psycopg2 = get_psycopg2()
    conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        dbname=pg_database,
        user=pg_user,
        password=pg_password,
    )
    try:
        summary = write_aggregated_rows(
            aggregated_rows,
            conn,
            schema_name=target_schema,
            table_name=target_table,
        )
    finally:
        conn.close()

    payload = aggregation_write_summary_to_dict(summary)
    payload["input_source"] = input_source
    payload["source_location"] = source_location
    payload["output_file"] = str(output_path)
    payload["preview_rows"] = aggregated_rows_to_jsonable(aggregated_rows[:5])
    return payload


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
        aggregated_rows = load_aggregated_rows_from_postgres(conn)
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


def _resolve_ranking_entities(
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

    from crawlernest_ranking_crawler.entity_resolver import (  # noqa: E402
        entity_resolution_summary_to_dict,
        resolve_ranking_preview_entities,
    )

    summary = resolve_ranking_preview_entities(
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
        target_schema=target_schema,
        target_table=target_table,
    )
    return entity_resolution_summary_to_dict(summary)


def _get_unresolved_ranking_entities(
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

    from crawlernest_ranking_crawler.unresolved_report import (  # noqa: E402
        get_unresolved_universities,
        unresolved_rows_to_dicts,
        write_unresolved_report,
    )

    rows = get_unresolved_universities(
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


def _refresh_ranking_resolution(
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

    before_summary = _get_unresolved_ranking_entities(
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

    resolution_summary = _resolve_ranking_entities(
        target_schema=target_schema,
        target_table=target_table,
        pg_host=pg_host,
        pg_port=pg_port,
        pg_database=pg_database,
        pg_user=pg_user,
        pg_password=pg_password,
    )

    after_full_summary = _get_unresolved_ranking_entities(
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
    after_display_summary = _get_unresolved_ranking_entities(
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
        "display_rows": after_display_summary["rows"],
        "output_file": after_display_summary["output_file"],
    }


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


def _cmd_write_ranking_warehouse_preview(args: argparse.Namespace) -> int:
    """Handler for the ``write-ranking-warehouse-preview`` command."""
    try:
        summary = _write_ranking_warehouse_preview(
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
        print(f"[write-ranking-warehouse-preview] aborted: {exc}")
        return 1

    print(
        "[write-ranking-warehouse-preview] "
        f"rows={summary['row_count']} "
        f"inserted={summary['inserted_row_count']} "
        f"skipped_existing={summary['skipped_existing_row_count']}"
    )
    print(f"[write-ranking-warehouse-preview] target={summary['target_location']}")
    print(f"[write-ranking-warehouse-preview] table={summary['table_name']}")
    return 0


def _cmd_aggregate_ranking_preview(args: argparse.Namespace) -> int:
    """Handler for the ``aggregate-ranking-preview`` command."""
    try:
        summary = _aggregate_ranking_preview(
            input_source=str(args.input_source),
            preview_input_file=str(args.preview_input_file),
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
        print(f"[aggregate-ranking-preview] aborted: {exc}")
        return 1

    print(
        "[aggregate-ranking-preview] "
        f"input_source={summary['input_source']} "
        f"rows={summary['row_count']} "
        f"written={summary['written_row_count']}"
    )
    print(f"[aggregate-ranking-preview] source={summary['source_location']}")
    print(f"[aggregate-ranking-preview] output={summary['output_file']}")
    print(f"[aggregate-ranking-preview] target={summary['target_location']}")
    print(f"[aggregate-ranking-preview] table={summary['table_name']}")
    if summary["preview_rows"]:
        print("[aggregate-ranking-preview] preview_rows:")
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


def _cmd_resolve_ranking_entities(args: argparse.Namespace) -> int:
    """Handler for the ``resolve-ranking-entities`` command."""
    try:
        summary = _resolve_ranking_entities(
            target_schema=str(args.target_schema),
            target_table=str(args.target_table),
            pg_host=str(args.pg_host),
            pg_port=int(args.pg_port),
            pg_database=str(args.pg_database),
            pg_user=str(args.pg_user),
            pg_password=str(args.pg_password),
        )
    except RuntimeError as exc:
        print(f"[resolve-ranking-entities] aborted: {exc}")
        return 1

    print(
        "[resolve-ranking-entities] "
        f"total={summary['total_rows']} "
        f"resolved={summary['resolved_row_count']} "
        f"unresolved={summary['unresolved_row_count']}"
    )
    print(f"[resolve-ranking-entities] target={summary['target_table']}")
    return 0


def _cmd_unresolved_ranking_entities(args: argparse.Namespace) -> int:
    """Handler for the ``unresolved-ranking-entities`` command."""
    try:
        summary = _get_unresolved_ranking_entities(
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
        print(f"[unresolved-ranking-entities] aborted: {exc}")
        return 1

    print(
        "[unresolved-ranking-entities] "
        f"target={summary['target_table']} "
        f"rows={summary['row_count']}"
    )
    if summary["rows"]:
        print("normalized_university_name | occurrence_count")
        for row in summary["rows"]:
            print(f"{row['normalized_university_name']} | {row['occurrence_count']}")
    else:
        print("No unresolved ranking entities found.")
    if summary["output_file"]:
        print(f"[unresolved-ranking-entities] output={summary['output_file']}")
    return 0


def _cmd_refresh_ranking_resolution(args: argparse.Namespace) -> int:
    """Handler for the ``refresh-ranking-resolution`` command."""
    try:
        summary = _refresh_ranking_resolution(
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
        print(f"[refresh-ranking-resolution] aborted: {exc}")
        return 1

    print(
        "[refresh-ranking-resolution] "
        f"target={summary['target_table']} "
        f"before_unresolved={summary['before_unresolved_count']} "
        f"after_unresolved={summary['after_unresolved_count']} "
        f"before_distinct={summary['before_distinct_university_count']} "
        f"after_distinct={summary['after_distinct_university_count']} "
        f"resolved={summary['resolved_row_count']} "
        f"unresolved={summary['unresolved_row_count']}"
    )
    if summary["display_rows"]:
        print("normalized_university_name | occurrence_count")
        for row in summary["display_rows"]:
            print(f"{row['normalized_university_name']} | {row['occurrence_count']}")
    else:
        print("No unresolved ranking entities found.")
    if summary["output_file"]:
        print(f"[refresh-ranking-resolution] output={summary['output_file']}")
    return 0


#: Commands this module owns, merged into run_pipeline's dispatch table.
COMMANDS: dict[str, Callable[[argparse.Namespace], int]] = {
    "validate-ranking-staging": _cmd_validate_ranking_staging,
    "ingest-ranking-staging": _cmd_ingest_ranking_staging,
    "preview-ranking-warehouse-map": _cmd_preview_ranking_warehouse_map,
    "write-ranking-warehouse-preview": _cmd_write_ranking_warehouse_preview,
    "aggregate-ranking-preview": _cmd_aggregate_ranking_preview,
    "decision-ranking-preview": _cmd_decision_ranking_preview,
    "resolve-ranking-entities": _cmd_resolve_ranking_entities,
    "unresolved-ranking-entities": _cmd_unresolved_ranking_entities,
    "refresh-ranking-resolution": _cmd_refresh_ranking_resolution,
}
