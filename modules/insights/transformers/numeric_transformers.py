"""Numeric transformation functions."""

import re
from typing import Any, Optional, List


def extract_numeric(value: Any, pattern: str = r"([0-9]+)") -> Optional[int]:
    """
    Extract first numeric value from string.

    Args:
        value: Input value
        pattern: Regex pattern to extract numbers

    Returns:
        Extracted integer or None

    Example:
        >>> extract_numeric("Age: 42 years")
        42
        >>> extract_numeric("4 2")  # "4 2" -> 42
        4
    """
    if value is None or value == "":
        return None

    str_value = str(value).strip()

    # First try to extract all digits and join them
    # This handles cases like "4 2" -> "42"
    all_digits = re.findall(r'\d', str_value)
    if all_digits:
        try:
            return int(''.join(all_digits))
        except ValueError:
            pass

    # Fallback to pattern extraction
    match = re.search(pattern, str_value)
    if match:
        try:
            return int(match.group(1))
        except (ValueError, IndexError):
            pass

    return None


def extract_currency(
    value: Any,
    pattern: str = r"([0-9,]+\.?[0-9]*)",
    remove_chars: Optional[List[str]] = None
) -> Optional[float]:
    """
    Extract currency amount from string.

    Args:
        value: Input value
        pattern: Regex pattern to extract amount
        remove_chars: Characters to remove (default: [","])

    Returns:
        Extracted float or None

    Example:
        >>> extract_currency("GHS 6,800")
        6800.0
        >>> extract_currency("$1,234.56")
        1234.56
    """
    if value is None or value == "":
        return None

    str_value = str(value).strip()

    # Extract numeric part using pattern
    match = re.search(pattern, str_value)
    if not match:
        return None

    numeric_str = match.group(1)

    # Remove specified characters (default: comma)
    if remove_chars is None:
        remove_chars = [',']

    for char in remove_chars:
        numeric_str = numeric_str.replace(char, '')

    try:
        return float(numeric_str)
    except ValueError:
        return None


def to_integer(value: Any) -> Optional[int]:
    """
    Convert value to integer.

    Args:
        value: Input value

    Returns:
        Integer or None

    Example:
        >>> to_integer("42")
        42
        >>> to_integer(42.7)
        42
    """
    if value is None or value == "":
        return None

    try:
        # Handle string numbers
        if isinstance(value, str):
            # Remove commas and spaces
            value = value.replace(',', '').replace(' ', '').strip()

        return int(float(value))
    except (ValueError, TypeError):
        return None


def to_float(value: Any) -> Optional[float]:
    """
    Convert value to float.

    Args:
        value: Input value

    Returns:
        Float or None

    Example:
        >>> to_float("42.5")
        42.5
        >>> to_float("1,234.56")
        1234.56
    """
    if value is None or value == "":
        return None

    try:
        # Handle string numbers
        if isinstance(value, str):
            # Remove commas and spaces
            value = value.replace(',', '').replace(' ', '').strip()

        return float(value)
    except (ValueError, TypeError):
        return None
