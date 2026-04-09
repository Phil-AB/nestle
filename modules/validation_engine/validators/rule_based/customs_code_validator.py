"""
Customs Code Validator

Validates Amount Payable and duty/VAT calculations based on Ghana customs codes:
- 40E68: Full VAT payment (5% × Customs Value)
- 40V02: VAT exempted (Amount Payable = 0.00, Amount Exempted calculated)
- 40U01: Import Duty exempted
- 40W01: Import Duty exempted, but taxes payable

Based on Ghana Customs ICUMS system validation rules.
"""

from typing import Dict, Any, List, Optional
from decimal import Decimal, ROUND_HALF_UP
from ...core.base import IValidator, ValidationResult, ValidationContext
from ...validators.validator_registry import ValidatorRegistry
from ...utils.constants import ValidatorType, Severity, DiscrepancyCategory
from shared.utils.logger import get_logger

logger = get_logger(__name__)


@ValidatorRegistry.register("customs_code_validator")
class CustomsCodeValidator(IValidator):
    """
    Validates customs code-specific rules for Ghana BOE processing

    Handles customs codes and their specific calculation rules:

    40E68 - Full VAT Payment:
        - Import VAT must be paid in full
        - Amount Payable = VAT Rate (5%) × Customs Value
        - No exemptions

    40V02 - VAT Exempted:
        - VAT is exempted for payment later
        - Amount Payable = 0.00
        - Amount Exempted = VAT Rate × Customs Value
        - No concession amount

    40U01 - Duty Exempted:
        - Import Duty is fully exempted
        - Only taxes payable

    40W01 - Duty Exempted with Taxes:
        - Import Duty is exempted
        - However, taxes (VAT, etc.) are still payable

    Config:
        customs_codes: Configuration for each customs code
            - code: Customs code (e.g., "40E68")
            - type: Code type (full_vat, vat_exempt, duty_exempt, etc.)
            - vat_rate: VAT rate (default 0.05 for 5%)
            - duty_exempted: Whether duty is exempted
            - vat_exempted: Whether VAT is exempted
            - taxes_payable: Whether taxes must be paid

        validations: List of field validations
            - customs_value_field: Field containing customs value
            - amount_payable_field: Field to validate for amount payable
            - amount_exempted_field: Field for exempted amount
            - duty_amount_field: Field for duty amount
            - vat_amount_field: Field for VAT amount
            - customs_code_field: Field containing customs code

    Example config:
        customs_codes:
          40E68:
            type: "full_vat_payment"
            vat_rate: 0.05
            duty_exempted: false
            vat_exempted: false

          40V02:
            type: "vat_exempted"
            vat_rate: 0.05
            duty_exempted: false
            vat_exempted: true

        validations:
          - customs_value_field: "bill_of_entry.customs_value"
            amount_payable_field: "bill_of_entry.amount_payable"
            amount_exempted_field: "bill_of_entry.amount_exempted"
            customs_code_field: "bill_of_entry.customs_code"
    """

    # Default customs code configurations
    DEFAULT_CUSTOMS_CODES = {
        "40E68": {
            "type": "full_vat_payment",
            "description": "Full VAT payment required",
            "vat_rate": Decimal("0.05"),  # 5%
            "duty_exempted": False,
            "vat_exempted": False,
            "taxes_payable": True,
            "formula": "amount_payable = vat_rate * customs_value"
        },
        "40V02": {
            "type": "vat_exempted",
            "description": "VAT exempted for later payment",
            "vat_rate": Decimal("0.05"),  # 5%
            "duty_exempted": False,
            "vat_exempted": True,
            "taxes_payable": False,
            "formula": "amount_payable = 0.00; amount_exempted = vat_rate * customs_value"
        },
        "40U01": {
            "type": "duty_exempted",
            "description": "Import duty fully exempted",
            "vat_rate": Decimal("0.05"),
            "duty_exempted": True,
            "vat_exempted": False,
            "taxes_payable": True,
            "formula": "duty_amount = 0.00"
        },
        "40W01": {
            "type": "duty_exempted_tax_payable",
            "description": "Import duty exempted but taxes payable",
            "vat_rate": Decimal("0.05"),
            "duty_exempted": True,
            "vat_exempted": False,
            "taxes_payable": True,
            "formula": "duty_amount = 0.00; vat payable"
        }
    }

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.validator_type = ValidatorType.RULE_BASED
        self.validator_name = "customs_code_validator"

        # Load customs code configurations (merge with defaults)
        config_codes = config.get("customs_codes", {})
        self.customs_codes = {**self.DEFAULT_CUSTOMS_CODES}

        # Merge user-provided codes
        for code, code_config in config_codes.items():
            if code in self.customs_codes:
                self.customs_codes[code].update(code_config)
            else:
                self.customs_codes[code] = code_config

        # Convert string decimals to Decimal
        for code_config in self.customs_codes.values():
            if "vat_rate" in code_config and not isinstance(code_config["vat_rate"], Decimal):
                code_config["vat_rate"] = Decimal(str(code_config["vat_rate"]))

        # Get validations
        self.validations = config.get("validations", [])

        # Tolerance for amount comparisons (default 0.01 for rounding)
        self.tolerance = Decimal(str(config.get("tolerance", "0.01")))

        # Whether each code requires an ETLS approval number when duty = 0
        for code, code_cfg in self.customs_codes.items():
            if "require_etls_approval" not in code_cfg:
                code_cfg["require_etls_approval"] = False

        logger.info(
            f"CustomsCodeValidator initialized with {len(self.customs_codes)} customs codes, "
            f"{len(self.validations)} validations"
        )

    async def validate(
        self,
        source_data: Dict[str, Any],
        target_data: Optional[Dict[str, Any]],
        context: ValidationContext
    ) -> List[ValidationResult]:
        """
        Validate customs code-specific rules

        Args:
            source_data: BOE document data
            target_data: Not used for customs code validation
            context: Validation context

        Returns:
            List of validation results
        """
        results = []

        for validation_config in self.validations:
            # Extract field paths
            customs_value_field = validation_config.get("customs_value_field")
            amount_payable_field = validation_config.get("amount_payable_field")
            amount_exempted_field = validation_config.get("amount_exempted_field")
            duty_amount_field = validation_config.get("duty_amount_field")
            vat_amount_field = validation_config.get("vat_amount_field")
            customs_code_field = validation_config.get("customs_code_field")
            etls_approval_field = validation_config.get("etls_approval_field")

            # Get values from documents
            customs_code = self._get_field_from_documents(customs_code_field, context)
            customs_value = self._get_field_from_documents(customs_value_field, context)
            actual_amount_payable = self._get_field_from_documents(amount_payable_field, context)
            actual_amount_exempted = self._get_field_from_documents(amount_exempted_field, context)
            actual_duty_amount = self._get_field_from_documents(duty_amount_field, context)
            actual_vat_amount = self._get_field_from_documents(vat_amount_field, context)
            etls_approval_number = self._get_field_from_documents(etls_approval_field, context) \
                if etls_approval_field else None

            # Validate customs code exists
            if not customs_code:
                results.append(self._create_result(
                    field_name="customs_code",
                    passed=False,
                    message="Customs code not found in BOE",
                    severity=Severity.CRITICAL,
                    source_value=None,
                    target_value=None
                ))
                continue

            # Validate customs code is recognized
            if customs_code not in self.customs_codes:
                results.append(self._create_result(
                    field_name="customs_code",
                    passed=False,
                    message=f"Unrecognized customs code: {customs_code}. Supported codes: {', '.join(self.customs_codes.keys())}",
                    severity=Severity.MAJOR,
                    source_value=customs_code,
                    target_value=None,
                    confidence=1.0
                ))
                continue

            # Get customs code configuration
            code_config = self.customs_codes[customs_code]
            logger.debug(f"Validating customs code {customs_code}: {code_config['description']}")

            # Validate based on customs code type
            if customs_code == "40E68":
                results.extend(self._validate_40E68(
                    customs_value, actual_amount_payable, code_config, customs_code_field
                ))

            elif customs_code == "40V02":
                results.extend(self._validate_40V02(
                    customs_value, actual_amount_payable, actual_amount_exempted,
                    code_config, customs_code_field
                ))

            elif customs_code == "40U01":
                results.extend(self._validate_40U01(
                    actual_duty_amount, code_config, customs_code_field
                ))
                if code_config.get("require_etls_approval"):
                    results.append(self._validate_etls_approval(
                        customs_code, etls_approval_number
                    ))

            elif customs_code == "40W01":
                results.extend(self._validate_40W01(
                    actual_duty_amount, actual_vat_amount, code_config, customs_code_field
                ))
                if code_config.get("require_etls_approval"):
                    results.append(self._validate_etls_approval(
                        customs_code, etls_approval_number
                    ))

        return results

    def _validate_40E68(
        self,
        customs_value: Optional[Any],
        actual_amount_payable: Optional[Any],
        code_config: Dict[str, Any],
        field_name: str
    ) -> List[ValidationResult]:
        """
        Validate 40E68: Full VAT payment

        Formula: Amount Payable = 5% × Customs Value
        """
        results = []

        if customs_value is None:
            results.append(self._create_result(
                field_name="customs_value",
                passed=False,
                message="Customs value required for 40E68 validation",
                severity=Severity.CRITICAL,
                source_value=None,
                target_value=None
            ))
            return results

        # Convert to Decimal
        customs_value = self._to_decimal(customs_value)
        vat_rate = code_config["vat_rate"]

        # Calculate expected amount payable
        expected_amount_payable = (customs_value * vat_rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        # Get actual amount payable
        actual_amount_payable = self._to_decimal(actual_amount_payable) if actual_amount_payable else Decimal("0")

        # Calculate difference
        difference = abs(expected_amount_payable - actual_amount_payable)

        # Validate
        passed = difference <= self.tolerance

        if passed:
            message = f"40E68: Amount Payable correct ({actual_amount_payable} = {vat_rate*100}% × {customs_value})"
            confidence = 1.0
            severity = Severity.INFO
        else:
            message = (
                f"40E68: Amount Payable incorrect. "
                f"Expected: {expected_amount_payable} ({vat_rate*100}% × {customs_value}), "
                f"Actual: {actual_amount_payable}, "
                f"Difference: {difference}"
            )
            confidence = 1.0 - min(float(difference / expected_amount_payable), 0.5) if expected_amount_payable > 0 else 0.5
            severity = Severity.CRITICAL if difference > expected_amount_payable * Decimal("0.05") else Severity.MAJOR

        results.append(self._create_result(
            field_name="amount_payable",
            passed=passed,
            message=message,
            severity=severity,
            source_value=float(actual_amount_payable),
            target_value=float(expected_amount_payable),
            confidence=confidence,
            metadata={
                "customs_code": "40E68",
                "customs_value": float(customs_value),
                "vat_rate": float(vat_rate),
                "expected": float(expected_amount_payable),
                "actual": float(actual_amount_payable),
                "difference": float(difference)
            }
        ))

        return results

    def _validate_40V02(
        self,
        customs_value: Optional[Any],
        actual_amount_payable: Optional[Any],
        actual_amount_exempted: Optional[Any],
        code_config: Dict[str, Any],
        field_name: str
    ) -> List[ValidationResult]:
        """
        Validate 40V02: VAT exempted

        Rules:
        - Amount Payable = 0.00
        - Amount Exempted = VAT Rate × Customs Value
        """
        results = []

        if customs_value is None:
            results.append(self._create_result(
                field_name="customs_value",
                passed=False,
                message="Customs value required for 40V02 validation",
                severity=Severity.CRITICAL,
                source_value=None,
                target_value=None
            ))
            return results

        # Convert to Decimal
        customs_value = self._to_decimal(customs_value)
        vat_rate = code_config["vat_rate"]

        # 1. Validate Amount Payable = 0.00
        actual_amount_payable = self._to_decimal(actual_amount_payable) if actual_amount_payable else Decimal("0")
        expected_amount_payable = Decimal("0.00")

        payable_passed = abs(actual_amount_payable - expected_amount_payable) <= self.tolerance

        results.append(self._create_result(
            field_name="amount_payable",
            passed=payable_passed,
            message=(
                f"40V02: Amount Payable correct (0.00)" if payable_passed
                else f"40V02: Amount Payable must be 0.00 for VAT exemption, got {actual_amount_payable}"
            ),
            severity=Severity.INFO if payable_passed else Severity.CRITICAL,
            source_value=float(actual_amount_payable),
            target_value=0.00,
            confidence=1.0,
            metadata={
                "customs_code": "40V02",
                "vat_exempted": True
            }
        ))

        # 2. Validate Amount Exempted = VAT Rate × Customs Value
        expected_amount_exempted = (customs_value * vat_rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        if actual_amount_exempted is None:
            # Field not extracted from BOE — report expected value as info
            # (cannot fail a validation if the field was never present in the document)
            results.append(self._create_result(
                field_name="amount_exempted",
                passed=True,
                message=(
                    f"40V02: Amount Exempted not extracted from BOE. "
                    f"Expected value based on customs_value: {expected_amount_exempted}"
                ),
                severity=Severity.INFO,
                source_value=None,
                target_value=float(expected_amount_exempted),
                confidence=0.5,
                metadata={
                    "customs_code": "40V02",
                    "customs_value": float(customs_value),
                    "vat_rate": float(vat_rate),
                    "expected_exempted": float(expected_amount_exempted)
                }
            ))
        else:
            actual_amount_exempted_dec = self._to_decimal(actual_amount_exempted)
            difference = abs(expected_amount_exempted - actual_amount_exempted_dec)
            exempted_passed = difference <= self.tolerance

            results.append(self._create_result(
                field_name="amount_exempted",
                passed=exempted_passed,
                message=(
                    f"40V02: Amount Exempted correct ({actual_amount_exempted_dec} = {vat_rate*100}% × {customs_value})"
                    if exempted_passed
                    else f"40V02: Amount Exempted incorrect. Expected: {expected_amount_exempted}, Actual: {actual_amount_exempted_dec}"
                ),
                severity=Severity.INFO if exempted_passed else Severity.MAJOR,
                source_value=float(actual_amount_exempted_dec),
                target_value=float(expected_amount_exempted),
                confidence=1.0 if exempted_passed else 0.7,
                metadata={
                    "customs_code": "40V02",
                    "customs_value": float(customs_value),
                    "vat_rate": float(vat_rate),
                    "expected_exempted": float(expected_amount_exempted)
                }
            ))

        return results

    def _validate_40U01(
        self,
        actual_duty_amount: Optional[Any],
        code_config: Dict[str, Any],
        field_name: str
    ) -> List[ValidationResult]:
        """
        Validate 40U01: Import Duty exempted

        Rule: Duty Amount = 0.00
        """
        results = []

        actual_duty_amount = self._to_decimal(actual_duty_amount) if actual_duty_amount else Decimal("0")
        expected_duty_amount = Decimal("0.00")

        passed = abs(actual_duty_amount - expected_duty_amount) <= self.tolerance

        results.append(self._create_result(
            field_name="duty_amount",
            passed=passed,
            message=(
                f"40U01: Duty Amount correct (0.00 - duty exempted)" if passed
                else f"40U01: Duty Amount must be 0.00 for duty exemption, got {actual_duty_amount}"
            ),
            severity=Severity.INFO if passed else Severity.CRITICAL,
            source_value=float(actual_duty_amount),
            target_value=0.00,
            confidence=1.0,
            metadata={
                "customs_code": "40U01",
                "duty_exempted": True
            }
        ))

        return results

    def _validate_40W01(
        self,
        actual_duty_amount: Optional[Any],
        actual_vat_amount: Optional[Any],
        code_config: Dict[str, Any],
        field_name: str
    ) -> List[ValidationResult]:
        """
        Validate 40W01: Import Duty exempted, but taxes payable

        Rules:
        - Duty Amount = 0.00
        - VAT must be payable (> 0)
        """
        results = []

        # 1. Validate Duty = 0.00
        actual_duty_amount = self._to_decimal(actual_duty_amount) if actual_duty_amount else Decimal("0")
        expected_duty_amount = Decimal("0.00")

        duty_passed = abs(actual_duty_amount - expected_duty_amount) <= self.tolerance

        results.append(self._create_result(
            field_name="duty_amount",
            passed=duty_passed,
            message=(
                f"40W01: Duty Amount correct (0.00 - duty exempted)" if duty_passed
                else f"40W01: Duty Amount must be 0.00 for duty exemption, got {actual_duty_amount}"
            ),
            severity=Severity.INFO if duty_passed else Severity.CRITICAL,
            source_value=float(actual_duty_amount),
            target_value=0.00,
            confidence=1.0,
            metadata={
                "customs_code": "40W01",
                "duty_exempted": True,
                "taxes_payable": True
            }
        ))

        # 2. Validate VAT is payable (informational check)
        if actual_vat_amount:
            actual_vat_amount = self._to_decimal(actual_vat_amount)
            vat_payable = actual_vat_amount > Decimal("0")

            results.append(self._create_result(
                field_name="vat_amount",
                passed=vat_payable,
                message=(
                    f"40W01: VAT payable ({actual_vat_amount})" if vat_payable
                    else f"40W01: Warning - VAT should be payable for this customs code"
                ),
                severity=Severity.INFO if vat_payable else Severity.MINOR,
                source_value=float(actual_vat_amount),
                target_value=None,
                confidence=0.8,
                metadata={
                    "customs_code": "40W01",
                    "taxes_payable": True
                }
            ))

        return results

    def _validate_etls_approval(
        self,
        customs_code: str,
        etls_approval_number: Optional[Any]
    ) -> ValidationResult:
        """
        Validate that an ETLS Approval Number is present when duty is exempted.

        ECOWAS Trade Liberalisation Scheme (ETLS) allows zero import duty on
        qualifying goods from ECOWAS member states. Ghana Customs requires the
        ETLS Approval Number to be referenced on the BOE whenever duty = 0 under
        codes 40U01 or 40W01.
        """
        has_approval = bool(etls_approval_number and str(etls_approval_number).strip())

        if has_approval:
            return self._create_result(
                field_name="etls_approval_number",
                passed=True,
                message=f"{customs_code}: ETLS Approval Number present ({etls_approval_number})",
                severity=Severity.INFO,
                source_value=str(etls_approval_number),
                target_value=None,
                confidence=1.0,
                metadata={"customs_code": customs_code}
            )
        else:
            return self._create_result(
                field_name="etls_approval_number",
                passed=False,
                message=(
                    f"{customs_code}: Import duty is zero/exempted but no ETLS Approval Number "
                    f"found on BOE. An ETLS Approval Number is required to justify zero duty."
                ),
                severity=Severity.MAJOR,
                source_value=None,
                target_value="ETLS Approval Number required",
                confidence=1.0,
                metadata={"customs_code": customs_code}
            )

    def _get_field_from_documents(self, field_path: str, context: ValidationContext) -> Any:
        """
        Get field value from context documents using dot notation

        Args:
            field_path: Field path like "bill_of_entry.customs_value"
            context: Validation context

        Returns:
            Field value or None
        """
        if not field_path:
            return None

        parts = field_path.split(".")
        if len(parts) < 2:
            return None

        doc_type = parts[0]
        field_name = ".".join(parts[1:])

        # Try normalized data first
        if doc_type in context.normalized_data:
            return self._get_nested_value(context.normalized_data[doc_type], field_name)

        # Fallback to original documents
        if doc_type in context.documents:
            return self._get_nested_value(context.documents[doc_type], field_name)

        return None

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get nested value using dot notation"""
        try:
            value = data
            for key in path.split("."):
                if isinstance(value, dict):
                    value = value.get(key)
                else:
                    return None
                if value is None:
                    return None
            return value
        except (KeyError, TypeError, AttributeError):
            return None

    def _to_decimal(self, value: Any) -> Decimal:
        """Convert value to Decimal for precise calculations"""
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        if isinstance(value, str):
            try:
                return Decimal(value)
            except:
                return Decimal("0")
        return Decimal("0")

    def _create_result(
        self,
        field_name: str,
        passed: bool,
        message: str,
        severity: str,
        source_value: Any,
        target_value: Any,
        confidence: float = 1.0,
        metadata: Optional[Dict] = None
    ) -> ValidationResult:
        """Create a validation result"""
        return ValidationResult(
            validator_name=self.validator_name,
            validator_type=self.validator_type,
            field_name=field_name,
            source_value=source_value,
            target_value=target_value,
            passed=passed,
            confidence=confidence,
            severity=severity,
            message=message,
            metadata=metadata or {}
        )

    def supports_field_type(self, field_type: str) -> bool:
        """
        Check if validator supports this field type

        Args:
            field_type: Type of field

        Returns:
            True for numeric/decimal fields
        """
        return field_type in ["number", "decimal", "currency", "string"]

    def get_metadata(self) -> Dict[str, Any]:
        """Return validator metadata"""
        return {
            "name": self.validator_name,
            "type": self.validator_type,
            "description": "Validates Ghana customs code-specific rules for duty and VAT calculations",
            "supported_codes": list(self.customs_codes.keys()),
            "config": self.config
        }
