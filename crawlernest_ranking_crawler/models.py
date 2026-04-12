from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass(slots=True)
class RankingRecord:
    university_name: str
    source: str
    rank: int
    year: int
    source_url: Optional[str]
    extracted_at: datetime
    raw_payload: Optional[dict[str, Any]] = None
