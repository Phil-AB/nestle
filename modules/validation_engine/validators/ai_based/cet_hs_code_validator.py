"""
CET HS Code Validator

Validates HS codes against the CET (Common External Tariff) file.

Checks:
1. HS code exists in CET
2. Description matches CET description
3. Duty rate matches CET rate
"""

from typing import Dict, Any, List, Optional
from decimal import Decimal
from ...core.base import IValidator, ValidationResult, ValidationContext
from ...validators.validator_registry import ValidatorRegistry
from ...services.cet_file_service import get_cet_service
from ...utils.constants import ValidatorType, Severity, DiscrepancyCategory
from shared.utils.logger import get_logger

logger = get_logger(__name__)


@ValidatorRegistry.register("cet_hs_code_validator")
class CETHSCodeValidator(IValidator):
    """
    Validates HS codes against CET (Common External Tariff) file

    Verifies:
    - HS code exists in official CET tariff schedule
    - Description matches or is similar to CET description
    - Duty rate matches CET rate

    Config:
        validations: List of field validations
            - hs_code_field: Field containing HS code
            - description_field: Field containing description
            - duty_rate_field: Field containing duty rate
            - document: Document type (e.g., "bill_of_entry")

        verify_hs_code_exists: Check if HS code exists in CET
        verify_description: Check description similarity
        verify_duty_rate: Check duty rate matches CET

        description_similarity_threshold: Minimum similarity (0-1)
        duty_rate_tolerance_percent: Tolerance for duty rate (%)

    Example config:
        validations:
          - hs_code_field: "bill_of_entry.hs_code"
            description_field: "bill_of_entry.description"
            duty_rate_field: "bill_of_entry.duty_rate"
            document: "bill_of_entry"

        verify_hs_code_exists: true
        verify_description: true
        verify_duty_rate: true
        description_similarity_threshold: 0.6
        duty_rate_tolerance_percent: 0.1
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.validator_type = ValidatorType.AI_BASED  # Uses similarity matching
        self.validator_name = "cet_hs_code_validator"

        # Get validations
        self.validations = config.get("validations", [])

        # Get verification flags
        self.verify_hs_code_exists = config.get("verify_hs_code_exists", True)
        self.verify_description = config.get("verify_description", True)
        self.verify_duty_rate = config.get("verify_duty_rate", True)

        # Get thresholds
        self.description_similarity_threshold = config.get("description_similarity_threshold", 0.6)
        self.duty_rate_tolerance_percent = Decimal(str(config.get("duty_rate_tolerance_percent", 0.1)))

        # Get CET service
        self.cet_service = get_cet_service()

        # Try to load CET file
        if not self.cet_service.load_cet_file():
            logger.warning("CET file not loaded - validator will fail gracefully")

        logger.info(
            f"CETHSCodeValidator initialized with {len(self.validations)} validations"
        )

    async def validate(
        self,
        source_data: Dict[str, Any],
        target_data: Optional[Dict[str, Any]],
        context: ValidationContext
    ) -> List[ValidationResult]:
        """
        Validate HS codes against CET

        Args:
            source_data: Source document data
            target_data: Not used
            context: Validation context

        Returns:
            List of validation results
        """
        results = []

        # Check if CET is loaded
        cet_stats = self.cet_service.get_cet_statistics()
        if not cet_stats.get("loaded"):
            results.append(self._create_result(
                field_name="cet_file",
                passed=True,
                message="CET file not available — HS code tariff validation skipped",
                severity=Severity.INFO,
                source_value=None,
                target_value=None,
                confidence=1.0
            ))
            return results

        for validation_config in self.validations:
            # Extract field paths
            hs_code_field = validation_config.get("hs_code_field")
            description_field = validation_config.get("description_field")
            duty_rate_field = validation_config.get("duty_rate_field")

            # Get values
            hs_code = self._get_field_from_documents(hs_code_field, context)
            description = self._get_field_from_documents(description_field, context)
            duty_rate = self._get_field_from_documents(duty_rate_field, context)

            if not hs_code:
                results.append(self._create_result(
                    field_name="hs_code",
                    passed=False,
                    message="HS code not found - cannot validate against CET",
                    severity=Severity.MAJOR,
                    source_value=None,
                    target_value=None
                ))
                continue

            # Clean HS code
            hs_code = str(hs_code).strip()

            # Get CET info
            cet_info = self.cet_service.get_hs_code_info(hs_code)

            # 1. Verify HS code exists
            if self.verify_hs_code_exists:
                results.append(self._validate_hs_code_exists(hs_code, cet_info))

            if not cet_info:
                # Can't do further validation without CET info
                continue

            # 2. Verify description matches
            if self.verify_description and description:
                results.append(self._validate_description(
                    hs_code, description, cet_info
                ))

            # 3. Verify duty rate matches
            if self.verify_duty_rate and duty_rate is not None:
                results.append(self._validate_duty_rate(
                    hs_code, duty_rate, cet_info
                ))

        return results

    def _validate_hs_code_exists(
        self,
        hs_code: str,
        cet_info: Optional[Dict[str, Any]]
    ) -> ValidationResult:
        """
        Validate HS code exists in CET

        Args:
            hs_code: HS code to validate
            cet_info: CET info (None if not found)

        Returns:
            Validation result
        """
        if cet_info:
            return self._create_result(
                field_name="hs_code",
                passed=True,
                message=f"HS code {hs_code} found in CET: {cet_info.get('description', '')[:100]}",
                severity=Severity.INFO,
                source_value=hs_code,
                target_value=cet_info.get("hs_code"),
                confidence=1.0,
                metadata={
                    "cet_description": cet_info.get("description"),
                    "cet_duty_rate": float(cet_info.get("duty_rate", 0))
                }
            )
        else:
            return self._create_result(
                field_name="hs_code",
                passed=False,
                message=f"HS code {hs_code} NOT FOUND in CET - verify code is correct",
                severity=Severity.CRITICAL,
                source_value=hs_code,
                target_value=None,
                confidence=1.0
            )

    def _validate_description(
        self,
        hs_code: str,
        provided_description: str,
        cet_info: Dict[str, Any]
    ) -> ValidationResult:
        """
        Validate description matches CET description

        Args:
            hs_code: HS code
            provided_description: Description from document
            cet_info: CET info

        Returns:
            Validation result
        """
        matches, similarity, cet_description = self.cet_service.verify_description_match(
            hs_code,
            provided_description,
            self.description_similarity_threshold
        )

        if matches:
            return self._create_result(
                field_name="description",
                passed=True,
                message=f"Description matches CET (similarity: {similarity:.2%})",
                severity=Severity.INFO,
                source_value=provided_description[:100],
                target_value=cet_description[:100] if cet_description else None,
                confidence=similarity,
                metadata={
                    "similarity_score": similarity,
                    "threshold": self.description_similarity_threshold,
                    "cet_description": cet_description
                }
            )
        else:
            return self._create_result(
                field_name="description",
                passed=False,
                message=(
                    f"Description does NOT match CET (similarity: {similarity:.2%}, "
                    f"threshold: {self.description_similarity_threshold:.2%}). "
                    f"Provided: '{provided_description[:50]}...', "
                    f"CET: '{cet_description[:50] if cet_description else 'N/A'}...'"
                ),
                severity=Severity.MAJOR if similarity < 0.3 else Severity.MINOR,
                source_value=provided_description[:100],
                target_value=cet_description[:100] if cet_description else None,
                confidence=1.0 - similarity,
                metadata={
                    "similarity_score": similarity,
                    "threshold": self.description_similarity_threshold,
                    "cet_description": cet_description
                }
            )

    def _validate_duty_rate(
        self,
        hs_code: str,
        provided_duty_rate: Any,
        cet_info: Dict[str, Any]
    ) -> ValidationResult:
        """
        Validate duty rate matches CET

        Args:
            hs_code: HS code
            provided_duty_rate: Duty rate from document
            cet_info: CET info

        Returns:
            Validation result
        """
        cet_duty_rate = cet_info.get("duty_rate", Decimal("0"))

        # Convert to Decimal
        provided_duty_rate = self._to_decimal(provided_duty_rate)

        # Normalise units: CET stores percentage (e.g. 5.0), but extracted
        # documents typically store duty_rate as a decimal fraction (e.g. 0.05).
        # If the provided value looks like a decimal fraction (< 1), convert to %.
        if provided_duty_rate is not None and provided_duty_rate < Decimal("1"):
            provided_duty_rate = provided_duty_rate * Decimal("100")

        # Calculate difference
        difference = abs(cet_duty_rate - provided_duty_rate)
        tolerance = cet_duty_rate * self.duty_rate_tolerance_percent

        passed = difference <= tolerance

        if passed:
            return self._create_result(
                field_name="duty_rate",
                passed=True,
                message=f"Duty rate matches CET: {provided_duty_rate}% (CET: {cet_duty_rate}%)",
                severity=Severity.INFO,
                source_value=float(provided_duty_rate),
                target_value=float(cet_duty_rate),
                confidence=1.0,
                metadata={
                    "cet_duty_rate": float(cet_duty_rate),
                    "difference": float(difference),
                    "tolerance": float(tolerance)
                }
            )
        else:
            return self._create_result(
                field_name="duty_rate",
                passed=False,
                message=(
                    f"Duty rate does NOT match CET. "
                    f"Provided: {provided_duty_rate}%, "
                    f"CET: {cet_duty_rate}%, "
                    f"Difference: {difference}% "
                    f"(tolerance: {tolerance}%)"
                ),
                severity=Severity.CRITICAL if difference > cet_duty_rate * Decimal("0.05") else Severity.MAJOR,
                source_value=float(provided_duty_rate),
                target_value=float(cet_duty_rate),
                confidence=1.0 - min(float(difference / (cet_duty_rate or Decimal("1"))), 0.5),
                metadata={
                    "cet_duty_rate": float(cet_duty_rate),
                    "difference": float(difference),
                    "tolerance": float(tolerance)
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
        """Convert value to Decimal"""
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        if isinstance(value, str):
            try:
                # Remove % sign if present
                value = value.replace("%", "").strip()
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
        """Check if validator supports this field type"""
        return field_type in ["string", "text", "code", "number", "decimal"]

    def get_metadata(self) -> Dict[str, Any]:
        """Return validator metadata"""
        cet_stats = self.cet_service.get_cet_statistics()

        return {
            "name": self.validator_name,
            "type": self.validator_type,
            "description": "Validates HS codes against CET (Common External Tariff) file",
            "cet_loaded": cet_stats.get("loaded", False),
            "cet_total_hs_codes": cet_stats.get("indexed_hs_codes", 0),
            "config": self.config
        }
