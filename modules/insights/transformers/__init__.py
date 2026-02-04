"""
Field transformers for insights profile extraction.

Provides transformation functions referenced in field_mapping.yaml configs.
"""

from modules.insights.transformers.text_transformers import (
    clean_whitespace,
    title_case,
    lowercase,
    uppercase,
)
from modules.insights.transformers.numeric_transformers import (
    extract_numeric,
    extract_currency,
    to_integer,
    to_float,
)
from modules.insights.transformers.pattern_transformers import (
    extract_checkbox,
    regex_extract,
)
from modules.insights.transformers.date_transformers import (
    parse_date,
    calculate_age_from_dob,
)

__all__ = [
    # Text
    "clean_whitespace",
    "title_case",
    "lowercase",
    "uppercase",
    # Numeric
    "extract_numeric",
    "extract_currency",
    "to_integer",
    "to_float",
    # Patterns
    "extract_checkbox",
    "regex_extract",
    # Dates
    "parse_date",
    "calculate_age_from_dob",
]
