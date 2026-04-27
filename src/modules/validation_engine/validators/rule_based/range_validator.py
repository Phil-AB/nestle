"""Range validator for numeric fields"""

from typing import Dict, Any, List, Optional, Union
from decimal import Decimal
from ...core.base import IValidator, ValidationResult, ValidationContext
from ...validators.validator_registry import ValidatorRegistry
from ...utils.constants import ValidatorType, Severity, Operator
from shared.utils.logger import get_logger

logger = get_logger(__name__)


@ValidatorRegistry.register("range_validator")
class RangeValidator(IValidator):
    """
    Validates that numeric fields are within specified ranges

    Config:
        validations: List of range validations
            - field: Field name to validate
            - min: Minimum value (optional)
            - max: Maximum value (optional)
            - operator: Comparison operator (optional)
                - "within_range": Between min and max
                - "greater_than": > min
                - "less_than": < max
                - "equals": == value
            - inclusive: Include boundaries (default: true)
            - required: Whether field is required (default: true)

    Example config:
        validations:
          - field: "net_weight"
            min: 0
            max: 10000
            operator: "within_range"
            inclusive: true

          - field: "duty_rate"
            min: 0
            max: 1.0
            operator: "within_range"
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.validator_type = ValidatorType.RULE_BASED
        self.validator_name = "range_validator"

        self.validations = config.get("validations", [])

        logger.debug(
            f"RangeValidator initialized with {len(self.validations)} validations"
        )

    async def validate(
        self,
        source_data: Dict[str, Any],
        target_data: Optional[Dict[str, Any]],
        context: ValidationContext
    ) -> List[ValidationResult]:
        """
        Validate numeric ranges

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
            min_value = validation_config.get("min")
            max_value = validation_config.get("max")
            operator = validation_config.get("operator", Operator.WITHIN_RANGE)
            inclusive = validation_config.get("inclusive", True)
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

            # Convert to numeric
            try:
                numeric_value = self._to_numeric(value)
            except (ValueError, TypeError) as e:
                results.append(ValidationResult(
                    validator_name=self.validator_name,
                    validator_type=self.validator_type,
                    field_name=field_name,
                    source_value=value,
                    target_value=None,
                    passed=False,
                    confidence=1.0,
                    severity=self.get_severity({}),
                    message=f"Field '{field_name}' value '{value}' is not numeric"
                ))
                continue

            # Perform range validation
            passed, message = self._validate_range(
                value=numeric_value,
                min_value=min_value,
                max_value=max_value,
                operator=operator,
                inclusive=inclusive,
                field_name=field_name
            )

            result = ValidationResult(
                validator_name=self.validator_name,
                validator_type=self.validator_type,
                field_name=field_name,
                source_value=value,
                target_value=None,
                expected_value={
                    "min": min_value,
                    "max": max_value,
                    "operator": operator
                },
                passed=passed,
                confidence=1.0,
                severity=self.get_severity({}) if not passed else Severity.INFO,
                message=message,
                discrepancy={
                    "value": float(numeric_value),
                    "min": min_value,
                    "max": max_value,
                    "operator": operator,
                    "inclusive": inclusive
                } if not passed else None
            )

            results.append(result)

        return results

    def _to_numeric(self, value: Any) -> Union[Decimal, float, int]:
        """
        Convert value to numeric type

        Args:
            value: Value to convert

        Returns:
            Numeric value

        Raises:
            ValueError: If value cannot be converted
        """
        if isinstance(value, (int, float, Decimal)):
            return Decimal(str(value))

        if isinstance(value, str):
            # Remove common formatting
            cleaned = value.replace(",", "").replace(" ", "").strip()
            return Decimal(cleaned)

        raise ValueError(f"Cannot convert {type(value)} to numeric")

    def _validate_range(
        self,
        value: Decimal,
        min_value: Optional[Union[int, float]],
        max_value: Optional[Union[int, float]],
        operator: str,
        inclusive: bool,
        field_name: str
    ) -> tuple[bool, str]:
        """
        Validate value against range

        Args:
            value: Value to validate
            min_value: Minimum value
            max_value: Maximum value
            operator: Comparison operator
            inclusive: Include boundaries
            field_name: Field name for messages

        Returns:
            Tuple of (passed, message)
        """
        min_val = Decimal(str(min_value)) if min_value is not None else None
        max_val = Decimal(str(max_value)) if max_value is not None else None

        if operator == Operator.WITHIN_RANGE:
            if min_val is not None and max_val is not None:
                if inclusive:
                    passed = min_val <= value <= max_val
                    message = (
                        f"Field '{field_name}' value {value} is within range [{min_val}, {max_val}]"
                        if passed
                        else f"Field '{field_name}' value {value} is outside range [{min_val}, {max_val}]"
                    )
                else:
                    passed = min_val < value < max_val
                    message = (
                        f"Field '{field_name}' value {value} is within range ({min_val}, {max_val})"
                        if passed
                        else f"Field '{field_name}' value {value} is outside range ({min_val}, {max_val})"
                    )
                return passed, message

        elif operator == Operator.GREATER_THAN:
            if min_val is not None:
                if inclusive:
                    passed = value >= min_val
                    message = (
                        f"Field '{field_name}' value {value} >= {min_val}"
                        if passed
                        else f"Field '{field_name}' value {value} < {min_val}"
                    )
                else:
                    passed = value > min_val
                    message = (
                        f"Field '{field_name}' value {value} > {min_val}"
                        if passed
                        else f"Field '{field_name}' value {value} <= {min_val}"
                    )
                return passed, message

        elif operator == Operator.LESS_THAN:
            if max_val is not None:
                if inclusive:
                    passed = value <= max_val
                    message = (
                        f"Field '{field_name}' value {value} <= {max_val}"
                        if passed
                        else f"Field '{field_name}' value {value} > {max_val}"
                    )
                else:
                    passed = value < max_val
                    message = (
                        f"Field '{field_name}' value {value} < {max_val}"
                        if passed
                        else f"Field '{field_name}' value {value} >= {max_val}"
                    )
                return passed, message

        elif operator == Operator.EQUALS:
            if min_val is not None:
                passed = value == min_val
                message = (
                    f"Field '{field_name}' value {value} equals {min_val}"
                    if passed
                    else f"Field '{field_name}' value {value} does not equal {min_val}"
                )
                return passed, message

        # Default: always pass if no constraints
        return True, f"Field '{field_name}' has no range constraints"

    def supports_field_type(self, field_type: str) -> bool:
        """
        Check if validator supports this field type

        Args:
            field_type: Type of field

        Returns:
            True for numeric types
        """
        return field_type in ["number", "integer", "decimal", "float"]
