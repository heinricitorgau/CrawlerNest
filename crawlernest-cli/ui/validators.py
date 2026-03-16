"""
Input validation utilities.
"""

from typing import Dict, List, Optional, Tuple


def validate_country_input(
    country_input: str,
    available_countries: Dict[str, str],
    country_aliases: Dict[str, str]
) -> Tuple[Optional[List[str]], List[str]]:
    """
    Validate and normalize country input (supports multiple countries).
    
    Args:
        country_input: User input (single or comma-separated countries)
        available_countries: Dict of available country codes and names
        country_aliases: Dict of country code aliases
        
    Returns:
        Tuple of (valid_countries, invalid_inputs)
    """
    if not country_input.strip():
        return None, []
    
    # Split by comma for multiple countries
    country_inputs = [x.strip() for x in country_input.split(',')]
    selected_countries = []
    invalid_countries = []

    for c_input in country_inputs:
        if not c_input:
            continue
            
        # Try direct code match
        normalized = country_aliases.get(c_input.lower(), c_input.lower())
        if normalized in available_countries:
            selected_countries.append(normalized)
            continue

        # Try name match
        matched = None
        for code, name in available_countries.items():
            if c_input.lower() == name.lower():
                matched = code
                break
        
        if matched:
            selected_countries.append(matched)
            continue

        # Invalid country
        invalid_countries.append(c_input)

    if invalid_countries:
        return None, invalid_countries
    
    if not selected_countries:
        return None, []
    
    # Remove duplicates while preserving order
    unique_countries = list(dict.fromkeys(selected_countries))
    return unique_countries, []


def validate_positive_integer(value: str) -> Optional[int]:
    """
    Validate that a string is a positive integer.
    
    Args:
        value: String to validate
        
    Returns:
        Integer value if valid, None otherwise
    """
    if not value.strip():
        return None
    
    if value.isdigit() and int(value) > 0:
        return int(value)
    
    return None


def validate_choice(value: str, min_choice: int, max_choice: int) -> Optional[int]:
    """
    Validate that a string is a valid choice within a range.
    
    Args:
        value: String to validate
        min_choice: Minimum valid choice
        max_choice: Maximum valid choice
        
    Returns:
        Integer choice if valid, None otherwise
    """
    if not value.strip():
        return None
    
    if value.isdigit():
        choice = int(value)
        if min_choice <= choice <= max_choice:
            return choice
    
    return None


def parse_multi_select(value: str, num_options: int) -> List[int]:
    """
    Parse multi-select input (comma-separated numbers).
    
    Args:
        value: User input (e.g., "1,3,5")
        num_options: Total number of available options
        
    Returns:
        List of selected indices (1-indexed)
    """
    if not value.strip():
        return list(range(1, num_options + 1))  # Return all if empty
    
    selected_idx = []
    for part in value.split(','):
        part = part.strip()
        if part.isdigit():
            idx = int(part)
            if 1 <= idx <= num_options:
                selected_idx.append(idx)
    
    return selected_idx
