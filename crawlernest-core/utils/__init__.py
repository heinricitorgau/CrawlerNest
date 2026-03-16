"""
Utility functions package for QS University Rankings crawler.

Provides logging, retry, formatting, and caching utilities.
"""

from .logging import setup_logging
from .retry import retry
from .formatters import (
    normalize_score,
    truncate_text,
    safe_float,
    format_score,
)
from .cache import SimpleCache

__all__ = [
    # Logging
    "setup_logging",
    # Retry
    "retry",
    # Formatters
    "normalize_score",
    "truncate_text",
    "safe_float",
    "format_score",
    # Cache
    "SimpleCache",
]
