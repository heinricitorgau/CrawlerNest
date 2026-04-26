"""Admission text extractor.

Parses raw HTML or plain text and returns a flat dict of admission fields.
All fields are optional — if a field cannot be confidently extracted, its
value is ``None`` (never a guess or a fabrication).

Public API
----------
``extract(raw_text: str) -> dict``
    Top-level entry point. Strips HTML, then runs each field extractor.
    Always returns a dict with these keys:
      ielts        float | None   e.g. 6.5
      toefl        int   | None   e.g. 90
      duolingo     int   | None   e.g. 110
      degree_level str   | None   "undergraduate" | "postgraduate" | "doctoral"
      deadline     str   | None   ISO-8601 "YYYY-MM-DD"
      gpa          float | None   e.g. 3.5

Design constraints
------------------
- Each field extractor is a standalone function: independently testable.
- All values are validated against plausible ranges before being returned.
- Ambiguous or out-of-range values are returned as None, not coerced.
- No LLM, no network, no I/O — purely deterministic regex + rules.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

# ── HTML stripping ─────────────────────────────────────────────────────────────

_MAX_RAW_INPUT_CHARS = 200_000
_MAX_CLEAN_TEXT_CHARS = 50_000

_HTML_BLOCK_TAGS_RE = re.compile(
    r"</?(p|div|section|article|header|footer|h[1-6]|br|li|tr|td|th)\b[^>]*>",
    re.IGNORECASE,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_MULTI_WS_RE = re.compile(r"[ \t]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _strip_html(text: str) -> str:
    """Remove HTML tags, collapse whitespace, preserve newlines at block boundaries."""
    text = _HTML_BLOCK_TAGS_RE.sub("\n", text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = _MULTI_WS_RE.sub(" ", text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


def _prepare_text(raw_text: Any) -> tuple[str, dict[str, Any]]:
    text = raw_text if isinstance(raw_text, str) else str(raw_text or "")
    control_chars_removed = len(_CONTROL_CHAR_RE.findall(text))
    if control_chars_removed:
        text = _CONTROL_CHAR_RE.sub(" ", text)

    raw_truncated = len(text) > _MAX_RAW_INPUT_CHARS
    if raw_truncated:
        text = text[:_MAX_RAW_INPUT_CHARS]

    clean = _strip_html(text)
    clean_truncated = len(clean) > _MAX_CLEAN_TEXT_CHARS
    if clean_truncated:
        clean = clean[:_MAX_CLEAN_TEXT_CHARS].rstrip()

    return clean, {
        "raw_truncated": raw_truncated,
        "clean_truncated": clean_truncated,
        "control_chars_removed": control_chars_removed,
        "raw_input_chars": len(str(raw_text or "")),
        "prepared_chars": len(clean),
    }


# ── IELTS ─────────────────────────────────────────────────────────────────────

_IELTS_RE = re.compile(
    r"IELTS"
    r"(?:\s+(?:Academic|General|score|minimum|requirement|band|of))*"
    # Allow optional qualifier (e.g., Overall) between separator and number
    r"[\s:=–\"'()\[\]{}-]*"  # separator
    r"(?:Overall|overall|Total|total)?"  # optional qualifier
    r"[\s:=–\"'()\[\]{}-]*"  # allow more separator after qualifier
    r"(?:score\s+of\s+|of\s+)?"
    r"(?:at\s+least\s+)?"
    r"([0-9](?:\.[05])?)"
    r"(?:\s*(?:overall|or above|minimum|band|score))?",
    re.IGNORECASE,
)

_IELTS_RANGE = (4.0, 9.0)


def extract_ielts(text: str) -> float | None:
    """Return first plausible IELTS score found in *text*, or ``None``."""
    m = _IELTS_RE.search(text)
    if not m:
        return None
    try:
        score = float(m.group(1))
    except ValueError:
        return None
    if _IELTS_RANGE[0] <= score <= _IELTS_RANGE[1]:
        return score
    return None


# ── TOEFL ─────────────────────────────────────────────────────────────────────

_TOEFL_RE = re.compile(
    r"TOEFL"
    r"(?:\s+(?:iBT|ibt|score|minimum|required|requirement|of))*"
    # Bug D fix: allow JSON-style quotes and other punctuation as separators
    r"""[\s:=–"'()\[\]{}-]*"""
    r"(?:Overall|overall|Total|total)?"  # Pattern 1 fix: handles "TOEFL iBT: Overall 90"
    r"""[\s:=–"'()\[\]{}-]*"""          # allow separator after qualifier
    r"(?:score\s+of\s+|of\s+|is\s+)?"   # "score of", "of", "is"
    r"(?:at\s+least\s+)?"
    r"([0-9]{2,3})"
    r"(?:\s*(?:or above|minimum|score|iBT|ibt|overall))?",
    re.IGNORECASE,
)

