"""
Dynamic schema generator from configuration.

Generates universal provider-agnostic schemas from document_config.yaml.
Supports open mode (extract everything) and focused mode (checklist fields only).
"""

from typing import Dict, Any, List
from shared.utils.document_config import get_document_config
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class SchemaGenerator:
    """
    Generates universal schemas from document configuration.

    Universal schema format is provider-agnostic and gets translated
    to provider-specific formats by each provider implementation.
    """

    def __init__(self):
        """Initialize schema generator with document configuration."""
        self.config = get_document_config()

    def generate_schema(self, document_type: str, extract_mode: str = "open") -> Dict[str, Any]:
        """
        Generate universal schema for ANY document type.

        Works for:
        - Document types defined in config (uses config fields)
        - Unknown document types (uses fallback/open extraction)

        Args:
            document_type: Type of document (any string - system handles all types)
            extract_mode:
                - "open": Extract ALL fields from document (recommended for unknown types)
                - "focused": Only extract fields defined in config (requires config)

        Returns:
            Universal schema dictionary

        Note:
            Unknown document types will use open mode extraction to get all fields.
            Structure preservation (layout, bboxes, tables) works for all types.

        Example output (open mode):
        {
            "mode": "open",
            "extract_all": true,
            "focus_fields": ["invoice_number", "currency", ...],
            "metadata": {
                "document_type": "invoice",
                "unique_field": "invoice_number",
                "required_fields": ["invoice_number", "currency"],
                "optional_fields": [...]
            }
        }

        Example output (focused mode):
        {
            "mode": "focused",
            "extract_all": false,
            "fields": {
                "invoice_number": {"type": "string", "required": true},
                ...
            },
            "metadata": {...}
        }
        """
        logger.info(f"Generating universal schema for: {document_type} (mode: {extract_mode})")
        
        # Check if document type exists in config
        document_type_lower = document_type.lower().strip()
        has_config = False
        
        try:
            self.config.get_document_type_config(document_type_lower)
            has_config = True
            logger.debug(f"Document type '{document_type}' found in config")
        except ValueError:
            logger.info(
                f"Document type '{document_type}' not in config - using fallback/open extraction. "
                f"Structure will be preserved but no field validation."
            )
            has_config = False

        # Get field definitions from config if available
        if has_config:
            required_fields = self.config.get_required_fields(document_type_lower)
            optional_fields = self.config.get_optional_fields(document_type_lower)
            all_fields = required_fields + optional_fields

            # Get item fields if applicable
            item_required = self.config.get_item_required_fields(document_type_lower) if self._has_items(document_type_lower) else []
            item_optional = self.config.get_item_optional_fields(document_type_lower) if self._has_items(document_type_lower) else []
            all_item_fields = item_required + item_optional
        else:
            # Fallback for unknown document types - empty fields, will extract everything
            required_fields = []
            optional_fields = []
            all_fields = []
            item_required = []
            item_optional = []
            all_item_fields = []

        if extract_mode == "open" or not has_config:
            # OPEN MODE: Extract everything
            # Always use open mode for unknown document types to get all fields
            schema = {
                "mode": "open",
                "extract_all": True,
                "focus_fields": all_fields if all_fields else None,  # Hint to provider what we care about (if config exists)
                "focus_item_fields": all_item_fields if all_item_fields else None,
                "metadata": {
                    "document_type": document_type,
                    "unique_field": self._get_unique_field(document_type_lower) if has_config else "id",
                    "required_fields": required_fields,
                    "optional_fields": optional_fields,
                    "item_required_fields": item_required,
                    "item_optional_fields": item_optional,
                    "min_items": self._get_min_items(document_type_lower) if has_config else 0,
                    "has_config": has_config  # Flag indicating if type was in config
                }
            }
        else:
            # FOCUSED MODE: Only extract defined fields (requires config)
            if not has_config:
                logger.warning(
                    f"Focused mode requested for unknown document type '{document_type}'. "
                    f"Falling back to open mode."
                )
                # Recursively call with open mode
                return self.generate_schema(document_type, extract_mode="open")
            
            fields = {}

            for field_name in required_fields:
                fields[field_name] = {
                    "type": self._infer_field_type(field_name),
                    "required": True
                }

            for field_name in optional_fields:
                fields[field_name] = {
                    "type": self._infer_field_type(field_name),
                    "required": False
                }

            schema = {
                "mode": "focused",
                "extract_all": False,
                "fields": fields,
                "metadata": {
                    "document_type": document_type,
                    "unique_field": self._get_unique_field(document_type_lower),
                    "min_items": self._get_min_items(document_type_lower),
                    "has_config": has_config
                }
            }

            # Add items schema if document has line items
            if self._has_items(document_type_lower):
                item_fields = {}

                for field_name in item_required:
                    item_fields[field_name] = {
                        "type": self._infer_field_type(field_name),
                        "required": True
                    }

                for field_name in item_optional:
                    item_fields[field_name] = {
                        "type": self._infer_field_type(field_name),
                        "required": False
                    }

                schema["items"] = {
                    "field_name": "items",
                    "fields": item_fields
                }

        logger.debug(f"Generated {extract_mode} schema for {document_type}")

        return schema

    def _infer_field_type(self, field_name: str) -> str:
        """
        Infer universal field type from field name and config.

        Universal types:
        - string: Text data
        - integer: Whole numbers
        - decimal: Decimal numbers (prices, quantities)
        - date: Date values
        - boolean: True/false values

        Args:
            field_name: Name of the field

        Returns:
            Universal type string
        """
        decimal_fields = set(self.config.get_decimal_fields())
        integer_fields = set(self.config.get_integer_fields())

        # Check against config lists
        if field_name in integer_fields:
            return "integer"

        if field_name in decimal_fields:
            return "decimal"

        # Date fields
        if field_name.endswith('_date') or field_name in ['issue_date']:
            return "date"

        # Default to string
        return "string"

    def _has_items(self, document_type: str) -> bool:
        """
        Check if document type has line items.

        Now uses config flag instead of inferring from fields.
        Returns False for unknown document types (will be detected during extraction).

        Args:
            document_type: Type of document

        Returns:
            True if document has items, False otherwise
        """
        try:
            return self.config.has_items(document_type)
        except ValueError:
            # Unknown document type - return False, will be detected during extraction
            return False

    def _get_unique_field(self, document_type: str) -> str:
        """
        Get unique identifier field for document type from config.

        Returns default 'id' for unknown document types.

        Args:
            document_type: Type of document

        Returns:
            Field name that uniquely identifies the document
        """
        try:
            unique_field = self.config.get_unique_field(document_type)
            if not unique_field:
                logger.warning(
                    f"No unique_field defined for {document_type} in config, "
                    f"defaulting to 'id'"
                )
                return "id"
            return unique_field
        except ValueError:
            # Unknown document type - use default
            logger.debug(f"Unknown document type '{document_type}', using default unique_field 'id'")
            return "id"

    def _get_min_items(self, document_type: str) -> int:
        """
        Get minimum items requirement for document type from config.

        Returns 0 for unknown document types.

        Args:
            document_type: Type of document

        Returns:
            Minimum number of items required
        """
        try:
            return self.config.get_min_items(document_type)
        except ValueError:
            # Unknown document type - no minimum requirement
            return 0

    def _get_extraction_description(self, field_name: str, hints: Dict[str, str]) -> str:
        """
        Build a description for focused-mode extraction.

        Priority:
        1. Per-field extraction hint from checklist.yaml (most specific)
        2. Field description from DocumentExtractionFields Pydantic schema
        3. Empty string fallback

        Args:
            field_name: Canonical field name (e.g. "po_number").
            hints: Dict of field_name → hint from get_extraction_hints().

        Returns:
            Description string for the field, or "" if none available.
        """
        if field_name in hints:
            return hints[field_name]

        try:
            from modules.extraction.parser.ai_semantic_enhancer import DocumentExtractionFields
            field_info = DocumentExtractionFields.model_fields.get(field_name)
            if field_info and field_info.description:
                return field_info.description
        except Exception:
            pass

        return ""

    def generate_checklist_schema(self, document_type: str) -> Dict[str, Any]:
        """
        Generate a focused schema containing only the fields from the import checklist.

        Loads field definitions from config/checklist.yaml for the given document
        type and returns a schema in focused mode format.

        Args:
            document_type: Type of document (e.g. "invoice", "boe")

        Returns:
            Focused schema dict with only checklist fields, or open schema as
            fallback if the document type has no checklist entries.
        """
        from shared.utils.checklist_config import get_checklist_config

        checklist = get_checklist_config()
        header_fields, item_fields = checklist.get_checklist_fields(document_type)

        if not header_fields and not item_fields:
            logger.info(
                f"No checklist fields found for '{document_type}' — "
                f"fall back to open extraction"
            )
            return self.generate_schema(document_type, extract_mode="open")

        logger.info(
            f"Checklist schema for '{document_type}': "
            f"{len(header_fields)} header fields, {len(item_fields)} item fields"
        )

        hints = checklist.get_extraction_hints(document_type)

        fields: Dict[str, Any] = {}
        for field_name in header_fields:
            fields[field_name] = {
                "type": self._infer_field_type(field_name),
                "required": False,
                "description": self._get_extraction_description(field_name, hints),
            }

        doc_type_lower = document_type.lower().strip()
        # For document types that don't have line items (e.g. bill_of_lading),
        # promote item-level checklist fields to header fields so Claude extracts
        # them as flat key-value pairs rather than looking for item rows.
        if item_fields and not self._has_items(doc_type_lower):
            for field_name in item_fields:
                if field_name not in header_fields:
                    header_fields.append(field_name)
                    fields[field_name] = {
                        "type": self._infer_field_type(field_name),
                        "required": False,
                        "description": self._get_extraction_description(field_name, hints),
                    }
            item_fields = []
        has_items = bool(item_fields)

        schema: Dict[str, Any] = {
            "mode": "focused",
            "extract_all": False,
            "fields": fields,
            "metadata": {
                "document_type": document_type,
                "unique_field": self._get_unique_field(doc_type_lower),
                "min_items": 0,
                "has_config": True,
                "source": "checklist",
            },
        }

        if has_items:
            item_field_defs: Dict[str, Any] = {}
            for field_name in item_fields:
                item_field_defs[field_name] = {
                    "type": self._infer_field_type(field_name),
                    "required": False,
                    "description": self._get_extraction_description(field_name, hints),
                }
            schema["items"] = {
                "field_name": "items",
                "fields": item_field_defs,
            }

        return schema

    def get_all_schemas(self, extract_mode: str = "open") -> Dict[str, Dict[str, Any]]:
        """
        Generate schemas for ALL configured document types dynamically.

        Now discovers document types from config automatically - no hardcoded list.

        Args:
            extract_mode: Mode to use for all schemas ("open" or "focused")

        Returns:
            Dictionary mapping document type to universal schema
        """
        # Dynamically get all document types from config
        document_types = self.config.get_all_document_types()
        
        logger.info(f"Generating schemas for {len(document_types)} document types: {document_types}")

        schemas = {}
        for doc_type in document_types:
            try:
                schemas[doc_type] = self.generate_schema(doc_type, extract_mode=extract_mode)
                logger.debug(f"Generated schema for {doc_type}")
            except Exception as e:
                logger.error(f"Failed to generate schema for {doc_type}: {e}", exc_info=True)

        return schemas
