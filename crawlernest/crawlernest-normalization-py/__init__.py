"""
crawlernest-normalization-py

Python bridge and fallback normalizers for the Clawer C normalization engine.

Exports
-------
CNormalizerBridge   — subprocess bridge to build/clawer_normalizer
normalize_name_py   — Python normalizer (thin wrapper around entity_resolution)
normalize_country_py — Python country normalizer (matching C mapping table)
"""

from .normalizer_bridge import (
    CNormalizerBridge,
    normalize_name_py,
    normalize_country_py,
)

__all__ = [
    "CNormalizerBridge",
    "normalize_name_py",
    "normalize_country_py",
]
