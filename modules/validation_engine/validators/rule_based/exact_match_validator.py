"""Exact match validator for field comparison"""

from typing import Dict, Any, List, Optional
from ...core.base import IValidator, ValidationResult, ValidationContext
from ...validators.validator_registry import ValidatorRegistry
from ...utils.constants import ValidatorType, Severity
from shared.utils.logger import get_logger

logger = get_logger(__name__)


@ValidatorRegistry.register("exact_match_validator")
class ExactMatchValidator(IValidator):
    """
    Validates that fields match exactly between source and target documents

    Config:
        fields: List of field mappings to validate
            - source: Source field path (e.g., "invoice.hs_code")
            - target: Target field path (e.g., "bill_of_entry.hs_code")
            - match_type: "exact" (default), "case_insensitive"
            - required: Whether field is required (default: true)

        mode: Validation mode
            - "strict": All fields must match exactly
            - "lenient": Allow minor differences (case, whitespace)

    Example config:
        fields:
          - source: "invoice.hs_code"
            target: "bill_of_entry.hs_code"
            match_type: "exact"

          - source: "invoice.description"
            target: "bill_of_entry.description"
            match_type: "case_insensitive"
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.validator_type = ValidatorType.RULE_BASED
        self.validator_name = "exact_match_validator"

        # Get field mappings
        self.fields = config.get("fields", [])
        self.mode = config.get("mode", "strict")

        logger.debug(f"ExactMatchValidator initialized with {len(self.fields)} field mappings")

    async def validate(
        self,
        source_data: Dict[str, Any],
        target_data: Optional[Dict[str, Any]],
        context: ValidationContext
    ) -> List[ValidationResult]:
        """
        Validate exact field matches

        Args:
            source_data: Source document data
            target_data: Target document data
            context: Validation context

        Returns:
            List of validation results
        """
        results = []

        if not target_data:
            logger.warning("No target data provided for exact match validation")
            return results

        for field_config in self.fields:
            source_path = field_config.get("source")
            target_path = field_config.get("target")
            match_type = field_config.get("match_type", "exact")
            required = field_config.get("required", True)

            # Extract field values
            source_value = self._get_nested_value(source_data, source_path)
            target_value = self._get_nested_value(target_data, target_path)

            # Extract field names
            source_field = source_path.split(".")[-1] if "." in source_path else source_path
            target_field = target_path.split(".")[-1] if "." in target_path else target_path

            # Check if fields exist
            if source_value is None and required:
                results.append(ValidationResult(
                    validator_name=self.validator_name,
                    validator_type=self.validator_type,
                    field_name=source_field,
                    source_value=None,
                    target_value=target_value,
                    passed=False,
                    confidence=1.0,
                    severity=self.get_severity({}),
                    message=f"Required field '{source_path}' not found in source document"
                ))
                continue

            if target_value is None and required:
                results.append(ValidationResult(
                    validator_name=self.validator_name,
                    validator_type=self.validator_type,
                    field_name=target_field,
                    source_value=source_value,
                    target_value=None,
                    passed=False,
                    confidence=1.0,
                    severity=self.get_severity({}),
                    message=f"Required field '{target_path}' not found in target document"
                ))
                continue

            # Skip if both are None and not required
            if source_value is None and target_value is None and not required:
                continue

            # Perform match
            passed = self._match_values(source_value, target_value, match_type)

            # Create result
            result = ValidationResult(
                validator_name=self.validator_name,
                validator_type=self.validator_type,
                field_name=source_field,
                source_document=source_path.split(".")[0] if "." in source_path else None,
                target_document=target_path.split(".")[0] if "." in target_path else None,
                source_value=source_value,
                target_value=target_value,
                passed=passed,
                confidence=1.0 if passed else 0.9,  # High confidence for exact match
                severity=self.get_severity({}) if not passed else Severity.INFO,
                message=(
                    f"Field '{source_field}' matches exactly"
                    if passed
                    else f"Field '{source_field}' mismatch: '{source_value}' != '{target_value}'"
                ),
                discrepancy={
                    "source_path": source_path,
                    "target_path": target_path,
                    "match_type": match_type
                } if not passed else None
            )

            results.append(result)

            logger.debug(
                f"Exact match validation: {source_path} vs {target_path} = "
                f"{'PASS' if passed else 'FAIL'}"
            )

        return results

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """
        Get value from nested dictionary using dot notation

        Args:
            data: Dictionary to search
            path: Dot-separated path (e.g., "invoice.hs_code")

        Returns:
            Value at path or None if not found
        """
        parts = path.split(".")
        value = data

        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
                if value is None:
                    return None
            else:
                return None

        return value

    def _match_values(self, source: Any, target: Any, match_type: str) -> bool:
        """
        Match two values based on match type

        Args:
            source: Source value
            target: Target value
            match_type: Type of match (exact, case_insensitive)

        Returns:
            True if values match
        """
        if match_type == "exact":
            return source == target

        elif match_type == "case_insensitive":
            if isinstance(source, str) and isinstance(target, str):
                return source.lower() == target.lower()
            return source == target

        elif match_type == "normalized":
            # Normalize whitespace and case
            if isinstance(source, str) and isinstance(target, str):
                source_norm = " ".join(source.lower().split())
                target_norm = " ".join(target.lower().split())
                return source_norm == target_norm
            return source == target

        # Default to exact match
        return source == target

    def supports_field_type(self, field_type: str) -> bool:
        """
        Check if validator supports this field type

        Args:
            field_type: Type of field

        Returns:
            True (supports all field types)
        """
        return True  # Exact match works for all types
