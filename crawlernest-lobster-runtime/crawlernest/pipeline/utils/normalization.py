from __future__ import annotations

import re
import unicodedata
from typing import Iterable

from constants import COUNTRY_CODES, COUNTRY_NAME_ALIASES
from models import University


def normalize_space(value: str) -> str:
    return " ".join((value or "").strip().split())


def normalize_country(value: str) -> str:
    cleaned = normalize_space(value)
    if not cleaned:
        return cleaned
    lowered = COUNTRY_NAME_ALIASES.get(cleaned.lower(), cleaned.lower())
    lowered = "".join(ch for ch in unicodedata.normalize("NFKD", lowered) if not unicodedata.combining(ch))
    lowered = re.sub(r"[^a-z0-9 ]+", " ", lowered)
    lowered = COUNTRY_NAME_ALIASES.get(normalize_space(lowered), normalize_space(lowered))
    for code, name in COUNTRY_CODES.items():
        if lowered in (code.lower(), name.lower()):
            return name
    return " ".join(part.capitalize() for part in lowered.split())


def normalize_rank(rank_text: str) -> str:
    match = re.search(r"\d+", str(rank_text or ""))
    return match.group(0) if match else str(rank_text or "N/A")


def normalize_universities(universities: Iterable[University]) -> list[University]:
    out: list[University] = []
    for uni in universities:
        uni.rank = normalize_rank(uni.rank)
        uni.name = normalize_space(uni.name)
        uni.country = normalize_country(uni.country)
        uni.path = normalize_space(uni.path)
        uni.table_metrics = {
            normalize_space(str(k)): normalize_space(str(v))
            for k, v in (uni.table_metrics or {}).items()
            if normalize_space(str(k))
        }
        out.append(uni)
    return out
