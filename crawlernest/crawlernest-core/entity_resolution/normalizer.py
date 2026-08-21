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


# Letters that one source writes with a diacritic and another spells out.
# normalize_university_name() folds diacritics through NFKD, so "München"
# becomes "munchen" while a source writing "Muenchen" stays "muenchen".
# Neither spelling is wrong; they simply never meet.
TRANSLITERATION_EXPANSIONS = {
    "ä": "ae", "Ä": "ae",
    "ö": "oe", "Ö": "oe",
    "ü": "ue", "Ü": "ue",
    "ß": "ss",
    "æ": "ae", "Æ": "ae",
    "ø": "oe", "Ø": "oe",
}

# Distinct letters rather than a base plus a combining mark, so NFKD leaves
# them alone and they survive normalization as themselves.
SINGLE_LETTER_FOLDS = {
    "ı": "i", "İ": "i",
    "ł": "l", "Ł": "l",
    "đ": "d", "Đ": "d",
    "ð": "d", "Ð": "d",
    "þ": "th", "Þ": "th",
}

_TRANSLITERATION_MAP = {**TRANSLITERATION_EXPANSIONS, **SINGLE_LETTER_FOLDS}
_TRANSLITERATION_CHARS = frozenset(_TRANSLITERATION_MAP)


def expanded_transliteration(name: str) -> str:
    """
    Normalized key for `name` under the spelled-out transliteration convention.

    Returns "" when there is nothing to expand or the result is identical to
    normalize_university_name(name), so callers can skip the extra key.

    normalize_university_name() is deliberately left untouched: the C engine in
    crawlernest-normalization/ mirrors it byte for byte, and the warehouse
    stores keys it produced. This is an additional index key, not a
    replacement.
    """
    if not name:
        return ""
    source = str(name)
    if not any(ch in _TRANSLITERATION_CHARS for ch in source):
        return ""
    expanded = "".join(_TRANSLITERATION_MAP.get(ch, ch) for ch in source)
    key = normalize_university_name(expanded)
    return key if key and key != normalize_university_name(source) else ""
