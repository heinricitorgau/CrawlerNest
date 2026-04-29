from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

SUPPORTED_QS_SUBJECT_KEYS = frozenset({"computer-science", "electrical-engineering"})

QS_SUBJECT_ALIASES: dict[str, str] = {
    "computer science": "computer-science",
    "computer-science": "computer-science",
    "computer_science": "computer-science",
    "computer science and information systems": "computer-science",
    "cs": "computer-science",
    "electrical engineering": "electrical-engineering",
    "electrical-engineering": "electrical-engineering",
    "electrical_engineering": "electrical-engineering",
    "engineering - electrical and electronic": "electrical-engineering",
    "engineering electrical and electronic": "electrical-engineering",
    "electrical & electronic engineering": "electrical-engineering",
}

_WHITESPACE_RE = re.compile(r"\s+")
_RANK_NUMBER_RE = re.compile(r"\d+")


@dataclass(frozen=True, slots=True)
class NormalizedSubjectRankingRow:
    source_code: str
    subject_key: str
    ranking_year: int
    rank_position: int | None
    rank_display: str
    university_name: str
    university_name_normalized: str
    country_hint: str | None
    canonical_university_id: int
    score: float | None = None
    score_scale: float | None = 100.0
    source_entity_id: str | None = None
    source_mapping_id: int | None = None
    source_url: str | None = None
    source_version: str | None = None
    raw_payload: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    extracted_at: datetime | None = None

    def __post_init__(self) -> None:
        normalized_source = self.source_code.strip().upper()
        if normalized_source != "QS":
            raise ValueError("Subject Ranking Phase 1 only supports QS source rows")
        object.__setattr__(self, "source_code", normalized_source)

        subject_key = normalize_qs_subject_key(self.subject_key)
        object.__setattr__(self, "subject_key", subject_key)

        if self.ranking_year <= 0:
            raise ValueError("ranking_year must be positive")
        if self.rank_position is not None and self.rank_position <= 0:
            raise ValueError("rank_position must be positive when present")
        if not self.rank_display.strip():
            raise ValueError("rank_display is required")
        if not self.university_name.strip():
            raise ValueError("university_name is required")
        if not self.university_name_normalized.strip():
            raise ValueError("university_name_normalized is required")
        if self.canonical_university_id <= 0:
            raise ValueError("canonical_university_id must be positive")
        if self.score is not None and self.score < 0:
            raise ValueError("score must be non-negative when present")


def normalize_qs_subject_key(value: str) -> str:
    normalized = _normalize_lookup_key(value)
    subject_key = QS_SUBJECT_ALIASES.get(normalized, normalized.replace(" ", "-"))
    if subject_key not in SUPPORTED_QS_SUBJECT_KEYS:
        raise ValueError(
            "Unsupported QS subject for Phase 1: "
            f"{value!r}. Supported subjects: {', '.join(sorted(SUPPORTED_QS_SUBJECT_KEYS))}"
        )
    return subject_key


def parse_rank_position(rank_display: str | int | None) -> int | None:
    if rank_display is None:
        return None
    if isinstance(rank_display, int):
        if rank_display <= 0:
            raise ValueError("rank must be positive")
        return rank_display
    match = _RANK_NUMBER_RE.search(rank_display)
    if match is None:
        return None
    parsed = int(match.group(0))
    if parsed <= 0:
        raise ValueError("rank must be positive")
    return parsed


def normalize_subject_university_name(name: str) -> str:
    collapsed = _WHITESPACE_RE.sub(" ", name.strip())
    return collapsed.casefold()


def build_source_entity_id(*, subject_key: str, ranking_year: int, university_name_normalized: str) -> str:
    normalized_subject = normalize_qs_subject_key(subject_key)
    slug = re.sub(r"[^a-z0-9]+", "-", university_name_normalized.casefold()).strip("-")
    return f"qs:subject:{normalized_subject}:{ranking_year}:{slug}"


def normalized_qs_subject_row_from_raw(
    raw: dict[str, Any],
    *,
    canonical_university_id: int,
) -> NormalizedSubjectRankingRow:
    payload = normalize_qs_subject_row(
        raw,
        subject_key=str(raw.get("subject_key") or raw.get("subject") or ""),
        year=int(raw["ranking_year"]),
    )
    return NormalizedSubjectRankingRow(
        source_code=str(payload["source_code"]),
        subject_key=str(payload["subject_key"]),
        ranking_year=int(payload["ranking_year"]),
        rank_position=None if payload["rank_position"] is None else int(payload["rank_position"]),
        rank_display=str(payload["rank_display"]),
        university_name=str(payload["university_name"]),
        university_name_normalized=str(payload["university_name_normalized"]),
        country_hint=None if payload["country_hint"] is None else str(payload["country_hint"]),
        canonical_university_id=canonical_university_id,
        score=None if payload["score"] is None else float(payload["score"]),
        score_scale=None if payload["score_scale"] is None else float(payload["score_scale"]),
        source_entity_id=None if payload["source_entity_id"] is None else str(payload["source_entity_id"]),
        source_url=None if payload["source_url"] is None else str(payload["source_url"]),
        raw_payload=dict(payload["raw_payload"] or {}),
        metadata={"phase": "subject-ranking-phase-2"},
    )


def normalize_qs_subject_row(raw_row: dict[str, Any], subject_key: str, year: int) -> dict[str, Any]:
    normalized_subject_key = normalize_qs_subject_key(subject_key or str(raw_row.get("subject") or ""))
    university_name = clean_qs_university_name(
        str(raw_row.get("name") or raw_row.get("university_name") or raw_row.get("institution") or "")
    )
    normalized_name = normalize_subject_university_name(university_name)
    rank_display = str(raw_row.get("rank_display") or raw_row.get("rank") or "").strip()
    score = parse_score(raw_row.get("score"))
    source_entity_id = raw_row.get("source_entity_id") or build_source_entity_id(
        subject_key=normalized_subject_key,
        ranking_year=year,
        university_name_normalized=normalized_name,
    )
    return {
        "source_code": "QS",
        "subject_key": normalized_subject_key,
        "ranking_year": int(year),
        "rank_position": parse_rank_position(rank_display),
        "rank_display": rank_display,
        "university_name": university_name,
        "university_name_normalized": normalized_name,
        "country_hint": raw_row.get("country") or raw_row.get("country_hint"),
        "score": score,
        "score_scale": 100.0,
        "source_entity_id": str(source_entity_id),
        "source_url": raw_row.get("url") or raw_row.get("source_url"),
        "raw_payload": dict(raw_row),
    }


def clean_qs_university_name(name: str) -> str:
    cleaned = _WHITESPACE_RE.sub(" ", name.strip())
    cleaned = re.sub(r"\s+\([A-Z0-9&.\-\s]{2,20}\)$", "", cleaned).strip()
    return cleaned


def parse_score(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text or text in {"-", "n/a", "N/A"}:
        return None
    return float(text)


def _normalize_lookup_key(value: str) -> str:
    cleaned = value.strip().casefold().replace("_", " ").replace("-", " ")
    cleaned = cleaned.replace("&", " and ")
    return _WHITESPACE_RE.sub(" ", cleaned).strip()
