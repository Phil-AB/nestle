"""Normalization engine - orchestrates all normalizers"""

from typing import Dict, Any, List, Optional
from ..normalizers.synonym_mapper import SynonymMapper
from ..normalizers.unit_converter import UnitConverter
from ..normalizers.format_normalizer import FormatNormalizer
from ...core.base import ValidationContext
from ...core.config_loader import get_config_loader
from ...utils.exceptions import NormalizationException
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class NormalizationEngine:
    """
    Main normalization engine

    Orchestrates all normalization steps:
    1. Field name normalization (synonyms)
    2. Format normalization (dates, decimals)
    3. Unit conversion (weights, currencies)
    4. Whitespace normalization
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize normalization engine

        Args:
            config: Normalization configuration
        """
        self.config = config or {}

        # Load normalization config
        config_loader = get_config_loader()
        self.norm_config = config_loader.load_normalization_config()

        # Initialize normalizers
        self.synonym_mapper = SynonymMapper(self.norm_config)
        self.unit_converter = UnitConverter(self.norm_config)
        self.format_normalizer = FormatNormalizer(self.norm_config)

        # Settings
        self.enabled = self.norm_config.get("enabled", True)
        self.strategy = self.norm_config.get("strategy", "hybrid")

        logger.info(f"NormalizationEngine initialized (strategy: {self.strategy})")

    async def normalize_documents(
        self,
        documents: Dict[str, Dict[str, Any]],
        context: Optional[ValidationContext] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Normalize all documents

        Args:
            documents: Documents to normalize {doc_type: doc_data}
            context: Optional validation context

        Returns:
            Normalized documents
        """
        if not self.enabled:
            return documents

        normalized_docs = {}

        for doc_type, doc_data in documents.items():
            try:
                normalized = await self.normalize_document(
                    document=doc_data,
                    document_type=doc_type,
                    context=context
                )
                normalized_docs[doc_type] = normalized

                logger.info(f"Normalized document: {doc_type}")

            except Exception as e:
                logger.error(f"Normalization failed for {doc_type}: {str(e)}")
                # Return original document on error
                normalized_docs[doc_type] = doc_data

        return normalized_docs

    async def normalize_document(
        self,
        document: Dict[str, Any],
        document_type: Optional[str] = None,
        context: Optional[ValidationContext] = None
    ) -> Dict[str, Any]:
        """
        Normalize a single document

        Args:
            document: Document to normalize
            document_type: Optional document type
            context: Optional validation context

        Returns:
            Normalized document
        """
        if not self.enabled:
            return document

        # Step 1: Normalize field names (synonyms)
        normalized = self.synonym_mapper.map_document_fields(
            document=document,
            document_type=document_type
        )

        # Step 2: Normalize field values
        normalized = await self._normalize_field_values(normalized, document_type)

        return normalized

    async def _normalize_field_values(
        self,
        document: Dict[str, Any],
        document_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Normalize field values (formats, units)

        Args:
            document: Document with normalized field names
            document_type: Optional document type

        Returns:
            Document with normalized field values
        """
        normalized = {}

        # Pre-read the document-level weight_unit so bare numeric weight fields
        # (e.g. gross_weight=28.02 with weight_unit="TNE" as a separate field)
        # can be converted even when the unit is not embedded in the value string.
        raw_wu = document.get("weight_unit")
        if isinstance(raw_wu, dict):
            raw_wu = raw_wu.get("value")
        doc_weight_unit = raw_wu.strip().upper() if isinstance(raw_wu, str) and raw_wu else None

        for field_name, value in document.items():
            try:
                # Detect field type and normalize accordingly
                normalized_value = await self._normalize_field_value(
                    field_name=field_name,
                    value=value,
                    document_type=document_type,
                    doc_weight_unit=doc_weight_unit,
                )
                normalized[field_name] = normalized_value

            except Exception as e:
                logger.warning(
                    f"Failed to normalize field '{field_name}': {str(e)}. "
                    f"Using original value."
                )
                normalized[field_name] = value

        return normalized

    async def _normalize_field_value(
        self,
        field_name: str,
        value: Any,
        document_type: Optional[str] = None,
        doc_weight_unit: Optional[str] = None,
    ) -> Any:
        """
        Normalize a single field value based on field type

        Args:
            field_name: Field name
            value: Field value
            document_type: Optional document type
            doc_weight_unit: Document-level weight unit (e.g. "TNE") for bare numeric weights

        Returns:
            Normalized value
        """
        # Skip None values
        if value is None:
            return value

        # Unwrap Reducto field-data dicts: {"value": "...", "original_label": ..., "bbox": ...}
        # The parser returns KV-extracted fields as dicts with a "value" key carrying the
        # actual content. Unwrap here so all downstream normalisers see plain scalars.
        # Exception: redacted markers {"value": null, "redacted": true} must be preserved
        # so that downstream validators can distinguish "field is absent" from "field is
        # present but physically redacted on the document".
        if isinstance(value, dict) and "value" in value:
            if value.get("redacted") is True:
                return value  # preserve redacted marker intact
            value = value["value"]
            if value is None:
                return None

        # Detect field type from name
        field_lower = field_name.lower()

        # Weight fields
        if any(w in field_lower for w in ["weight", "poids"]):
            return await self._normalize_weight_field(value, doc_weight_unit)

        # Currency/price fields
        if any(c in field_lower for c in ["price", "prix", "amount", "montant", "value", "valeur", "cost", "coût"]):
            return self._normalize_currency_field(value)

        # Date fields
        if any(d in field_lower for d in ["date", "datetime"]):
            return self._normalize_date_field(value)

        # Quantity fields
        if any(q in field_lower for q in ["quantity", "quantité", "qty"]):
            return self._normalize_numeric_field(value)

        # Rate/percentage fields
        if any(r in field_lower for r in ["rate", "taux", "percent"]):
            return self._normalize_numeric_field(value)

        # Boolean fields
        if field_lower in ["active", "enabled", "disabled", "required"]:
            return self._normalize_boolean_field(value)

        # String fields - normalize whitespace
        if isinstance(value, str):
            # For name/party fields: take only the first line so that multi-line
            # address blocks ("Nestlé Ghana Limited\nSanyo Road\nTEMA\nGHANA")
            # are reduced to just the company name before whitespace collapsing.
            NAME_KEYWORDS = ["name", "nom", "party", "shipper", "consignee",
                             "exporter", "importer", "expediteur", "destinataire"]
            if any(n in field_lower for n in NAME_KEYWORDS) and "\n" in value:
                value = value.split("\n")[0].strip()
            return self.format_normalizer.normalize_whitespace(value)

        # Default - return as is
        return value

    async def _normalize_weight_field(self, value: Any, doc_weight_unit: Optional[str] = None) -> Any:
        """Normalize weight field"""
        # Extract unit and value
        # Format: "1000 KG", "189.000,00 kg", "189,000.000", or 1000
        if isinstance(value, str):
            parts = value.strip().split()
            if len(parts) >= 2:
                # Last token might be a unit; numeric portion is everything before it
                unit = parts[-1].upper()
                raw_num = " ".join(parts[:-1])
                try:
                    # Parse the numeric string with the smart decimal heuristic
                    parsed = self.format_normalizer.normalize_decimal(raw_num)
                    # Only attempt unit conversion for non-KG units
                    if unit != "KG":
                        return float(await self.unit_converter.convert_weight(str(parsed), unit))
                    return float(parsed)
                except Exception:
                    pass

        # No embedded unit — try document-level unit if available
        if doc_weight_unit and doc_weight_unit != "KG":
            try:
                parsed = self.format_normalizer.normalize_decimal(value)
                return float(await self.unit_converter.convert_weight(str(parsed), doc_weight_unit))
            except Exception:
                pass

        # No unit or already numeric — normalize as decimal
        try:
            return float(self.format_normalizer.normalize_decimal(value))
        except Exception:
            return value

    def _normalize_currency_field(self, value: Any) -> Any:
        """Normalize currency field"""
        try:
            return float(self.format_normalizer.normalize_currency(value))
        except:
            return value

    def _normalize_date_field(self, value: Any) -> str:
        """Normalize date field"""
        try:
            return self.format_normalizer.normalize_date(value)
        except:
            return str(value)

    def _normalize_numeric_field(self, value: Any) -> Any:
        """Normalize numeric field"""
        try:
            return float(self.format_normalizer.normalize_decimal(value))
        except:
            return value

    def _normalize_boolean_field(self, value: Any) -> bool:
        """Normalize boolean field"""
        try:
            return self.format_normalizer.normalize_boolean(value)
        except:
            return bool(value)

    def get_normalization_stats(self) -> Dict[str, Any]:
        """
        Get normalization statistics

        Returns:
            Dictionary with statistics
        """
        return {
            "enabled": self.enabled,
            "strategy": self.strategy,
            "synonym_mapper": self.synonym_mapper.get_mapping_stats(),
            "normalizers": {
                "synonym_mapper": "active",
                "unit_converter": "active",
                "format_normalizer": "active"
            }
        }

    def clear_caches(self):
        """Clear all normalization caches"""
        self.synonym_mapper.clear_cache()
        self.unit_converter.clear_cache()
        logger.info("Normalization caches cleared")


# Singleton instance
_normalization_engine_instance: Optional[NormalizationEngine] = None


def get_normalization_engine() -> NormalizationEngine:
    """
    Get singleton normalization engine instance

    Returns:
        NormalizationEngine instance
    """
    global _normalization_engine_instance
    if _normalization_engine_instance is None:
        _normalization_engine_instance = NormalizationEngine()
    return _normalization_engine_instance
