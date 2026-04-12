"""Ranking row extraction helpers."""

from __future__ import annotations

from typing import Iterable

from models import RankingRecord


def to_ranking_records(rows: Iterable[dict[str, object]]) -> list[RankingRecord]:
    records: list[RankingRecord] = []
    for row in rows:
        records.append(
            RankingRecord(
                source=str(row["source"]),
                ranking_year=int(row["ranking_year"]),
                universe_type=str(row["universe_type"]),
                universe_key=str(row["universe_key"]),
                institution_name=str(row["institution_name"]),
                country=str(row["country"]),
                rank=int(row["rank"]),
                score=float(row["score"]) if row.get("score") is not None else None,
            )
        )
    return records
