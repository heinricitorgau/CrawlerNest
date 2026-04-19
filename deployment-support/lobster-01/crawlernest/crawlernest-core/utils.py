"""
Utility functions for QS University Rankings crawler.

This module re-exports utilities from the modularized utils package
to maintain backward compatibility with existing code.
"""

# Re-export from utils package for backward compatibility
from utils.logging import setup_logging
from utils.retry import retry
from utils.formatters import (
    normalize_score,
    truncate_text,
    safe_float,
    format_score,
)
from utils.cache import SimpleCache

__all__ = [
    "setup_logging",
    "retry",
    "normalize_score",
    "truncate_text",
    "safe_float",
    "format_score",
    "SimpleCache",
]
