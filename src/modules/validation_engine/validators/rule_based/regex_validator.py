"""Regex pattern validator"""

import re
from typing import Dict, Any, List, Optional
from ...core.base import IValidator, ValidationResult, ValidationContext
from ...validators.validator_registry import ValidatorRegistry
from ...utils.constants import ValidatorType, Severity
from shared.utils.logger import get_logger

logger = get_logger(__name__)


@ValidatorRegistry.register("regex_validator")
class RegexValidator(IValidator):
    """
    Validates that fields match specified regex patterns

    Config:
        validations: List of pattern validations
            - field: Field name to validate
            - pattern: Regex pattern
            - description: Human-readable description of pattern
            - flags: Regex flags (optional)
                - "ignorecase": Case-insensitive matching
                - "multiline": Multiline matching
            - required: Whether field is required (default: true)

    Example config:
        validations:
          - field: "hs_code"
            pattern: "^\\d{4}\\.\\d{2}$"
            description: "HS Code format (XXXX.XX)"

          - field: "email"
            pattern: "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
            description: "Valid email address"
            flags: ["ignorecase"]
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.validator_type = ValidatorType.RULE_BASED
        self.validator_name = "regex_validator"

        self.validations = config.get("validations", [])

        # Compile patterns
        self.compiled_patterns = {}
        for validation in self.validations:
            field = validation.get("field")
            pattern = validation.get("pattern")
            flags_list = validation.get("flags", [])

            # Convert flags
            flags = 0
            if "ignorecase" in flags_list:
                flags |= re.IGNORECASE
            if "multiline" in flags_list:
                flags |= re.MULTILINE

            try:
                self.compiled_patterns[field] = re.compile(pattern, flags)
            except re.error as e:
                logger.error(f"Invalid regex pattern for field '{field}': {e}")

        logger.debug(
            f"RegexValidator initialized with {len(self.validations)} patterns"
        )

    async def validate(
        self,
        source_data: Dict[str, Any],
        target_data: Optional[Dict[str, Any]],
        context: ValidationContext
    ) -> List[ValidationResult]:
        """
        Validate regex patterns

        Args:
            source_data: Source document data
            target_data: Target document data (optional)
            context: Validation context

        Returns:
            List of validation results
        """
        results = []

        for validation_config in self.validations:
            field_name = validation_config.get("field")
            pattern = validation_config.get("pattern")
            description = validation_config.get("description", pattern)
            required = validation_config.get("required", True)

            # Get field value
            value = source_data.get(field_name)

            # Check if field exists
            if value is None:
                if required:
                    results.append(ValidationResult(
                        validator_name=self.validator_name,
                        validator_type=self.validator_type,
                        field_name=field_name,
                        source_value=None,
                        target_value=None,
                        passed=False,
                        confidence=1.0,
                        severity=self.get_severity({}),
                        message=f"Required field '{field_name}' not found"
                    ))
                continue

            # Convert to string
            value_str = str(value)

            # Get compiled pattern
            compiled_pattern = self.compiled_patterns.get(field_name)

            if not compiled_pattern:
                logger.warning(f"No compiled pattern for field '{field_name}'")
                continue

            # Match pattern
            match = compiled_pattern.match(value_str)
            passed = match is not None

            result = ValidationResult(
                validator_name=self.validator_name,
                validator_type=self.validator_type,
                field_name=field_name,
                source_value=value,
                target_value=None,
                expected_value={
                    "pattern": pattern,
                    "description": description
                },
                passed=passed,
                confidence=1.0,
                severity=self.get_severity({}) if not passed else Severity.INFO,
                message=(
                    f"Field '{field_name}' matches pattern: {description}"
                    if passed
                    else f"Field '{field_name}' does not match pattern: {description}. "
                         f"Value: '{value_str}'"
                ),
                discrepancy={
                    "value": value_str,
                    "pattern": pattern,
                    "description": description
                } if not passed else None
            )

            results.append(result)

            if not passed:
                logger.debug(
                    f"Regex validation failed: '{value_str}' does not match '{pattern}'"
                )

        return results

    def supports_field_type(self, field_type: str) -> bool:
        """
        Check if validator supports this field type

        Args:
            field_type: Type of field

        Returns:
            True for string types
        """
        return field_type in ["string", "text"]
