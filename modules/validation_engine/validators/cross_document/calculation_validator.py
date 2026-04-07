"""Calculation validator for computed field verification"""

import ast
from typing import Dict, Any, List, Optional
from decimal import Decimal
from ...core.base import IValidator, ValidationResult, ValidationContext
from ...validators.validator_registry import ValidatorRegistry
from ...utils.constants import ValidatorType, Severity
from shared.utils.logger import get_logger

logger = get_logger(__name__)


@ValidatorRegistry.register("calculation_validator")
class CalculationValidator(IValidator):
    """
    Validates calculated fields by recomputing and comparing

    Critical for BOE duty calculation verification.

    Config:
        calculations: List of calculation validations
            - name: Calculation name
            - formula: Formula string (e.g., "unit_price * quantity * duty_rate")
            - fields: Dict mapping variable names to field paths
                Example:
                    unit_price: "invoice.unit_price"
                    quantity: "packing_list.quantity"
                    duty_rate: "bill_of_entry.duty_rate"
            - target: Target field path (calculated result)
            - tolerance_percent: Tolerance for comparison (default: 0.5%)
            - description: Human-readable description

    Example config:
        calculations:
          - name: "duty_amount"
            formula: "unit_price * quantity * duty_rate"
            fields:
              unit_price: "invoice.unit_price"
              quantity: "packing_list.quantity"
              duty_rate: "bill_of_entry.duty_rate"
            target: "bill_of_entry.duty_amount"
            tolerance_percent: 0.5
            description: "Duty amount calculation"
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.validator_type = ValidatorType.CROSS_DOCUMENT
        self.validator_name = "calculation_validator"

        self.calculations = config.get("calculations", [])

        logger.debug(
            f"CalculationValidator initialized with {len(self.calculations)} calculations"
        )

    async def validate(
        self,
        source_data: Dict[str, Any],
        target_data: Optional[Dict[str, Any]],
        context: ValidationContext
    ) -> List[ValidationResult]:
        """
        Validate calculated fields

        Args:
            source_data: Source document data
            target_data: Target document data (optional)
            context: Validation context

        Returns:
            List of validation results
        """
        results = []

        for calc_config in self.calculations:
            calc_name = calc_config.get("name")
            formula = calc_config.get("formula")
            fields_config = calc_config.get("fields", {})
            target_path = calc_config.get("target")
            tolerance_percent = calc_config.get("tolerance_percent", 0.5)
            description = calc_config.get("description", calc_name)

            try:
                # Gather field values from all documents
                field_values = {}
                missing_fields = []

                for var_name, field_path in fields_config.items():
                    value = self._get_field_from_documents(
                        field_path=field_path,
                        context=context
                    )

                    if value is None:
                        missing_fields.append(field_path)
                    else:
                        try:
                            field_values[var_name] = self._to_numeric(value)
                        except (ValueError, TypeError) as e:
                            logger.error(
                                f"Cannot convert '{field_path}' value '{value}' to numeric: {e}"
                            )
                            missing_fields.append(field_path)

                # Check for missing fields
                if missing_fields:
                    results.append(ValidationResult(
                        validator_name=self.validator_name,
                        validator_type=self.validator_type,
                        field_name=calc_name,
                        source_value=None,
                        target_value=None,
                        passed=False,
                        confidence=1.0,
                        severity=self.get_severity({}),
                        message=f"Calculation '{calc_name}' missing fields: {', '.join(missing_fields)}"
                    ))
                    continue

                # Calculate expected value
                try:
                    calculated_value = self._evaluate_formula(formula, field_values)
                except Exception as e:
                    results.append(ValidationResult(
                        validator_name=self.validator_name,
                        validator_type=self.validator_type,
                        field_name=calc_name,
                        source_value=None,
                        target_value=None,
                        passed=False,
                        confidence=1.0,
                        severity=self.get_severity({}),
                        message=f"Calculation '{calc_name}' formula error: {str(e)}"
                    ))
                    continue

                # Get actual target value
                target_value = self._get_field_from_documents(
                    field_path=target_path,
                    context=context
                )

                if target_value is None:
                    # Target field absent — skip comparison rather than fail.
                    # Record the calculated value as informational so it is visible
                    # in the report but doesn't count as a discrepancy.
                    results.append(ValidationResult(
                        validator_name=self.validator_name,
                        validator_type=self.validator_type,
                        field_name=calc_name,
                        source_value=calculated_value,
                        target_value=None,
                        passed=True,
                        confidence=0.5,
                        severity="info",
                        message=(
                            f"Calculation '{calc_name}' = {calculated_value} "
                            f"(target '{target_path}' not present — cannot verify)"
                        )
                    ))
                    continue

                try:
                    target_numeric = self._to_numeric(target_value)
                except (ValueError, TypeError) as e:
                    results.append(ValidationResult(
                        validator_name=self.validator_name,
                        validator_type=self.validator_type,
                        field_name=calc_name,
                        source_value=calculated_value,
                        target_value=target_value,
                        passed=False,
                        confidence=1.0,
                        severity=self.get_severity({}),
                        message=f"Calculation '{calc_name}' target value '{target_value}' is not numeric"
                    ))
                    continue

                # Compare with tolerance
                difference = abs(calculated_value - target_numeric)
                tolerance_value = abs(target_numeric * Decimal(str(tolerance_percent / 100)))
                passed = difference <= tolerance_value

                # Calculate percentage difference
                pct_diff = float(difference / target_numeric * 100) if target_numeric != 0 else 0

                # Calculate confidence
                confidence = self._calculate_confidence(difference, tolerance_value, passed)

                result = ValidationResult(
                    validator_name=self.validator_name,
                    validator_type=self.validator_type,
                    field_name=calc_name,
                    source_value=float(calculated_value),
                    target_value=float(target_numeric),
                    expected_value={
                        "formula": formula,
                        "fields": {k: float(v) for k, v in field_values.items()},
                        "calculated": float(calculated_value)
                    },
                    passed=passed,
                    confidence=confidence,
                    severity=self.get_severity({}) if not passed else Severity.INFO,
                    message=(
                        f"Calculation '{description}' correct: {calculated_value} ≈ {target_numeric} "
                        f"(diff: {pct_diff:.2f}%)"
                        if passed
                        else f"Calculation '{description}' error: expected {calculated_value}, "
                             f"got {target_numeric} (diff: {pct_diff:.2f}%, tolerance: {tolerance_percent}%)"
                    ),
                    discrepancy={
                        "formula": formula,
                        "calculated_value": float(calculated_value),
                        "actual_value": float(target_numeric),
                        "difference": float(difference),
                        "percentage_diff": pct_diff,
                        "tolerance_percent": tolerance_percent,
                        "field_values": {k: float(v) for k, v in field_values.items()}
                    } if not passed else None
                )

                results.append(result)

                logger.debug(
                    f"Calculation '{calc_name}': {calculated_value} vs {target_numeric} "
                    f"(diff: {pct_diff:.2f}%) = {'PASS' if passed else 'FAIL'}"
                )

            except Exception as e:
                logger.error(f"Calculation validation error for '{calc_name}': {str(e)}")
                results.append(ValidationResult(
                    validator_name=self.validator_name,
                    validator_type=self.validator_type,
                    field_name=calc_name,
                    source_value=None,
                    target_value=None,
                    passed=False,
                    confidence=0.0,
                    severity=self.get_severity({}),
                    message=f"Calculation '{calc_name}' validation error: {str(e)}"
                ))

        return results

    def _get_field_from_documents(
        self,
        field_path: str,
        context: ValidationContext
    ) -> Any:
        """
        Get field value from any document in context

        Args:
            field_path: Field path (e.g., "invoice.unit_price")
            context: Validation context

        Returns:
            Field value or None if not found
        """
        parts = field_path.split(".")
        if len(parts) < 2:
            return None

        doc_type = parts[0]
        field_parts = parts[1:]

        # Get document data
        doc_data = context.documents.get(doc_type)
        if not doc_data:
            return None

        # Navigate to field
        value = doc_data
        for part in field_parts:
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

        Handles US format (189,000.00), European format (189.000,00 kg),
        and integer-with-European-thousands (7.560 → 7560).
        """
        import re as _re

        if isinstance(value, (int, float, Decimal)):
            return Decimal(str(value))

        if isinstance(value, dict):
            value = value.get("value", "")

        if isinstance(value, str):
            raw = value.strip()
            raw = _re.sub(r'[^0-9.,\-]+$', '', raw).strip()
            raw = _re.sub(r'^[^0-9\-]+', '', raw).strip()
            if not raw:
                raise ValueError(f"No numeric content in: {value!r}")
            dot_count = raw.count('.')
            comma_count = raw.count(',')
            if dot_count > 0 and comma_count > 0:
                last_dot = raw.rindex('.')
                last_comma = raw.rindex(',')
                if last_comma > last_dot:
                    raw = raw.replace('.', '').replace(',', '.')
                else:
                    raw = raw.replace(',', '')
            elif comma_count > 0 and dot_count == 0:
                digits_after = len(raw) - raw.rindex(',') - 1
                if comma_count == 1 and digits_after in (1, 2):
                    raw = raw.replace(',', '.')
                else:
                    raw = raw.replace(',', '')
            elif dot_count > 0 and comma_count == 0:
                if dot_count == 1 and len(raw) - raw.rindex('.') - 1 == 3:
                    raw = raw.replace('.', '')
                elif dot_count > 1:
                    raw = raw.replace('.', '')
            return Decimal(raw)

        raise ValueError(f"Cannot convert {type(value)} to numeric")

    def _evaluate_formula(
        self,
        formula: str,
        variables: Dict[str, Decimal]
    ) -> Decimal:
        """
        Safely evaluate mathematical formula using AST (correct operator precedence).

        Supports: +, -, *, /, ** and parentheses.
        No attribute access, function calls, or subscripts permitted.

        Args:
            formula: Formula string (e.g., "unit_price * quantity + freight")
            variables: Variable values (Decimal)

        Returns:
            Calculated result as Decimal

        Raises:
            ValueError: If formula contains unsupported syntax or unknown variables
        """
        _ALLOWED_BIN_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
        _ALLOWED_UNARY_OPS = (ast.UAdd, ast.USub)

        def _eval(node: ast.expr) -> Decimal:
            if isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)):
                    return Decimal(str(node.value))
                raise ValueError(f"Unsupported constant type: {type(node.value)}")

            if isinstance(node, ast.Name):
                if node.id not in variables:
                    raise ValueError(f"Unknown variable: {node.id}")
                return variables[node.id]

            if isinstance(node, ast.BinOp):
                if not isinstance(node.op, _ALLOWED_BIN_OPS):
                    raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
                left = _eval(node.left)
                right = _eval(node.right)
                if isinstance(node.op, ast.Add):
                    return left + right
                if isinstance(node.op, ast.Sub):
                    return left - right
                if isinstance(node.op, ast.Mult):
                    return left * right
                if isinstance(node.op, ast.Div):
                    if right == 0:
                        raise ValueError("Division by zero in formula")
                    return left / right
                if isinstance(node.op, ast.Pow):
                    return left ** right

            if isinstance(node, ast.UnaryOp):
                if not isinstance(node.op, _ALLOWED_UNARY_OPS):
                    raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
                operand = _eval(node.operand)
                return +operand if isinstance(node.op, ast.UAdd) else -operand

            raise ValueError(f"Unsupported expression node: {type(node).__name__}")

        try:
            tree = ast.parse(formula, mode="eval")
        except SyntaxError as e:
            raise ValueError(f"Invalid formula syntax: {formula!r} — {e}")

        return _eval(tree.body)

    def _calculate_confidence(
        self,
        difference: Decimal,
        tolerance: Decimal,
        passed: bool
    ) -> float:
        """Calculate confidence score based on calculation accuracy"""
        if passed:
            if tolerance == 0:
                return 1.0

            ratio = abs(difference) / tolerance
            confidence = max(0.7, 1.0 - (ratio * 0.3))
            return float(confidence)
        else:
            if tolerance == 0:
                return 0.3

            ratio = abs(difference) / tolerance
            if ratio < 2:
                confidence = 0.5
            elif ratio < 5:
                confidence = 0.3
            else:
                confidence = 0.1

            return confidence

    def supports_field_type(self, field_type: str) -> bool:
        """Check if validator supports this field type"""
        return field_type in ["number", "integer", "decimal", "float", "calculated"]