# Pattern 2 fix: handles "TOEFL iBT score for [institution name] is N"
# (UCL-style where a long noun phrase separates "score" from the number)
_TOEFL_SECONDARY_RE = re.compile(
    r"TOEFL(?:\s+iBT)?\s+score\s+for\s+\S+(?:\s+\S+){1,8}\s+is\s+([0-9]{2,3})\b",
    re.IGNORECASE,
)

_TOEFL_RANGE = (50, 120)


def extract_toefl(text: str) -> int | None:
    """Return first plausible TOEFL iBT score found in *text*, or ``None``."""
    m = _TOEFL_RE.search(text)
    if not m:
        # Fallback: "TOEFL iBT score for [institution] is N" pattern
        m = _TOEFL_SECONDARY_RE.search(text)
    if not m:
        return None
    try:
        score = int(m.group(1))
    except ValueError:
        return None
    if _TOEFL_RANGE[0] <= score <= _TOEFL_RANGE[1]:
        return score
    return None


# ── Duolingo English Test ─────────────────────────────────────────────────────

_DUOLINGO_RE = re.compile(
    r"Duolingo"
    r"(?:\s+(?:English\s+Test|DET))?"   # optional qualifier
    r"[^0-9\n]{0,50}"                   # permissive single-line gap; handles
                                        # ": minimum score of" and other phrases
    r"(\d{2,3})"
    r"(?:\s*(?:or above|minimum|score))?",
    re.IGNORECASE,
)

_DUOLINGO_RANGE = (10, 160)


def extract_duolingo(text: str) -> int | None:
    """Return first plausible Duolingo score found in *text*, or ``None``."""
    m = _DUOLINGO_RE.search(text)
    if not m:
        return None
    try:
        score = int(m.group(1))
    except ValueError:
        return None
    if _DUOLINGO_RANGE[0] <= score <= _DUOLINGO_RANGE[1]:
        return score
    return None


# ── Degree level ──────────────────────────────────────────────────────────────

# Maps raw tokens → canonical level.  Order matters: try more specific first.
_DEGREE_MAP: list[tuple[str, str]] = [
    # Doctoral
    ("ph\\.?d", "doctoral"),
    ("doctoral", "doctoral"),
    ("doctorate", "doctoral"),
    ("doctor of", "doctoral"),
    ("d\\.?phil", "doctoral"),
    # Postgraduate
    ("master(?:'?s)?", "postgraduate"),
    ("msc|m\\.sc", "postgraduate"),
    ("mba|m\\.b\\.a", "postgraduate"),
    ("ma\\b|m\\.a\\b", "postgraduate"),
    ("postgraduate", "postgraduate"),
    ("post-graduate", "postgraduate"),
    (r"\bgraduate\b(?!\s+school)", "postgraduate"),  # Bug A fix: \b prevents matching inside "undergraduate"
    # Undergraduate
    ("bachelor(?:'?s)?", "undergraduate"),
    ("bsc|b\\.sc", "undergraduate"),
    ("undergraduate", "undergraduate"),
    ("b\\.a\\b|ba\\b", "undergraduate"),
    ("b\\.eng|beng", "undergraduate"),
]

_DEGREE_COMPILED = [
    (re.compile(pattern, re.IGNORECASE), level) for pattern, level in _DEGREE_MAP
]

# Context cues that usually accompany degree-level mentions.
_DEGREE_CONTEXT_RE = re.compile(
    r"(?:degree|level|program|programme|admission|applicant|student|study)",
    re.IGNORECASE,
)


def extract_degree_level(text: str) -> str | None:
    """Return canonical degree level string, or ``None`` if not found."""
    # Search in a 300-char window around context cues for higher precision.
    context_positions: list[int] = [
        m.start() for m in _DEGREE_CONTEXT_RE.finditer(text)
    ]
    search_zones: list[str] = []
    if context_positions:
        for pos in context_positions:
            lo = max(0, pos - 150)
            hi = min(len(text), pos + 150)
            search_zones.append(text[lo:hi])
    # Also search the full text as fallback.
    search_zones.append(text)

    for zone in search_zones:
        for pattern, level in _DEGREE_COMPILED:
            if pattern.search(zone):
                return level
    return None


# ── Application deadline ──────────────────────────────────────────────────────

_MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

# ISO date: 2026-01-15
_ISO_DATE_RE = re.compile(r"\b(20[2-9]\d)[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])\b")

