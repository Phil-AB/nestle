"""Text transformation functions."""

import re
from typing import Any, Optional


def clean_whitespace(value: Any) -> Optional[str]:
    """
    Remove extra whitespace and trim.

    Args:
        value: Input value

    Returns:
        Cleaned string or None

    Example:
        >>> clean_whitespace("  hello   world  ")
        "hello world"
    """
    if value is None or value == "":
        return None

    str_value = str(value)
    # Strip leading/trailing whitespace
    cleaned = str_value.strip()
    # Collapse multiple spaces to single space
    cleaned = re.sub(r'\s+', ' ', cleaned)

    return cleaned if cleaned else None


def title_case(value: Any) -> Optional[str]:
    """
    Convert to title case.

    Args:
        value: Input value

    Returns:
        Title cased string or None

    Example:
        >>> title_case("JOHN DOE")
        "John Doe"
    """
    if value is None or value == "":
        return None

    str_value = str(value).strip()
    return str_value.title() if str_value else None


def lowercase(value: Any) -> Optional[str]:
    """
    Convert to lowercase.

    Args:
        value: Input value

    Returns:
        Lowercase string or None

    Example:
        >>> lowercase("HELLO")
        "hello"
    """
    if value is None or value == "":
        return None

    str_value = str(value).strip()
    return str_value.lower() if str_value else None


def uppercase(value: Any) -> Optional[str]:
    """
    Convert to uppercase.

    Args:
        value: Input value

    Returns:
        Uppercase string or None

    Example:
        >>> uppercase("hello")
        "HELLO"
    """
    if value is None or value == "":
        return None

    str_value = str(value).strip()
    return str_value.upper() if str_value else None
