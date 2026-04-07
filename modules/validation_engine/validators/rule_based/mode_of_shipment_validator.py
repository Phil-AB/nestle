"""
Mode of Shipment Validator

Validates that the correct transport document is provided based on BOE Section 21.

Rules (from PPTX Slide 2):
- Section 21 = KIA (Kotoka International Airport) → Expect Air Waybill (AWB)
- Section 21 = TMA (Tema Port) → Expect Bill of Lading (BL)
- Section 21 = Border/Land → Expect Delivery Note (DN)
"""

from typing import Dict, Any, List, Optional
from ...core.base import IValidator, ValidationResult, ValidationContext
from ...validators.validator_registry import ValidatorRegistry
from ...utils.constants import ValidatorType, Severity
from shared.utils.logger import get_logger

logger = get_logger(__name__)


@ValidatorRegistry.register("mode_of_shipment_validator")
class ModeOfShipmentValidator(IValidator):
    """
    Validates shipment mode consistency

    Checks that the transport document matches the mode of shipment
    declared in BOE Section 21.

    Config:
        section_21_field: Field path for Section 21 entry/exit code
        transport_documents: List of available transport documents

        mode_mappings: Map of entry codes to expected transport modes
            KIA: air
            TMA: sea
            etc.

        document_type_mappings: Map of transport modes to expected documents
            air: airway_bill
            sea: bill_of_lading
            road: delivery_note
    """

    # Default mode mappings
    DEFAULT_MODE_MAPPINGS = {
        "KIA": "air",  # Kotoka International Airport
        "KOTOKA": "air",
        "AIRPORT": "air",
        "TMA": "sea",  # Tema Port
        "TEMA": "sea",
        "PORT": "sea",
        "HARBOR": "sea",
        "HARBOUR": "sea",
        "BORDER": "road",
        "LAND": "road",
    }

    # Expected documents per mode
    DEFAULT_DOCUMENT_MAPPINGS = {
        "air": ["airway_bill", "awb", "air_waybill"],
        "sea": ["bill_of_lading", "bl", "bol"],
        "road": ["delivery_note", "dn", "cmr"],
    }

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.validator_type = ValidatorType.RULE_BASED
        self.validator_name = "mode_of_shipment_validator"

        # Get field paths
        self.section_21_field = config.get("section_21_field", "bill_of_entry.section_21.entry_exit_code")

        # Get mappings (with defaults)
        self.mode_mappings = {**self.DEFAULT_MODE_MAPPINGS, **config.get("mode_mappings", {})}
        self.document_mappings = {**self.DEFAULT_DOCUMENT_MAPPINGS, **config.get("document_type_mappings", {})}

        logger.info(f"ModeOfShipmentValidator initialized")

    async def validate(
        self,
        source_data: Dict[str, Any],
        target_data: Optional[Dict[str, Any]],
        context: ValidationContext
    ) -> List[ValidationResult]:
        """
        Validate mode of shipment consistency

        Args:
            source_data: Not used
            target_data: Not used
            context: Validation context with documents

        Returns:
            List of validation results
        """
        results = []

        # Get Section 21 entry/exit code
        entry_exit_code = self._get_field_from_documents(self.section_21_field, context)

        if not entry_exit_code:
            results.append(self._create_result(
                field_name="section_21",
                passed=True,
                message="Section 21 (Entry/Exit code) not extracted from BOE — shipment mode validation skipped",
                severity=Severity.INFO,
                source_value=None,
                target_value=None
            ))
            return results

        # Determine expected transport mode
        entry_code_upper = str(entry_exit_code).upper().strip()
        expected_mode = None

        for code_pattern, mode in self.mode_mappings.items():
            if code_pattern in entry_code_upper:
                expected_mode = mode
                break

        if not expected_mode:
            results.append(self._create_result(
                field_name="section_21",
                passed=False,
                message=f"Unknown Entry/Exit code: {entry_exit_code}. Cannot determine expected transport mode.",
                severity=Severity.MINOR,
                source_value=entry_exit_code,
                target_value=None,
                confidence=0.5
            ))
            return results

        # Check which transport documents are available
        available_docs = list(context.documents.keys())
        expected_doc_types = self.document_mappings.get(expected_mode, [])

        # Check if correct transport document is provided
        correct_doc_found = any(
            any(exp_type in doc_type.lower() for exp_type in expected_doc_types)
            for doc_type in available_docs
        )

        if correct_doc_found:
            results.append(self._create_result(
                field_name="transport_document",
                passed=True,
                message=f"Correct transport document for {expected_mode} shipment (Section 21: {entry_exit_code})",
                severity=Severity.INFO,
                source_value=expected_mode,
                target_value=expected_doc_types,
                confidence=1.0,
                metadata={
                    "entry_exit_code": entry_exit_code,
                    "expected_mode": expected_mode,
                    "expected_documents": expected_doc_types,
                    "available_documents": available_docs
                }
            ))
        else:
            results.append(self._create_result(
                field_name="transport_document",
                passed=False,
                message=(
                    f"INCORRECT transport document for {expected_mode} shipment. "
                    f"Section 21: {entry_exit_code} indicates {expected_mode} transport, "
                    f"expected {' or '.join(expected_doc_types)}, "
                    f"but found: {', '.join(available_docs)}"
                ),
                severity=Severity.MAJOR,
                source_value=expected_mode,
                target_value=expected_doc_types,
                confidence=1.0,
                metadata={
                    "entry_exit_code": entry_exit_code,
                    "expected_mode": expected_mode,
                    "expected_documents": expected_doc_types,
                    "available_documents": available_docs
                }
            ))

        return results

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
        except:
            return None

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
        return field_type in ["string", "code"]

    def get_metadata(self) -> Dict[str, Any]:
        """Return validator metadata"""
        return {
            "name": self.validator_name,
            "type": self.validator_type,
            "description": "Validates shipment mode consistency based on BOE Section 21",
            "mode_mappings": self.mode_mappings,
            "config": self.config
        }
