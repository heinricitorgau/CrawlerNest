from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from crawlernest_ranking_crawler.normalize import NormalizedRankingRow


def write_normalized_ranking_rows_to_jsonl(
    rows: list[NormalizedRankingRow],
    output_path: Path,
) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(_row_to_staging_payload(row), ensure_ascii=False) for row in rows]
    serialized = "\n".join(lines)
    if lines:
        serialized += "\n"
    output_path.write_text(serialized, encoding="utf-8")
    return len(rows)


def _row_to_staging_payload(row: NormalizedRankingRow) -> dict[str, object]:
    payload = asdict(row)
    extracted_at = payload.get("extracted_at")
    if isinstance(extracted_at, datetime):
        payload["extracted_at"] = extracted_at.isoformat()
    return payload
