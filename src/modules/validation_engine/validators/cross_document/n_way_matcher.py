"""N-way matcher for multi-document field comparison"""

from typing import Dict, Any, List, Optional
from ...core.base import IValidator, ValidationResult, ValidationContext
from ...validators.validator_registry import ValidatorRegistry
from ...utils.constants import ValidatorType, Severity, MatchType
from shared.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Fuzzy similarity — use rapidfuzz when available, fall back to stdlib difflib
# ---------------------------------------------------------------------------
try:
    from rapidfuzz import fuzz as _fuzz

    def _similarity(a: str, b: str) -> float:
        """Return similarity score in [0, 1] using rapidfuzz token_set_ratio."""
        return _fuzz.token_set_ratio(a, b) / 100.0

    _FUZZY_BACKEND = "rapidfuzz"
except ImportError:
    import difflib

    def _similarity(a: str, b: str) -> float:
        """Return similarity score in [0, 1] using stdlib SequenceMatcher."""
        return difflib.SequenceMatcher(None, a, b).ratio()

    _FUZZY_BACKEND = "difflib"

logger.debug(f"NWayMatcher fuzzy backend: {_FUZZY_BACKEND}")

# Default similarity threshold when match_type is "fuzzy"
_DEFAULT_FUZZY_THRESHOLD = 0.7


