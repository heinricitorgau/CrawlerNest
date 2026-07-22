"""Shared lookup / ranking intent detection for the web-agent generation layer.

This logic was previously duplicated verbatim in ``prompt_builder`` and
``context_builder``. The two copies had already drifted — the "the" (Times Higher
Education) ranking pattern was ``\\bthe\\b`` in one and ``the `` in the other — so
the two builders could disagree on the detected intents for the same input. This
is now the single source of truth; both builders delegate here.

Patterns are pre-compiled once at import into a single alternation per intent,
instead of rebuilding the pattern lists and running one ``re.search`` per pattern
on every request.
"""

from __future__ import annotations

import re


def _alternation(patterns: list[str]) -> re.Pattern[str]:
    return re.compile("|".join(patterns), re.IGNORECASE)


# Ordered (intent -> matcher). Order defines the order of the returned list.
_LOOKUP_INTENTS: list[tuple[str, re.Pattern[str]]] = [
    ("location", _alternation([
        r"\bwhere\b", r"\blocated\b", r"在哪", r"哪裡", r"位於", r"位在",
        r"哪個國家", r"哪个国家", r"城市",
    ])),
    ("admission", _alternation([
        r"錄取門檻", r"录取门槛", r"申請門檻", r"申请门槛",
        r"admission", r"requirement", r"ielts", r"toefl",
    ])),
    ("ranking", _alternation([
        r"排名", r"\brank\b", r"\branking\b", r"qs", r"\bthe\b", r"arwu",
    ])),
]

_RANKING_INTENTS: list[tuple[str, re.Pattern[str]]] = [
    ("compare", _alternation([
        r"比較", r"比较", r"\bcompare\b", r"\bvs\b", r"versus", r"差別", r"差异",
    ])),
    ("rank_position", _alternation([
        r"第幾", r"第几", r"幾名", r"几名", r"排名多少", r"ranked",
        r"\bwhat rank\b", r"\brank\b", r"\bposition\b",
    ])),
    ("why_high", _alternation([
        r"為什麼", r"为什么", r"\bwhy\b", r"原因", r"為何", r"为何",
        r"ranks highly", r"ranks so high",
    ])),
]


def detect_lookup_intents(user_input: str) -> list[str]:
    """Intents for a ``university_lookup`` query; defaults to ``["identity"]``."""
    lowered = user_input.lower()
    intents = [name for name, matcher in _LOOKUP_INTENTS if matcher.search(lowered)]
    return intents or ["identity"]


def detect_ranking_intents(user_input: str) -> list[str]:
    """Intents for a ``ranking_explain`` query; defaults to ``["general_explain"]``."""
    lowered = user_input.lower()
    intents = [name for name, matcher in _RANKING_INTENTS if matcher.search(lowered)]
    return intents or ["general_explain"]
