"""
Universal data transformation service.

Transforms provider-agnostic extraction output into validated data for storage.
Works with any provider (Reducto, Google Document AI, etc.).
"""

from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, List, Optional
from pydantic import create_model, BaseModel
import re

from shared.utils.document_config import get_document_config
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class UniversalTransformer:
    """
    Transforms universal extraction format into database-ready format.

    Works with normalized data from any provider.
    """

    def __init__(self):
        """Initialize universal transformer with configuration."""
        self.config = get_document_config()
        self.date_formats = self.config.get_date_formats()
        self.decimal_fields = set(self.config.get_decimal_fields())
        self.integer_fields = set(self.config.get_integer_fields())
        self.currency_mapping = self.config.get_currency_mapping()

    def transform_document(
        self,
        document_type: str,
        universal_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transform universal extraction data into database-ready format.

        This method is now fully generic - works for ANY document type
        defined in config without code changes.

        Args:
            document_type: Type of document (any type defined in config)
            universal_data: Normalized universal format from provider:
                {
                    "fields": {"invoice_number": "INV-001", ...},
                    "items": [{"line_number": 1, ...}],
                    "metadata": {"provider": "reducto", "confidence": 0.95}
                }

        Returns:
            Dict with transformed data:
            {
                'header_data': {...},  # Ready for database
                'items_data': [{...}],  # Ready for database
                'extraction_status': 'complete',
                'extraction_confidence': 0.95,
                'raw_data': {...},
                'saved_fields': [...],
                'missing_fields': [...],
                'items_count': 5
            }

        Raises:
            ValueError: If document_type not found in config
        """
        logger.info(f"Transforming {document_type} data (universal format)")
        
        # Validate document type exists in config
        try:
            self.config.get_document_type_config(document_type)
        except ValueError as e:
            logger.error(f"Invalid document type: {document_type}")
            raise

        # Extract components from universal format
        fields = universal_data.get('fields', {})
        items = universal_data.get('items', [])
        metadata = universal_data.get('metadata', {})

        # Get field definitions from config
        required_fields = self.config.get_required_fields(document_type)
        optional_fields = self.config.get_optional_fields(document_type)
        all_fields = required_fields + optional_fields

        # Transform ALL fields from input (including AI-enhanced fields not in config)
        # This ensures dynamic fields like exporter_name, consignee_address from AI enhancement are preserved
        header_data = self._transform_dict(fields, fields.keys())

        # Handle missing unique identifier
        unique_field = self._get_unique_field(document_type)
        if not header_data.get(unique_field):
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            header_data[unique_field] = f"UNKNOWN-{document_type.upper()}-{timestamp}"
            logger.warning(f"No {unique_field} extracted, using placeholder: {header_data[unique_field]}")

        # Transform items if document has them
        items_data = []
        if self._has_items(document_type):
            item_required = self.config.get_item_required_fields(document_type)
            item_optional = self.config.get_item_optional_fields(document_type)
            item_fields = item_required + item_optional

            for raw_item in items:
                # Transform item fields - extract values for database storage
                # Column metadata is preserved in raw_data, not in database columns
                transformed_item = {}
                column_metadata = {}  # Track column info for this item
                
                for field_name in item_fields:
                    raw_value = raw_item.get(field_name)
                    
                    # Handle field objects with column metadata: {"value": "...", "column_index": 0, ...}
                    if isinstance(raw_value, dict) and "value" in raw_value:
                        # Extract value for transformation and database storage
                        actual_value = raw_value["value"]
                        transformed_item[field_name] = self._transform_value(field_name, actual_value)
                        
                        # Preserve column metadata separately (will be in raw_data)
                        if "column_index" in raw_value or "column_number" in raw_value:
                            column_metadata[field_name] = {
                                k: v for k, v in raw_value.items() 
                                if k != "value" and k in ["column_index", "column_number", 
                                                          "original_header", "normalized_header",
                                                          "row_index", "table_block_index", 
                                                          "table_bbox", "cell_bbox", "confidence"]
                                and v is not None
                            }
                    else:
                        # Simple value
                        transformed_item[field_name] = self._transform_value(field_name, raw_value)
                
                # Add column metadata to item if present (for raw_data preservation)
                if column_metadata:
                    transformed_item["_column_metadata"] = column_metadata
                
                items_data.append(transformed_item)

        # Determine extraction status
        extraction_status = self._check_extraction_status(
            header_data,
            required_fields,
            items_data,
            document_type
        )

        # Extract confidence from metadata
        extraction_confidence = metadata.get('confidence', 0.0)

        # Track which fields were saved and which are missing
        saved_fields = [k for k, v in header_data.items() if v is not None]
        missing_fields = [f for f in required_fields if header_data.get(f) is None]

        logger.info(
            f"Transformation complete: {document_type}, "
            f"status={extraction_status}, fields={len(saved_fields)}, items={len(items_data)}"
        )

        return {
            'header_data': header_data,
            'items_data': items_data,
            'extraction_status': extraction_status,
            'extraction_confidence': extraction_confidence,
            'raw_data': universal_data,  # Store the full universal format
            'saved_fields': saved_fields,
            'missing_fields': missing_fields,
            'items_count': len(items_data)
        }

    def _transform_dict(self, data: Dict[str, Any], field_names: List[str]) -> Dict[str, Any]:
        """
        Transform all fields in a dictionary.

        Handles both simple values and field objects with layout metadata.

        Args:
            data: Raw data dictionary (may contain field objects with 'value' key)
            field_names: List of field names to transform

        Returns:
            Transformed dictionary
        """
        transformed = {}
        for field_name in field_names:
            raw_value = data.get(field_name)
            
            # Handle field objects with layout metadata: {"value": "...", "bbox": [...]}
            if isinstance(raw_value, dict) and "value" in raw_value:
                # Extract just the value for transformation
                actual_value = raw_value["value"]
                transformed[field_name] = self._transform_value(field_name, actual_value)
            else:
                # Simple value
                transformed[field_name] = self._transform_value(field_name, raw_value)

        return transformed

    def _transform_value(self, field_name: str, value: Any) -> Any:
        """
        Transform a single field value based on its type.

        Args:
            field_name: Name of the field
            value: Raw value

        Returns:
            Transformed value
        """
        if field_name in self.decimal_fields:
            return self._parse_decimal(value)
        elif field_name in self.integer_fields:
            return self._parse_integer(value)
        elif field_name.endswith('_date') or field_name == 'issue_date':
            return self._parse_date(value)
        elif field_name == 'currency':
            return self._normalize_currency(value)
        else:
            # Return as-is
            return value

    def _parse_date(self, value: Any) -> Optional[date]:
        """Parse date from various formats."""
        if value is None:
            return None

        if isinstance(value, date):
            return value

        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None

            # Try configured date formats
            for fmt in self.date_formats:
                try:
                    parsed = datetime.strptime(value, fmt)
                    return parsed.date()
                except ValueError:
                    continue

            logger.warning(f"Could not parse date: {value}")
            return None

        return None

    def _parse_decimal(self, value: Any) -> Optional[Decimal]:
        """Parse decimal from various formats."""
        if value is None:
            return None

        if isinstance(value, Decimal):
            return value

        if isinstance(value, (int, float)):
            return Decimal(str(value))

        if isinstance(value, str):
            # Remove currency symbols, commas, spaces
            value = value.strip()
            value = re.sub(r'[,$€£\s]', '', value)

            if not value or value == '-':
                return None

            try:
                return Decimal(value)
            except (InvalidOperation, ValueError):
                logger.warning(f"Could not parse decimal: {value}")
                return None

        return None

    def _parse_integer(self, value: Any) -> Optional[int]:
        """Parse integer from various formats."""
        if value is None:
            return None

        if isinstance(value, int):
            return value

        if isinstance(value, float):
            return int(value)

        if isinstance(value, str):
            value = value.strip()
            value = re.sub(r'[,\s]', '', value)

            if not value:
                return None

            try:
                return int(float(value))
            except ValueError:
                logger.warning(f"Could not parse integer: {value}")
                return None

        return None

    def _normalize_currency(self, value: Any) -> str:
        """Normalize currency code."""
        if value is None or value == '':
            return self.config.get_defaults().get('currency', 'USD')

        value = str(value).strip().upper()

        # Map common currency symbols/codes to standard codes
        return self.currency_mapping.get(value, value)

    def _check_extraction_status(
        self,
        data: Dict[str, Any],
        required_fields: List[str],
        items: Optional[List[Any]] = None,
        document_type: Optional[str] = None
    ) -> str:
        """
        Determine extraction status based on required fields presence.

        Args:
            data: Transformed data dictionary
            required_fields: List of required field names
            items: Optional list of items
            document_type: Optional document type for min_items check

        Returns:
            Status string ('complete' or 'incomplete')
        """
        # Check if all required fields have values
        for field in required_fields:
            value = data.get(field)
            if value is None or value == '' or value == []:
                return 'incomplete'

        # If items are provided and expected, check minimum count from config
        if items is not None and document_type:
            min_items = self.config.get_min_items(document_type)
            if len(items) < min_items:
                return 'incomplete'

        return 'complete'

    def _has_items(self, document_type: str) -> bool:
        """
        Check if document type has line items.
        
        Now uses config flag instead of inferring from fields.
        """
        return self.config.has_items(document_type)

    def _get_unique_field(self, document_type: str) -> str:
        """
        Get unique identifier field for document type from config.
        
        Now fully config-driven - no hardcoded mappings.
        """
        unique_field = self.config.get_unique_field(document_type)
        
        if not unique_field:
            logger.warning(
                f"No unique_field defined for {document_type} in config, "
                f"defaulting to 'id'"
            )
            return "id"
        
        return unique_field
