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
from typing import Any, Optional

from models import AdmissionRequirements


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


def extract(raw_input):
    """Extract university, program, and quota from raw input safely."""

    empty_result = {
        'university': None,
        'program': None,
        'quota': None,
    }

    try:
        if raw_input is None:
            return empty_result

        if isinstance(raw_input, dict):
            result = _extract_from_dict(raw_input)
            return {
                'university': result.get('university'),
                'program': result.get('program'),
                'quota': result.get('quota'),
            }

        parsed_json = None
        if isinstance(raw_input, str):
            stripped = raw_input.strip()
            if not stripped:
                return empty_result
            try:
                parsed_json = json.loads(stripped)
            except Exception:
                parsed_json = None

        if isinstance(parsed_json, dict):
            result = _extract_from_dict(parsed_json)
            if any(value is not None for value in result.values()):
                return {
                    'university': result.get('university'),
                    'program': result.get('program'),
                    'quota': result.get('quota'),
                }

        text = raw_input if isinstance(raw_input, str) else str(raw_input)
        text = _normalize_text(text)
        if not text:
            return empty_result

        return {
            'university': _extract_university(text),
            'program': _extract_program(text),
            'quota': _extract_quota(text),
        }
    except Exception:
        return empty_result


def extract_fields(raw_input: Any) -> dict[str, Any]:
    return extract(raw_input)


def run_extractor(raw_input: Any) -> dict[str, Any]:
    return extract(raw_input)


def parse(raw_input: Any) -> dict[str, Any]:
    return extract(raw_input)


def extract_admission_data(raw_input: Any) -> dict[str, Any]:
    return extract(raw_input)


DEADLINE_PATTERN = re.compile(
    r"(application deadline|deadline|apply by|applications close)\s*[:\-]?\s*([A-Za-z]{3,9}\s+\d{1,2}(?:,\s*\d{4})?)",
    re.IGNORECASE,
)


class ScoreValidator:
    RANGES = {
        "gmat": (200, 800),
        "gre": (260, 340),
        "gpa": (0, 4.0),
        "ielts": (0, 9.0),
        "toefl": (0, 120),
        "duolingo": (60, 160),
    }

    @classmethod
    def is_valid(cls, score_type: str, value: float) -> bool:
        if score_type not in cls.RANGES:
            return False
        min_val, max_val = cls.RANGES[score_type]
        return min_val <= value <= max_val


class DataExtractor:
    def __init__(self):
        self.validator = ScoreValidator()

    def extract_master_section(self, html: str) -> str:
        master_start = -1
        patterns = [
            r'univ-section-title["\s>]+[^<]*(?:Master|Masters|Postgraduate|Graduate|Entry\s+requirements|English\s+language)[^<]*<',
            r"<h[23][^>]*>[^<]*(?:Master|Masters|Postgraduate|Graduate|Entry\s+requirements|English\s+language)[^<]*</h[23]>",
            r">\s*(?:Master|Masters|Postgraduate|Graduate)\s*<",
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                master_start = match.end()
                break

        if master_start == -1:
            return ""

        text_chunk = html[master_start:]
        next_section = re.search(r'univ-section-title["\s]|<h[23][^>]*>', text_chunk)
        if next_section:
            text_chunk = text_chunk[: next_section.start()]
        else:
            text_chunk = text_chunk[:10000]

        text_content = re.sub(r"<[^>]+>", " ", text_chunk)
        text_content = re.sub(r"\s+", " ", text_content)
        return text_content

    def find_score(self, keyword: str, text: str, pattern: str, score_type: str) -> Optional[float]:
        window = 140
        search_patterns = [
            rf"{keyword}.{{0,{window}}}?{pattern}",
            rf"{pattern}.{{0,{window}}}?{keyword}",
        ]
        values: list[float] = []

        for search_pattern in search_patterns:
            matches = list(re.finditer(search_pattern, text, re.IGNORECASE))
            for match in matches:
                try:
                    val_str = match.group(1).strip("+").strip()
                    if "-" in val_str and val_str.count("-") == 1:
                        low_s, high_s = val_str.split("-")
                        low = float(low_s)
                        high = float(high_s)
                        if self.validator.is_valid(score_type, low) and self.validator.is_valid(score_type, high):
                            values.append((low + high) / 2)
                        continue

                    val = float(val_str)
                    if self.validator.is_valid(score_type, val):
                        values.append(val)
                except Exception:
                    continue

        if not values:
            return None
        return sum(values) / len(values)

    def extract_requirements(self, html: str) -> AdmissionRequirements:
        text_content = self.extract_master_section(html)
        parsed_status = "master_section"
        if not text_content:
            parsed_status = "full_page_fallback"
            text_content = re.sub(r"<[^>]+>", " ", html[:20000])
            text_content = re.sub(r"\s+", " ", text_content)

        def first_score(keywords: list[str], pattern: str, score_type: str) -> Optional[float]:
            for kw in keywords:
                val = self.find_score(kw, text_content, pattern, score_type)
                if val is not None:
                    return val
            return None

        gmat = first_score([r"GMAT", r"GMAT\s*Focus"], r"(\d{3}(?:\.\d+)?(?:-\d{3}(?:\.\d+)?)?)\+?", "gmat")
        gre = first_score([r"GRE", r"GRE\s*General"], r"(\d{3}(?:\.\d+)?(?:-\d{3}(?:\.\d+)?)?)\+?", "gre")
        toefl = first_score(
            [r"TOEFL\s*iBT", r"TOEFL", r"internet[- ]based\s*TOEFL", r"TOEFL\s*IBT"],
            r"(\d{2,3}(?:\.\d+)?(?:-\d{2,3}(?:\.\d+)?)?)\+?",
            "toefl",
        )
        ielts = first_score(
            [r"IELTS\s*Academic", r"IELTS", r"International\s+English\s+Language\s+Testing\s+System"],
            r"(\d(?:\.\d)?(?:-\d(?:\.\d)?)?)\+?",
            "ielts",
        )
        gpa = first_score(
            [r"GPA", r"CGPA", r"Grade\s+Point\s+Average", r"cumulative\s+GPA"],
            r"([0-4](?:\.\d{1,2})?(?:-[0-4](?:\.\d{1,2})?)?)\+?",
            "gpa",
        )
        duolingo = first_score([r"Duolingo\s+English\s+Test", r"Duolingo", r"DET"], r"(\d{2,3}(?:\.\d+)?(?:-\d{2,3}(?:\.\d+)?)?)\+?", "duolingo")

        application_deadline_text = None
        matched_deadline = DEADLINE_PATTERN.search(text_content)
        if matched_deadline:
            application_deadline_text = matched_deadline.group(2)

        req = AdmissionRequirements(
            gmat=gmat,
            gre=gre,
            gpa=gpa,
            ielts=ielts,
            toefl=toefl,
            duolingo=duolingo,
            application_deadline_text=application_deadline_text,
            raw_text=text_content[:2000],
            parsed_status=parsed_status,
            overall_score=None,
        )
        req.calculate_overall_score()
        return req
