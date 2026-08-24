"""Load warehouse-ready ranking rows from the preview JSON artifact.

This module also used to write those rows into warehouse.ranking_records_preview,
a landing table that MultiSourceRankingPipeline superseded when it became the
sole writer of warehouse.ranking_record. The write half was removed with the
table; what remains is artifact I/O and touches no database.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from crawlernest_ranking_crawler.warehouse_mapper import WarehouseReadyRankingRow


def load_warehouse_preview_rows(preview_file: Path) -> list[WarehouseReadyRankingRow]:
    payload = json.loads(preview_file.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("warehouse preview artifact must be a JSON array")

    rows: list[WarehouseReadyRankingRow] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("warehouse preview artifact rows must be JSON objects")
        rows.append(
            WarehouseReadyRankingRow(
                university_name=str(item["university_name"]),
                normalized_university_name=str(item["normalized_university_name"]),
                source=str(item["source"]),
                rank=int(item["rank"]),
                year=int(item["year"]),
                source_url=item.get("source_url"),
                extracted_at=datetime.fromisoformat(str(item["extracted_at"])),
                ranking_year=int(item["ranking_year"]),
                universe_type=str(item["universe_type"]),
                universe_key=str(item["universe_key"]),
                canonical_university_id=(
                    None if item.get("canonical_university_id") is None else int(item["canonical_university_id"])
                ),
                entity_resolution_status=str(item.get("entity_resolution_status", "unresolved")),
                source_resolution_status=str(item.get("source_resolution_status", "direct_source_only")),
            )
        )
    return rows


def preview_row_to_jsonable(row: WarehouseReadyRankingRow) -> dict[str, object]:
    payload = asdict(row)
    extracted_at = payload.get("extracted_at")
    if isinstance(extracted_at, datetime):
        payload["extracted_at"] = extracted_at.isoformat()
    return payload
