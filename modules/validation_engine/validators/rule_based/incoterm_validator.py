"""
Incoterm Validator

Validates freight and insurance values based on Incoterm.

Rules (from PPTX Slide 2):
- CFR (Cost & Freight): Invoice should have freight value stated
- CIF (Cost, Insurance, Freight): Invoice should have insurance + freight values stated
- FCA/FOB (Free Carrier/Free on Board): No freight value needed on invoice
- CIF Calculation: CIF = FOB + Insurance + Freight (all in same currency)
"""

from typing import Dict, Any, List, Optional
from decimal import Decimal, ROUND_HALF_UP
from ...core.base import IValidator, ValidationResult, ValidationContext
from ...validators.validator_registry import ValidatorRegistry
from ...utils.constants import ValidatorType, Severity
from shared.utils.logger import get_logger

logger = get_logger(__name__)


@ValidatorRegistry.register("incoterm_validator")
class IncotermValidator(IValidator):
    """
    Validates freight/insurance based on Incoterm

    Config:
        validations: List of validations
            - incoterm_field: Field containing incoterm
            - freight_field: Field containing freight value
            - insurance_field: Field containing insurance value
            - fob_field: Field containing FOB value
            - cif_field: Field containing CIF value
            - document: Document type

        tolerance: Tolerance for CIF calculation (default 0.01)
    """

    # Incoterms requiring freight
    FREIGHT_REQUIRED = ["CFR", "CIF", "CPT", "CIP", "DAP", "DPU", "DDP"]

    # Incoterms requiring insurance
    INSURANCE_REQUIRED = ["CIF", "CIP"]

    # Incoterms with no freight/insurance
    NO_FREIGHT = ["EXW", "FCA", "FAS", "FOB"]

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.validator_type = ValidatorType.RULE_BASED
        self.validator_name = "incoterm_validator"

        self.validations = config.get("validations", [])
        self.tolerance = Decimal(str(config.get("tolerance", "0.01")))

        logger.info(f"IncotermValidator initialized with {len(self.validations)} validations")

    async def validate(
        self,
        source_data: Dict[str, Any],
        target_data: Optional[Dict[str, Any]],
        context: ValidationContext
    ) -> List[ValidationResult]:
        """Validate incoterm rules"""
        results = []

        for validation_config in self.validations:
            # Get fields
            incoterm_field = validation_config.get("incoterm_field")
            freight_field = validation_config.get("freight_field")
            insurance_field = validation_config.get("insurance_field")
            fob_field = validation_config.get("fob_field")
            cif_field = validation_config.get("cif_field")

            # Get values
            incoterm = self._get_field_from_documents(incoterm_field, context)
            freight_value = self._get_field_from_documents(freight_field, context)
            insurance_value = self._get_field_from_documents(insurance_field, context)
            fob_value = self._get_field_from_documents(fob_field, context)
            cif_value = self._get_field_from_documents(cif_field, context)

            if not incoterm:
                results.append(self._create_result(
                    field_name="incoterm",
                    passed=False,
                    message="Incoterm not found - cannot validate freight/insurance rules",
                    severity=Severity.MAJOR,
                    source_value=None,
                    target_value=None
                ))
                continue

            # Extract the incoterm code (first word only).
            # The extracted value may be "FCA ROTTERDAM PORT" — we only need "FCA".
            incoterm_upper = str(incoterm).upper().strip().split()[0] if incoterm else ""

            # Validate based on incoterm
            if incoterm_upper in self.FREIGHT_REQUIRED:
                results.extend(self._validate_freight_required(
                    incoterm_upper, freight_value, freight_field
                ))

            if incoterm_upper in self.INSURANCE_REQUIRED:
                results.extend(self._validate_insurance_required(
                    incoterm_upper, insurance_value, insurance_field
                ))

            if incoterm_upper in self.NO_FREIGHT:
                results.extend(self._validate_no_freight(
                    incoterm_upper, freight_value, insurance_value
                ))

            # CIF specific: validate calculation
            if incoterm_upper == "CIF" and all([fob_value, freight_value, insurance_value, cif_value]):
                results.append(self._validate_cif_calculation(
                    fob_value, freight_value, insurance_value, cif_value
                ))

        return results

    def _validate_freight_required(
        self,
        incoterm: str,
        freight_value: Any,
        freight_field: str
    ) -> List[ValidationResult]:
        """Validate freight value is present for CFR/CIF"""
        results = []

        freight_decimal = self._to_decimal(freight_value) if freight_value else None

        if freight_decimal and freight_decimal > Decimal("0"):
            results.append(self._create_result(
                field_name="freight_value",
                passed=True,
                message=f"{incoterm}: Freight value present ({freight_decimal})",
                severity=Severity.INFO,
                source_value=float(freight_decimal),
                target_value=None,
                confidence=1.0,
                metadata={"incoterm": incoterm}
            ))
        else:
            results.append(self._create_result(
                field_name="freight_value",
                passed=False,
                message=f"{incoterm} requires freight value on invoice, but none found",
                severity=Severity.CRITICAL,
                source_value=freight_value,
                target_value="> 0",
                confidence=1.0,
                metadata={"incoterm": incoterm}
            ))

        return results

    def _validate_insurance_required(
        self,
        incoterm: str,
        insurance_value: Any,
        insurance_field: str
    ) -> List[ValidationResult]:
        """Validate insurance value is present for CIF/CIP"""
        results = []

        insurance_decimal = self._to_decimal(insurance_value) if insurance_value else None

        if insurance_decimal and insurance_decimal > Decimal("0"):
            results.append(self._create_result(
                field_name="insurance_value",
                passed=True,
                message=f"{incoterm}: Insurance value present ({insurance_decimal})",
                severity=Severity.INFO,
                source_value=float(insurance_decimal),
                target_value=None,
                confidence=1.0,
                metadata={"incoterm": incoterm}
            ))
        else:
            results.append(self._create_result(
                field_name="insurance_value",
                passed=False,
                message=f"{incoterm} requires insurance value on invoice, but none found",
                severity=Severity.CRITICAL,
                source_value=insurance_value,
                target_value="> 0",
                confidence=1.0,
                metadata={"incoterm": incoterm}
            ))

        return results

    def _validate_no_freight(
        self,
        incoterm: str,
        freight_value: Any,
        insurance_value: Any
    ) -> List[ValidationResult]:
        """Validate no freight/insurance for FOB/FCA"""
        results = []

        freight_decimal = self._to_decimal(freight_value) if freight_value else Decimal("0")
        insurance_decimal = self._to_decimal(insurance_value) if insurance_value else Decimal("0")

        if freight_decimal > Decimal("0") or insurance_decimal > Decimal("0"):
            results.append(self._create_result(
                field_name="freight_insurance",
                passed=False,
                message=f"{incoterm} should not have freight/insurance on invoice (Freight: {freight_decimal}, Insurance: {insurance_decimal})",
                severity=Severity.MINOR,
                source_value={"freight": float(freight_decimal), "insurance": float(insurance_decimal)},
                target_value={"freight": 0, "insurance": 0},
                confidence=0.8,
                metadata={"incoterm": incoterm}
            ))
        else:
            results.append(self._create_result(
                field_name="freight_insurance",
                passed=True,
                message=f"{incoterm}: No freight/insurance on invoice (correct)",
                severity=Severity.INFO,
                source_value=None,
                target_value=None,
                confidence=1.0,
                metadata={"incoterm": incoterm}
            ))

        return results

    def _validate_cif_calculation(
        self,
        fob_value: Any,
        freight_value: Any,
        insurance_value: Any,
        cif_value: Any
    ) -> ValidationResult:
        """Validate CIF = FOB + Insurance + Freight"""
        fob = self._to_decimal(fob_value)
        freight = self._to_decimal(freight_value)
        insurance = self._to_decimal(insurance_value)
        cif = self._to_decimal(cif_value)

        calculated_cif = (fob + freight + insurance).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        difference = abs(calculated_cif - cif)

        passed = difference <= self.tolerance

        if passed:
            return self._create_result(
                field_name="cif_calculation",
                passed=True,
                message=f"CIF calculation correct: {cif} = {fob} + {freight} + {insurance}",
                severity=Severity.INFO,
                source_value=float(cif),
                target_value=float(calculated_cif),
                confidence=1.0,
                metadata={
                    "fob": float(fob),
                    "freight": float(freight),
                    "insurance": float(insurance),
                    "calculated_cif": float(calculated_cif)
                }
            )
        else:
            return self._create_result(
                field_name="cif_calculation",
                passed=False,
                message=f"CIF calculation INCORRECT. Expected: {calculated_cif} ({fob}+{freight}+{insurance}), Actual: {cif}, Difference: {difference}",
                severity=Severity.CRITICAL,
                source_value=float(cif),
                target_value=float(calculated_cif),
                confidence=1.0,
                metadata={
                    "fob": float(fob),
                    "freight": float(freight),
                    "insurance": float(insurance),
                    "calculated_cif": float(calculated_cif),
                    "difference": float(difference)
                }
            )

    def _get_field_from_documents(self, field_path: str, context: ValidationContext) -> Any:
        """Get field value from context documents"""
        if not field_path:
            return None
        parts = field_path.split(".")
        if len(parts) < 2:
            return None
        doc_type = parts[0]
        field_name = ".".join(parts[1:])
        if doc_type in context.normalized_data:
            return self._get_nested_value(context.normalized_data[doc_type], field_name)
        if doc_type in context.documents:
            return self._get_nested_value(context.documents[doc_type], field_name)
        return None

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get nested value using dot notation"""
        try:
            value = data
            for key in path.split("."):
                value = value.get(key) if isinstance(value, dict) else None
                if value is None:
                    return None
            return value
        except:
            return None

    def _to_decimal(self, value: Any) -> Decimal:
        """Convert value to Decimal"""
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except:
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
        """Check if validator supports this field type"""
        return field_type in ["string", "number", "decimal"]

    def get_metadata(self) -> Dict[str, Any]:
        """Return validator metadata"""
        return {
            "name": self.validator_name,
            "type": self.validator_type,
            "description": "Validates freight/insurance based on Incoterm",
            "config": self.config
        }
