"""Tolerance-based validator for numeric comparisons"""

from typing import Dict, Any, List, Optional, Union
from decimal import Decimal
from ...core.base import IValidator, ValidationResult, ValidationContext
from ...validators.validator_registry import ValidatorRegistry
from ...utils.constants import ValidatorType, Severity, ToleranceType
from shared.utils.logger import get_logger

logger = get_logger(__name__)


@ValidatorRegistry.register("tolerance_validator")
class ToleranceValidator(IValidator):
    """
    Validates numeric fields with configurable tolerance

    Critical for BOE weight matching where exact matches are rare due to
    rounding, measurement variations, and unit conversions.

    Config:
        tolerance_type: Type of tolerance (default: "percentage")
            - "percentage": Tolerance as percentage of target value
            - "absolute": Fixed tolerance value
            - "relative": Tolerance relative to average

        default_tolerance: Default tolerance value
            - For percentage: 1.0 = 1%
            - For absolute: Fixed amount (e.g., 10)

        per_session_override: Allow session-specific tolerance (default: true)

        validations: List of field validations
            - name: Validation name
            - source: Source field path
            - target: Target field path
            - tolerance_percent: Tolerance percentage (overrides default)
            - tolerance_absolute: Absolute tolerance (overrides default)
            - operator: Comparison operator (default: "equals")
                - "equals": Values should be equal within tolerance
                - "less_than": Source should be less than target
                - "greater_than": Source should be greater than target

    Example config:
        tolerance_type: "percentage"
        default_tolerance: 1.0
        per_session_override: true

        validations:
          - name: "net_weight_check"
            source: "invoice.net_weight"
            target: "bill_of_entry.net_weight"
            tolerance_percent: 1.0

          - name: "gross_weight_check"
            source: "packing_list.gross_weight"
            target: "bill_of_entry.gross_weight"
            tolerance_percent: 1.0
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.validator_type = ValidatorType.STATISTICAL
        self.validator_name = "tolerance_validator"

        self.tolerance_type = config.get("tolerance_type", ToleranceType.PERCENTAGE)
        self.default_tolerance = config.get("default_tolerance", 1.0)
        self.per_session_override = config.get("per_session_override", True)
        self.validations = config.get("validations", [])

        logger.debug(
            f"ToleranceValidator initialized with {len(self.validations)} validations, "
            f"default tolerance: {self.default_tolerance}%"
        )

    async def validate(
        self,
        source_data: Dict[str, Any],
        target_data: Optional[Dict[str, Any]],
        context: ValidationContext
    ) -> List[ValidationResult]:
        """
        Validate numeric fields with tolerance

        Args:
            source_data: Source document data
            target_data: Target document data
            context: Validation context

        Returns:
            List of validation results
        """
        results = []

        if not target_data:
            logger.warning("No target data provided for tolerance validation")
            return results

        for validation_config in self.validations:
            validation_name = validation_config.get("name")
            source_path = validation_config.get("source")
            target_path = validation_config.get("target")
            tolerance_percent = validation_config.get("tolerance_percent")
            tolerance_absolute = validation_config.get("tolerance_absolute")
            operator = validation_config.get("operator", "equals")

            # Check for session-level tolerance override
            if self.per_session_override:
                override_key = f"{validation_name}_tolerance"
                if override_key in context.tolerance_overrides:
                    tolerance_percent = context.tolerance_overrides[override_key]
                    logger.debug(
                        f"Using session override for {validation_name}: "
                        f"{tolerance_percent}%"
                    )

            # Get field values
            source_value = self._get_nested_value(source_data, source_path)
            target_value = self._get_nested_value(target_data, target_path)

            # Extract field names
            source_field = source_path.split(".")[-1] if "." in source_path else source_path
            target_field = target_path.split(".")[-1] if "." in target_path else target_path

            # Check if fields exist
            if source_value is None or target_value is None:
                results.append(ValidationResult(
                    validator_name=self.validator_name,
                    validator_type=self.validator_type,
                    field_name=source_field,
                    source_value=source_value,
                    target_value=target_value,
                    passed=False,
                    confidence=1.0,
                    severity=self.get_severity({}),
                    message=f"Missing values for tolerance comparison: {source_path} or {target_path}"
                ))
                continue

            # Convert to numeric
            try:
                source_numeric = self._to_numeric(source_value)
                target_numeric = self._to_numeric(target_value)
            except Exception as e:
                results.append(ValidationResult(
                    validator_name=self.validator_name,
                    validator_type=self.validator_type,
                    field_name=source_field,
                    source_value=source_value,
                    target_value=target_value,
                    passed=False,
                    confidence=1.0,
                    severity=self.get_severity({}),
                    message=f"Non-numeric values in tolerance comparison: {str(e)}"
                ))
                continue

            # Determine tolerance
            if tolerance_percent is not None:
                tolerance = tolerance_percent
                tolerance_type = ToleranceType.PERCENTAGE
            elif tolerance_absolute is not None:
                tolerance = tolerance_absolute
                tolerance_type = ToleranceType.ABSOLUTE
            else:
                tolerance = self.default_tolerance
                tolerance_type = self.tolerance_type

            # Perform tolerance validation
            passed, difference, tolerance_value, message = self._validate_tolerance(
                source=source_numeric,
                target=target_numeric,
                tolerance=tolerance,
                tolerance_type=tolerance_type,
                operator=operator,
                field_name=source_field
            )

            # Calculate confidence based on how close values are
            confidence = self._calculate_confidence(
                difference=difference,
                tolerance=tolerance_value,
                passed=passed
            )

            result = ValidationResult(
                validator_name=self.validator_name,
                validator_type=self.validator_type,
                field_name=source_field,
                source_document=source_path.split(".")[0] if "." in source_path else None,
                target_document=target_path.split(".")[0] if "." in target_path else None,
                source_value=source_value,
                target_value=target_value,
                expected_value={
                    "tolerance": tolerance,
                    "tolerance_type": tolerance_type
                },
                passed=passed,
                confidence=confidence,
                severity=self.get_severity({}) if not passed else Severity.INFO,
                message=message,
                discrepancy={
                    "source_path": source_path,
                    "target_path": target_path,
                    "difference": float(difference),
                    "tolerance": tolerance,
                    "tolerance_type": tolerance_type,
                    "percentage_diff": float(abs(difference) / target_numeric * 100) if target_numeric != 0 else 0
                } if not passed else None
            )

            results.append(result)

            logger.debug(
                f"Tolerance validation '{validation_name}': {source_value} vs {target_value} "
                f"(diff: {difference}, tolerance: {tolerance_value}) = "
                f"{'PASS' if passed else 'FAIL'}"
            )

        return results

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get value from nested dictionary using dot notation"""
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

    def _to_numeric(self, value: Any) -> Decimal:
        """
        Convert value to Decimal for precise calculations.

        Handles:
        - US format: "189,000.000" (comma=thousands, dot=decimal)
        - European format: "189.000,00 kg" (dot=thousands, comma=decimal)
        - Integer-with-European-thousands: "7.560" → 7560
        - Unit suffixes stripped: "189.000,00 kg" → 189000.00
        """
        import re as _re

        if isinstance(value, (int, float, Decimal)):
            return Decimal(str(value))

        # Unwrap field-data dicts: {"value": "189,000.000", "confidence": ...}
        if isinstance(value, dict):
            value = value.get("value", "")

        if isinstance(value, str):
            # Extract the numeric portion (strip leading/trailing spaces and unit suffixes)
            raw = value.strip()
            # Remove trailing non-numeric characters (units like "kg", "BAG", "MT", etc.)
            raw = _re.sub(r'[^0-9.,\-]+$', '', raw).strip()
            raw = _re.sub(r'^[^0-9\-]+', '', raw).strip()

            if not raw:
                raise ValueError(f"No numeric content in: {value!r}")

            dot_count = raw.count('.')
            comma_count = raw.count(',')

            if dot_count > 0 and comma_count > 0:
                # Both present — determine which is decimal separator
                last_dot = raw.rindex('.')
                last_comma = raw.rindex(',')
                if last_comma > last_dot:
                    # European: dot=thousands, comma=decimal → "189.000,00"
                    raw = raw.replace('.', '').replace(',', '.')
                else:
                    # US: comma=thousands, dot=decimal → "189,000.000"
                    raw = raw.replace(',', '')
            elif comma_count > 0 and dot_count == 0:
                # Only commas — determine whether decimal or thousands separator
                digits_after = len(raw) - raw.rindex(',') - 1
                if comma_count == 1 and digits_after in (1, 2):
                    # 1-2 digits after single comma → decimal separator (e.g. "7,5" or "9,50")
                    raw = raw.replace(',', '.')
                else:
                    # 3 digits after comma OR multiple commas → thousands separators
                    # e.g. "7,560" → 7560, "1,000,000" → 1000000
                    raw = raw.replace(',', '')
            elif dot_count > 0 and comma_count == 0:
                # Only dots
                if dot_count == 1 and len(raw) - raw.rindex('.') - 1 == 3:
                    # Single dot with exactly 3 trailing digits → European thousands
                    # e.g. "7.560" → 7560, "189.000" → 189000
                    raw = raw.replace('.', '')
                elif dot_count > 1:
                    # Multiple dots → all are thousands separators → remove
                    raw = raw.replace('.', '')
                # else: single dot, not 3 decimal digits → regular decimal, keep as-is

            return Decimal(raw)

        raise ValueError(f"Cannot convert {type(value)} to numeric")

    def _validate_tolerance(
        self,
        source: Decimal,
        target: Decimal,
        tolerance: float,
        tolerance_type: str,
        operator: str,
        field_name: str
    ) -> tuple[bool, Decimal, Decimal, str]:
        """
        Validate values within tolerance

        Returns:
            Tuple of (passed, difference, tolerance_value, message)
        """
        difference = source - target

        # Calculate tolerance value
        if tolerance_type == ToleranceType.PERCENTAGE:
            tolerance_value = abs(target * Decimal(str(tolerance / 100)))
        elif tolerance_type == ToleranceType.ABSOLUTE:
            tolerance_value = Decimal(str(tolerance))
        else:  # RELATIVE
            avg = (source + target) / 2
            tolerance_value = abs(avg * Decimal(str(tolerance / 100)))

        # Validate based on operator
        if operator == "equals":
            passed = abs(difference) <= tolerance_value
            message = (
                f"Field '{field_name}': {source} ≈ {target} (within ±{tolerance}% tolerance)"
                if passed
                else f"Field '{field_name}': {source} ≠ {target} (difference {difference} exceeds ±{tolerance}% tolerance)"
            )

        elif operator == "less_than":
            passed = source < target and abs(difference) <= tolerance_value
            message = (
                f"Field '{field_name}': {source} < {target} (within tolerance)"
                if passed
                else f"Field '{field_name}': {source} not less than {target} (within tolerance)"
            )

        elif operator == "greater_than":
            passed = source > target and abs(difference) <= tolerance_value
            message = (
                f"Field '{field_name}': {source} > {target} (within tolerance)"
                if passed
                else f"Field '{field_name}': {source} not greater than {target} (within tolerance)"
            )

        else:
            passed = abs(difference) <= tolerance_value
            message = f"Field '{field_name}': comparison with tolerance"

        return passed, difference, tolerance_value, message

    def _calculate_confidence(
        self,
        difference: Decimal,
        tolerance: Decimal,
        passed: bool
    ) -> float:
        """
        Calculate confidence score based on how close values are

        Args:
            difference: Actual difference between values
            tolerance: Allowed tolerance
            passed: Whether validation passed

        Returns:
            Confidence score (0.0 - 1.0)
        """
        if passed:
            if tolerance == 0:
                return 1.0

            # Confidence decreases as difference approaches tolerance
            ratio = float(abs(difference) / tolerance)
            confidence = max(0.7, 1.0 - (ratio * 0.3))
            return float(confidence)
        else:
            # Failed validation - confidence based on how far outside tolerance
            if tolerance == 0:
                return 0.5

            ratio = abs(difference) / tolerance
            if ratio < 1.2:  # Just barely outside tolerance
                confidence = 0.6
            elif ratio < 1.5:
                confidence = 0.4
            else:
                confidence = 0.2

            return confidence

    def supports_field_type(self, field_type: str) -> bool:
        """Check if validator supports this field type"""
        return field_type in ["number", "integer", "decimal", "float"]
