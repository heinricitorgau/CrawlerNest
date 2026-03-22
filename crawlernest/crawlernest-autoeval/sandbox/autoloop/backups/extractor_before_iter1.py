#!/usr/bin/env python3
"""CrawlerNest extractor with robust fallback parsing for AutoEval.

This module exposes a stable module-level ``extract`` function that always
returns a plain dict with exactly these keys:
- university
- program
- quota
"""

from __future__ import annotations

import json
import re
from typing import Any


UNIVERSITY_ALIASES = {
    "NYCU": "National Yang Ming Chiao Tung University",
    "國立陽明交通大學": "National Yang Ming Chiao Tung University",
    "國立臺北科技大學": "National Taipei University of Technology",
    "國立東華大學": "National Dong Hwa University",
}

UNIVERSITY_PATTERNS = [
    r"University\s*[:=]\s*([^\n]+)",
    r"University Name\s*[:=]\s*([^\n]+)",
    r"School\s*[:=]\s*([^\n]+)",
    r"\b(National [A-Z][A-Za-z&'().\- ]+University)\b",
    r"\b(Fu Jen Catholic University)\b",
    r"\b(Tamkang University)\b",
    r"\b(NYCU)\b",
    r"\b國立陽明交通大學\b",
    r"\b國立臺北科技大學\b",
    r"\b國立東華大學\b",
]

PROGRAM_PATTERNS = [
    r"Program\s*[:=]\s*([^\n]+)",
    r"Major(?:/Program)?\s*[:=]\s*([^\n]+)",
    r"Department(?:/Track)?\s*[:=]\s*([^\n]+)",
    r"Track\s*[:=]\s*([^\n]+)",
    r"program track\s*[:=]\s*([^\n]+)",
    r"major\s*[:=]\s*([^\n]+)",
    r"Department of\s+([^\n]+)",
    r"Major -\s*([^\n]+)",
]

QUOTA_PATTERNS = [
    r"Capacity(?:\s+is|\s+for\s+\d{4}\s+entry)?\s*[:=]?\s*(?:approximately|approx\.?|about|up to|around)?\s*(\d+)",
    r"Intake(?:\s+is|\s*[:=~])?\s*(?:approximately|approx\.?|about|up to|around)?\s*(\d+)",
    r"admits around\s*(\d+)",
    r"about\s*(\d+)\s*seats",
    r"approximately\s*(\d+)\s*seats",
    r"enrollment cap\s*[:=]?\s*(\d+)",
    r"招生名額[：:]?\s*(?:約|approximately|approx\.?|about)?\s*(\d+)",
    r"預計招收(?:約)?\s*(\d+)",
    r"招收約\s*(\d+)\s*人",
    r"(\d+)\s*seats",
    r"(\d+)\s*students",
]


def _strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(
        r"</p>|</div>|</section>|</h1>|</h2>|</header>|</footer>|</body>|</html>",
        "\n",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"<[^>]+>", " ", text)
    return text


def _normalize_text(text: str) -> str:
    text = _strip_html(text)
    text = text.replace("\r", "\n")
    text = re.sub(r"[|•]", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"\n+", "\n", text)
    return text.strip()


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    match = re.search(r"\d+", str(value))
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def _extract_first(patterns: list[str], text: str, flags: int = re.IGNORECASE) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return match.group(1).strip()
    return None


def _clean_field(value: str | None) -> str | None:
    if value is None:
        return None
    value = re.split(r"[;|]", value)[0].strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[.,;:]+$", "", value).strip()
    return value or None


def _normalize_university(value: str | None) -> str | None:
    value = _clean_field(value)
    if value is None:
        return None
    if value in UNIVERSITY_ALIASES:
        return UNIVERSITY_ALIASES[value]
    for alias, canonical in UNIVERSITY_ALIASES.items():
        if alias in value:
            return canonical
    return value


def _extract_from_dict(data: dict[str, Any]) -> dict[str, Any]:
    university = None
    program = None
    quota = None

    for key in ("school", "university"):
        if data.get(key):
            university = _normalize_university(str(data[key]))
            break

    for key in ("department", "program", "major", "track"):
        if data.get(key):
            program = _clean_field(str(data[key]))
            break

    for key in ("quota", "capacity", "intake"):
        if data.get(key) is not None:
            quota = _safe_int(data[key])
            if quota is not None:
                break

    if quota is None and data.get("notes"):
        quota = _safe_int(data["notes"])

    return {
        "university": university,
        "program": program,
        "quota": quota,
    }


def _extract_university(text: str) -> str | None:
    value = _extract_first(UNIVERSITY_PATTERNS, text)
    return _normalize_university(value)


def _extract_program(text: str) -> str | None:
    for pattern in PROGRAM_PATTERNS:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        if matches:
            candidate = _clean_field(matches[0])
            if candidate:
                return candidate
    return None


def _extract_quota(text: str) -> int | None:
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    priority_keywords = ("intake", "capacity", "招生名額", "招收", "seats", "students", "admits")

    for line in lines:
        lowered = line.lower()
        if any(keyword in lowered for keyword in priority_keywords) or any(
            keyword in line for keyword in ("招生名額", "招收")
        ):
            for pattern in QUOTA_PATTERNS:
                match = re.search(pattern, line, flags=re.IGNORECASE)
                if match:
                    value = _safe_int(match.group(1))
                    if value is not None:
                        return value

    for pattern in QUOTA_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = _safe_int(match.group(1))
            if value is not None:
                return value

    return None


def extract(raw_input: Any) -> dict[str, Any]:
    """Extract university, program, and quota from raw input.

    This function is deterministic and never raises exceptions outward.
    """
    try:
        if isinstance(raw_input, dict):
            result = _extract_from_dict(raw_input)
            return {
                "university": result.get("university"),
                "program": result.get("program"),
                "quota": result.get("quota"),
            }

        parsed_json = None
        if isinstance(raw_input, str):
            try:
                parsed_json = json.loads(raw_input)
            except Exception:
                parsed_json = None

        if isinstance(parsed_json, dict):
            result = _extract_from_dict(parsed_json)
            if any(value is not None for value in result.values()):
                return {
                    "university": result.get("university"),
                    "program": result.get("program"),
                    "quota": result.get("quota"),
                }

        text = raw_input if isinstance(raw_input, str) else str(raw_input)
        text = _normalize_text(text)

        university = _extract_university(text)
        program = _extract_program(text)
        quota = _extract_quota(text)

        return {
            "university": university,
            "program": program,
            "quota": quota,
        }
    except Exception:
        return {
            "university": None,
            "program": None,
            "quota": None,
        }


def extract_fields(raw_input: Any) -> dict[str, Any]:
    return extract(raw_input)


def run_extractor(raw_input: Any) -> dict[str, Any]:
    return extract(raw_input)


def parse(raw_input: Any) -> dict[str, Any]:
    return extract(raw_input)


def extract_admission_data(raw_input: Any) -> dict[str, Any]:
    return extract(raw_input)