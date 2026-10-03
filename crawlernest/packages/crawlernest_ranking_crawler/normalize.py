from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from crawlernest_ranking_crawler.models import RankingRecord

_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(slots=True)
class NormalizedRankingRow:
    university_name: str
    normalized_university_name: str
    source: str
    rank: int
    year: int
    source_url: str | None
    extracted_at: datetime


def normalize_ranking_records(records: list[RankingRecord]) -> list[NormalizedRankingRow]:
    return [
        NormalizedRankingRow(
            university_name=record.university_name,
            normalized_university_name=normalize_university_name(record.university_name),
            source=record.source.strip(),
            rank=record.rank,
            year=record.year,
            source_url=record.source_url,
            extracted_at=record.extracted_at,
        )
        for record in records
    ]


def normalize_university_name(name: str) -> str:
    collapsed = _WHITESPACE_RE.sub(" ", name.strip())
    if not collapsed:
        return collapsed
    return " ".join(_normalize_token(token) for token in collapsed.split(" "))


def _normalize_token(token: str) -> str:
    if token.isupper() and len(token) <= 5:
        return token
    if token.islower() or token.isupper():
        return token.capitalize()
    return token
