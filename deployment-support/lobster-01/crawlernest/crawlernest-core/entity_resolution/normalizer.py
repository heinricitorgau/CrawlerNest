from __future__ import annotations

import html as _html
import re
import unicodedata

# Conservative abbreviation map; safe expansions only.
ABBREVIATION_MAP = {
    "inst": "institute",
    "inst.": "institute",
    "tech": "technology",
    "tech.": "technology",
    "univ": "university",
    "univ.": "university",
    "dept": "department",
    "dept.": "department",
    # Extended safe entries (Fix R1)
    "sci": "science",
    "natl": "national",
    "coll": "college",
    "engr": "engineering",
    "intl": "international",
}

STOPWORDS = {
    "the",
    "of",
    "and",
    "for",
}


def _strip_safe_parenthetical_alias_noise(text: str) -> str:
    match = re.search(r"\s*\(([^)]{1,16})\)\s*$", str(text or "").strip())
    if not match:
        return str(text or "")
    inner = match.group(1).strip()
    compact = re.sub(r"[^A-Za-z0-9]+", "", inner)
    if compact and len(compact) <= 10 and compact.upper() == compact:
        return re.sub(r"\s*\([^)]*\)\s*$", "", str(text or "")).strip()
    return str(text or "")


def _strip_accents(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))


def normalize_university_name(name: str) -> str:
    if not name:
        return ""

    # Fix R2: decode HTML entities (e.g. &amp; → &) before any other processing
    s = _strip_safe_parenthetical_alias_noise(_html.unescape(name))
    s = _strip_accents(s).lower().strip()
    s = s.replace("&", " and ")
    s = re.sub(r"[\u2010-\u2015]", "-", s)
    s = re.sub(r"[^\w\s\u4e00-\u9fff-]", " ", s)
    s = re.sub(r"[_\-]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    tokens: list[str] = []
    for token in s.split():
        token = ABBREVIATION_MAP.get(token, token)
        if token in STOPWORDS:
            continue
        tokens.append(token)
    return " ".join(tokens)


def tokenize_for_blocking(name: str) -> tuple[str, ...]:
    n = normalize_university_name(name)
    if not n:
        return ()
    return tuple(sorted(set(n.split())))
