"""
Recursive Dynamic Field Extractor for Population Agent.

Comprehensively extracts all field names and values from database results,
handling nested structures, arrays, and complex objects recursively.
"""

from typing import Dict, Any, List, Optional, Set, Tuple
import logging

logger = logging.getLogger(__name__)


class RecursiveFieldExtractor:
    """
    Recursively and dynamically extract all fields from database data.

    Features:
    - Recursive traversal of nested objects
    - Array handling (extracts from all elements, not just first)
    - Path tracking (knows exact location of each field)
    - Value cleaning (extracts clean values from complex objects)
    - Deduplication (handles same field from multiple documents)
    - Document provenance tracking

    Example:
        >>> extractor = RecursiveFieldExtractor()
        >>> fields = extractor.extract_all_fields(db_data)
        >>> print(fields)
        [
            {
                "field_name": "exporter",
                "value": "IB TEC INTERNATIONAL COMPANY LTD",
                "path": "fields.exporter.value",
                "source_document": "bill_of_lading",
                "nesting_level": 2
            },
            ...
        ]
    """

    def __init__(self, max_depth: int = 10):
        """
        Initialize field extractor.

        Args:
            max_depth: Maximum recursion depth to prevent infinite loops
        """
        self.max_depth = max_depth
        self.seen_paths: Set[str] = set()

    def extract_all_fields(
        self,
        db_data: Dict[str, Any],
        include_metadata: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Extract all fields recursively from database data.

        Args:
            db_data: Database result with fields, items, metadata
            include_metadata: Whether to extract from metadata section

        Returns:
            List of field dictionaries with comprehensive information
        """
        logger.info("🔍 Starting recursive field extraction...")

        self.seen_paths = set()
        all_fields = []

        # Get document types for provenance tracking
        doc_types = db_data.get("metadata", {}).get("document_types", ["unknown"])

        # Extract from 'fields' section
        if "fields" in db_data:
            fields_data = db_data["fields"]
            logger.debug(f"Extracting from 'fields' section ({len(fields_data)} top-level keys)")

            field_results = self._recursive_extract(
                data=fields_data,
                path_prefix="fields",
                document_type=doc_types[0] if doc_types else "unknown",
                current_depth=0
            )
            all_fields.extend(field_results)

        # Extract from 'items' array (ALL items, not just first)
        if "items" in db_data and isinstance(db_data["items"], list):
            items = db_data["items"]
            logger.debug(f"Extracting from 'items' array ({len(items)} items)")

            # First, try to consolidate multi-row fields (like exporter/consignee across rows)
            consolidated = self._consolidate_multi_row_fields(items)
            all_fields.extend(consolidated)

            # Then extract remaining fields from individual items
            for item_index, item in enumerate(items):
                if isinstance(item, dict):
                    item_results = self._recursive_extract(
                        data=item,
                        path_prefix=f"items.{item_index}",
                        document_type="items",
                        current_depth=0
                    )
                    all_fields.extend(item_results)

        # Extract from metadata if requested
        if include_metadata and "metadata" in db_data:
            metadata = db_data["metadata"]
            logger.debug("Extracting from 'metadata' section")

            metadata_results = self._recursive_extract(
                data=metadata,
                path_prefix="metadata",
                document_type="metadata",
                current_depth=0
            )
            all_fields.extend(metadata_results)

        # Deduplicate by field name (keep highest quality)
        deduplicated = self._deduplicate_fields(all_fields)

        logger.info(
            f"✅ Extracted {len(deduplicated)} unique fields "
            f"from {len(all_fields)} total extractions"
        )

        return deduplicated

    def _recursive_extract(
        self,
        data: Any,
        path_prefix: str,
        document_type: str,
        current_depth: int,
        parent_key: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Recursively extract fields from nested data structure.

        Args:
            data: Current data node (dict, list, or value)
            path_prefix: Current path in dot notation
            document_type: Source document type
            current_depth: Current recursion depth
            parent_key: Parent key name for context

        Returns:
            List of extracted field dictionaries
        """
        # Depth limit check
        if current_depth >= self.max_depth:
            logger.warning(f"⚠️ Max depth {self.max_depth} reached at path: {path_prefix}")
            return []

        results = []

        # Handle dictionaries
        if isinstance(data, dict):
            # Check if this is a leaf node with 'value' key (extraction result format)
            if 'value' in data and isinstance(data['value'], (str, int, float, bool)):
                # This is a leaf node - extract the value
                clean_value = self._extract_clean_value(data['value'])

                if clean_value and clean_value != 'null' and clean_value != '':
                    # Extract field name from path
                    field_name = path_prefix.split('.')[-1]

                    # Avoid duplicate paths
                    if path_prefix not in self.seen_paths:
                        self.seen_paths.add(path_prefix)

                        results.append({
                            "field_name": field_name,
                            "value": clean_value,
                            "path": path_prefix,
                            "full_path": path_prefix,
                            "source_document": document_type,
                            "nesting_level": current_depth,
                            "confidence": data.get('confidence', 'unknown'),
                            "original_data": data  # Keep for debugging
                        })

                        logger.debug(f"  {'  ' * current_depth}📄 {field_name}: {str(clean_value)[:50]}")

            # Recurse into nested keys
            for key, value in data.items():
                # Skip metadata keys that aren't useful
                if key in ['bbox', 'block_type', 'row_index', 'cell_index', 'original_label', 'original_page', 'page']:
                    continue

                # Recurse
                nested_results = self._recursive_extract(
                    data=value,
                    path_prefix=f"{path_prefix}.{key}",
                    document_type=document_type,
                    current_depth=current_depth + 1,
                    parent_key=key
                )
                results.extend(nested_results)

        # Handle lists/arrays
        elif isinstance(data, list):
            logger.debug(f"  {'  ' * current_depth}📋 Array with {len(data)} elements at {path_prefix}")

            for index, item in enumerate(data):
                list_results = self._recursive_extract(
                    data=item,
                    path_prefix=f"{path_prefix}.{index}",
                    document_type=document_type,
                    current_depth=current_depth + 1,
                    parent_key=parent_key
                )
                results.extend(list_results)

        # Handle primitive values (string, number, bool)
        elif isinstance(data, (str, int, float, bool)):
            clean_value = self._extract_clean_value(data)

            if clean_value and clean_value != 'null' and clean_value != '':
                field_name = path_prefix.split('.')[-1]

                if path_prefix not in self.seen_paths:
                    self.seen_paths.add(path_prefix)

                    results.append({
                        "field_name": field_name,
                        "value": clean_value,
                        "path": path_prefix,
                        "full_path": path_prefix,
                        "source_document": document_type,
                        "nesting_level": current_depth,
                        "confidence": "direct",
                        "original_data": data
                    })

                    logger.debug(f"  {'  ' * current_depth}💎 {field_name}: {str(clean_value)[:50]}")

        return results

    def _consolidate_multi_row_fields(self, items: List[Dict]) -> List[Dict[str, Any]]:
        """
        Consolidate fields that span multiple table rows.

        Example: Packing list with exporter/consignee data split across rows:
          Row 0: {"exporter": "IB TEC INTERNATIONAL", "consignee": "ALEX ODOOM"}
          Row 1: {"exporter": "1-6-19-501, SAKAE CHO", "consignee": "CHURCH C/O EASTERN"}
          Row 2: {"exporter": "Japan", "consignee": "Ghana"}

        Consolidates into:
          {"exporter": "IB TEC INTERNATIONAL, 1-6-19-501, SAKAE CHO, Japan"}
          {"consignee": "ALEX ODOOM, CHURCH C/O EASTERN, Ghana"}

        Args:
            items: List of item dictionaries (table rows)

        Returns:
            List of consolidated field dictionaries
        """
        if not items or len(items) < 2:
            return []

        # Find common column headers across rows
        column_names = set()
        for item in items:
            if isinstance(item, dict):
                column_names.update(item.keys())

        # Group values by column name across all rows
        consolidated_fields = []
        multi_row_columns = {}  # {column_name: [values]}

        for column in column_names:
            values = []
            for item in items:
                if isinstance(item, dict) and column in item:
                    # Extract clean value
                    cell_data = item[column]
                    if isinstance(cell_data, dict) and 'value' in cell_data:
                        value = cell_data['value']
                    else:
                        value = cell_data

                    # Clean and validate
                    clean_value = self._extract_clean_value(value)
                    if clean_value and clean_value != '-' and not clean_value.endswith(':'):
                        # Skip labels like "EXPORTER:", "CONSIGNEE:"
                        values.append(clean_value)

            # If we found multiple values for this column, consolidate
            if len(values) >= 2:
                multi_row_columns[column] = values
                logger.debug(f"  🔗 Consolidating '{column}': {len(values)} rows → {values}")

        # Create consolidated field entries
        for field_name, values in multi_row_columns.items():
            # Join with newline for address-like fields, comma for others
            if any(keyword in field_name.lower() for keyword in ['address', 'exporter', 'consignee', 'shipper']):
                # Use newline for better readability in PDFs
                consolidated_value = '\n'.join(values)
            else:
                consolidated_value = ', '.join(values)

            consolidated_fields.append({
                "field_name": field_name,
                "value": consolidated_value,
                "path": f"items.consolidated.{field_name}",
                "full_path": f"items.consolidated.{field_name}",
                "source_document": "items_consolidated",
                "nesting_level": 0,
                "confidence": "consolidated",
                "original_data": values  # Keep original rows for reference
            })

            logger.info(f"✨ Consolidated field '{field_name}': {consolidated_value[:80]}...")

        return consolidated_fields

    def _extract_clean_value(self, value: Any) -> Optional[str]:
        """
        Extract clean string value from any data type.

        Handles:
        - Primitives: return as string
        - Dicts with 'value': extract recursively
        - Lists: extract first non-empty
        - Complex objects: stringify safely
        """
        if value is None or value == 'null' or value == '':
            return None

        # Primitives
        if isinstance(value, (str, int, float, bool)):
            return str(value).strip()

        # Dict with 'value' key
        if isinstance(value, dict) and 'value' in value:
            return self._extract_clean_value(value['value'])

        # Lists
        if isinstance(value, list):
            for item in value:
                clean = self._extract_clean_value(item)
                if clean:
                    return clean
            return None

        # Dict without 'value' - try to extract meaningful content
        if isinstance(value, dict):
            # Skip metadata and label keys
            skip_keys = {
                'bbox', 'confidence', 'block_type', 'row_index', 'cell_index',
                'label', 'original_label', 'field_name', 'page', 'original_page',
                'header', 'title', 'field_label'
            }

            # Try to find actual value in common value keys
            value_keys = ['text', 'content', 'data', 'amount', 'number']
            for vkey in value_keys:
                if vkey in value:
                    clean = self._extract_clean_value(value[vkey])
                    if clean and not clean.endswith(':'):  # Skip if it looks like a label
                        return clean

            # Single key-value (excluding skip_keys)
            useful_keys = {k: v for k, v in value.items() if k not in skip_keys}
            if len(useful_keys) == 1:
                return self._extract_clean_value(list(useful_keys.values())[0])

            # Multiple keys - join non-meta values
            values = []
            for k, v in value.items():
                if k not in skip_keys:
                    clean = self._extract_clean_value(v)
                    if clean and not clean.endswith(':'):  # Skip label-like values
                        values.append(clean)

            if values:
                return ', '.join(values[:3])  # Limit to 3 values

        # Fallback
        return str(value)

    def _deduplicate_fields(
        self,
        fields: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Deduplicate fields by name, keeping highest quality.

        Priority:
        1. Shorter path (less nesting = more direct)
        2. Higher confidence
        3. Non-empty value
        4. Specific document types over generic
        """
        field_map: Dict[str, Dict[str, Any]] = {}

        for field in fields:
            name = field['field_name']

            # First occurrence
            if name not in field_map:
                field_map[name] = field
                continue

            # Compare with existing
            existing = field_map[name]

            # Quality scoring
            new_score = self._calculate_field_quality(field)
            existing_score = self._calculate_field_quality(existing)

            # Keep higher quality
            if new_score > existing_score:
                logger.debug(
                    f"🔄 Replacing '{name}': "
                    f"{existing['path']} (score: {existing_score:.2f}) → "
                    f"{field['path']} (score: {new_score:.2f})"
                )
                field_map[name] = field

        return list(field_map.values())

    def _calculate_field_quality(self, field: Dict[str, Any]) -> float:
        """
        Calculate quality score for a field.

        Higher score = better quality field
        """
        score = 100.0

        # Prefer shorter paths (less nesting)
        nesting_penalty = field['nesting_level'] * 5
        score -= nesting_penalty

        # Confidence boost
        confidence = field.get('confidence', 'unknown')
        if confidence == 'high':
            score += 20
        elif confidence == 'medium':
            score += 10
        elif isinstance(confidence, (int, float)):
            score += float(confidence) * 20

        # Value length boost (longer = more complete)
        value_length = len(str(field['value']))
        score += min(value_length / 10, 20)  # Cap at 20

        # Document type preference
        doc_type = field['source_document']
        if doc_type == 'items_consolidated':
            # Consolidated fields are high quality (multiple rows merged)
            score += 30
        elif doc_type in ['bill_of_lading', 'invoice']:
            score += 15
        elif doc_type in ['coo', 'packing_list']:
            score += 10
        elif doc_type == 'items':
            score += 5

        return score

    def print_extraction_summary(self, fields: List[Dict[str, Any]]):
        """Print a summary of extracted fields for debugging."""

        logger.info("\n" + "="*80)
        logger.info("FIELD EXTRACTION SUMMARY")
        logger.info("="*80)

        # Group by document type
        by_doc_type: Dict[str, List[Dict]] = {}
        for field in fields:
            doc_type = field['source_document']
            if doc_type not in by_doc_type:
                by_doc_type[doc_type] = []
            by_doc_type[doc_type].append(field)

        for doc_type, doc_fields in sorted(by_doc_type.items()):
            logger.info(f"\n📄 {doc_type.upper()} ({len(doc_fields)} fields):")
            for field in sorted(doc_fields, key=lambda x: x['field_name'])[:10]:  # Show first 10
                logger.info(
                    f"  • {field['field_name']:30s} = {str(field['value'])[:40]:40s} "
                    f"[{field['path']}]"
                )
            if len(doc_fields) > 10:
                logger.info(f"  ... and {len(doc_fields) - 10} more")

        logger.info("="*80 + "\n")
