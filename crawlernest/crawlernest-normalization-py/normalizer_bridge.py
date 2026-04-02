"""
Python bridge to the CrawlerNest C normalization engine.
Falls back to pure Python if the C binary is not available or fails.
"""

from __future__ import annotations

import csv
import io
import subprocess
import sys
from pathlib import Path
from typing import Optional

import html as _html
import re
import unicodedata

ABBREVIATION_MAP = {
    "inst": "institute", "inst.": "institute",
    "tech": "technology", "tech.": "technology",
    "univ": "university", "univ.": "university",
    "natl": "national", "intl": "international",
    "coll": "college", "sci": "science",
    "engr": "engineering",
}

STOPWORDS = {"the", "of", "and", "for", "de", "la", "le", "les", "a", "an"}

COUNTRY_VARIANTS: dict[str, str] = {
    "usa": "United States", "us": "United States",
    "united states of america": "United States",
    "uk": "United Kingdom", "great britain": "United Kingdom",
    "china mainland": "China (Mainland)",
    "peoples republic of china": "China (Mainland)",
    "people s republic of china": "China (Mainland)",
    "prc": "China (Mainland)",
    "hong kong sar": "Hong Kong SAR",
    "hong kong": "Hong Kong SAR",
    "south korea": "South Korea",
    "republic of korea": "South Korea",
    "russia": "Russia", "russian federation": "Russia",
    "iran": "Iran", "islamic republic of iran": "Iran",
    "taiwan": "Taiwan", "republic of china": "Taiwan",
}


def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    )


def normalize_name_py(name: str) -> str:
    """Pure Python university name normalization (baseline fallback)."""
    if not name:
        return ""
    s = _html.unescape(name)
    s = _strip_accents(s).lower().strip()
    s = s.replace("&", " and ")
    s = re.sub(r"[\u2010-\u2015]", "-", s)
    s = re.sub(r"[^\w\s\u4e00-\u9fff-]", " ", s)
    s = re.sub(r"[_\-]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    tokens = []
    for token in s.split():
        token = ABBREVIATION_MAP.get(token, token)
        if token in STOPWORDS:
            continue
        tokens.append(token)
    return " ".join(tokens)


def normalize_country_py(country: str) -> str:
    """Pure Python country normalization (baseline fallback)."""
    if not country:
        return ""
    key = re.sub(r"[^\w\s]", " ", country.lower()).strip()
    key = re.sub(r"\s+", " ", key)
    return COUNTRY_VARIANTS.get(key, country.strip())


class CNormalizerBridge:
    """
    Bridge to the CrawlerNest C normalization engine.
    Automatically falls back to pure Python if C binary unavailable.
    """

    DEFAULT_BINARY_RELATIVE = (
        Path(__file__).parent.parent
        / "crawlernest-normalization"
        / "c_engine"
        / "build"
        / "clawer_normalizer"
    )

    def __init__(self, binary_path: Optional[str] = None):
        self._binary = Path(binary_path) if binary_path else self.DEFAULT_BINARY_RELATIVE
        self._available: Optional[bool] = None

    @property
    def is_available(self) -> bool:
        if self._available is None:
            self._available = self._binary.exists() and self._binary.is_file()
        return self._available

    def normalize_name(self, name: str) -> str:
        """
        Normalize university name.
        Uses C engine if available, falls back to Python.
        """
        if not name:
            return ""
        result = self.normalize_batch([{"name": name, "country": "", "rank": "", "score": ""}])
        if result:
            return result[0].get("normalized_name", normalize_name_py(name))
        return normalize_name_py(name)

    def normalize_country(self, country: str) -> str:
        """
        Normalize country name.
        Uses C engine if available, falls back to Python.
        """
        if not country:
            return ""
        result = self.normalize_batch([{"name": "", "country": country, "rank": "", "score": ""}])
        if result:
            return result[0].get("normalized_country", normalize_country_py(country))
        return normalize_country_py(country)

    def normalize_batch(self, records: list[dict]) -> list[dict]:
        """
        Normalize a batch of records.
        Each record: {"name": str, "country": str, "rank": str, "score": str}
        Returns records with added fields:
          normalized_name, normalized_country, rank_min, rank_max, score
        Falls back to Python if C engine unavailable or fails.
        """
        if not records:
            return []

        if not self.is_available:
            return self._python_fallback_batch(records)

        try:
            return self._c_normalize_batch(records)
        except Exception as exc:
            print(
                f"[CNormalizerBridge] C engine failed ({exc}), falling back to Python",
                file=sys.stderr,
            )
            return self._python_fallback_batch(records)

    def _c_normalize_batch(self, records: list[dict]) -> list[dict]:
        """Call C binary via subprocess with CSV pipe."""
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["name", "country", "rank", "score"])
        for r in records:
            writer.writerow([
                r.get("name", ""),
                r.get("country", ""),
                r.get("rank", ""),
                r.get("score", ""),
            ])
        csv_input = buf.getvalue()

        result = subprocess.run(
            [str(self._binary), "--stdin-csv"],
            input=csv_input,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise RuntimeError(f"C binary exited {result.returncode}: {result.stderr}")

        reader = csv.DictReader(io.StringIO(result.stdout))
        output = list(reader)

        merged = []
        for orig, norm in zip(records, output):
            merged.append({**orig, **norm})
        return merged

    def _python_fallback_batch(self, records: list[dict]) -> list[dict]:
        """Pure Python fallback for batch normalization."""
        out = []
        for r in records:
            out.append({
                **r,
                "normalized_name": normalize_name_py(r.get("name", "")),
                "normalized_country": normalize_country_py(r.get("country", "")),
                "rank_min": None,
                "rank_max": None,
            })
        return out


_default_bridge: Optional[CNormalizerBridge] = None


def get_bridge() -> CNormalizerBridge:
    global _default_bridge
    if _default_bridge is None:
        _default_bridge = CNormalizerBridge()
    return _default_bridge
