"""
Reducto API implementation of the parser provider interface.
"""

import httpx
from typing import Dict, Any, Optional, List
from pathlib import Path

from .base import (
    IParserProvider,
    ParsedDocument,
    ParserException,
    ParserConnectionError,
    ParserTimeoutError,
)
from .spatial_extractor import SpatialExtractor
from shared.utils.config import settings
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class ReductoProvider(IParserProvider):
    """
    Reducto API implementation for document parsing.

    This provider can be swapped with any other implementation
    of IParserProvider without affecting other modules.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 600,
    ):
        """
        Initialize Reducto provider.

        Args:
            api_key: Reducto API key (defaults to settings.REDUCTO_API_KEY)
            base_url: Reducto API base URL (defaults to settings.REDUCTO_BASE_URL)
            timeout: Request timeout in seconds (default: 600 = 10 minutes)
        """
        self.api_key = api_key or settings.REDUCTO_API_KEY
        self.base_url = base_url or settings.REDUCTO_BASE_URL
        self.timeout = timeout
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                timeout=timeout,
                connect=30.0,  # Connection timeout
                read=timeout,  # Read timeout (for long responses)
                write=60.0,    # Write timeout (for uploading files)
                pool=10.0      # Pool timeout
            ),
            headers={"Authorization": f"Bearer {self.api_key}"},
        )

        # Initialize spatial/bbox-aware extractor
        self.spatial_extractor = SpatialExtractor()

        logger.info(f"Initialized Reducto provider with bbox-aware extraction: {self.base_url}")

    async def parse_document(
        self,
        file_bytes: bytes,
        file_name: str,
        document_type: str,
        **options,
    ) -> ParsedDocument:
        """
        Parse document using Reducto API.

        Args:
            file_bytes: Document content
            file_name: Original file name
            document_type: Type (invoice, boe, packing_list, coo, freight)
            **options: Additional Reducto options

        Returns:
            ParsedDocument with extracted content
        """
        try:
            logger.info(f"Parsing document: {file_name} (type: {document_type})")

            # Step 1: Upload document to Reducto
            file_id = await self._upload_document(file_bytes, file_name)
            logger.debug(f"Document uploaded: {file_id}")

            # Step 2: Get parse configuration for document type
            parse_config = self._get_parse_config(document_type, options)

            # Step 3: Parse document
            parse_result = await self._parse(file_id, parse_config)

            # Step 4: Convert to common format
            parsed_doc = self._convert_to_parsed_document(
                file_id, document_type, file_name, parse_result
            )

            logger.info(
                f"Document parsed successfully: {file_name} "
                f"({parsed_doc.page_count} pages, {len(parsed_doc.tables)} tables)"
            )

            return parsed_doc

        except httpx.TimeoutException as e:
            logger.error(f"Reducto API timeout: {e}")
            raise ParserTimeoutError(f"Parsing timed out after {self.timeout}s")
        except httpx.HTTPError as e:
            logger.error(f"Reducto API HTTP error: {e}")
            raise ParserConnectionError(f"Failed to connect to Reducto: {e}")
        except Exception as e:
            logger.error(f"Unexpected parsing error: {e}")
            raise ParserException(f"Failed to parse document: {e}")

    async def extract_fields(
        self, file_bytes: bytes, schema: Dict[str, Any], **options
    ) -> Dict[str, Any]:
        """
        Extract specific fields using Reducto /extract endpoint.

        Args:
            file_bytes: Document content
            schema: Universal field extraction schema (provider-agnostic)
            **options: Additional options

        Returns:
            Dictionary with extracted fields in universal format
        """
        try:
            logger.info(f"Extracting fields using schema")

            # Translate universal schema to Reducto JSON Schema format
            reducto_schema = self.translate_schema(schema)
            logger.debug(f"Translated schema: {reducto_schema}")

            # Get file name from options or use default
            file_name = options.get('file_name', 'document.pdf')

            # Upload document
            logger.info(f"Uploading document: {file_name}")
            file_id = await self._upload_document(file_bytes, file_name)
            logger.info(f"Upload successful, file_id: {file_id}")

            # CRITICAL FIX: Always use /parse endpoint to get blocks (chunks)
            # The /extract endpoint doesn't return chunks, which breaks UI approve/save functionality
            # We'll apply schema filtering during normalization instead
            logger.info("Using /parse endpoint to ensure blocks are extracted")
            payload = {
                "input": f"reducto://{file_id}"
            }
            endpoint = f"{self.base_url}/parse"

            # Store schema for normalization step (to extract structured fields from chunks)
            normalize_schema = reducto_schema

            logger.debug(f"Request payload: {payload}")

            # Use explicit timeout for field extraction (large files take time)
            response = await self.client.post(
                endpoint, 
                json=payload,
                timeout=httpx.Timeout(
                    timeout=self.timeout,
                    read=self.timeout,
                    write=60.0
                )
            )

            if response.status_code != 200:
                logger.error(f"Extract error: {response.status_code} - {response.text}")
                logger.error(f"Request payload was: {payload}")

            response.raise_for_status()

            raw_result = response.json()
            logger.info(f"Field extraction complete")

            # Normalize Reducto response to universal format for internal processing
            document_type = options.get('document_type', 'unknown')
            normalized = self.normalize_response(
                raw_result,
                document_type,
                schema=normalize_schema  # Pass schema for field filtering
            )

            # IMPORTANT: Preserve raw Reducto response for API output
            # This allows users to get the exact Reducto format
            normalized['raw_provider_response'] = raw_result

            return normalized

        except Exception as e:
            logger.error(f"Field extraction failed: {e}")
            raise ParserException(f"Failed to extract fields: {e}")

    def translate_schema(self, universal_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translate universal schema to Reducto JSON Schema format.

        Args:
            universal_schema: Universal schema from SchemaGenerator

        Returns:
            Reducto-compatible JSON Schema or None for open extraction
        """
        mode = universal_schema.get("mode", "focused")

        if mode == "open":
            # OPEN MODE: Don't send a schema - let Reducto extract everything
            logger.info("Using OPEN mode - Reducto will extract all fields")
            return None  # No schema = extract everything

        # FOCUSED MODE: Traditional schema-based extraction
        logger.debug("Translating focused schema to Reducto JSON Schema format")

        # Reducto expects JSON Schema format
        json_schema = {
            "type": "object",
            "properties": {}
        }

        # Translate header fields
        fields = universal_schema.get("fields", {})
        for field_name, field_def in fields.items():
            json_schema["properties"][field_name] = self._translate_field_type(field_def)

        # Translate items if present
        items_def = universal_schema.get("items")
        if items_def:
            item_fields = items_def.get("fields", {})
            field_name = items_def.get("field_name", "items")

            # Create array schema for items
            json_schema["properties"][field_name] = {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {}
                }
            }

            # Add item fields
            for item_field_name, item_field_def in item_fields.items():
                json_schema["properties"][field_name]["items"]["properties"][item_field_name] = \
                    self._translate_field_type(item_field_def)

        logger.debug(f"Translated schema: {json_schema}")
        return json_schema

    def _translate_field_type(self, field_def: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translate universal field type to Reducto JSON Schema type.

        Args:
            field_def: Universal field definition

        Returns:
            JSON Schema type definition
        """
        universal_type = field_def.get("type", "string")

        # Map universal types to JSON Schema types
        type_mapping = {
            "string": "string",
            "integer": "number",  # Reducto uses 'number' for both int and decimal
            "decimal": "number",
            "date": "string",  # Dates are strings in Reducto
            "boolean": "boolean"
        }

        json_type = type_mapping.get(universal_type, "string")

        # Build JSON Schema field
        field_schema = {"type": json_type}

        # Make field nullable if not required
        if not field_def.get("required", False):
            field_schema["type"] = [json_type, "null"]

        return field_schema

    def normalize_response(
        self,
        provider_response: Dict[str, Any],
        document_type: str,
        schema: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Normalize Reducto response to universal format.

        Handles both /parse (open extraction) and /extract (schema-based) responses.

        Args:
            provider_response: Raw Reducto API response
            document_type: Type of document
            schema: Optional schema for field filtering (None = extract all fields)

        Returns:
            Normalized universal format with ALL extracted fields
        """
        logger.info(f"Normalizing Reducto response for {document_type}")
        if schema:
            logger.info("Schema provided - will apply field filtering to chunks")

        # DEBUG: Log full response structure
        logger.info(f"Provider response keys: {list(provider_response.keys())}")
        logger.info(f"Provider response type: {type(provider_response)}")

        # Extract result from Reducto response
        result = provider_response.get('result', provider_response)

        logger.info(f"Result type: {type(result)}")
        logger.info(f"Result keys: {list(result.keys()) if isinstance(result, dict) else 'not a dict'}")

        # Handle case where result is a list (Reducto sometimes returns array)
        if isinstance(result, list):
            logger.info(f"Result is a list with {len(result)} items")
            if len(result) == 0:
                result = {}
            else:
                result = result[0]
                logger.info(f"Using first item from list, keys: {list(result.keys())}")

        # Since we always use /parse endpoint, response always has chunks
        blocks = []  # Initialize blocks list
        if 'chunks' in result:
            # Extract ALL structured data from chunks (fields, items, blocks)
            logger.info("Processing /parse response - extracting all fields from chunks")
            fields, items, blocks = self._extract_from_parse_chunks(result)

            # If schema provided (FOCUSED mode), VALIDATE but don't filter out discovered fields
            # Keep ALL extracted fields, schema is for validation/structure guidance only
            if schema and schema.get('properties'):
                logger.info("Schema provided for validation (not filtering) - keeping all extracted fields")
                schema_fields = set(schema['properties'].keys())

                # Log which fields are in schema vs discovered
                schema_matched = {k for k in fields.keys() if k in schema_fields}
                extra_discovered = {k for k in fields.keys() if k not in schema_fields and k != 'items'}

                logger.info(f"Schema fields matched: {len(schema_matched)}")
                logger.info(f"Extra fields discovered: {len(extra_discovered)} - {list(extra_discovered)[:5]}")
                logger.info(f"Total fields preserved: {len(fields)}")
                # NO FILTERING - keep all fields
        else:
            # Fallback: No chunks found (shouldn't happen with /parse endpoint)
            logger.warning("No chunks found in /parse response - this shouldn't happen!")
            fields = {}
            items = []
            blocks = []

        # Extract metadata from Reducto response
        metadata = {
            "provider": "reducto",
            "job_id": provider_response.get("job_id"),
            "extraction_duration": provider_response.get("duration"),  # Fixed: duration → extraction_duration
            "duration": provider_response.get("duration"),  # Keep both for compatibility
            "confidence": self._calculate_confidence(provider_response),
            "page_count": result.get("chunks", [{}])[0].get("page") if 'chunks' in result else None,
            # Preserve additional Reducto metadata
            "studio_link": provider_response.get("studio_link"),
            "pdf_url": provider_response.get("pdf_url"),
            "usage": provider_response.get("usage")  # Contains num_pages, credits
        }

        # Extract layout/structure information
        layout = self._extract_layout_structure(provider_response, result)

        # Build universal format with BOTH normalized data AND raw provider response
        normalized = {
            "fields": fields,
            "items": items,
            "blocks": blocks,  # NEW: ALL content blocks for full document rendering
            "layout": layout,  # Layout/structure information
            "metadata": metadata,
            "raw_provider_response": provider_response  # PRESERVE original Reducto structure
        }

        logger.info(
            f"Normalized: {len(fields)} fields, {len(items)} items, "
            f"{len(blocks)} blocks, {len(layout.get('pages', []))} pages with layout"
        )
        logger.info(f"Raw provider response preserved with keys: {list(provider_response.keys())}")

        return normalized

    def _extract_layout_structure(
        self,
        provider_response: Dict[str, Any],
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Extract layout and structure information from Reducto response.

        Preserves bounding boxes, block positions, form fields, and visual structure.

        Args:
            provider_response: Full Reducto API response
            result: Result object from response

        Returns:
            Layout structure dictionary with pages, blocks, bounding boxes
        """
        layout = {
            "pages": [],
            "total_pages": 0,
            "has_form_fields": False,
            "has_tables": False
        }

        # Extract from chunks if available (from /parse endpoint)
        chunks = result.get("chunks", [])
        
        if chunks:
            # Group blocks by page
            pages_dict = {}
            
            for chunk in chunks:
                page_num = chunk.get("page", 1)
                blocks = chunk.get("blocks", [])
                
                if page_num not in pages_dict:
                    pages_dict[page_num] = {
                        "page_number": page_num,
                        "blocks": [],
                        "regions": []
                    }
                
                for block in blocks:
                    block_info = {
                        "type": block.get("type", ""),
                        "content": block.get("content", ""),
                        "bbox": block.get("bbox"),  # [x, y, width, height] or similar
                        "confidence": block.get("confidence"),
                        "page": block.get("page", page_num)
                    }
                    
                    # Remove None values
                    block_info = {k: v for k, v in block_info.items() if v is not None}
                    
                    pages_dict[page_num]["blocks"].append(block_info)
                    
                    # Track if we have form fields or tables
                    if block.get("type") == "FormField" or "form" in block.get("type", "").lower():
                        layout["has_form_fields"] = True
                    if block.get("type") == "Table":
                        layout["has_tables"] = True
                
                # Extract regions (if Reducto provides them)
                regions = chunk.get("regions", [])
                if regions:
                    pages_dict[page_num]["regions"].extend(regions)
            
            # Convert to list sorted by page number
            layout["pages"] = [pages_dict[p] for p in sorted(pages_dict.keys())]
            layout["total_pages"] = len(pages_dict)
        
        # Extract from result directly if no chunks (from /extract endpoint)
        # Some providers might return layout info differently
        if not layout["pages"] and "layout" in result:
            layout.update(result.get("layout", {}))
        
        return layout

    def _extract_from_structured_table(
        self,
        table_data: Dict[str, Any] | List[Any],
        block: Dict[str, Any],
        block_idx: int
    ) -> List[Dict[str, Any]]:
        """
        Extract items from Reducto's structured table_data format.
        
        This format includes cell-level bounding boxes and structured row/cell data,
        which is more accurate than parsing HTML strings.
        
        Args:
            table_data: Structured table data from Reducto (can be list of rows or dict with rows)
            block: Block object containing table
            block_idx: Index of the table block
            
        Returns:
            List of item dictionaries with column metadata and cell-level bbox
        """
        items = []
        
        # Normalize table_data format (could be list or dict)
        if isinstance(table_data, dict):
            rows = table_data.get("rows", table_data.get("data", []))
        else:
            rows = table_data
        
        if not rows or len(rows) == 0:
            logger.warning(f"Table block {block_idx} has no rows in table_data")
            return items
        
        # First row is typically headers
        header_row = rows[0] if rows else []
        
        # Extract headers - handle different formats
        headers = []
        if isinstance(header_row, list):
            # List of cell values
            headers = [str(cell.get("value", cell) if isinstance(cell, dict) else cell).strip() 
                      for cell in header_row]
        elif isinstance(header_row, dict):
            # Dict with cells array
            cells = header_row.get("cells", [])
            headers = [str(cell.get("value", cell.get("text", ""))).strip() for cell in cells]
        
        # Normalize headers
        normalized_headers = [self._normalize_key(h) for h in headers]
        
        logger.info(f"Extracting from structured table: {len(rows)-1} data rows, {len(headers)} columns")
        
        # Extract data rows
        for row_idx, row in enumerate(rows[1:], start=1):
            item = {}
            
            # Handle different row formats
            if isinstance(row, list):
                cells = row
            elif isinstance(row, dict):
                cells = row.get("cells", [])
            else:
                continue
            
            for col_idx, cell in enumerate(cells):
                if col_idx >= len(normalized_headers):
                    continue
                
                normalized_header = normalized_headers[col_idx]
                if not normalized_header:
                    continue
                
                # Extract cell value
                if isinstance(cell, dict):
                    cell_value = cell.get("value") or cell.get("text") or cell.get("content", "")
                    cell_bbox = cell.get("bbox")  # Cell-level bounding box!
                    cell_confidence = cell.get("confidence")
                else:
                    cell_value = str(cell).strip()
                    cell_bbox = None
                    cell_confidence = None
                
                if not cell_value:
                    continue
                
                # Store with full metadata including cell-level bbox
                item[normalized_header] = {
                    "value": str(cell_value).strip(),
                    "column_index": col_idx,
                    "column_number": col_idx + 1,
                    "original_header": headers[col_idx] if col_idx < len(headers) else None,
                    "normalized_header": normalized_header,
                    "row_index": row_idx,
                    "table_block_index": block_idx
                }
                
                # Add cell-level bbox (more precise than table-level bbox)
                if cell_bbox:
                    item[normalized_header]["cell_bbox"] = cell_bbox
                
                # Add table-level bbox as fallback
                if block.get("bbox"):
                    item[normalized_header]["table_bbox"] = block.get("bbox")
                
                # Add confidence if available
                if cell_confidence is not None:
                    item[normalized_header]["confidence"] = cell_confidence
                
                # Remove None values
                item[normalized_header] = {
                    k: v for k, v in item[normalized_header].items() 
                    if v is not None
                }
            
            if item:
                items.append(item)
        
        return items

    def _extract_from_parse_chunks(self, parse_result: Dict[str, Any]) -> tuple:
        """
        Extract ALL fields, tables, and raw blocks from Reducto /parse response.

        The /parse endpoint returns chunks with blocks containing structured data.
        We extract EVERYTHING including titles, text, key-values, tables.

        Args:
            parse_result: Result from /parse endpoint

        Returns:
            Tuple of (fields_dict, items_list, blocks_list)
        """
        fields = {}
        items = []
        all_blocks = []  # NEW: Store ALL blocks for full document rendering

        chunks = parse_result.get("chunks", [])

        logger.info(f"Processing {len(chunks)} chunks from /parse response")
        logger.info(f"Parse result structure: {list(parse_result.keys())}")

        for chunk_idx, chunk in enumerate(chunks):
            logger.info(f"Chunk {chunk_idx} keys: {list(chunk.keys())}")
            logger.info(f"Chunk {chunk_idx} type: {type(chunk)}")

            # Get the full content
            content = chunk.get("content", "")

            # Extract from blocks
            blocks = chunk.get("blocks", [])

            logger.info(f"Chunk {chunk_idx} has {len(blocks)} blocks")

            # If no blocks, log the entire chunk to see its structure
            if len(blocks) == 0:
                logger.warning(f"Chunk {chunk_idx} has no blocks! Chunk structure: {list(chunk.keys())}")
                logger.info(f"Chunk {chunk_idx} content preview: {str(chunk)[:500]}")

            for block_idx, block in enumerate(blocks):
                block_type = block.get("type", "")
                block_content = block.get("content", "")

                logger.info(f"Block {block_idx}: type={block_type}, content_length={len(block_content) if block_content else 0}")

                # Log block structure
                if isinstance(block, dict):
                    logger.info(f"Block {block_idx} keys: {list(block.keys())}")

                # NEW: Store ALL blocks (including empty ones) for full document rendering
                all_blocks.append({
                    "type": block_type,
                    "content": block_content,
                    "bbox": block.get("bbox"),
                    "page": block.get("page", chunk_idx + 1),
                    "confidence": block.get("confidence"),
                    "granular_confidence": block.get("granular_confidence")  # Include numeric confidence scores
                })

                # Skip empty content for field extraction
                if not block_content:
                    logger.warning(f"Skipping empty block {block_idx} (no content) for field extraction")
                    continue

                # Log first 200 chars of content for debugging
                logger.info(f"Block {block_idx} content preview: {block_content[:200]}")

                # Extract from ALL block types that have content
                # Key Value, Text, Figure, Header - all can contain structured data

                # Extract tables as items (highest priority)
                if block_type == "Table":
                    logger.info(f"Extracting table from block {block_idx}")
                    
                    # Check if Reducto provided structured table_data (preferred - has cell-level bbox)
                    table_data = block.get("table_data")
                    
                    if table_data and isinstance(table_data, (list, dict)):
                        # Use structured table_data from Reducto (has cell-level info)
                        logger.info("Using structured table_data from Reducto (with cell-level metadata)")
                        table_items = self._extract_from_structured_table(table_data, block, block_idx)
                        items.extend(table_items)
                    else:
                        # Fall back to parsing HTML/content string
                        logger.info("Parsing table from HTML/content (fallback)")
                        table_rows = self._parse_table_dynamic(block_content)

                        if table_rows and len(table_rows) > 1:
                            # First row is headers
                            headers = table_rows[0]
                            # Normalize headers to snake_case
                            normalized_headers = [
                                self._normalize_key(h) for h in headers
                            ]

                            logger.info(f"Extracted {len(table_rows)-1} rows with headers: {normalized_headers}")

                            # Extract data rows with column metadata
                            for row_idx, row in enumerate(table_rows[1:], start=1):
                                if len(row) > 0:
                                    item = {}
                                    for col_idx, (original_header, normalized_header) in enumerate(zip(headers, normalized_headers)):
                                        if col_idx < len(row) and normalized_header and row[col_idx]:
                                            cell_value = row[col_idx].strip()
                                            
                                            # Store value with column metadata
                                            item[normalized_header] = {
                                                "value": cell_value,
                                                "column_index": col_idx,  # 0-based column position
                                                "column_number": col_idx + 1,  # 1-based column number
                                                "original_header": original_header,  # Original header name
                                                "normalized_header": normalized_header,  # Snake case header
                                                "row_index": row_idx,  # Row number in table
                                                "table_block_index": block_idx  # Which table block this came from
                                            }
                                            
                                            # Also store bbox if available from block
                                            if block.get("bbox"):
                                                item[normalized_header]["table_bbox"] = block.get("bbox")
                                            
                                            # Remove None values
                                            item[normalized_header] = {
                                                k: v for k, v in item[normalized_header].items() 
                                                if v is not None
                                            }
                                            
                                            # If only value exists, store as simple value for backward compatibility
                                            if len(item[normalized_header]) == 1:
                                                item[normalized_header] = cell_value
                                    
                                    if item:  # Only add non-empty items
                                        items.append(item)

                # Extract from ANY block with content (Text, Figure, Header, Key Value, Footer, Title, etc.)
                # This makes it truly universal - we extract from EVERYTHING
                else:
                    # Dynamic key:value extraction - handles any format
                    extracted_fields = self._extract_key_values_dynamic(block_content)

                    # Merge extracted fields (first occurrence wins)
                    # Also preserve layout info (bbox) for each field if available
                    for key, value in extracted_fields.items():
                        if key not in fields:
                            # Store field value with optional layout metadata
                            field_data = {
                                "value": value,
                                "bbox": block.get("bbox"),  # Preserve bounding box
                                "block_type": block_type,
                                "page": block.get("page"),
                                "confidence": block.get("confidence")
                            }
                            # Remove None values for cleaner JSON
                            field_data = {k: v for k, v in field_data.items() if v is not None}
                            fields[key] = field_data if len(field_data) > 1 else value

        # BBOX-AWARE EXTRACTION: Use spatial intelligence to extract additional fields
        logger.info("Starting bbox-aware spatial extraction...")
        try:
            spatial_fields = self.spatial_extractor.extract_fields_from_blocks(all_blocks)
            logger.info(f"Spatial extractor found {len(spatial_fields)} fields")

            # Merge spatial fields with existing fields (spatial fields have priority for richer data)
            for field_key, field_data in spatial_fields.items():
                if field_key not in fields:
                    fields[field_key] = field_data
                    logger.debug(f"Added spatial field: {field_key}")
                else:
                    logger.debug(f"Field {field_key} already exists, keeping original")

        except Exception as e:
            logger.error(f"Error in spatial extraction: {e}", exc_info=True)

        logger.info(f"Extracted from chunks: {len(fields)} fields, {len(items)} table rows, {len(all_blocks)} blocks")

        return fields, items, all_blocks

    def _normalize_key(self, key: str) -> str:
        """
        Normalize a key to snake_case format.

        Args:
            key: Original key

        Returns:
            Normalized key in snake_case
        """
        if not key:
            return ""

        # Remove HTML tags and special characters
        import re
        key = re.sub(r'<[^>]+>', '', key)  # Remove HTML tags
        key = key.lower()
        key = key.replace(" ", "_").replace("-", "_").replace("/", "_")
        key = key.replace("(", "").replace(")", "").replace(".", "").replace(",", "")
        key = key.replace("\n", "_").replace("\r", "")

        # Remove multiple underscores
        key = "_".join(filter(None, key.split("_")))

        return key

    def _parse_table_dynamic(self, table_content: str) -> list:
        """
        Dynamically parse table from any format (HTML, markdown, pipe-delimited, etc.).

        Args:
            table_content: Raw table content

        Returns:
            List of rows, where each row is a list of cells
        """
        import re
        from html.parser import HTMLParser

        # Check format and parse accordingly
        content_stripped = table_content.strip()

        # Try HTML table first
        if '<table' in content_stripped.lower():
            return self._parse_html_table(table_content)

        # Try markdown/pipe-delimited table
        elif '|' in content_stripped:
            return self._parse_pipe_table(table_content)

        # Fallback: try to parse as tab/comma separated
        else:
            return self._parse_delimited_table(table_content)

    def _parse_html_table(self, html_content: str) -> list:
        """Parse HTML table."""
        from html.parser import HTMLParser

        class TableParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.tables = []
                self.current_table = []
                self.current_row = []
                self.current_cell = []
                self.in_table = False
                self.in_row = False
                self.in_cell = False

            def handle_starttag(self, tag, attrs):
                if tag == 'table':
                    self.in_table = True
                    self.current_table = []
                elif tag == 'tr':
                    self.in_row = True
                    self.current_row = []
                elif tag in ['td', 'th']:
                    self.in_cell = True
                    self.current_cell = []

            def handle_endtag(self, tag):
                if tag == 'table':
                    self.in_table = False
                    if self.current_table:
                        self.tables.append(self.current_table)
                elif tag == 'tr':
                    self.in_row = False
                    if self.current_row:
                        self.current_table.append(self.current_row)
                elif tag in ['td', 'th']:
                    self.in_cell = False
                    cell_content = ''.join(self.current_cell).strip()
                    self.current_row.append(cell_content)

            def handle_data(self, data):
                if self.in_cell:
                    self.current_cell.append(data)

        parser = TableParser()
        try:
            parser.feed(html_content)
            return parser.tables[0] if parser.tables else []
        except Exception as e:
            logger.warning(f"HTML table parsing failed: {e}")
            return []

    def _parse_pipe_table(self, pipe_content: str) -> list:
        """Parse pipe-delimited (markdown) table."""
        import re

        lines = [line.strip() for line in pipe_content.split('\n') if line.strip()]
        table_rows = []

        for line in lines:
            # Skip separator lines (e.g., |---|---|)
            if re.match(r'^\|[\s\-:]+\|$', line):
                continue

            # Split by | and clean
            cells = [cell.strip() for cell in line.split('|')]
            # Remove empty first/last cells (from leading/trailing |)
            cells = [c for c in cells if c]

            # Clean HTML tags from cells
            cells = [re.sub(r'<br\s*/?>', ' ', c) for c in cells]

            if cells:
                table_rows.append(cells)

        return table_rows

    def _parse_delimited_table(self, content: str) -> list:
        """Parse tab or comma delimited table."""
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        table_rows = []

        for line in lines:
            # Try tab-delimited first
            if '\t' in line:
                cells = [c.strip() for c in line.split('\t') if c.strip()]
            # Try comma-delimited
            elif ',' in line:
                cells = [c.strip() for c in line.split(',') if c.strip()]
            # Single cell
            else:
                cells = [line]

            if cells:
                table_rows.append(cells)

        return table_rows

    def _extract_key_values_dynamic(self, content: str) -> dict:
        """
        Dynamically extract key:value pairs from any text format.

        Handles:
        - Single-line: "Key: Value"
        - Multi-line: "Key:\nValue"
        - Bullet points: "- Key: Value"
        - Any separator variations

        Args:
            content: Raw text content

        Returns:
            Dictionary of extracted key:value pairs
        """
        fields = {}
        lines = content.split("\n")

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if not line:
                i += 1
                continue

            # Remove bullet points
            if line.startswith("-") or line.startswith("•"):
                line = line[1:].strip()

            # Check for key:value pattern
            if ":" in line:
                parts = line.split(":", 1)
                key = parts[0].strip()
                value = parts[1].strip() if len(parts) > 1 else ""

                # If value is empty, check next line
                if not value and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    # If next line doesn't have a colon, it's likely the value
                    if next_line and ":" not in next_line:
                        value = next_line
                        i += 1  # Skip next line since we consumed it

                # Filter out very long keys (likely not field names) and empty values
                if key and len(key) < 100 and value:
                    normalized_key = self._normalize_key(key)
                    if normalized_key:
                        fields[normalized_key] = value

            i += 1

        return fields

    def _calculate_confidence(self, provider_response: Dict[str, Any]) -> float:
        """
        Calculate overall confidence score from Reducto response.

        Args:
            provider_response: Reducto API response

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Reducto doesn't provide per-field confidence in extract endpoint
        # We can add this later if Reducto adds confidence scores
        # For now, return 0.0 to indicate unknown confidence
        return 0.0

    async def health_check(self) -> bool:
        """
        Check if Reducto API is accessible.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Simple health check - try to access the API
            response = await self.client.get(f"{self.base_url}/")
            return response.status_code in [200, 404]  # 404 is ok, means API is up
        except Exception as e:
            logger.error(f"Reducto health check failed: {e}")
            return False

    async def _upload_document(self, file_bytes: bytes, file_name: str) -> str:
        """
        Upload document to Reducto.

        Args:
            file_bytes: Document content
            file_name: File name with extension

        Returns:
            Reducto file ID
        """
        files = {"file": (file_name, file_bytes)}

        response = await self.client.post(f"{self.base_url}/upload", files=files)
        response.raise_for_status()

        result = response.json()
        return result["file_id"]

    async def _parse(self, file_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse document using Reducto /parse endpoint.

        Args:
            file_id: Reducto file ID
            config: Parse configuration

        Returns:
            Parse result from Reducto
        """
        payload = {"input": f"reducto://{file_id}", **config}

        logger.debug(f"Parse payload: {payload}")

        response = await self.client.post(
            f"{self.base_url}/parse", 
            json=payload,
            timeout=httpx.Timeout(
                timeout=self.timeout,
                read=self.timeout
            )
        )

        if response.status_code != 200:
            logger.error(f"Reducto parse error: {response.status_code} - {response.text}")

        response.raise_for_status()

        return response.json()

    def _get_parse_config(
        self, document_type: str, options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get Reducto parse configuration based on document type.

        Args:
            document_type: Type of document
            options: User-provided options to override defaults

        Returns:
            Parse configuration for Reducto
        """
        # Minimal configuration for Reducto
        config = {}

        # Add basic options if needed
        if document_type == "freight":
            config["spreadsheet"] = {
                "clustering": "accurate",
            }

        # Merge with user options
        if options:
            config = self._deep_merge(config, options)

        return config

    def _convert_to_parsed_document(
        self, file_id: str, document_type: str, file_name: str, parse_result: Dict
    ) -> ParsedDocument:
        """
        Convert Reducto parse result to common ParsedDocument format.

        Args:
            file_id: Reducto file ID
            document_type: Document type
            file_name: Original file name
            parse_result: Reducto parse result

        Returns:
            ParsedDocument
        """
        result = parse_result.get("result", {})

        # Extract text content
        chunks = result.get("chunks", [])
        raw_text = "\n".join([chunk.get("content", "") for chunk in chunks])

        # Extract tables
        tables = []
        for chunk in chunks:
            if chunk.get("type") == "table":
                tables.append(
                    {
                        "data": chunk.get("table_data"),
                        "page": chunk.get("page"),
                        "bbox": chunk.get("bbox"),
                    }
                )

        # Extract metadata
        metadata = {
            "job_id": parse_result.get("job_id"),
            "duration": parse_result.get("duration"),
            "usage": parse_result.get("usage"),
            "pdf_url": parse_result.get("pdf_url"),
            "studio_link": parse_result.get("studio_link"),
        }

        # Page count
        page_count = None
        if metadata.get("usage"):
            page_count = metadata["usage"].get("pages")

        return ParsedDocument(
            document_id=file_id,
            document_type=document_type,
            raw_text=raw_text,
            structured_data=result,
            tables=tables,
            metadata=metadata,
            page_count=page_count,
        )

    @staticmethod
    def _deep_merge(dict1: Dict, dict2: Dict) -> Dict:
        """Deep merge two dictionaries."""
        result = dict1.copy()

        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ReductoProvider._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - close HTTP client."""
        await self.client.aclose()


# ==============================================================================
# AUTO-REGISTRATION: Register Reducto provider with factory
# ==============================================================================

def _create_reducto_provider(provider_config: dict) -> IParserProvider:
    """
    Factory function for creating Reducto provider instances.

    This function is registered with ProviderFactory and called when
    a Reducto provider is requested.

    Args:
        provider_config: Provider configuration from providers.yaml

    Returns:
        ReductoProvider instance configured with settings
    """
    from shared.utils.config import settings

    # API key from environment (loaded by settings)
    api_key = settings.REDUCTO_API_KEY

    # Base URL from config or settings
    base_url = provider_config.get('base_url', settings.REDUCTO_BASE_URL)

    # Timeout from config
    timeout = provider_config.get('timeout', 120)

    logger.debug(
        f"Creating Reducto provider: base_url={base_url}, timeout={timeout}"
    )

    return ReductoProvider(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout
    )


# Register this provider with the factory
# This happens automatically when this module is imported
try:
    from .provider_factory import ProviderFactory
    ProviderFactory.register_provider("reducto", _create_reducto_provider)
    logger.info("Reducto provider registered successfully")
except Exception as e:
    logger.warning(f"Failed to register Reducto provider: {e}")
