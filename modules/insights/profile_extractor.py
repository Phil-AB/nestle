"""
Profile Extractor - Rule-based field extraction.

Extracts normalized customer profile from raw OCR data using field_mapping config.
100% rule-based, no LLM.
"""

import re
from typing import Dict, Any, Optional, List
from shared.utils.logger import setup_logger
from modules.insights import transformers

logger = setup_logger(__name__)


class ProfileExtractor:
    """
    Extracts normalized customer profile from raw extracted data.

    Uses field_mapping.yaml config to:
    1. Map raw field names to normalized attributes
    2. Apply transformations (extract numbers, parse dates, etc.)
    3. Apply value mappings
    4. Validate required fields
    """

    def __init__(self, field_mapping_config: Dict[str, Any]):
        """
        Initialize profile extractor with field mapping config.

        Args:
            field_mapping_config: Field mapping configuration from YAML
        """
        self.config = field_mapping_config
        self.profile_mapping = field_mapping_config.get("profile_mapping", {})
        self.transformations = field_mapping_config.get("transformations", {})
        self.empty_markers = field_mapping_config.get("empty_value_markers", [])

    def extract_profile(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract normalized profile from raw data.

        Args:
            raw_data: Raw extracted data from OCR/database

        Returns:
            Normalized customer profile

        Example:
            >>> raw_data = {
            ...     "surname": {"value": "mensah"},
            ...     "first_names": {"value": "kwame daniel"},
            ...     "age": {"value": "4 2"},
            ...     "net_salary": {"value": "GHS 6,800"}
            ... }
            >>> profile = extractor.extract_profile(raw_data)
            >>> profile["full_name"]
            "Kwame Daniel Mensah"
            >>> profile["age"]
            42
            >>> profile["monthly_income"]
            6800.0
        """
        # Flatten raw data (extract "value" from nested structures)
        flattened = self._flatten_raw_data(raw_data)

        # Extract each profile attribute
        profile = {}
        for attr_name, attr_config in self.profile_mapping.items():
            value = self._extract_attribute(attr_name, attr_config, flattened)

            # Only include non-None values
            if value is not None:
                profile[attr_name] = value

        logger.debug(f"Extracted profile with {len(profile)} attributes")
        return profile

    def _flatten_raw_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Flatten raw data structure.

        Handles nested structures like:
        {"field": {"value": "actual", "bbox": {...}}} -> {"field": "actual"}

        Args:
            raw_data: Raw nested data

        Returns:
            Flattened data
        """
        flattened = {}

        for key, val in raw_data.items():
            if isinstance(val, dict) and "value" in val:
                # Extract value from nested structure
                extracted_val = val["value"]

                # Check for empty markers
                if self._is_empty_value(extracted_val):
                    flattened[key] = None
                else:
                    flattened[key] = extracted_val
            else:
                # Already flat or non-standard structure
                if self._is_empty_value(val):
                    flattened[key] = None
                else:
                    flattened[key] = val

        return flattened

    def _is_empty_value(self, value: Any) -> bool:
        """Check if value is considered empty."""
        if value is None or value == "":
            return True

        if isinstance(value, str):
            return value.strip() in self.empty_markers

        return False

    def _extract_attribute(
        self,
        attr_name: str,
        attr_config: Dict[str, Any],
        flattened_data: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Extract a single profile attribute.

        Args:
            attr_name: Attribute name (e.g., "full_name")
            attr_config: Attribute configuration
            flattened_data: Flattened raw data

        Returns:
            Extracted value or None
        """
        # Get source fields
        source_fields = attr_config.get("source_fields", [])
        if not source_fields:
            logger.warning(f"No source_fields defined for {attr_name}")
            return None

        # Try each source field in order
        raw_value = None
        for field_name in source_fields:
            if field_name in flattened_data:
                raw_value = flattened_data[field_name]
                if raw_value is not None:
                    break

        if raw_value is None:
            # Check if required
            if attr_config.get("required", False):
                logger.warning(f"Required field {attr_name} is missing")
            return None

        # Handle combining multiple fields
        if attr_config.get("combine", False):
            raw_value = self._combine_fields(attr_config, flattened_data)
            if raw_value is None:
                return None

        # Apply transformations
        transforms = attr_config.get("transforms", [])
        value = self._apply_transforms(raw_value, transforms)

        # Apply value mapping
        value_mapping = attr_config.get("value_mapping", {})
        if value_mapping and value is not None:
            value = value_mapping.get(str(value), value)

        # Apply validation
        validation = attr_config.get("validation", {})
        if validation and value is not None:
            value = self._validate_value(value, validation)

        # Apply default if still None
        if value is None:
            value = attr_config.get("default")

        return value

    def _combine_fields(
        self,
        attr_config: Dict[str, Any],
        flattened_data: Dict[str, Any]
    ) -> Optional[str]:
        """
        Combine multiple fields into one.

        Args:
            attr_config: Attribute configuration
            flattened_data: Flattened data

        Returns:
            Combined string or None
        """
        source_fields = attr_config.get("source_fields", [])
        separator = attr_config.get("separator", " ")
        order = attr_config.get("order", source_fields)

        parts = []
        for field_name in order:
            if field_name in flattened_data:
                val = flattened_data[field_name]
                if val is not None and str(val).strip():
                    parts.append(str(val).strip())

        return separator.join(parts) if parts else None

    def _apply_transforms(
        self,
        value: Any,
        transforms: List[Dict[str, Any]]
    ) -> Optional[Any]:
        """
        Apply transformation pipeline to value.

        Transforms are tried in order. If a transform succeeds (returns non-None),
        we stop and return that result. This allows fallback strategies.

        Args:
            value: Input value
            transforms: List of transformations to apply

        Returns:
            Transformed value
        """
        original_value = value

        for transform in transforms:
            transform_type = transform.get("type")
            if not transform_type:
                continue

            # Get transformer function
            transformer_func = getattr(transformers, transform_type, None)
            if transformer_func is None:
                logger.warning(f"Unknown transformer: {transform_type}")
                continue

            # Apply transformer with optional parameters
            try:
                if "pattern" in transform:
                    result = transformer_func(original_value, pattern=transform["pattern"])
                elif "remove_chars" in transform:
                    result = transformer_func(original_value, remove_chars=transform["remove_chars"])
                else:
                    result = transformer_func(original_value)

                # If transform succeeded (non-None), return it
                if result is not None:
                    return result

            except Exception as e:
                logger.debug(f"Transformation {transform_type} failed: {e}")
                # Try next transform
                continue

        # All transforms failed, return None
        return None

    def _validate_value(
        self,
        value: Any,
        validation: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Validate extracted value.

        Args:
            value: Value to validate
            validation: Validation rules

        Returns:
            Value if valid, None otherwise
        """
        # Min/max validation for numbers
        if "min" in validation:
            try:
                if float(value) < float(validation["min"]):
                    logger.warning(f"Value {value} below minimum {validation['min']}")
                    return None
            except (ValueError, TypeError):
                pass

        if "max" in validation:
            try:
                if float(value) > float(validation["max"]):
                    logger.warning(f"Value {value} above maximum {validation['max']}")
                    return None
            except (ValueError, TypeError):
                pass

        # Pattern validation
        if "pattern" in validation and isinstance(value, str):
            if not re.match(validation["pattern"], value):
                logger.warning(f"Value {value} doesn't match pattern {validation['pattern']}")
                return None

        return value
