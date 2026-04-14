from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Sequence

from crawlernest_admission_crawler.engine import AdmissionCrawlerEngine
from crawlernest_admission_crawler.normalize import normalize_admission_records
from crawlernest_admission_crawler.writer import write_normalized_admission_rows_to_jsonl
from crawlernest_ranking_crawler.engine import RankingCrawlerEngine
from crawlernest_ranking_crawler.normalize import normalize_ranking_records
from crawlernest_ranking_crawler.writer import write_normalized_ranking_rows_to_jsonl


def run_ranking_sample_export(
    output_path: Path,
    *,
    normalized_output_path: Path | None = None,
    staging_output_path: Path | None = None,
) -> tuple[Path, int, Path | None, Path | None]:
    records = RankingCrawlerEngine().run()
    write_records_to_json(records, output_path)
    normalized_path: Path | None = None
    staging_path: Path | None = None
    normalized_rows = None
    if normalized_output_path is not None or staging_output_path is not None:
        normalized_rows = normalize_ranking_records(records)
    if normalized_output_path is not None and normalized_rows is not None:
        write_records_to_json(normalized_rows, normalized_output_path)
        normalized_path = normalized_output_path
    if staging_output_path is not None and normalized_rows is not None:
        write_normalized_ranking_rows_to_jsonl(normalized_rows, staging_output_path)
        staging_path = staging_output_path
    return output_path, len(records), normalized_path, staging_path


def run_admission_sample_export(
    output_path: Path,
    *,
    normalized_output_path: Path | None = None,
    staging_output_path: Path | None = None,
) -> tuple[Path, int, Path | None, Path | None]:
    records = AdmissionCrawlerEngine().run()
    write_records_to_json(records, output_path)
    normalized_path: Path | None = None
    staging_path: Path | None = None
    normalized_rows = None
    if normalized_output_path is not None or staging_output_path is not None:
        normalized_rows = normalize_admission_records(records)
    if normalized_output_path is not None and normalized_rows is not None:
        write_records_to_json(normalized_rows, normalized_output_path)
        normalized_path = normalized_output_path
    if staging_output_path is not None and normalized_rows is not None:
        write_normalized_admission_rows_to_jsonl(normalized_rows, staging_output_path)
        staging_path = staging_output_path
    return output_path, len(records), normalized_path, staging_path


def write_records_to_json(records: Sequence[Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [_to_jsonable(record) for record in records]
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value
