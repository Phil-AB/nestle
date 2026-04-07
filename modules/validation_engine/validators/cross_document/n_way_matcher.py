"""N-way matcher for multi-document field comparison"""

from typing import Dict, Any, List, Optional, Set
from ...core.base import IValidator, ValidationResult, ValidationContext
from ...validators.validator_registry import ValidatorRegistry
from ...utils.constants import ValidatorType, Severity, MatchType
from shared.utils.logger import get_logger

logger = get_logger(__name__)


@ValidatorRegistry.register("n_way_matcher")
class NWayMatcher(IValidator):
    """
    Validates that a field has the same value across N documents

    Critical for BOE validation where HS Code must match across
    BOE, Invoice, and Packing List.

    Config:
        field_name: Field name to match (e.g., "hs_code")
        documents: List of document types to check
            Example: ["bill_of_entry", "invoice", "packing_list"]
        match_type: Type of matching
            - "exact": Exact match (default)
            - "case_insensitive": Case-insensitive match
            - "normalized": Normalize whitespace and case
        require_all: Whether all documents must have the field (default: true)
        line_items: Whether to match line items (default: false)

    Example config:
        field_name: "hs_code"
        documents: ["bill_of_entry", "invoice", "packing_list"]
        match_type: "exact"
        require_all: true
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.validator_type = ValidatorType.CROSS_DOCUMENT
        self.validator_name = "n_way_matcher"

        self.field_name = config.get("field_name")
        self.documents = config.get("documents", [])
        self.match_type = config.get("match_type", MatchType.EXACT)
        self.require_all = config.get("require_all", True)
        self.line_items = config.get("line_items", False)

        logger.debug(
            f"NWayMatcher initialized for field '{self.field_name}' "
            f"across {len(self.documents)} documents"
        )

    async def validate(
        self,
        source_data: Dict[str, Any],
        target_data: Optional[Dict[str, Any]],
        context: ValidationContext
    ) -> List[ValidationResult]:
        """
        Validate N-way field matching — dispatches to header or line-item mode.

        Args:
            source_data: Source document data (or full documents dict for cross-doc)
            target_data: Target document data (optional)
            context: Validation context

        Returns:
            List of validation results
        """
        if self.line_items:
            return self._validate_line_items(context)
        return self._validate_header_field(context)

    def _validate_header_field(self, context: ValidationContext) -> List[ValidationResult]:
        """Validate a single header-level field across N documents."""
        results = []

        # Gather field values from all specified documents
        field_values = {}
        missing_docs = []

        for doc_type in self.documents:
            doc_data = context.documents.get(doc_type)

            if not doc_data:
                missing_docs.append(doc_type)
                continue

            value = doc_data.get(self.field_name)

            if value is None:
                if self.require_all:
                    missing_docs.append(doc_type)
            else:
                field_values[doc_type] = value

        # Check for missing documents/fields
        if missing_docs:
            if self.require_all:
                results.append(ValidationResult(
                    validator_name=self.validator_name,
                    validator_type=self.validator_type,
                    field_name=self.field_name,
                    source_value=None,
                    target_value=None,
                    passed=False,
                    confidence=1.0,
                    severity=self.get_severity({}),
                    message=(
                        f"Field '{self.field_name}' missing from required documents: "
                        f"{', '.join(missing_docs)}"
                    )
                ))
                return results

        # Need at least 2 documents to compare
        if len(field_values) < 2:
            if not self.require_all:
                # Skip gracefully — field is only present in one (or zero) docs.
                # Not enough data to cross-validate; not treated as a failure.
                results.append(ValidationResult(
                    validator_name=self.validator_name,
                    validator_type=self.validator_type,
                    field_name=self.field_name,
                    source_value=None,
                    target_value=None,
                    passed=True,
                    confidence=0.5,
                    severity=Severity.INFO,
                    message=f"Field '{self.field_name}' only present in {len(field_values)} document(s) — skipping cross-validation"
                ))
            else:
                results.append(ValidationResult(
                    validator_name=self.validator_name,
                    validator_type=self.validator_type,
                    field_name=self.field_name,
                    source_value=None,
                    target_value=None,
                    passed=False,
                    confidence=0.5,
                    severity=Severity.MINOR,
                    message=f"Field '{self.field_name}' found in less than 2 documents"
                ))
            return results

        # Check if all values match
        normalized_values = {
            doc: self._normalize_value(val, self.match_type)
            for doc, val in field_values.items()
        }

        unique_values = set(normalized_values.values())

        if len(unique_values) == 1:
            results.append(ValidationResult(
                validator_name=self.validator_name,
                validator_type=self.validator_type,
                field_name=self.field_name,
                source_value=list(field_values.values())[0],
                target_value=None,
                passed=True,
                confidence=1.0,
                severity=Severity.INFO,
                message=(
                    f"Field '{self.field_name}' matches across all {len(field_values)} documents: "
                    f"{', '.join(field_values.keys())}"
                ),
                metadata={
                    "documents": list(field_values.keys()),
                    "value": list(unique_values)[0]
                }
            ))
        else:
            mismatches = self._identify_mismatches(field_values, normalized_values)
            results.append(ValidationResult(
                validator_name=self.validator_name,
                validator_type=self.validator_type,
                field_name=self.field_name,
                source_value=field_values,
                target_value=None,
                passed=False,
                confidence=0.9,
                severity=self.get_severity({}),
                message=(
                    f"Field '{self.field_name}' mismatch across documents. "
                    f"Found {len(unique_values)} different values."
                ),
                discrepancy={
                    "field_name": self.field_name,
                    "documents": list(field_values.keys()),
                    "values": field_values,
                    "unique_values": list(unique_values),
                    "mismatches": mismatches
                }
            ))
            logger.warning(f"N-way mismatch for '{self.field_name}': {mismatches}")

        return results

    def _validate_line_items(self, context: ValidationContext) -> List[ValidationResult]:
        """
        Validate a field across line items in N documents.

        Items are matched by HS code (primary key) with positional fallback.
        One ValidationResult is emitted per matched item group.
        """
        results = []

        # Collect items arrays from each document
        doc_items: Dict[str, List[Dict[str, Any]]] = {}
        for doc_type in self.documents:
            doc_data = context.documents.get(doc_type)
            if not doc_data:
                if self.require_all:
                    results.append(ValidationResult(
                        validator_name=self.validator_name,
                        validator_type=self.validator_type,
                        field_name=self.field_name,
                        source_value=None,
                        target_value=None,
                        passed=False,
                        confidence=1.0,
                        severity=self.get_severity({}),
                        message=f"Document '{doc_type}' not found for line-item validation"
                    ))
                    return results
                continue

            items = doc_data.get("items", [])
            if not isinstance(items, list):
                items = []
            doc_items[doc_type] = items

        if len(doc_items) < 2:
            results.append(ValidationResult(
                validator_name=self.validator_name,
                validator_type=self.validator_type,
                field_name=self.field_name,
                source_value=None,
                target_value=None,
                passed=False,
                confidence=0.5,
                severity=Severity.MINOR,
                message=f"Line-item validation for '{self.field_name}' requires at least 2 documents"
            ))
            return results

        # Build HS-code keyed index from the first document; fall back to positional
        ref_doc = list(doc_items.keys())[0]
        ref_items = doc_items[ref_doc]

        def _hs_key(item: Dict[str, Any]) -> Optional[str]:
            """Return normalised HS code from an item dict, or None."""
            for key in ("hs_code", "hsn_code", "tariff_code"):
                val = item.get(key)
                if val:
                    return str(val).strip()
            return None

        for idx, ref_item in enumerate(ref_items):
            ref_hs = _hs_key(ref_item)
            ref_value = ref_item.get(self.field_name)

            field_values: Dict[str, Any] = {ref_doc: ref_value}

            for doc_type, items in doc_items.items():
                if doc_type == ref_doc:
                    continue

                # Match by HS code first, then by position
                matched_item: Optional[Dict[str, Any]] = None
                if ref_hs:
                    matched_item = next(
                        (it for it in items if _hs_key(it) == ref_hs),
                        None
                    )
                if matched_item is None and idx < len(items):
                    matched_item = items[idx]

                if matched_item is not None:
                    field_values[doc_type] = matched_item.get(self.field_name)

            # Only compare docs where we found a value
            comparable = {doc: v for doc, v in field_values.items() if v is not None}

            if len(comparable) < 2:
                results.append(ValidationResult(
                    validator_name=self.validator_name,
                    validator_type=self.validator_type,
                    field_name=self.field_name,
                    source_value=ref_value,
                    target_value=None,
                    passed=False,
                    confidence=0.5,
                    severity=Severity.MINOR,
                    message=(
                        f"Item {idx + 1} (HS: {ref_hs or 'unknown'}): "
                        f"'{self.field_name}' found in fewer than 2 documents"
                    ),
                    metadata={"item_index": idx, "hs_code": ref_hs}
                ))
                continue

            normalized = {
                doc: self._normalize_value(v, self.match_type)
                for doc, v in comparable.items()
            }
            unique = set(normalized.values())
            passed = len(unique) == 1

            results.append(ValidationResult(
                validator_name=self.validator_name,
                validator_type=self.validator_type,
                field_name=self.field_name,
                source_value=comparable,
                target_value=None,
                passed=passed,
                confidence=1.0 if passed else 0.9,
                severity=Severity.INFO if passed else self.get_severity({}),
                message=(
                    f"Item {idx + 1} (HS: {ref_hs or 'unknown'}): "
                    f"'{self.field_name}' {'matches' if passed else 'mismatch'} across "
                    f"{', '.join(comparable.keys())}"
                ),
                discrepancy=None if passed else {
                    "field_name": self.field_name,
                    "item_index": idx,
                    "hs_code": ref_hs,
                    "values": comparable,
                    "unique_values": list(unique)
                },
                metadata={"item_index": idx, "hs_code": ref_hs}
            ))

            if not passed:
                logger.warning(
                    f"Line-item {idx + 1} '{self.field_name}' mismatch "
                    f"(HS: {ref_hs}): {comparable}"
                )

        return results

    def _normalize_value(self, value: Any, match_type: str) -> Any:
        """
        Normalize value based on match type

        Args:
            value: Value to normalize
            match_type: Type of matching

        Returns:
            Normalized value
        """
        if match_type == MatchType.EXACT:
            return value

        if isinstance(value, str):
            if match_type == MatchType.CASE_INSENSITIVE:
                return value.lower()

            elif match_type == "normalized":
                # Normalize whitespace and case
                return " ".join(value.lower().split())

        return value

    def _identify_mismatches(
        self,
        original_values: Dict[str, Any],
        normalized_values: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Identify which documents have mismatching values

        Args:
            original_values: Original field values by document
            normalized_values: Normalized values by document

        Returns:
            List of mismatch details
        """
        mismatches = []

        # Group documents by their normalized values
        value_groups: Dict[Any, List[str]] = {}
        for doc, norm_value in normalized_values.items():
            if norm_value not in value_groups:
                value_groups[norm_value] = []
            value_groups[norm_value].append(doc)

        # Create mismatch entries
        for norm_value, docs in value_groups.items():
            # Get original values for these docs
            orig_values = {doc: original_values[doc] for doc in docs}

            mismatches.append({
                "normalized_value": norm_value,
                "documents": docs,
                "original_values": orig_values
            })

        return mismatches

    def supports_field_type(self, field_type: str) -> bool:
        """Check if validator supports this field type"""
        return True  # Supports all field types
