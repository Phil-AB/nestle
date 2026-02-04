"""
Helper utility functions.
"""

from datetime import datetime
from typing import Any
import hashlib
import json


def generate_file_hash(file_bytes: bytes) -> str:
    """
    Generate SHA256 hash of file content.

    Args:
        file_bytes: File content as bytes

    Returns:
        Hexadecimal hash string
    """
    return hashlib.sha256(file_bytes).hexdigest()


def safe_get(data: dict, *keys: str, default: Any = None) -> Any:
    """
    Safely get nested dictionary value.

    Args:
        data: Dictionary to query
        *keys: Sequence of keys to traverse
        default: Default value if key not found

    Returns:
        Value at the nested key or default

    Example:
        safe_get({"a": {"b": {"c": 1}}}, "a", "b", "c")  # Returns 1
        safe_get({"a": {"b": {}}}, "a", "b", "c", default=0)  # Returns 0
    """
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def normalize_address(address: str) -> str:
    """
    Normalize address for comparison.
    Removes extra spaces, converts to lowercase.

    Args:
        address: Address string

    Returns:
        Normalized address
    """
    if not address:
        return ""

    # Convert to lowercase
    normalized = address.lower()

    # Remove extra spaces
    normalized = " ".join(normalized.split())

    # Remove common punctuation variations
    replacements = {
        "street": "st",
        "avenue": "ave",
        "road": "rd",
        "boulevard": "blvd",
        "drive": "dr",
        "lane": "ln",
    }

    for full, abbrev in replacements.items():
        normalized = normalized.replace(full, abbrev)

    return normalized


def format_currency(value: float, currency: str = "USD") -> str:
    """
    Format currency value for display.

    Args:
        value: Numeric value
        currency: Currency code

    Returns:
        Formatted currency string
    """
    return f"{currency} {value:,.2f}"


def calculate_percentage(part: float, total: float) -> float:
    """
    Calculate percentage with safe division.

    Args:
        part: Part value
        total: Total value

    Returns:
        Percentage value (0-100)
    """
    if total == 0:
        return 0.0
    return round((part / total) * 100, 2)


def serialize_for_json(obj: Any) -> Any:
    """
    Serialize object for JSON storage.
    Handles datetime objects and other non-serializable types.

    Args:
        obj: Object to serialize

    Returns:
        JSON-serializable object
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, (set, frozenset)):
        return list(obj)
    elif hasattr(obj, "__dict__"):
        return obj.__dict__
    else:
        return str(obj)


def deep_merge(dict1: dict, dict2: dict) -> dict:
    """
    Deep merge two dictionaries.

    Args:
        dict1: First dictionary
        dict2: Second dictionary (takes precedence)

    Returns:
        Merged dictionary
    """
    result = dict1.copy()

    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate text to maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add when truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix
