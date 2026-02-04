"""
Spatial/BBox-Aware Field Extractor

Uses bounding box information to intelligently extract fields from document blocks.
Works for ANY document type by understanding spatial relationships.
"""

from typing import Dict, List, Any, Tuple, Optional
from bs4 import BeautifulSoup
import re
import logging

logger = logging.getLogger(__name__)


class SpatialExtractor:
    """Extract fields using spatial/bbox intelligence"""

    def __init__(self):
        self.proximity_threshold = 0.05  # 5% of page height for vertical proximity
        self.horizontal_threshold = 0.1  # 10% of page width for horizontal alignment

    def extract_fields_from_blocks(
        self,
        blocks: List[Dict[str, Any]],
        document_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract fields from blocks using bbox-aware logic.

        Args:
            blocks: List of content blocks with bbox information
            document_type: Optional document type for type-specific extraction

        Returns:
            Dictionary of extracted fields with bbox metadata
        """
        logger.info(f"Starting bbox-aware extraction for {len(blocks)} blocks")

        # Sort blocks by spatial position (top-to-bottom, left-to-right)
        sorted_blocks = self._sort_blocks_spatially(blocks)

        fields = {}

        # Extract from each block type
        for block in sorted_blocks:
            block_type = block.get('type', '')

            if block_type == 'Table':
                # Parse table structure using bbox
                table_fields = self._extract_from_table_block(block)
                fields.update(table_fields)

            elif block_type in ['Text', 'Title', 'Footer', 'Header']:
                # Extract key-value pairs from text blocks
                text_fields = self._extract_from_text_block(block)
                fields.update(text_fields)

            elif block_type == 'Field':
                # Direct field block
                field_data = self._extract_field_block(block)
                if field_data:
                    fields.update(field_data)

        logger.info(f"Extracted {len(fields)} fields using bbox-aware logic")
        return fields

    def _sort_blocks_spatially(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort blocks by position: top-to-bottom, left-to-right"""
        return sorted(
            blocks,
            key=lambda b: (
                b.get('bbox', {}).get('page', 1),
                b.get('bbox', {}).get('top', 0),
                b.get('bbox', {}).get('left', 0)
            )
        )

    def _extract_from_table_block(self, block: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract fields from table block using HTML structure and bbox.

        Parses the table to find field labels and values based on:
        - Table cell structure (headers vs data)
        - Spatial proximity of cells
        - Field number patterns (1., 2., Field 1:, etc.)
        """
        content = block.get('content', '')
        bbox = block.get('bbox', {})

        if not content or not content.strip().startswith('<table'):
            return {}

        fields = {}

        try:
            soup = BeautifulSoup(content, 'html.parser')
            table = soup.find('table')

            if not table:
                return {}

            # Process table rows
            rows = table.find_all('tr')

            for row_idx, row in enumerate(rows):
                # Get all cells (th and td)
                cells = row.find_all(['th', 'td'])

                for cell_idx, cell in enumerate(cells):
                    cell_text = cell.get_text(separator=' ', strip=True)

                    if not cell_text:
                        continue

                    # Try to extract field from cell content
                    field_data = self._parse_field_from_text(cell_text, bbox, row_idx, cell_idx)

                    if field_data:
                        fields.update(field_data)

            logger.info(f"Extracted {len(fields)} fields from table block")

        except Exception as e:
            logger.error(f"Error parsing table block: {e}")

        return fields

    def _parse_field_from_text(
        self,
        text: str,
        table_bbox: Dict[str, Any],
        row_idx: int,
        cell_idx: int
    ) -> Dict[str, Any]:
        """
        Parse field label and value from text using patterns.

        Recognizes patterns like:
        - "1 Regime 40 PMD"
        - "Field 7: Importer Name"
        - "Invoice Number: INV-001"
        - "2 Exporter & Address No : Company Ltd"
        """
        fields = {}

        # Pattern 1: Numbered field with colon (e.g., "1 Regime: 40")
        pattern1 = r'(\d+)\s+([^:]+?):\s*(.+)'
        match = re.match(pattern1, text)
        if match:
            field_num, field_label, field_value = match.groups()
            field_key = self._normalize_field_name(field_label)
            fields[field_key] = {
                'value': field_value.strip(),
                'field_number': field_num,
                'original_label': field_label.strip(),
                'bbox': table_bbox,
                'row_index': row_idx,
                'cell_index': cell_idx
            }
            return fields

        # Pattern 2: Numbered field without colon (e.g., "1 Regime 40 PMD")
        pattern2 = r'(\d+)\s+([A-Za-z][^0-9]{2,}?)\s+(.+)'
        match = re.match(pattern2, text)
        if match:
            field_num, field_label, field_value = match.groups()
            field_key = self._normalize_field_name(field_label)
            fields[field_key] = {
                'value': field_value.strip(),
                'field_number': field_num,
                'original_label': field_label.strip(),
                'bbox': table_bbox,
                'row_index': row_idx,
                'cell_index': cell_idx
            }
            return fields

        # Pattern 3: Label with colon (e.g., "Invoice Number: INV-001")
        pattern3 = r'([A-Za-z][^:]+?):\s*(.+)'
        match = re.match(pattern3, text)
        if match:
            field_label, field_value = match.groups()
            field_key = self._normalize_field_name(field_label)
            fields[field_key] = {
                'value': field_value.strip(),
                'original_label': field_label.strip(),
                'bbox': table_bbox,
                'row_index': row_idx,
                'cell_index': cell_idx
            }
            return fields

        # Pattern 4: Multi-line field (label on one line, value below)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if len(lines) >= 2:
            # First line might be label, rest is value
            potential_label = lines[0]
            potential_value = ' '.join(lines[1:])

            # Check if first line looks like a label
            if re.match(r'^\d+\s+[A-Za-z]', potential_label) or ':' in potential_label:
                field_label = re.sub(r'^\d+\s+', '', potential_label).rstrip(':')
                field_key = self._normalize_field_name(field_label)

                fields[field_key] = {
                    'value': potential_value,
                    'original_label': potential_label,
                    'bbox': table_bbox,
                    'row_index': row_idx,
                    'cell_index': cell_idx
                }
                return fields

        return fields

    def _extract_from_text_block(self, block: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key-value pairs from text blocks (Title, Footer, etc.)"""
        content = block.get('content', '').strip()
        bbox = block.get('bbox', {})
        block_type = block.get('type', '')

        if not content:
            return {}

        fields = {}

        # Try to parse as key-value
        field_data = self._parse_field_from_text(content, bbox, 0, 0)

        if field_data:
            return field_data

        # If no clear key-value, store as metadata field based on block type
        if block_type == 'Footer':
            field_key = 'doc_status'
        elif block_type == 'Title':
            # Extract specific info from title if recognizable
            if 'CURRENCY' in content.upper():
                field_key = 'local_currency'
            else:
                field_key = 'document_title'
        else:
            field_key = f'text_block_{bbox.get("top", 0):.3f}'

        fields[field_key] = {
            'value': content,
            'bbox': bbox,
            'block_type': block_type
        }

        return fields

    def _extract_field_block(self, block: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract from dedicated field block"""
        content = block.get('content', '')
        bbox = block.get('bbox', {})

        # Field blocks should have key-value structure
        if ':' in content:
            parts = content.split(':', 1)
            field_key = self._normalize_field_name(parts[0])
            field_value = parts[1].strip()

            return {
                field_key: {
                    'value': field_value,
                    'bbox': bbox,
                    'block_type': 'Field'
                }
            }

        return None

    def _normalize_field_name(self, field_label: str) -> str:
        """
        Normalize field label to consistent key format.

        Examples:
        - "2 Exporter & Address No" -> "exporter_address_no"
        - "Invoice Number" -> "invoice_number"
        - "Total FOB Fcy-Imp/Ncy-Exp" -> "total_fob_fcy_imp_ncy_exp"
        """
        # Remove leading numbers
        normalized = re.sub(r'^\d+\s*', '', field_label)

        # Remove special characters, keep alphanumeric and spaces
        normalized = re.sub(r'[^a-zA-Z0-9\s]', ' ', normalized)

        # Convert to lowercase and replace spaces with underscores
        normalized = '_'.join(normalized.lower().split())

        # Remove consecutive underscores
        normalized = re.sub(r'_+', '_', normalized)

        # Remove leading/trailing underscores
        normalized = normalized.strip('_')

        return normalized

    def _calculate_proximity(
        self,
        bbox1: Dict[str, Any],
        bbox2: Dict[str, Any]
    ) -> float:
        """Calculate spatial proximity between two bboxes"""
        if bbox1.get('page') != bbox2.get('page'):
            return float('inf')  # Different pages

        # Calculate vertical distance
        v_distance = abs(bbox1.get('top', 0) - bbox2.get('top', 0))

        # Calculate horizontal distance
        h_distance = abs(bbox1.get('left', 0) - bbox2.get('left', 0))

        # Combined distance (Euclidean)
        return (v_distance ** 2 + h_distance ** 2) ** 0.5

    def _is_horizontally_aligned(
        self,
        bbox1: Dict[str, Any],
        bbox2: Dict[str, Any]
    ) -> bool:
        """Check if two bboxes are horizontally aligned"""
        if bbox1.get('page') != bbox2.get('page'):
            return False

        top1 = bbox1.get('top', 0)
        top2 = bbox2.get('top', 0)

        return abs(top1 - top2) < self.proximity_threshold

    def _is_vertically_aligned(
        self,
        bbox1: Dict[str, Any],
        bbox2: Dict[str, Any]
    ) -> bool:
        """Check if two bboxes are vertically aligned"""
        if bbox1.get('page') != bbox2.get('page'):
            return False

        left1 = bbox1.get('left', 0)
        left2 = bbox2.get('left', 0)

        return abs(left1 - left2) < self.horizontal_threshold
