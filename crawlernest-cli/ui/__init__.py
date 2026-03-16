"""
User interface package for QS University Rankings crawler.

Provides CLI, interactive input, and validation utilities.
"""

from .cli import main, parse_arguments
from .interactive import (
    fetch_rankings,
    get_user_parameters,
    print_available_countries_table,
)
from .validators import (
    validate_country_input,
    validate_positive_integer,
    validate_choice,
    parse_multi_select,
)

__all__ = [
    # CLI
    "main",
    "parse_arguments",
    # Interactive
    "fetch_rankings",
    "get_user_parameters",
    "print_available_countries_table",
    # Validators
    "validate_country_input",
    "validate_positive_integer", 
    "validate_choice",
    "parse_multi_select",
]