# Bug C fix: Handle three date formats separately:
#   "Month Day, Year"  : January 15, 2026 | January 15 2026
#   "Day Month Year"   : 15 January 2026  | 28 February 2026
#   "Year Month Day"   : 2026 January 15
_MONTH_DAY_YEAR_RE = re.compile(
    r"\b(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2}),?\s+(?P<year>20[2-9]\d)\b"
)
_DAY_MONTH_YEAR_RE = re.compile(
    r"\b(?P<day>\d{1,2})\s+(?P<month>[A-Za-z]+)\s+(?P<year>20[2-9]\d)\b"
)
_YEAR_MONTH_DAY_RE = re.compile(
    r"\b(?P<year>20[2-9]\d)\s+(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2})\b"
)

# Deadline context cue
_DEADLINE_CONTEXT_RE = re.compile(
    r"(?:deadline|apply\s+by|apply\s+before|closing\s+date|due\s+date|application\s+due"
    r"|submit\s+by|close(?:s)?\s+on|due\s+by|last\s+date)",
    re.IGNORECASE,
)
_DEADLINE_EARLY_RE = re.compile(r"\bearly\b", re.IGNORECASE)
_DEADLINE_FINAL_RE = re.compile(r"\bfinal\b", re.IGNORECASE)
_DEADLINE_ROLLING_RE = re.compile(r"\brolling\b", re.IGNORECASE)
_DEADLINE_ACCEPTED_UNTIL_RE = re.compile(r"\baccepted\s+until\b", re.IGNORECASE)
_DEADLINE_INTERNATIONAL_RE = re.compile(r"\binternational\b", re.IGNORECASE)
_DEADLINE_DOMESTIC_RE = re.compile(r"\bdomestic\b", re.IGNORECASE)
_DEADLINE_PRIORITY = {
    "early": 0,
    "international": 1,
    "general": 2,
    "final": 3,
    "rolling": 4,
    "domestic": 5,
}
_DEADLINE_LABEL_SPECIFICITY = {
    "early": 0,
    "final": 0,
    "rolling": 0,
    "international": 0,
    "domestic": 0,
    "general": 1,
}
_DEADLINE_WINDOW_BACKTRACK = 32


def _try_parse_iso(text: str) -> str | None:
    m = _ISO_DATE_RE.search(text)
    if not m:
        return None
    try:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return d.isoformat()
    except ValueError:
        return None


def _try_parse_month_name(text: str) -> str | None:
    """Try three named-month date formats and return the first valid ISO date."""
    for pattern in (_MONTH_DAY_YEAR_RE, _DAY_MONTH_YEAR_RE, _YEAR_MONTH_DAY_RE):
        for m in pattern.finditer(text):
            groups = m.groupdict()
            month_name = groups["month"].lower()
            month_num = _MONTH_MAP.get(month_name)
            if month_num is None:
                continue
            try:
                d = date(int(groups["year"]), month_num, int(groups["day"]))
                return d.isoformat()
            except ValueError:
                continue
    return None


def _iter_named_month_dates(text: str) -> list[tuple[int, str]]:
    results: list[tuple[int, str]] = []
    for pattern in (_MONTH_DAY_YEAR_RE, _DAY_MONTH_YEAR_RE, _YEAR_MONTH_DAY_RE):
        for m in pattern.finditer(text):
            groups = m.groupdict()
            month_name = groups["month"].lower()
            month_num = _MONTH_MAP.get(month_name)
            if month_num is None:
                continue
            try:
                d = date(int(groups["year"]), month_num, int(groups["day"]))
            except ValueError:
                continue
            results.append((m.start(), d.isoformat()))
    results.sort(key=lambda item: item[0])
    return results


def _classify_deadline_label(prefix_text: str) -> str:
    local_prefix = re.split(r"[;\n]", prefix_text)[-1]
    if _DEADLINE_EARLY_RE.search(local_prefix):
        return "early"
    if _DEADLINE_FINAL_RE.search(local_prefix):
        return "final"
    if _DEADLINE_ROLLING_RE.search(local_prefix) or _DEADLINE_ACCEPTED_UNTIL_RE.search(local_prefix):
        return "rolling"
    if _DEADLINE_INTERNATIONAL_RE.search(local_prefix):
        return "international"
    if _DEADLINE_DOMESTIC_RE.search(local_prefix):
        return "domestic"
    return "general"


