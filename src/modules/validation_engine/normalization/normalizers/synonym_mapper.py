"""Synonym mapper for field name resolution"""

from typing import Dict, Any, Optional, List, Set
from difflib import SequenceMatcher
from ...core.config_loader import get_config_loader
from ...utils.exceptions import NormalizationException
from shared.utils.logger import get_logger
from shared.utils.llm_config import get_llm_for_module

logger = get_logger(__name__)


class SynonymMapper:
    """
    Maps field name variations to canonical names

    Handles:
    - French ↔ English translations (Poids Net → net_weight)
    - Case variations (NetWeight → net_weight)
    - Formatting differences (net_weight → NetWeight)

    Strategy:
    1. Try exact match (fast)
    2. Try case-insensitive match
    3. Try config synonym lookup
    4. Try fuzzy matching (similarity > 0.85)
    5. Try LLM semantic matching (if enabled)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize synonym mapper

        Args:
            config: Normalization configuration
        """
        self.config = config or {}

        # Load normalization config
        config_loader = get_config_loader()
        norm_config = config_loader.load_normalization_config()

        # Synonym mapping settings
        self.synonym_config = norm_config.get("synonym_mapping", {})
        self.enabled = self.synonym_config.get("enabled", True)

        # LLM fallback settings
        llm_fallback_config = self.synonym_config.get("llm_fallback", {})
        self.llm_enabled = llm_fallback_config.get("enabled", False)
        self.llm_provider = llm_fallback_config.get("provider", "google")
        self.llm_model = llm_fallback_config.get("model", "default")
        self.llm_confidence_threshold = llm_fallback_config.get("confidence_threshold", 0.8)
        self.cache_llm_results = llm_fallback_config.get("cache_successful_mappings", True)

        # Build synonym dictionary
        self.synonyms = norm_config.get("synonym_mapping", {}).get("synonyms", {})

        # Build reverse lookup (synonym -> canonical)
        self.reverse_lookup: Dict[str, str] = {}
        self._build_reverse_lookup()

        # Cache for performance
        self.cache: Dict[str, str] = {}

        logger.info(
            f"SynonymMapper initialized with {len(self.synonyms)} canonical fields, "
            f"{len(self.reverse_lookup)} total synonyms"
        )

    def _build_reverse_lookup(self):
        """Build reverse lookup dictionary: synonym -> canonical name"""
        for canonical, synonym_list in self.synonyms.items():
            # Add canonical name itself
            self.reverse_lookup[canonical] = canonical
            self.reverse_lookup[canonical.lower()] = canonical

            # Add all synonyms
            for synonym in synonym_list:
                self.reverse_lookup[synonym] = canonical
                self.reverse_lookup[synonym.lower()] = canonical

    def map_field_name(
        self,
        field_name: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Map field name to canonical name

        Args:
            field_name: Field name to map
            context: Optional context (document type, etc.)

        Returns:
            Canonical field name (or original if no mapping found)
        """
        if not self.enabled:
            return field_name

        # Check cache first
        if field_name in self.cache:
            return self.cache[field_name]

        # Step 1: Exact match in reverse lookup
        if field_name in self.reverse_lookup:
            canonical = self.reverse_lookup[field_name]
            self.cache[field_name] = canonical
            return canonical

        # Step 2: Case-insensitive match
        field_lower = field_name.lower()
        if field_lower in self.reverse_lookup:
            canonical = self.reverse_lookup[field_lower]
            self.cache[field_name] = canonical
            return canonical

        # Step 3: Fuzzy matching (similarity > 0.85)
        fuzzy_match = self._fuzzy_match(field_name)
        if fuzzy_match:
            self.cache[field_name] = fuzzy_match
            return fuzzy_match

        # Step 4: LLM matching is handled in batch by map_document_fields.
        # If called standalone, fall through to return original.

        # No mapping found - return original
        logger.debug("No synonym mapping found for field: %s", field_name)
        return field_name

    def map_document_fields(
        self,
        document: Dict[str, Any],
        document_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Map all field names in a document to canonical names.

        Runs exact/fuzzy matching per field first, then sends ALL remaining
        unmatched fields to the LLM in a single batched request instead of
        one call per field.
        """
        if not self.enabled:
            return document

        context = {"document_type": document_type} if document_type else None
        normalized = {}
        unmatched: Dict[str, str] = {}  # original_name -> field_name key

        # Track which canonical fields were set by a DIRECT canonical-name match.
        # A canonical field (e.g. "customs_code" -> "customs_code") always beats a
        # synonym mapping (e.g. "container_nos_chassis_nos" -> "customs_code").
        canonical_set_directly: set = set()

        def _unwrap(v: Any) -> Any:
            return v.get("value") if isinstance(v, dict) and "value" in v else v

        def _is_empty(v: Any) -> bool:
            raw = _unwrap(v)
            return raw is None or str(raw).strip() in ("", "<empty>", "-", "—")

        def _set(canonical: str, value: Any, is_direct: bool = False) -> None:
            """
            Set a canonical field value with priority rules:
            - Direct canonical-name match always overwrites a synonym-mapped value.
            - Synonym mapping only writes if the field is not yet set or is empty.
            """
            if is_direct:
                # Only overwrite another direct mapping if the existing is empty
                if canonical in canonical_set_directly:
                    if _is_empty(normalized.get(canonical)) and not _is_empty(value):
                        normalized[canonical] = value
                else:
                    # This direct field takes priority over any prior synonym mapping
                    normalized[canonical] = value
                    canonical_set_directly.add(canonical)
            else:
                # Synonym mapping: only fill if not already set by a direct match or non-empty
                if canonical in canonical_set_directly:
                    return  # direct match already won — don't overwrite
                existing = normalized.get(canonical)
                if _is_empty(existing) and not _is_empty(value):
                    normalized[canonical] = value
                elif canonical not in normalized:
                    normalized[canonical] = value

        for field_name, value in document.items():
            # Canonical fields (field_name IS the canonical name) get direct priority
            is_canonical_self = (
                field_name in self.synonyms or field_name.lower() in self.synonyms
            )

            # Cache hit
            if field_name in self.cache:
                canonical = self.cache[field_name]
                _set(canonical, value, is_direct=(canonical == field_name or canonical == field_name.lower()))
                continue

            # Exact match
            if field_name in self.reverse_lookup:
                canonical = self.reverse_lookup[field_name]
                self.cache[field_name] = canonical
                _set(canonical, value, is_direct=(canonical == field_name))
                continue

            # Case-insensitive match
            field_lower = field_name.lower()
            if field_lower in self.reverse_lookup:
                canonical = self.reverse_lookup[field_lower]
                self.cache[field_name] = canonical
                _set(canonical, value, is_direct=(canonical == field_lower))
                continue

            # Fuzzy match
            fuzzy = self._fuzzy_match(field_name)
            if fuzzy:
                self.cache[field_name] = fuzzy
                _set(fuzzy, value, is_direct=False)
                continue

            # Needs LLM — collect for batch
            unmatched[field_name] = value

        # Single batched LLM call for all unmatched fields
        if unmatched and self.llm_enabled:
            llm_mappings = self._llm_match_batch(list(unmatched.keys()), context)
            for field_name, value in unmatched.items():
                canonical = llm_mappings.get(field_name)
                if canonical:
                    self.cache[field_name] = canonical
                    _set(canonical, value, is_direct=(canonical == field_name))
                else:
                    _set(field_name, value, is_direct=True)  # unmatched stays as-is
        else:
            for field_name, value in unmatched.items():
                _set(field_name, value, is_direct=True)  # unmatched stays as-is

        return normalized

    def _fuzzy_match(self, field_name: str, threshold: float = 0.85) -> Optional[str]:
        """
        Find fuzzy match using string similarity

        Args:
            field_name: Field name to match
            threshold: Similarity threshold (0.0-1.0)

        Returns:
            Canonical name if match found, None otherwise
        """
        best_match = None
        best_score = 0.0

        # Compare with all known synonyms
        field_lower = field_name.lower()

        for synonym, canonical in self.reverse_lookup.items():
            # Calculate similarity
            similarity = SequenceMatcher(None, field_lower, synonym.lower()).ratio()

            if similarity > best_score and similarity >= threshold:
                best_score = similarity
                best_match = canonical

        if best_match:
            logger.debug(
                f"Fuzzy match found: '{field_name}' → '{best_match}' "
                f"(similarity: {best_score:.2%})"
            )

        return best_match

    def _llm_match(
        self,
        field_name: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Use LLM to find semantic match

        Args:
            field_name: Field name to match
            context: Optional context

        Returns:
            Canonical name if match found, None otherwise
        """
        try:
            # Get available canonical fields
            canonical_fields = list(self.synonyms.keys())

            # Build prompt
            prompt = self._build_llm_prompt(field_name, canonical_fields, context)

            # Get LLM via centralized config (resolves provider/variant → real model ID)
            llm = get_llm_for_module("synonym_mapper")

            # Query LLM
            result = llm.invoke(prompt)
            response = result.content if hasattr(result, "content") else str(result)

            # Parse response
            canonical, confidence = self._parse_llm_response(response, canonical_fields)

            if canonical and confidence >= self.llm_confidence_threshold:
                logger.info(
                    f"LLM match found: '{field_name}' → '{canonical}' "
                    f"(confidence: {confidence:.2%})"
                )

                # Cache successful mapping
                if self.cache_llm_results:
                    pass

                return canonical

            return None

        except Exception as e:
            logger.error(f"LLM matching failed for '{field_name}': {str(e)}")
            return None

    def _llm_match_batch(
        self,
        field_names: List[str],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Optional[str]]:
        """
        Send all unmatched field names to the LLM in one request.
        Returns a dict mapping original field name → canonical name (or None).
        """
        if not field_names:
            return {}
        try:
            canonical_fields = list(self.synonyms.keys())
            prompt = self._build_batch_prompt(field_names, canonical_fields, context)
            llm = get_llm_for_module("synonym_mapper")
            result = llm.invoke(prompt)
            response = result.content if hasattr(result, "content") else str(result)
            logger.info(f"LLM batch response (first 800 chars): {response[:800]}")
            return self._parse_batch_response(response, field_names, canonical_fields)
        except Exception as e:
            logger.error(f"Batch LLM matching failed: {e}")
            return {}

    def _build_batch_prompt(
        self,
        field_names: List[str],
        canonical_fields: List[str],
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build a single prompt covering all unmatched fields."""
        context_str = ""
        if context and context.get("document_type"):
            context_str = f"\nDocument type: {context['document_type']}"

        fields_list = "\n".join(f"  - {f}" for f in field_names)
        canonical_list = ", ".join(canonical_fields)

        return f"""Map each of the following extracted field names to its canonical equivalent.{context_str}

Extracted fields to map:
{fields_list}

Canonical field names:
{canonical_list}

For each extracted field, output one line:
FIELD: <extracted_name> | MATCH: <canonical_name> | CONFIDENCE: <0.0-1.0>

If no good match exists for a field, output:
FIELD: <extracted_name> | NO_MATCH

Rules:
- Consider semantic meaning, language translations (French/Arabic ↔ English), abbreviations.
- Only use names from the canonical list.
- Output exactly one line per input field, in the same order."""

    def _parse_batch_response(
        self,
        response: str,
        field_names: List[str],
        canonical_fields: List[str]
    ) -> Dict[str, Optional[str]]:
        """Parse the batched LLM response into a field→canonical mapping."""
        results: Dict[str, Optional[str]] = {f: None for f in field_names}

        for line in response.strip().splitlines():
            line = line.strip()
            if not line.startswith("FIELD:"):
                continue
            try:
                parts = [p.strip() for p in line.split("|")]
                original = parts[0].replace("FIELD:", "").strip()
                if "NO_MATCH" in line:
                    results[original] = None
                    continue
                match_part = next((p for p in parts if p.startswith("MATCH:")), None)
                conf_part = next((p for p in parts if p.startswith("CONFIDENCE:")), None)
                if not match_part:
                    continue
                canonical = match_part.replace("MATCH:", "").strip()
                confidence = float(conf_part.replace("CONFIDENCE:", "").strip()) if conf_part else 0.0
                if canonical in canonical_fields and confidence >= self.llm_confidence_threshold:
                    results[original] = canonical
                    logger.info(f"LLM batch match: '{original}' → '{canonical}' ({confidence:.0%})")
            except Exception:
                continue

        return results

    def _build_llm_prompt(
        self,
        field_name: str,
        canonical_fields: List[str],
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build prompt for single-field LLM matching (kept for standalone use)."""
        context_str = ""
        if context and context.get("document_type"):
            context_str = f"\nDocument type: {context['document_type']}"

        return f"""Given the field name "{field_name}", which of these canonical fields is the best match?{context_str}

Canonical fields:
{', '.join(canonical_fields)}

Respond with:
MATCH: <canonical_field_name>
CONFIDENCE: <0.0-1.0>

Or if no match:
NO_MATCH"""

    def _parse_llm_response(
        self,
        response: str,
        canonical_fields: List[str]
    ) -> tuple[Optional[str], float]:
        """
        Parse LLM response to extract match and confidence

        Returns:
            Tuple of (canonical_name, confidence)
        """
        lines = response.strip().split("\n")

        canonical = None
        confidence = 0.0

        for line in lines:
            line = line.strip()

            if line.startswith("NO_MATCH"):
                return None, 0.0

            if line.startswith("MATCH:"):
                canonical = line.replace("MATCH:", "").strip()

                # Validate it's a real canonical field
                if canonical not in canonical_fields:
                    logger.warning(f"LLM returned invalid canonical field: {canonical}")
                    return None, 0.0

            if line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.replace("CONFIDENCE:", "").strip())
                except ValueError:
                    confidence = 0.0

        return canonical, confidence

    def get_mapping_stats(self) -> Dict[str, Any]:
        """
        Get synonym mapping statistics

        Returns:
            Dictionary with mapping statistics
        """
        return {
            "canonical_fields": len(self.synonyms),
            "total_synonyms": len(self.reverse_lookup),
            "cached_mappings": len(self.cache),
            "llm_enabled": self.llm_enabled,
            "enabled": self.enabled
        }

    def clear_cache(self):
        """Clear mapping cache"""
        self.cache.clear()
        logger.info("Synonym mapping cache cleared")

    def add_synonym(self, canonical: str, synonym: str):
        """
        Add a new synonym mapping

        Args:
            canonical: Canonical field name
            synonym: Synonym to add
        """
        if canonical not in self.synonyms:
            self.synonyms[canonical] = []

        if synonym not in self.synonyms[canonical]:
            self.synonyms[canonical].append(synonym)
            self.reverse_lookup[synonym] = canonical
            self.reverse_lookup[synonym.lower()] = canonical

            logger.info(f"Added synonym: '{synonym}' → '{canonical}'")