@ValidatorRegistry.register("n_way_matcher")
class NWayMatcher(IValidator):
    """
    Validates that a field has the same (or sufficiently similar) value across
    N documents.

    Critical for vendor document validation where the same field may appear
    under different labels or in abbreviated forms across invoice, packing
    list, and bill of lading.

    Config:
        field_name (str):
            Canonical field name to match.
        documents (list[str]):
            Document types to compare, e.g. ["invoice", "packing_list", "bill_of_lading"].
        match_type (str):
            How to compare values. Options:
              - "exact"            — byte-identical (default)
              - "case_insensitive" — lower-cased before comparison
              - "normalized"       — whitespace/case normalised; comma-lists sorted
              - "incoterm"         — compare only the 3-letter Incoterm code
              - "fuzzy"            — similarity threshold comparison via rapidfuzz
                                     (falls back to difflib when rapidfuzz absent)
        fuzzy_threshold (float):
            Minimum similarity score [0–1] for a fuzzy match to pass.
            Only used when match_type is "fuzzy". Default: 0.7.
        require_all (bool):
            If true, all listed documents must have the field; otherwise
            the check is skipped gracefully when fewer than 2 docs have it.
            Default: true.
        line_items (bool):
            When true, match the field across line-item arrays instead of
            header fields. Default: false.

    Example config (header-level fuzzy):
        field_name: "product_description"
        documents: ["invoice", "packing_list", "bill_of_lading"]
        match_type: "fuzzy"
        fuzzy_threshold: 0.65
        require_all: false

    Example config (exact cross-document):
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
        self.fuzzy_threshold = float(config.get("fuzzy_threshold", _DEFAULT_FUZZY_THRESHOLD))
        self.require_all = config.get("require_all", True)
        self.line_items = config.get("line_items", False)

        logger.debug(
            f"NWayMatcher initialised: field='{self.field_name}', "
            f"docs={self.documents}, match_type={self.match_type}, "
            f"fuzzy_threshold={self.fuzzy_threshold}, require_all={self.require_all}"
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def validate(
        self,
        source_data: Dict[str, Any],
        target_data: Optional[Dict[str, Any]],
        context: ValidationContext,
    ) -> List[ValidationResult]:
        """Dispatch to header-field or line-item validation mode."""
        if self.line_items:
            return self._validate_line_items(context)
        return self._validate_header_field(context)

    # ------------------------------------------------------------------
    # Header-level validation
    # ------------------------------------------------------------------

    def _validate_header_field(self, context: ValidationContext) -> List[ValidationResult]:
        """Validate a single header-level field across N documents."""

        field_values: Dict[str, Any] = {}
        missing_docs: List[str] = []

        for doc_type in self.documents:
            doc_data = context.documents.get(doc_type)
            if not doc_data:
                missing_docs.append(doc_type)
                continue

            value = self._resolve_field(doc_data, self.field_name)

            if value is None:
                if self.require_all:
                    missing_docs.append(doc_type)
            else:
                field_values[doc_type] = value

        # --- Missing required documents/fields ---
        if missing_docs and self.require_all:
            return [ValidationResult(
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
                ),
            )]

        # --- Not enough data to cross-validate ---
        if len(field_values) < 2:
            severity = Severity.INFO if not self.require_all else Severity.MINOR
            passed = not self.require_all
            return [ValidationResult(
                validator_name=self.validator_name,
                validator_type=self.validator_type,
                field_name=self.field_name,
                source_value=None,
                target_value=None,
                passed=passed,
                confidence=0.5,
                severity=severity,
                message=(
                    f"Field '{self.field_name}' present in only "
                    f"{len(field_values)} document(s) — skipping cross-validation"
                ),
            )]

        # --- Compare ---
        return self._compare_values(field_values)

    def _compare_values(
        self, field_values: Dict[str, Any]
    ) -> List[ValidationResult]:
        """
        Compare field values across documents using the configured match type.

        For fuzzy matching, every pair of documents is compared individually
        and the check passes only when ALL pairs meet the similarity threshold.
        For all other match types, normalised values are compared for equality.
        """
        if self.match_type == MatchType.FUZZY:
            return self._compare_fuzzy(field_values)

        # Deterministic normalisation + equality
        normalized: Dict[str, Any] = {
            doc: self._normalize_value(val, self.match_type)
            for doc, val in field_values.items()
        }
        unique = set(normalized.values())

        if len(unique) == 1:
            return [ValidationResult(
                validator_name=self.validator_name,
                validator_type=self.validator_type,
                field_name=self.field_name,
                source_value=list(field_values.values())[0],
                target_value=None,
                passed=True,
                confidence=1.0,
                severity=Severity.INFO,
                message=(
                    f"'{self.field_name}' matches across "
                    f"{', '.join(field_values.keys())}"
                ),
                metadata={
                    "documents": list(field_values.keys()),
                    "value": list(unique)[0],
                },
            )]

        mismatches = self._identify_mismatches(field_values, normalized)
        return [ValidationResult(
            validator_name=self.validator_name,
            validator_type=self.validator_type,
            field_name=self.field_name,
            source_value=field_values,
            target_value=None,
            passed=False,
            confidence=0.9,
            severity=self.get_severity({}),
            message=(
                f"'{self.field_name}' mismatch across documents — "
                f"{len(unique)} distinct values found."
            ),
            discrepancy={
                "field_name": self.field_name,
                "documents": list(field_values.keys()),
                "values": field_values,
                "unique_values": list(unique),
                "mismatches": mismatches,
            },
        )]

    def _compare_fuzzy(
        self, field_values: Dict[str, Any]
    ) -> List[ValidationResult]:
        """
        Pairwise fuzzy comparison across all document combinations.

        Each pair is scored with rapidfuzz token_set_ratio (or difflib as
        fallback).  The result passes when every pair exceeds the configured
        threshold.  The minimum pairwise score is reported as confidence so
        the reviewer can see exactly how close the weakest pair was.
        """
        docs = list(field_values.keys())
        pairs_checked: List[Dict[str, Any]] = []
        min_score = 1.0
        all_passed = True

        for i in range(len(docs)):
            for j in range(i + 1, len(docs)):
                doc_a, doc_b = docs[i], docs[j]
                val_a = str(field_values[doc_a]).strip().lower()
                val_b = str(field_values[doc_b]).strip().lower()

                score = _similarity(val_a, val_b)
                passed = score >= self.fuzzy_threshold
                min_score = min(min_score, score)
                if not passed:
                    all_passed = False

                pairs_checked.append({
                    "doc_a": doc_a,
                    "doc_b": doc_b,
                    "value_a": field_values[doc_a],
                    "value_b": field_values[doc_b],
                    "similarity": round(score, 4),
                    "threshold": self.fuzzy_threshold,
                    "passed": passed,
                })

        if all_passed:
            return [ValidationResult(
                validator_name=self.validator_name,
                validator_type=self.validator_type,
                field_name=self.field_name,
                source_value=field_values,
                target_value=None,
                passed=True,
                confidence=round(min_score, 4),
                severity=Severity.INFO,
                message=(
                    f"'{self.field_name}' is semantically consistent across "
                    f"{', '.join(docs)} "
                    f"(min similarity: {min_score:.0%}, threshold: {self.fuzzy_threshold:.0%})"
                ),
                metadata={
                    "match_type": "fuzzy",
                    "backend": _FUZZY_BACKEND,
                    "fuzzy_threshold": self.fuzzy_threshold,
                    "pairs": pairs_checked,
                },
            )]

        failing = [p for p in pairs_checked if not p["passed"]]
        return [ValidationResult(
            validator_name=self.validator_name,
            validator_type=self.validator_type,
            field_name=self.field_name,
            source_value=field_values,
            target_value=None,
            passed=False,
            confidence=round(min_score, 4),
            severity=self.get_severity({}),
            message=(
                f"'{self.field_name}' descriptions are too dissimilar across documents "
                f"(min similarity: {min_score:.0%}, threshold: {self.fuzzy_threshold:.0%}). "
                f"{len(failing)} pair(s) failed."
            ),
            discrepancy={
                "field_name": self.field_name,
                "match_type": "fuzzy",
                "backend": _FUZZY_BACKEND,
                "fuzzy_threshold": self.fuzzy_threshold,
                "failing_pairs": failing,
                "all_pairs": pairs_checked,
            },
        )]

    # ------------------------------------------------------------------
    # Line-item validation
    # ------------------------------------------------------------------

    def _validate_line_items(self, context: ValidationContext) -> List[ValidationResult]:
        """
        Validate a field across line items in N documents.

        Items are matched by HS code (primary key) with positional fallback.
        One ValidationResult is emitted per matched item group.
        """
        results: List[ValidationResult] = []

        doc_items: Dict[str, List[Dict[str, Any]]] = {}
        for doc_type in self.documents:
            doc_data = context.documents.get(doc_type)
            if not doc_data:
                if self.require_all:
                    return [ValidationResult(
                        validator_name=self.validator_name,
                        validator_type=self.validator_type,
                        field_name=self.field_name,
                        source_value=None,
                        target_value=None,
                        passed=False,
                        confidence=1.0,
                        severity=self.get_severity({}),
                        message=f"Document '{doc_type}' not found for line-item validation",
                    )]
                continue

            items = doc_data.get("items", [])
            doc_items[doc_type] = items if isinstance(items, list) else []

        if len(doc_items) < 2:
            return [ValidationResult(
                validator_name=self.validator_name,
                validator_type=self.validator_type,
                field_name=self.field_name,
                source_value=None,
                target_value=None,
                passed=False,
                confidence=0.5,
                severity=Severity.MINOR,
                message=f"Line-item validation for '{self.field_name}' requires at least 2 documents",
            )]

        ref_doc = list(doc_items.keys())[0]
        ref_items = doc_items[ref_doc]

        def _hs_key(item: Dict[str, Any]) -> Optional[str]:
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
                matched = (
                    next((it for it in items if _hs_key(it) == ref_hs), None)
                    if ref_hs else None
                )
                if matched is None and idx < len(items):
                    matched = items[idx]
                if matched is not None:
                    field_values[doc_type] = matched.get(self.field_name)

            comparable = {d: v for d, v in field_values.items() if v is not None}

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
                    metadata={"item_index": idx, "hs_code": ref_hs},
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
                    f"'{self.field_name}' "
                    f"{'matches' if passed else 'mismatch'} across "
                    f"{', '.join(comparable.keys())}"
                ),
                discrepancy=None if passed else {
                    "field_name": self.field_name,
                    "item_index": idx,
                    "hs_code": ref_hs,
                    "values": comparable,
                    "unique_values": list(unique),
                },
                metadata={"item_index": idx, "hs_code": ref_hs},
            ))

            if not passed:
                logger.warning(
                    f"Line-item {idx + 1} '{self.field_name}' mismatch "
                    f"(HS: {ref_hs}): {comparable}"
                )

        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_field(doc_data: Dict[str, Any], field_name: str) -> Any:
        """
        Resolve a field value from a document dict.

        Checks top-level fields first.  If the field is absent there, falls
        back to items[0] — some fields (e.g. product_description) are only
        present in line-item rows after extraction.
        """
        value = doc_data.get(field_name)
        if value is None:
            items = doc_data.get("items") or []
            if items and isinstance(items[0], dict):
                value = items[0].get(field_name)
        return value

    @staticmethod
    def _normalize_value(value: Any, match_type: str) -> Any:
        """
        Normalize a value for deterministic equality comparison.

        Note: fuzzy matching does NOT use this method — it operates directly
        on the raw string values via _compare_fuzzy / _similarity.
        """
        # Coerce numeric-like values to a canonical form so that 2, 2.0, and
        # "2" all compare equal regardless of how different extractors typed them.
        if isinstance(value, float) and value == int(value):
            value = int(value)
        elif isinstance(value, str):
            try:
                f = float(value)
                value = int(f) if f == int(f) else f
            except (ValueError, OverflowError):
                pass

        if match_type == MatchType.EXACT:
            return value

        if not isinstance(value, str):
            return value

        if match_type == MatchType.CASE_INSENSITIVE:
            return value.lower()

        if match_type == "normalized":
            # Normalise whitespace and case.
            # For comma-separated lists (e.g. container IDs), sort tokens so
            # order differences don't cause false-positive mismatches.
            stripped = value.strip()
            if "," in stripped:
                tokens = sorted(
                    t.strip().upper() for t in stripped.split(",") if t.strip()
                )
                return ",".join(tokens)
            return " ".join(value.lower().split())

        if match_type == "incoterm":
            # Compare only the 3-letter Incoterm code, ignoring the port.
            # e.g. "FCA ROTTERDAM PORT" and "FCA TEMA" both → "FCA"
            import re as _re
            m = _re.match(r'([A-Z]{3})', value.strip().upper())
            return m.group(1) if m else value.upper().strip()

        # Unknown match types: return value unchanged so they don't silently pass.
        return value

    @staticmethod
    def _identify_mismatches(
        original_values: Dict[str, Any],
        normalized_values: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Group documents by their normalised value and return mismatch details."""
        value_groups: Dict[Any, List[str]] = {}
        for doc, norm_value in normalized_values.items():
            value_groups.setdefault(norm_value, []).append(doc)

        return [
            {
                "normalized_value": norm_value,
                "documents": docs,
                "original_values": {d: original_values[d] for d in docs},
            }
            for norm_value, docs in value_groups.items()
        ]

    def supports_field_type(self, field_type: str) -> bool:
        return True
