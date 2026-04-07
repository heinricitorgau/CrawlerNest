"""
Data formatting and conversion utilities.
"""

from typing import Any, Optional


def normalize_score(score: float, max_value: float) -> float:
    """
    Normalize a score to a 0-100 scale.
    
    Args:
        score: Raw score value
        max_value: Maximum possible value
        
    Returns:
        Normalized score (0-100)
    """
    if max_value <= 0:
        return 0.0
    return (score / max_value) * 100


def truncate_text(text: str, max_length: int = 40, suffix: str = "...") -> str:
    """
    Truncate text to a maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to append when truncating
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """
    Safely convert a value to float.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Float value or default
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def format_score(value: Optional[float], decimals: int = 2) -> str:
    """
    Format a score value for display.
    
    Args:
        value: Score value to format
        decimals: Number of decimal places
        
    Returns:
        Formatted score string or "N/A" if None
    """
    if value is None:
        return "N/A"
    
    formatted = f"{value:.{decimals}f}".rstrip('0').rstrip('.')
    return formatted if formatted else "0"
