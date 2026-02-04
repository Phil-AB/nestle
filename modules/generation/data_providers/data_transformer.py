"""
Data transformer for generation module.

Transforms database data structure to template-friendly format.
"""

from typing import Dict, Any, List
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class DataTransformer:
    """
    Transforms nested database structure to flat template structure.
    
    Database fields come as:
    {
        "field_name": {
            "value": "actual_value",
            "bbox": {...},
            "confidence": "high"
        }
    }
    
    We transform to:
    {
        "field_name": "actual_value"
    }
    """
    
    @staticmethod
    def transform_fields(fields: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform nested fields to flat dictionary.
        
        Args:
            fields: Nested fields from database
        
        Returns:
            Flat dictionary with just values
        """
        if not fields:
            return {}
        
        transformed = {}
        
        for field_name, field_data in fields.items():
            if isinstance(field_data, dict):
                # Extract value from nested structure
                if 'value' in field_data:
                    value = field_data['value']
                    # Handle "null" strings
                    if value == "null" or value is None:
                        transformed[field_name] = None
                    else:
                        transformed[field_name] = value
                else:
                    # If no value key, use as-is
                    transformed[field_name] = field_data
            else:
                # Already flat, use as-is
                transformed[field_name] = field_data
        
        return transformed
    
    @staticmethod
    def transform_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Transform nested items to flat list.
        
        Args:
            items: Nested items from database
        
        Returns:
            List of flat dictionaries
        """
        if not items:
            return []
        
        transformed_items = []
        
        for item in items:
            transformed_item = {}
            
            for column_name, column_data in item.items():
                if isinstance(column_data, dict):
                    # Extract value from nested structure
                    if 'value' in column_data:
                        value = column_data['value']
                        # Handle "null" strings
                        if value == "null" or value is None:
                            transformed_item[column_name] = None
                        else:
                            transformed_item[column_name] = value
                    
                    # Optionally keep row/column indices for ordering
                    if 'row_index' in column_data:
                        transformed_item['_row_index'] = column_data['row_index']
                    if 'column_index' in column_data:
                        transformed_item[f'_{column_name}_col_idx'] = column_data['column_index']
                else:
                    # Already flat
                    transformed_item[column_name] = column_data
            
            transformed_items.append(transformed_item)
        
        return transformed_items
    
    @staticmethod
    def flatten_items_to_fields(items: List[Dict[str, Any]], fields: Dict[str, Any]) -> Dict[str, Any]:
        """
        Flatten table/item data into fields dictionary.

        Extracts party information, shipping details, and other metadata
        from items (table rows) and promotes them to top-level fields.

        Args:
            items: List of transformed items
            fields: Existing fields dictionary

        Returns:
            Enhanced fields dictionary with flattened item data
        """
        if not items:
            return fields

        # Fields to extract from items (table rows) and promote to fields
        # Format: item_key -> field_key
        PROMOTABLE_FIELDS = {
            # Party information
            'exporter_shipper': 'exporter_shipper',
            'consignee_importer': 'consignee_importer',
            'shipper_/_exporter': 'shipper_exporter',
            'consignee': 'consignee',
            'forwarding_agent': 'forwarding_agent',
            'notify_party': 'notify_party',
            # Shipping details
            'vessel': 'vessel',
            'port_of_loading': 'port_of_loading',
            'port_of_discharge': 'port_of_discharge',
            'place_of_delivery': 'place_of_delivery',
            'marks_&_numbers': 'marks_and_numbers',
            'description_of_packages_&_goods': 'description_of_goods',
            'gross_weight': 'gross_weight',
            'measurement': 'measurement',
            # Financial
            'qty': 'quantity',
            'unit_price': 'unit_price',
            'total_(jpy)': 'total_jpy',
        }

        # Party fields that should concatenate multi-row table data (name + address)
        MULTI_ROW_FIELDS = {
            'exporter_shipper', 'consignee_importer', 'shipper_exporter',
            'consignee', 'forwarding_agent', 'notify_party', 'description_of_goods'
        }

        # Aggregate non-null values from all items
        for item in items:
            if not isinstance(item, dict):
                continue

            # Intelligent financial data extraction based on description
            if 'description_of_goods' in item and 'total_jpy' in item:
                desc = str(item.get('description_of_goods', '')).lower()
                total_value = item.get('total_jpy')

                if total_value and total_value not in ['null', '-', 'N/A', '']:
                    # Map financial line items to specific fields
                    if 'freight' in desc:
                        fields['freight'] = total_value
                    elif 'insurance' in desc:
                        fields['insurance'] = total_value
                    elif 'used vehicle' in desc or 'goods' in desc or item.get('no'):
                        # This is likely the FOB value (goods line item)
                        if 'fob_value' not in fields:
                            fields['fob_value'] = total_value

            for item_key, field_key in PROMOTABLE_FIELDS.items():
                if item_key in item:
                    value = item[item_key]
                    # Only promote non-null, non-empty, non-dash values
                    if value and value not in ['null', '-', 'N/A', '']:
                        # If field doesn't exist or is empty, set it
                        if field_key not in fields or not fields[field_key]:
                            fields[field_key] = value
                        # If multiple non-empty values, concatenate with delimiter
                        elif fields[field_key] != value:
                            # Skip duplicates
                            existing = str(fields[field_key])
                            if str(value) not in existing:
                                # Always concatenate for multi-row party/description fields
                                if field_key in MULTI_ROW_FIELDS:
                                    fields[field_key] = f"{existing}, {value}"
                                # Also concatenate for any field with address/description/name keywords
                                elif any(keyword in field_key for keyword in ['address', 'description', 'name']):
                                    fields[field_key] = f"{existing}\n{value}"

        logger.debug(f"Flattened items to fields: {len(fields)} total fields")
        return fields

    @staticmethod
    def transform_document(doc_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform entire document structure.

        Args:
            doc_data: Raw document data from database

        Returns:
            Transformed data ready for templates
        """
        transformed = {
            "fields": {},
            "items": [],
            "metadata": {}
        }

        # Transform fields
        if 'fields' in doc_data:
            transformed['fields'] = DataTransformer.transform_fields(doc_data['fields'])

        # Transform items
        if 'items' in doc_data:
            transformed['items'] = DataTransformer.transform_items(doc_data['items'])

        # Flatten relevant item data into fields for easier mapping
        transformed['fields'] = DataTransformer.flatten_items_to_fields(
            transformed['items'],
            transformed['fields']
        )

        # Keep metadata as-is
        if 'metadata' in doc_data:
            transformed['metadata'] = doc_data['metadata']
        elif 'doc_metadata' in doc_data:
            transformed['metadata'] = doc_data['doc_metadata']

        # Add document-level fields
        for key in ['document_id', 'document_type', 'extraction_status', 'extraction_confidence']:
            if key in doc_data:
                transformed[key] = doc_data[key]

        logger.debug(f"Transformed {len(transformed['fields'])} fields and {len(transformed['items'])} items")

        return transformed
