"""
normalizer_bridge.py

Python bridge to the Clawer C Data Normalization Engine binary.

Provides:
  CNormalizerBridge   — wraps subprocess calls to build/clawer_normalizer
                        with automatic fallback to the Python normalizer when
                        the binary is unavailable or fails.

All public methods have type hints.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

# Python fallback normalizer (must not be modified)
# The project resolves sub-packages via sys.path rather than a top-level package.
import sys as _sys, os as _os
_core_path = _os.path.join(_os.path.dirname(__file__), "..", "crawlernest-core")
if _core_path not in _sys.path:
    _sys.path.insert(0, _os.path.normpath(_core_path))
from entity_resolution.normalizer import (  # type: ignore[import]
    normalize_university_name as _py_normalize_name,
)


def _py_normalize_country(country: str) -> str:
    """
    Minimal Python-level country normalizer used as fallback.
    Strips whitespace and punctuation, lowercases, then maps common aliases.
    This intentionally mirrors the basic logic in country_normalizer.c.
    """
    import re
    import unicodedata

    if not country:
        return ""

    s = "".join(
        ch for ch in unicodedata.normalize("NFKD", country)
        if not unicodedata.combining(ch)
    )
    s = re.sub(r"[''ʼ]", "", s)  # remove apostrophes without inserting space
    s = re.sub(r"[^\w\s]", " ", s).lower()
    s = re.sub(r"\s+", " ", s).strip()

    _COUNTRY_MAP: dict[str, str] = {
        "usa": "United States",
        "us": "United States",
        "u s a": "United States",
        "united states": "United States",
        "united states of america": "United States",
        "uk": "United Kingdom",
        "u k": "United Kingdom",
        "united kingdom": "United Kingdom",
        "great britain": "United Kingdom",
        "sg": "Singapore",
        "singapore": "Singapore",
        "china mainland": "China (Mainland)",
        "peoples republic of china": "China (Mainland)",
        "china": "China (Mainland)",
        "iran": "Iran",
        "islamic republic of iran": "Iran",
        "russia": "Russia",
        "russian federation": "Russia",
        "hong kong sar": "Hong Kong SAR",
        "hong kong": "Hong Kong SAR",
        "macau": "Macau SAR",
        "macao": "Macau SAR",
        "macau sar": "Macau SAR",
        "taiwan": "Taiwan",
        "province of china": "Taiwan",
        "republic of china": "Taiwan",
        "roc": "Taiwan",
        "south korea": "South Korea",
        "korea": "South Korea",
        "republic of korea": "South Korea",
    }

    return _COUNTRY_MAP.get(s, country.strip())


# Public re-exports used by __init__.py
def normalize_name_py(name: str) -> str:
    """Normalize a university name using the Python normalizer."""
    return _py_normalize_name(name)


def normalize_country_py(country: str) -> str:
    """Normalize a country name using the Python fallback."""
    return _py_normalize_country(country)


# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_BINARY_CANDIDATES: list[str] = [
    # crawlernest/ → crawlernest-normalization (sibling module)
    str(Path(__file__).resolve().parents[1] / "crawlernest-normalization" / "c_engine" / "build" / "clawer_normalizer"),
    # Windows portable build (same engine, dist layout)
    str(Path(__file__).resolve().parents[1] / "crawlernest-normalization" / "c_engine" / "dist" / "ClawerNormalizer-Portable" / "clawer_normalizer.exe"),
]


class CNormalizerBridge:
    """
    Bridge between Python pipeline and the compiled Clawer C normalizer binary.

    On initialisation, the bridge locates the binary and probes it with a
    simple test call.  If the binary cannot be found or fails, every public
    method silently falls back to the pure-Python normalizer so that the
    pipeline always gets a result.

    Parameters
    ----------
    binary_path : str or None
        Explicit path to the ``clawer_normalizer`` binary.  When *None* the
        bridge searches the default candidate locations.
    """

    _TIMEOUT: int = 30  # seconds

    def __init__(self, binary_path: Optional[str] = None) -> None:
        self._binary: Optional[str] = None

        candidates: list[str] = (
            [binary_path] if binary_path else _DEFAULT_BINARY_CANDIDATES
        )

        for candidate in candidates:
            expanded = os.path.expandvars(os.path.expanduser(candidate))
            if os.path.isfile(expanded) and os.access(expanded, os.X_OK):
                self._binary = expanded
                break

        # Validate with a trivial pipe call
        if self._binary is not None:
            try:
                result = subprocess.run(
                    [self._binary, "--pipe-name"],
                    input="test\n",
                    capture_output=True,
                    text=True,
                    timeout=self._TIMEOUT,
                )
                if result.returncode != 0:
                    self._binary = None
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                self._binary = None

    # ── public interface ──────────────────────────────────────────────────────

    @property
    def is_available(self) -> bool:
        """True when the C binary was found and passed the startup probe."""
        return self._binary is not None

    def normalize_name(self, name: str) -> str:
        """
        Normalize a university name.

        Delegates to the C binary via ``--pipe-name``; falls back to Python on
        any subprocess error or timeout.

        Parameters
        ----------
        name : str
            Raw university name string.

        Returns
        -------
        str
            Normalized name (lowercase, accent-stripped, stopwords removed,
            abbreviations expanded).
        """
        if not name:
            return ""
        if not self.is_available:
            return normalize_name_py(name)
        try:
            result = subprocess.run(
                [self._binary, "--pipe-name"],
                input=name + "\n",
                capture_output=True,
                text=True,
                timeout=self._TIMEOUT,
            )
            if result.returncode == 0:
                return result.stdout.rstrip("\n\r")
            return normalize_name_py(name)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
                FileNotFoundError, OSError):
            return normalize_name_py(name)

    def normalize_country(self, country: str) -> str:
        """
        Normalize a country name to its canonical form.

        Delegates to the C binary via ``--pipe-country``; falls back to the
        Python country normalizer on any error.

        Parameters
        ----------
        country : str
            Raw country string.

        Returns
        -------
        str
            Canonical country name (e.g. ``"United States"``, ``"Taiwan"``).
        """
        if not country:
            return ""
        if not self.is_available:
            return normalize_country_py(country)
        try:
            result = subprocess.run(
                [self._binary, "--pipe-country"],
                input=country + "\n",
                capture_output=True,
                text=True,
                timeout=self._TIMEOUT,
            )
            if result.returncode == 0:
                return result.stdout.rstrip("\n\r")
            return normalize_country_py(country)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
                FileNotFoundError, OSError):
            return normalize_country_py(country)

    def normalize_batch(self, records: list[dict]) -> list[dict]:
        """
        Normalize a list of university records.

        Each record is a dict with (at minimum) ``"name"`` and/or ``"country"``
        keys.  Returns a new list of dicts with ``"normalized_name"`` and
        ``"normalized_country"`` keys added (original keys preserved).

        Delegates to the C binary via ``--pipe-batch`` for efficiency; falls
        back record-by-record to Python on any error.

        Parameters
        ----------
        records : list[dict]
            Input records, each containing ``"name"`` and/or ``"country"``.

        Returns
        -------
        list[dict]
            Records enriched with ``normalized_name`` and
            ``normalized_country``.
        """
        if not records:
            return []

        if not self.is_available:
            return self._batch_python_fallback(records)

        try:
            lines: list[str] = []
            for rec in records:
                name = str(rec.get("name", "")).replace(",", " ")
                country = str(rec.get("country", "")).replace(",", " ")
                lines.append(f"{name},{country}")
            csv_input = "\n".join(lines) + "\n"

            result = subprocess.run(
                [self._binary, "--pipe-batch"],
                input=csv_input,
                capture_output=True,
                text=True,
                timeout=self._TIMEOUT,
            )
            if result.returncode != 0:
                return self._batch_python_fallback(records)

            output_lines = result.stdout.splitlines()
            # Skip header line
            data_lines = [
                ln for ln in output_lines
                if not ln.startswith("normalized_name")
            ]

            enriched: list[dict] = []
            for i, rec in enumerate(records):
                new_rec = dict(rec)
                if i < len(data_lines):
                    parts = data_lines[i].split(",", 1)
                    new_rec["normalized_name"] = parts[0] if parts else ""
                    new_rec["normalized_country"] = parts[1] if len(parts) > 1 else ""
                else:
                    new_rec["normalized_name"] = normalize_name_py(
                        str(rec.get("name", ""))
                    )
                    new_rec["normalized_country"] = normalize_country_py(
                        str(rec.get("country", ""))
                    )
                enriched.append(new_rec)
            return enriched

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
                FileNotFoundError, OSError):
            return self._batch_python_fallback(records)

    # ── private helpers ───────────────────────────────────────────────────────

    def _batch_python_fallback(self, records: list[dict]) -> list[dict]:
        enriched: list[dict] = []
        for rec in records:
            new_rec = dict(rec)
            new_rec["normalized_name"] = normalize_name_py(
                str(rec.get("name", ""))
            )
            new_rec["normalized_country"] = normalize_country_py(
                str(rec.get("country", ""))
            )
            enriched.append(new_rec)
        return enriched
