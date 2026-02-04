"""Pattern-based transformation functions."""

import re
from typing import Any, Optional


def extract_checkbox(value: Any, pattern: str = r"\[x\]\s*([^\[\]]+)") -> Optional[str]:
    """
    Extract checked value from checkbox notation.

    Args:
        value: Input value with checkbox format
        pattern: Regex pattern to match checked item

    Returns:
        Extracted value or None

    Example:
        >>> extract_checkbox("[x] Male [ ] Female")
        "Male"
        >>> extract_checkbox("[ ] Single [x] Married [ ] Divorced")
        "Married"
    """
    if value is None or value == "":
        return None

    str_value = str(value).strip()

    match = re.search(pattern, str_value, re.IGNORECASE)
    if match:
        extracted = match.group(1).strip()
        return extracted if extracted else None

    return None


def regex_extract(value: Any, pattern: str) -> Optional[str]:
    """
    Extract value using custom regex pattern.

    Args:
        value: Input value
        pattern: Regex pattern with capture group

    Returns:
        Extracted value or None

    Example:
        >>> regex_extract("ID: 12345", r"ID:\s*(\d+)")
        "12345"
    """
    if value is None or value == "":
        return None

    str_value = str(value).strip()

    match = re.search(pattern, str_value)
    if match:
        try:
            return match.group(1).strip()
        except (IndexError, AttributeError):
            return None

    return None