def _extract_deadline_candidates(text: str) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    best_by_date: dict[str, tuple[int, str, int]] = {}

    for match in _DEADLINE_CONTEXT_RE.finditer(text):
        window_start = max(0, match.start() - _DEADLINE_WINDOW_BACKTRACK)
        window = text[window_start: match.start() + 120]
        for date_start, iso_date in _iter_named_month_dates(window):
            prefix = window[:date_start]
            label = _classify_deadline_label(prefix)
            rank = _DEADLINE_LABEL_SPECIFICITY.get(label, 99)
            existing = best_by_date.get(iso_date)
            if existing is None or rank < existing[0]:
                best_by_date[iso_date] = (rank, label, date_start)

        iso_result = _try_parse_iso(window)
        if iso_result:
            prefix = window.split(iso_result, 1)[0]
            label = _classify_deadline_label(prefix)
            rank = _DEADLINE_LABEL_SPECIFICITY.get(label, 99)
            existing = best_by_date.get(iso_result)
            iso_position = window.find(iso_result)
            if existing is None or rank < existing[0]:
                best_by_date[iso_result] = (rank, label, iso_position)

    for iso_date, (_, label, position) in sorted(best_by_date.items(), key=lambda item: item[1][2]):
        candidates.append((label, iso_date))

    return candidates


def _select_deadline(candidates: list[tuple[str, str]]) -> str | None:
    if not candidates:
        return None
    ranked = sorted(
        enumerate(candidates),
        key=lambda item: (_DEADLINE_PRIORITY.get(item[1][0], 99), item[0]),
    )
    return ranked[0][1][1]


def extract_deadline(text: str) -> str | None:
    """Return the first plausible application deadline as ISO-8601, or ``None``."""
    candidates = _extract_deadline_candidates(text)
    result = _select_deadline(candidates)
    if result:
        return result
    # Fallback: any ISO date in the full text.
    return _try_parse_iso(text) or _try_parse_month_name(text)


# ── GPA ───────────────────────────────────────────────────────────────────────

# Bug B fix: use two separate permissive separator spans so "GPA: minimum 3.0"
# and "GPA 最低 3.0" both match (CJK or ASCII words between GPA and the number
# are consumed by the middle [^0-9]* group, kept short to avoid runaway matches).
_GPA_RE = re.compile(
    r"GPA"
    r"[\s:=–-]*"                       # handle "GPA: " and "GPA "
    r"(?:of|minimum|above|score|requirement|最低|最小)?"  # optional qualifier (ASCII or CJK)
    r"[^0-9]{0,20}"                    # allow up to 20 non-digit chars (covers CJK gap)
    r"([0-9]+\.[0-9]+)"
    r"(?:\s*/\s*4(?:\.0)?)?",           # optional /4.0 suffix
    re.IGNORECASE,
)

_GPA_RANGE = (0.0, 4.0)


def extract_gpa(text: str) -> float | None:
    """Return first plausible GPA requirement found in *text*, or ``None``."""
    m = _GPA_RE.search(text)
    if not m:
        return None
    try:
        score = float(m.group(1))
    except ValueError:
        return None
    if _GPA_RANGE[0] <= score <= _GPA_RANGE[1]:
        return round(score, 2)
    return None


# ── Top-level extract() ───────────────────────────────────────────────────────

def extract_with_diagnostics(raw_text: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Parse *raw_text* (HTML or plain text) and return a dict of admission fields.

    All keys are always present.  Any field that could not be confidently
    extracted is ``None`` — never a guess.

    Keys
    ----
    ielts        float | None   e.g. 6.5
    toefl        int   | None   e.g. 90
    duolingo     int   | None   e.g. 110
    degree_level str   | None   "undergraduate" | "postgraduate" | "doctoral"
    deadline     str   | None   ISO-8601 "YYYY-MM-DD"
    gpa          float | None   e.g. 3.5
    """
    clean, diagnostics = _prepare_text(raw_text)
    deadline_candidates = _extract_deadline_candidates(clean)
    fields = {
        "ielts": extract_ielts(clean),
        "toefl": extract_toefl(clean),
        "duolingo": extract_duolingo(clean),
        "degree_level": extract_degree_level(clean),
        "deadline": _select_deadline(deadline_candidates)
        or _try_parse_iso(clean)
        or _try_parse_month_name(clean),
        "gpa": extract_gpa(clean),
    }
    if deadline_candidates and (len(deadline_candidates) > 1 or deadline_candidates[0][0] != "general"):
        diagnostics["deadline_candidates"] = deadline_candidates
    if len(deadline_candidates) > 1:
        diagnostics["deadline_candidates"] = deadline_candidates
        diagnostics["deadline_conflict"] = True
    return fields, diagnostics


def extract(raw_text: str) -> dict[str, Any]:
    fields, _ = extract_with_diagnostics(raw_text)
    return fields
