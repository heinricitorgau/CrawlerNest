"""Ranking crawler data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RankingRecord:
    source: str
    ranking_year: int
    universe_type: str
    universe_key: str
    institution_name: str
    country: str
    rank: int
    score: float | None = None
