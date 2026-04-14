"""
Shipper/Consignee Cross-Document Validator

Validates that shipper and consignee information matches across multiple documents:
- Bill of Entry (BOE)
- Invoice
- Bill of Lading (BL) / Air Waybill (AWB) / Delivery Note (DN)
- Packing List

Supports:
- Exact matching
- Case-insensitive matching
- Fuzzy matching for name variations
- Normalization (whitespace, punctuation)
"""

from typing import Dict, Any, List, Optional
import unicodedata
from ...core.base import IValidator, ValidationResult, ValidationContext
from ...validators.validator_registry import ValidatorRegistry
from ...utils.constants import ValidatorType, Severity, DiscrepancyCategory
from shared.utils.logger import get_logger

logger = get_logger(__name__)


@ValidatorRegistry.register("shipper_consignee_validator")
class ShipperConsigneeValidator(IValidator):
    """
    Validates shipper and consignee match across multiple documents

    Ensures party information is consistent across:
    - BOE
    - Invoice
    - BL/AWB/DN
    - Packing List

    Config:
        parties: List of parties to validate
            - name: Party name (e.g., "shipper", "consignee")
            - documents: Documents to compare
            - field_mappings: Field paths for each document
            - match_type: "exact", "case_insensitive", "fuzzy"
            - fuzzy_threshold: Minimum similarity for fuzzy (0-1)

        normalization:
            remove_whitespace: Remove extra whitespace
            remove_punctuation: Remove commas, periods, etc.
            lowercase: Convert to lowercase
            remove_company_suffixes: Remove Ltd, Inc, etc.

    Example config:
        parties:
          - name: "shipper"
            documents:
              - "bill_of_entry"
              - "invoice"
              - "bill_of_lading"
            field_mappings:
              bill_of_entry: "shipper_name"
              invoice: "shipper_name"
              bill_of_lading: "shipper_name"
            address_mappings:          # optional — enables address cross-check
              bill_of_entry: "shipper_address"
              invoice: "shipper_address"
            match_type: "fuzzy"
            fuzzy_threshold: 0.8
            check_address: false       # set true to also validate address fields

          - name: "consignee"
            documents:
              - "bill_of_entry"
              - "invoice"
            field_mappings:
              bill_of_entry: "consignee_name"
              invoice: "consignee_name"
            address_mappings:
              bill_of_entry: "consignee_address"
              invoice: "consignee_address"
            match_type: "case_insensitive"
            check_address: false
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.validator_type = ValidatorType.CROSS_DOCUMENT
        self.validator_name = "shipper_consignee_validator"

        # Get parties to validate
        self.parties = config.get("parties", [])

        # Get normalization settings
        normalization_config = config.get("normalization", {})
        self.remove_whitespace = normalization_config.get("remove_whitespace", True)
        self.remove_punctuation = normalization_config.get("remove_punctuation", True)
        self.lowercase = normalization_config.get("lowercase", True)
        self.remove_company_suffixes = normalization_config.get("remove_company_suffixes", True)

        # Company suffixes to remove
        self.company_suffixes = [
            "Ltd", "Limited", "Inc", "Incorporated", "Corp", "Corporation",
            "LLC", "LLP", "SA", "SARL", "GmbH", "AG", "NV", "BV",
            "Pty", "Co", "Company", "Plc"
        ]

        logger.info(
            f"ShipperConsigneeValidator initialized with {len(self.parties)} parties"
        )

    async def validate(
        self,
        source_data: Dict[str, Any],
        target_data: Optional[Dict[str, Any]],
        context: ValidationContext
    ) -> List[ValidationResult]:
        """
        Validate shipper/consignee across documents

        Args:
            source_data: Not used (cross-document validation)
            target_data: Not used
            context: Validation context with all documents

        Returns:
            List of validation results
        """
        results = []

        for party_config in self.parties:
            party_name = party_config.get("name", "party")
            documents = party_config.get("documents", [])
            field_mappings = party_config.get("field_mappings", {})
            address_mappings = party_config.get("address_mappings", {})
            match_type = party_config.get("match_type", "case_insensitive")
            fuzzy_threshold = party_config.get("fuzzy_threshold", 0.8)
            check_address = party_config.get("check_address", False)

            # Collect party name values from all documents
            party_values = {}

            for doc_type in documents:
                field_path = field_mappings.get(doc_type)

                if not field_path:
                    logger.warning(f"No field mapping for {doc_type} in party {party_name}")
                    continue

                value = self._get_field_from_documents(f"{doc_type}.{field_path}", context)

                if value:
                    normalized_value = self._normalize_name(str(value))
                    party_values[doc_type] = {
                        "original": value,
                        "normalized": normalized_value
                    }
                else:
                    logger.debug(f"{party_name} not found in {doc_type}")

            # Check if we have at least 2 documents to compare
            if len(party_values) < 2:
                results.append(self._create_result(
                    field_name=party_name,
                    passed=True,
                    message=(
                        f"{party_name.title()} found in {len(party_values)} document(s) "
                        f"({', '.join(party_values.keys()) or 'none'}) — "
                        "insufficient data for cross-validation, skipping"
                    ),
                    severity=Severity.INFO,
                    source_value=None,
                    target_value=None,
                    confidence=0.5,
                    metadata={
                        "party": party_name,
                        "documents_found": list(party_values.keys()),
                        "documents_expected": documents
                    }
                ))
                continue

            # Validate party name matches across documents
            result = self._validate_party_match(
                party_name,
                party_values,
                match_type,
                fuzzy_threshold
            )
            results.append(result)

            # Optionally validate address fields
            if check_address and address_mappings:
                address_values = {}
                for doc_type in documents:
                    addr_field = address_mappings.get(doc_type)
                    if not addr_field:
                        continue
                    addr_value = self._get_field_from_documents(
                        f"{doc_type}.{addr_field}", context
                    )
                    if addr_value:
                        address_values[doc_type] = {
                            "original": addr_value,
                            "normalized": self._normalize_address(str(addr_value))
                        }

                if len(address_values) >= 2:
                    addr_result = self._validate_address_match(
                        party_name, address_values, fuzzy_threshold
                    )
                    results.append(addr_result)

        return results

    def _validate_party_match(
        self,
        party_name: str,
        party_values: Dict[str, Dict[str, str]],
        match_type: str,
        fuzzy_threshold: float
    ) -> ValidationResult:
        """
        Validate that party values match across documents

        Args:
            party_name: Party name (shipper, consignee)
            party_values: Dictionary of {doc_type: {original, normalized}}
            match_type: "exact", "case_insensitive", "fuzzy"
            fuzzy_threshold: Minimum similarity for fuzzy match

        Returns:
            Validation result
        """
        # Get reference value (first document)
        ref_doc = list(party_values.keys())[0]
        ref_value = party_values[ref_doc]["normalized"]

        # Compare all other values to reference
        mismatches = []
        matches = []
        min_similarity = 1.0

        for doc_type, values in party_values.items():
            if doc_type == ref_doc:
                continue

            compare_value = values["normalized"]

            # Perform matching based on type
            if match_type == "exact":
                match = ref_value == compare_value
                similarity = 1.0 if match else 0.0

            elif match_type == "case_insensitive":
                match = ref_value.lower() == compare_value.lower()
                similarity = 1.0 if match else 0.0

            elif match_type == "fuzzy":
                similarity = self._calculate_similarity(ref_value, compare_value)
                match = similarity >= fuzzy_threshold

            else:
                # Default to case-insensitive
                match = ref_value.lower() == compare_value.lower()
                similarity = 1.0 if match else 0.0

            if match:
                matches.append(doc_type)
            else:
                mismatches.append({
                    "document": doc_type,
                    "value": values["original"],
                    "similarity": similarity
                })

            min_similarity = min(min_similarity, similarity)

        # Determine overall result
        if not mismatches:
            # All documents match
            return self._create_result(
                field_name=party_name,
                passed=True,
                message=f"{party_name.title()} matches across all documents",
                severity=Severity.INFO,
                source_value=party_values[ref_doc]["original"],
                target_value=None,
                confidence=min_similarity,
                metadata={
                    "party": party_name,
                    "documents_checked": list(party_values.keys()),
                    "all_values": {k: v["original"] for k, v in party_values.items()},
                    "match_type": match_type
                }
            )
        else:
            # Some documents don't match
            mismatch_docs = [m["document"] for m in mismatches]

            mismatch_str = ', '.join([f"{m['document']}='{m['value']}'" for m in mismatches])
            return self._create_result(
                field_name=party_name,
                passed=False,
                message=(
                    f"{party_name.title()} MISMATCH: "
                    f"{ref_doc} vs {', '.join(mismatch_docs)}. "
                    f"Reference: '{party_values[ref_doc]['original']}', "
                    f"Mismatches: {mismatch_str}"
                ),
                severity=Severity.CRITICAL if len(mismatches) > 1 else Severity.MAJOR,
                source_document=ref_doc,
                source_value=party_values[ref_doc]["original"],
                target_value={m["document"]: m["value"] for m in mismatches},
                confidence=min_similarity,
                metadata={
                    "party": party_name,
                    "reference_document": ref_doc,
                    "reference_value": party_values[ref_doc]["original"],
                    "mismatches": mismatches,
                    "match_type": match_type,
                    "min_similarity": min_similarity
                }
            )

    def _normalize_name(self, name: str) -> str:
        """
        Normalize company/party name for comparison

        Args:
            name: Original name

        Returns:
            Normalized name
        """
        if not name:
            return ""

        # Unwrap field-data dict if not yet unwrapped by normalization
        if isinstance(name, dict) and "value" in name:
            name = str(name["value"])

        # Take first line only — multi-line values have the company name on
        # line 1 followed by postal/physical address on subsequent lines.
        if "\n" in name:
            name = name.split("\n")[0].strip()

        # Strip accents (é → e, ñ → n, etc.) so "Nestlé" and "Nestle" compare equal
        normalized = unicodedata.normalize("NFD", name)
        normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")

        # Strip common postal-address tokens that appear after the company name
        # e.g. "Nestlé Ghana Limited Private Mail Bag" → "Nestlé Ghana Limited"
        _ADDRESS_TOKENS = [
            "private mail bag", "pmb", "p.o. box", "po box", "p o box",
            "post box", "postbox", "mailbox", "mail bag", "postal bag",
            "gpo box", "locked bag",
        ]
        norm_lower = normalized.lower()
        for token in _ADDRESS_TOKENS:
            idx = norm_lower.find(token)
            if idx > 0:  # only strip if token is not at start
                normalized = normalized[:idx].strip()
                norm_lower = normalized.lower()

        # Remove extra whitespace
        if self.remove_whitespace:
            normalized = " ".join(normalized.split())

        # Remove punctuation
        if self.remove_punctuation:
            for char in ".,;:!?()[]{}\"'":
                normalized = normalized.replace(char, " ")
            normalized = " ".join(normalized.split())

        # Convert to lowercase
        if self.lowercase:
            normalized = normalized.lower()

        # Remove company suffixes
        if self.remove_company_suffixes:
            for suffix in self.company_suffixes:
                # Check both lowercase and original case
                for suffix_variant in [suffix, suffix.lower(), suffix.upper()]:
                    if normalized.endswith(" " + suffix_variant):
                        normalized = normalized[:-len(suffix_variant)-1].strip()
                    if normalized.endswith(suffix_variant):
                        normalized = normalized[:-len(suffix_variant)].strip()

        return normalized.strip()

    def _normalize_address(self, address: str) -> str:
        """
        Normalize an address for fuzzy comparison.

        Strips accents, lowercases, removes common noise words (PO Box,
        Private Mail Bag, etc.) and collapses whitespace so that minor
        formatting differences don't cause false mismatches.
        """
        if not address:
            return ""

        # Strip accents
        normalized = unicodedata.normalize("NFD", address)
        normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")

        # Lowercase
        normalized = normalized.lower()

        # Remove noise tokens that vary between documents
        _NOISE = [
            "private mail bag", "pmb", "p.o. box", "po box", "p o box",
            "post box", "postbox", "mail bag", "postal bag", "gpo box",
            "locked bag", "motorway extens", "motorway extension",
        ]
        for token in _NOISE:
            normalized = normalized.replace(token, " ")

        # Remove punctuation
        for char in ".,;:!?()[]{}\"'-":
            normalized = normalized.replace(char, " ")

        # Collapse whitespace
        normalized = " ".join(normalized.split())
        return normalized

    def _validate_address_match(
        self,
        party_name: str,
        address_values: Dict[str, Dict[str, str]],
        fuzzy_threshold: float
    ) -> ValidationResult:
        """
        Validate that address values are consistent across documents.

        Uses a relaxed fuzzy threshold (default 0.5) because addresses often
        differ legitimately between documents (registered vs. delivery address).
        """
        # Addresses are inherently less consistent than names — use a softer threshold
        address_threshold = max(fuzzy_threshold * 0.6, 0.4)

        ref_doc = list(address_values.keys())[0]
        ref_value = address_values[ref_doc]["normalized"]

        mismatches = []
        min_similarity = 1.0

        for doc_type, values in address_values.items():
            if doc_type == ref_doc:
                continue

            similarity = self._calculate_similarity(ref_value, values["normalized"])
            match = similarity >= address_threshold
            min_similarity = min(min_similarity, similarity)

            if not match:
                mismatches.append({
                    "document": doc_type,
                    "value": values["original"],
                    "similarity": round(similarity, 3)
                })

        if not mismatches:
            return self._create_result(
                field_name=f"{party_name}_address",
                passed=True,
                message=f"{party_name.title()} address consistent across documents",
                severity=Severity.INFO,
                source_value=address_values[ref_doc]["original"],
                target_value=None,
                confidence=min_similarity,
                metadata={
                    "party": party_name,
                    "check": "address",
                    "documents_checked": list(address_values.keys())
                }
            )
        else:
            mismatch_str = "; ".join(
                f"{m['document']}='{m['value']}' (sim={m['similarity']})"
                for m in mismatches
            )
            return self._create_result(
                field_name=f"{party_name}_address",
                passed=False,
                message=(
                    f"{party_name.title()} address MISMATCH: "
                    f"Reference ({ref_doc}): '{address_values[ref_doc]['original']}' | "
                    f"Mismatches: {mismatch_str}"
                ),
                severity=Severity.MINOR,  # Address differences are often legitimate
                source_document=ref_doc,
                source_value=address_values[ref_doc]["original"],
                target_value={m["document"]: m["value"] for m in mismatches},
                confidence=min_similarity,
                metadata={
                    "party": party_name,
                    "check": "address",
                    "reference_document": ref_doc,
                    "mismatches": mismatches,
                    "threshold_used": address_threshold
                }
            )

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate text similarity using word overlap (Jaccard)

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score (0-1)
        """
        if not text1 or not text2:
            return 0.0

        # Normalize
        text1 = text1.lower().strip()
        text2 = text2.lower().strip()

        if text1 == text2:
            return 1.0

        # Word-based similarity
        words1 = set(text1.split())
        words2 = set(text2.split())

        if not words1 or not words2:
            return 0.0

        # Jaccard similarity
        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0

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

    def _create_result(
        self,
        field_name: str,
        passed: bool,
        message: str,
        severity: str,
        source_value: Any,
        target_value: Any,
        confidence: float = 1.0,
        metadata: Optional[Dict] = None,
        source_document: Optional[str] = None,
    ) -> ValidationResult:
        """Create a validation result"""
        return ValidationResult(
            validator_name=self.validator_name,
            validator_type=self.validator_type,
            field_name=field_name,
            source_document=source_document,
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
        return field_type in ["string", "text"]

    def get_metadata(self) -> Dict[str, Any]:
        """Return validator metadata"""
        return {
            "name": self.validator_name,
            "type": self.validator_type,
            "description": "Validates shipper and consignee match across multiple documents",
            "parties_validated": [p.get("name") for p in self.parties],
            "config": self.config
        }
