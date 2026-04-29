"""Required fields validator"""

from typing import Dict, Any, List, Optional
from ...core.base import IValidator, ValidationResult, ValidationContext
from ...validators.validator_registry import ValidatorRegistry
from ...utils.constants import ValidatorType, Severity
from shared.utils.logger import get_logger

logger = get_logger(__name__)


@ValidatorRegistry.register("required_fields_validator")
class RequiredFieldsValidator(IValidator):
    """
    Validates that required fields exist and are not empty

    Config:
        required_fields: Dict mapping document types to required field lists
            Example:
                bill_of_entry: ["hs_code", "net_weight", "gross_weight"]
                invoice: ["hs_code", "unit_price"]

        allow_empty: Whether to allow empty values (default: false)
        check_nested: Whether to check nested fields (default: true)

    Example config:
        required_fields:
          bill_of_entry: ["hs_code", "net_weight", "duty_amount"]
          invoice: ["hs_code", "net_weight", "unit_price"]
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.validator_type = ValidatorType.RULE_BASED
        self.validator_name = "required_fields_validator"

        self.required_fields = config.get("required_fields", {})
        self.allow_empty = config.get("allow_empty", False)
        self.check_nested = config.get("check_nested", True)
        # Documents listed here are skipped entirely when absent (no failure emitted)
        self.optional_documents = set(config.get("optional_documents", []))

        logger.debug(
            f"RequiredFieldsValidator initialized for "
            f"{len(self.required_fields)} document types"
        )

    async def validate(
        self,
        source_data: Dict[str, Any],
        target_data: Optional[Dict[str, Any]],
        context: ValidationContext
    ) -> List[ValidationResult]:
        """
        Validate required fields exist

        Args:
            source_data: Source document data
            target_data: Target document data (optional)
            context: Validation context

        Returns:
            List of validation results
        """
        results = []

        # Validate all document types that have required fields configured.
        # Use context.documents so both primary and supporting docs are covered
        # regardless of how source_data/target_data were dispatched.
        # Field name synonyms are resolved upstream by the normalize_node,
        # which adds canonical field names to the normalized documents.
        for doc_type, fields in self.required_fields.items():
            doc_data = context.documents.get(doc_type)
            if doc_data is None and doc_type == context.primary_document:
                doc_data = source_data
            if not doc_data:
                if doc_type in self.optional_documents:
                    logger.debug(f"Optional document '{doc_type}' not present — skipping required field checks")
                    results.append(ValidationResult(
                        validator_name=self.validator_name,
                        validator_type=self.validator_type,
                        field_name=f"{doc_type}_not_uploaded",
                        source_document=doc_type,
                        source_value=None,
                        target_value=None,
                        passed=True,
                        confidence=1.0,
                        severity=Severity.INFO,
                        message=f"Document '{doc_type}' not uploaded — field checks skipped (optional)"
                    ))
                    continue
                # Required document not present — mark every field as missing
                for field_name in fields:
                    results.append(ValidationResult(
                        validator_name=self.validator_name,
                        validator_type=self.validator_type,
                        field_name=field_name,
                        source_document=doc_type,
                        source_value=None,
                        target_value=None,
                        passed=False,
                        confidence=1.0,
                        severity=self.get_severity({}),
                        message=f"Document '{doc_type}' not present — required field '{field_name}' cannot be checked"
                    ))
                continue
            doc_results = self._validate_document(
                document_data=doc_data,
                document_type=doc_type,
                required_fields=fields
            )
            results.extend(doc_results)

        return results

    def _validate_document(
        self,
        document_data: Dict[str, Any],
        document_type: str,
        required_fields: List[str]
    ) -> List[ValidationResult]:
        """
        Validate required fields for a single document

        Args:
            document_data: Document data
            document_type: Type of document
            required_fields: List of required field names

        Returns:
            List of validation results
        """
        results = []

        for field_name in required_fields:
            # Get field value
            value = self._get_field_value(document_data, field_name)

            # Check if field exists
            field_exists = value is not None

            # Check if field is empty
            is_empty = self._is_empty(value)

            # Determine if validation passed
            if not field_exists:
                passed = False
                message = f"Required field '{field_name}' is missing from {document_type}"
                confidence = 1.0

            elif is_empty and not self.allow_empty:
                passed = False
                message = f"Required field '{field_name}' in {document_type} is empty"
                confidence = 1.0

            else:
                passed = True
                message = f"Required field '{field_name}' exists in {document_type}"
                confidence = 1.0

            # Create result
            result = ValidationResult(
                validator_name=self.validator_name,
                validator_type=self.validator_type,
                field_name=field_name,
                source_document=document_type,
                source_value=value,
                target_value=None,
                passed=passed,
                confidence=confidence,
                severity=self.get_severity({}) if not passed else Severity.INFO,
                message=message,
                discrepancy={
                    "document_type": document_type,
                    "field_name": field_name,
                    "exists": field_exists,
                    "is_empty": is_empty
                } if not passed else None
            )

            results.append(result)

            if not passed:
                logger.warning(f"Required field validation failed: {message}")

        return results

    def _get_field_value(self, data: Dict[str, Any], field_name: str) -> Any:
        """
        Get field value, supporting nested dot-path traversal.

        Also unwraps ``{"value": X, "confidence": Y}`` dicts that may
        survive normalization when a field is only added by the use-case
        synonym pass (which runs *after* value normalization).

        Args:
            data: Dictionary to search
            field_name: Field name (can be nested with dots)

        Returns:
            Field value or None if not found
        """
        # 1. Exact match
        value = data.get(field_name)
        if value is not None:
            # Unwrap {"value": ..., "confidence": ...} envelope
            if isinstance(value, dict) and "value" in value:
                if value.get("redacted") is True:
                    return value  # preserve redacted marker
                return value["value"] if value["value"] is not None else value
            return value

        # 2. Nested dot-path
        if self.check_nested and "." in field_name:
            parts = field_name.split(".")
            value = data
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                    if value is None:
                        return None
                else:
                    return None
            # Unwrap at the leaf level too
            if isinstance(value, dict) and "value" in value and value.get("redacted") is not True:
                return value["value"] if value["value"] is not None else value
            return value

        # 3. Items fallback — field may live in the items array (item-level fields
        #    like product_description are put in items[], not in the flat fields dict).
        items = data.get("items")
        if items and isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and field_name in item:
                    val = item[field_name]
                    if isinstance(val, dict) and "value" in val:
                        return val["value"] if val["value"] is not None else val
                    return val

        return None

    def _is_empty(self, value: Any) -> bool:
        """
        Check if value is considered empty

        Args:
            value: Value to check

        Returns:
            True if empty
        """
        if value is None:
            return True

        if isinstance(value, str):
            return len(value.strip()) == 0

        if isinstance(value, (list, dict)):
            return len(value) == 0

        return False

    def supports_field_type(self, field_type: str) -> bool:
        """
        Check if validator supports this field type

        Args:
            field_type: Type of field

        Returns:
            True (supports all field types)
        """
        return True
