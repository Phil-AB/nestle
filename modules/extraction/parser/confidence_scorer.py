"""
Deterministic per-field confidence scorer.

Replaces Claude's self-assessed visual confidence (which is subjective and
non-deterministic) with a computed score built from verifiable signals only:

  1. Presence / redaction  (hard rules — score is 0.0)
  2. Format match          (sole signal — 100% weight)

Formula (for non-null, non-redacted values):
    score = format_score

Claude's visual confidence is intentionally excluded — LLM temperature means
Claude returns different confidence values for the same field on different runs,
making any formula that includes it non-deterministic.

Score table:
  - Field present, correct format         → 1.0
  - Field present, date with digits only  → 0.85
  - Field present, format mismatch        → 0.75–0.90
  - Null or redacted field                → 0.0

Scores are rounded to 2 decimal places.
"""

import re
import logging
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Field-type detection — keyword sets mapped to format validators
# ---------------------------------------------------------------------------

_NUMERIC_KEYWORDS = {
    "weight", "quantity", "units", "bags", "amount", "total",
    "price", "value", "rate", "gross", "nett", "net", "cbm",
    "count", "number_of", "no_of",
}

_REF_KEYWORDS = {
    "number", "_no", "reference", "_ref", "_id", "contract",
    "booking", "bl_", "b_l", "invoice_no", "order_no",
    "customer_ref", "po_number",
}

_DATE_KEYWORDS = {
    "date", "ets", "dated", "shipped_on", "issued",
    "expiry", "exp_date", "prod_date",
}

_NAME_KEYWORDS = {
    "name", "carrier", "consignee", "shipper", "exporter",
    "importer", "seller", "buyer", "notify",
}

_ADDRESS_KEYWORDS = {
    "address", "bill_to", "ship_to", "delivery",
    "place_of", "port_of", "port",
}

# Regex patterns
_RE_HAS_DIGIT = re.compile(r'\d')
_RE_ALNUM_REF = re.compile(r'^[A-Z0-9][A-Z0-9\-/.\s]{1,}$', re.IGNORECASE)
_RE_DATE = re.compile(
    r'\d{2}[\-/]\d{2}[\-/]\d{2,4}'      # DD-MM-YYYY or DD/MM/YY
    r'|\d{4}[\-/]\d{2}[\-/]\d{2}'       # YYYY-MM-DD
    r'|[A-Za-z]{3}\s+\d{1,2},?\s+\d{4}'  # Jan 21, 2026
)


def _field_type(name: str) -> str:
    """Classify a field name into a semantic type."""
    n = name.lower()
    if any(kw in n for kw in _DATE_KEYWORDS):
        return "date"
    if any(kw in n for kw in _NUMERIC_KEYWORDS):
        return "numeric"
    if any(kw in n for kw in _REF_KEYWORDS):
        return "reference"
    if any(kw in n for kw in _ADDRESS_KEYWORDS):
        return "address"
    if any(kw in n for kw in _NAME_KEYWORDS):
        return "name"
    return "text"


def _format_score(field_name: str, value: str) -> float:
    """
    Return a format match score (0.0–1.0) based on whether the extracted
    value looks correct for this field type.

    A mismatch does NOT mean the value is wrong — it means Claude may have
    extracted something unexpected (e.g. a label instead of a value).
    """
    val = str(value).strip()
    if not val:
        return 0.0

    ftype = _field_type(field_name)

    if ftype == "numeric":
        # Must contain at least one digit
        if _RE_HAS_DIGIT.search(val):
            return 1.0
        return 0.75  # text where a number was expected

    if ftype == "reference":
        # Should be alphanumeric, may contain dashes/slashes
        if _RE_ALNUM_REF.match(val) and len(val) >= 3:
            return 1.0
        # Contains digits — probably still correct but unusual format
        if _RE_HAS_DIGIT.search(val):
            return 0.90
        return 0.80

    if ftype == "date":
        if _RE_DATE.search(val):
            return 1.0
        # Contains digits but doesn't look like a date
        if _RE_HAS_DIGIT.search(val):
            return 0.85
        return 0.75

    # name, address, text — any non-empty string is acceptable
    return 1.0


def _unwrap(field_value: Any) -> Tuple[Any, float, bool]:
    """
    Unwrap a Claude field value envelope.

    Returns:
        (raw_value, claude_confidence, is_redacted)
    """
    if isinstance(field_value, dict):
        redacted = field_value.get("redacted", False)
        value = field_value.get("value")
        confidence = float(field_value.get("confidence") or 1.0)
        return value, confidence, redacted
    # Bare scalar (post-processing sometimes sets these directly)
    return field_value, 1.0, False


def compute_field_confidence(field_name: str, field_value: Any) -> float:
    """
    Compute a deterministic confidence score for a single extracted field.

    Args:
        field_name:  Snake-case field key.
        field_value: Raw value from Claude (dict envelope or scalar).

    Returns:
        Confidence score in [0.0, 1.0], rounded to 2 decimal places.
    """
    raw_value, _, is_redacted = _unwrap(field_value)

    # Hard rule: redacted or null → 0.0
    if is_redacted:
        return 0.0
    if raw_value is None or str(raw_value).strip() == "":
        return 0.0

    # Format match is the sole signal — fully deterministic, no LLM input
    fmt = _format_score(field_name, str(raw_value))
    return round(min(1.0, max(0.0, fmt)), 2)


def score_fields(fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    Replace Claude's self-assessed confidence values in every field with
    deterministically computed scores.

    Operates in-place on the fields dict and also returns it.

    Fields that are already bare scalars (set by post-processing) are wrapped
    into the standard envelope ``{"value": ..., "confidence": <score>}``.

    Args:
        fields: Extracted fields dict from the provider.

    Returns:
        The same dict with updated confidence values.
    """
    for key, val in fields.items():
        score = compute_field_confidence(key, val)

        if isinstance(val, dict) and "value" in val:
            # Envelope — update confidence in place
            val["confidence"] = score
        else:
            # Bare scalar set by post-processing — wrap it
            fields[key] = {"value": val, "confidence": score}

    logger.debug(f"Confidence scored {len(fields)} fields")
    return fields


def score_items(items: list) -> list:
    """
    Apply confidence scoring to all cell values in the items array.

    Each item is a flat dict of ``{column: cell_value}`` where cell_value
    is a Claude envelope ``{"value": ..., "confidence": ...}``.

    Args:
        items: List of item dicts from the provider.

    Returns:
        The same list with updated confidence values.
    """
    for item in items:
        if not isinstance(item, dict):
            continue
        for col, cell in item.items():
            score = compute_field_confidence(col, cell)
            if isinstance(cell, dict) and "value" in cell:
                cell["confidence"] = score
            else:
                item[col] = {"value": cell, "confidence": score}
    return items
