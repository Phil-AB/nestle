"""Date transformation functions."""

from datetime import datetime, date
from typing import Any, Optional, List


def parse_date(
    value: Any,
    formats: Optional[List[str]] = None
) -> Optional[date]:
    """
    Parse date string to date object.

    Args:
        value: Input date string
        formats: List of date formats to try

    Returns:
        Parsed date or None

    Example:
        >>> parse_date("02/01/1980")
        datetime.date(1980, 1, 2)
    """
    if value is None or value == "":
        return None

    if isinstance(value, date):
        return value

    if isinstance(value, datetime):
        return value.date()

    str_value = str(value).strip()

    # Default formats if none provided
    if formats is None:
        formats = [
            "%d/%m/%Y",
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%m/%d/%Y",
            "%Y/%m/%d",
            "%d.%m.%Y",
        ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(str_value, fmt)
            return parsed.date()
        except ValueError:
            continue

    return None


def calculate_age_from_dob(value: Any) -> Optional[int]:
    """
    Calculate age from date of birth.

    Args:
        value: Date of birth (string or date object)

    Returns:
        Age in years or None

    Example:
        >>> calculate_age_from_dob("02/01/1980")
        46  # As of 2026
    """
    if value is None or value == "":
        return None

    # Parse date if it's a string
    if isinstance(value, str):
        dob = parse_date(value)
        if dob is None:
            return None
    elif isinstance(value, datetime):
        dob = value.date()
    elif isinstance(value, date):
        dob = value
    else:
        return None

    # Calculate age
    today = date.today()
    age = today.year - dob.year

    # Adjust if birthday hasn't occurred this year
    if (today.month, today.day) < (dob.month, dob.day):
        age -= 1

    return age if age >= 0 else None
