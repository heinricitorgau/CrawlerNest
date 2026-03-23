from __future__ import annotations

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
}

STOPWORDS = {
    "the",
    "of",
    "and",
    "for",
}


def _strip_accents(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))


def normalize_university_name(name: str) -> str:
    if not name:
        return ""

    s = _strip_accents(name).lower().strip()
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
