"""
AI Semantic Enhancer for intelligent document extraction post-processing.

Adds AI-powered semantic understanding to raw extraction results from
providers like Reducto. Solves problems like:
- Text sections treated as single-column tables
- Section headers (EXPORTER:, CONSIGNEE:) not recognized as labels
- Multi-line addresses split into separate rows
- Context-dependent field extraction
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class AISemanticEnhancer:
    """
    Enhances raw extraction with AI-powered semantic understanding.

    This layer adds intelligence on top of computer vision extraction,
    enabling the system to understand document structure and context
    beyond bounding boxes and table grids.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model_variant: Optional[str] = None
    ):
        """
        Initialize AI Semantic Enhancer.

        Uses centralized LLM configuration from config/llm.yaml.
        Module name: "ai_semantic_enhancer"

        Args:
            provider: Override LLM provider (anthropic, google, openai)
            model_variant: Override model variant (default, fast, pro)
        """
        from shared.utils.llm_config import get_llm_for_module

        self.llm = get_llm_for_module(
            module_name="ai_semantic_enhancer",
            provider=provider,
            model_variant=model_variant
        )

        logger.info("Initialized AI Semantic Enhancer with centralized LLM config")

    async def enhance_extraction(
        self,
        raw_extraction: Dict[str, Any],
        document_type: str
    ) -> Dict[str, Any]:
        """
        Enhance raw extraction with AI-powered semantic understanding.

        Process:
        1. Analyze items array for section patterns
        2. Identify section headers (ends with ":")
        3. Extract content under each section
        4. Parse multi-line structured text (addresses, party info)
        5. Return enhanced fields to merge with original

        Args:
            raw_extraction: Normalized extraction from provider (fields, items, blocks)
            document_type: Type of document being processed

        Returns:
            Enhanced extraction with additional AI-parsed fields
        """
        try:
            logger.info(f"🤖 AI Semantic Enhancement starting for {document_type}")

            # Extract components
            fields = raw_extraction.get("fields", {})
            items = raw_extraction.get("items", [])
            blocks = raw_extraction.get("blocks", [])

            logger.info(f"Input: {len(fields)} fields, {len(items)} items, {len(blocks)} blocks")

            # Enhanced fields to return
            enhanced_fields = {}

            # STEP 1: Detect if items array is a single-column table (common problem)
            single_column_table = self._detect_single_column_table(items)

            if single_column_table:
                logger.info("🔍 Detected single-column table - applying AI section parsing")
                section_fields = await self._parse_sections_with_ai(
                    items,
                    document_type
                )
                enhanced_fields.update(section_fields)
                logger.info(f"  ✅ Extracted {len(section_fields)} fields from sections")

            # STEP 2: Parse multi-column tables with AI intelligence
            # Even well-structured tables can benefit from AI understanding
            elif items:
                logger.info("🔍 Analyzing multi-column table structure")
                table_fields = await self._parse_table_with_ai(
                    items,
                    document_type
                )
                enhanced_fields.update(table_fields)
                logger.info(f"  ✅ Extracted {len(table_fields)} fields from table")

            # STEP 3: Parse unstructured blocks for additional context
            if blocks:
                logger.info("🔍 Analyzing unstructured blocks")
                block_fields = await self._parse_blocks_with_ai(
                    blocks,
                    document_type
                )
                enhanced_fields.update(block_fields)
                logger.info(f"  ✅ Extracted {len(block_fields)} fields from blocks")

            # Build result
            result = {
                "fields": enhanced_fields,
                "metadata": {
                    "ai_enhanced": True,
                    "enhancement_method": "gemini_semantic_parsing",
                    "fields_added": len(enhanced_fields)
                }
            }

            logger.info(f"✅ AI Semantic Enhancement complete: {len(enhanced_fields)} enhanced fields")

            return result

        except Exception as e:
            logger.error(f"AI Semantic Enhancement failed: {e}", exc_info=True)
            # Return empty on error (original extraction preserved)
            return {
                "fields": {},
                "metadata": {
                    "ai_enhanced": False,
                    "enhancement_error": str(e)
                }
            }

    def _detect_single_column_table(self, items: List[Dict]) -> bool:
        """
        Detect if items array represents a single-column table.

        This is a common Reducto failure mode where structured sections
        are treated as a table with only one column.

        Args:
            items: Items array from extraction

        Returns:
            True if single-column table detected
        """
        if not items or len(items) < 3:
            return False

        # Check if all items have the same single key
        # (ignoring metadata keys like row_index, table_bbox)
        first_item = items[0]
        if not isinstance(first_item, dict):
            return False

        # Get data keys (not metadata)
        data_keys = [k for k in first_item.keys()
                    if not k.startswith('_') and k not in ['row_index', 'table_bbox']]

        if len(data_keys) != 1:
            return False

        # Check if all items have the same structure
        column_name = data_keys[0]
        consistent_count = 0

        for item in items[:10]:  # Check first 10 items
            if isinstance(item, dict) and column_name in item:
                consistent_count += 1

        # If 80%+ have same single column, it's likely single-column table
        is_single_column = (consistent_count / min(len(items), 10)) >= 0.8

        if is_single_column:
            logger.info(f"Single-column table detected with column: '{column_name}'")

        return is_single_column

    async def _parse_sections_with_ai(
        self,
        items: List[Dict],
        document_type: str
    ) -> Dict[str, Any]:
        """
        Use AI to parse section-based content from single-column table.

        Example input (items array):
        [
          {"column": "EXPORTER:"},
          {"column": "IB TEC INTERNATIONAL"},
          {"column": "1-6-19-501, SAKAE CHO"},
          {"column": "Japan"},
          {"column": "CONSIGNEE:"},
          {"column": "ALEX ODOOM"},
          ...
        ]

        Example output:
        {
          "exporter_name": "IB TEC INTERNATIONAL",
          "exporter_address": "1-6-19-501, SAKAE CHO",
          "exporter_country": "Japan",
          "exporter_full": "IB TEC INTERNATIONAL\n1-6-19-501...",
          "consignee_name": "ALEX ODOOM",
          ...
        }

        Args:
            items: Items array with single-column structure
            document_type: Document type for context

        Returns:
            Dictionary of parsed fields
        """
        try:
            # Extract text content from items
            text_lines = []
            for item in items:
                if isinstance(item, dict):
                    # Get the data value (first non-metadata key)
                    for key, value in item.items():
                        if not key.startswith('_') and key not in ['row_index', 'table_bbox']:
                            if isinstance(value, dict) and 'value' in value:
                                text_lines.append(value['value'])
                            else:
                                text_lines.append(str(value))
                            break

            if not text_lines:
                return {}

            # Build structured content for AI
            content = "\n".join(text_lines)

            # Create AI prompt for semantic parsing
            prompt = self._build_section_parsing_prompt(content, document_type)

            # Call LLM
            logger.debug("Calling LLM for section parsing...")
            response = await self.llm.ainvoke(prompt)

            # Parse LLM response
            parsed_fields = self._parse_llm_json_response(response.content)

            logger.info(f"LLM parsed {len(parsed_fields)} fields from {len(text_lines)} lines")

            # Wrap in Reducto-compatible format for consistency
            # Reducto returns: {"field_name": {"value": "...", "bbox": {...}, ...}}
            # AI fields should have similar structure for proper merging and storage
            structured_fields = {}
            for field_name, field_value in parsed_fields.items():
                structured_fields[field_name] = {
                    "value": field_value,
                    "source": "ai_enhancement",
                    "enhancement_method": "gemini_semantic_parsing"
                }

            return structured_fields

        except Exception as e:
            logger.error(f"Section parsing with AI failed: {e}")
            return {}

    async def _parse_table_with_ai(
        self,
        items: List[Dict],
        document_type: str
    ) -> Dict[str, Any]:
        """
        Use AI to parse multi-column table data intelligently.

        Even well-structured tables can benefit from AI understanding
        for consolidating related rows and extracting semantic meaning.

        Args:
            items: Items array with table data
            document_type: Document type for context

        Returns:
            Dictionary of parsed fields
        """
        try:
            # For now, return empty (focus on single-column problem first)
            # This can be expanded later for multi-column intelligence
            return {}

        except Exception as e:
            logger.error(f"Table parsing with AI failed: {e}")
            return {}

    async def _parse_blocks_with_ai(
        self,
        blocks: List[Dict],
        document_type: str
    ) -> Dict[str, Any]:
        """
        Use AI to parse unstructured blocks for additional fields.

        Args:
            blocks: Blocks array from extraction
            document_type: Document type for context

        Returns:
            Dictionary of parsed fields
        """
        try:
            # For now, return empty (focus on items array first)
            # This can be expanded later for block intelligence
            return {}

        except Exception as e:
            logger.error(f"Block parsing with AI failed: {e}")
            return {}

    def _build_section_parsing_prompt(
        self,
        content: str,
        document_type: str
    ) -> str:
        """
        Build LLM prompt for parsing section-based content.

        Args:
            content: Text content with sections
            document_type: Document type for context

        Returns:
            LLM prompt string
        """
        prompt = f"""You are a document parsing expert. Extract structured fields from this {document_type} document.

The document contains SECTION HEADERS (ending with ":") followed by their content.
Common sections include EXPORTER:, CONSIGNEE:, SHIPPING DETAILS:, etc.

DOCUMENT CONTENT:
{content}

INSTRUCTIONS:
1. Identify section headers (lines ending with ":")
2. Extract content lines under each section (until next section header)
3. Parse multi-line structured data:
   - For addresses: Extract name, address lines, country separately
   - For shipping: Extract vessel, ports, container info
   - For party info (exporter/consignee): Extract name, address, country
4. Create both detailed fields AND consolidated fields:
   - Detailed: exporter_name, exporter_address, exporter_country
   - Consolidated: exporter_full (newline-separated)

OUTPUT FORMAT:
Return ONLY a JSON object with extracted fields. Use snake_case field names.
Example for EXPORTER section:
{{
  "exporter_name": "COMPANY NAME",
  "exporter_address": "Street Address",
  "exporter_country": "Country",
  "exporter_full": "COMPANY NAME\\nStreet Address\\nCountry"
}}

For CONSIGNEE: use consignee_name, consignee_address, consignee_country, consignee_full
For SHIPPING: use vessel, vessel_name, port_of_loading, port_of_discharge, container_no, container_type
For other fields: use descriptive snake_case names

Return ONLY the JSON object, no markdown formatting or explanation."""

        return prompt

    def _parse_llm_json_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse JSON from LLM response, handling markdown code blocks.

        Args:
            response_text: Raw LLM response

        Returns:
            Parsed JSON dictionary
        """
        import json

        # Remove markdown code blocks if present
        cleaned = response_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]  # Remove ```json
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]  # Remove ```
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]  # Remove trailing ```

        cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            logger.debug(f"Raw response: {response_text}")
            return {}


# Singleton instance
_enhancer_instance: Optional[AISemanticEnhancer] = None


def get_ai_enhancer() -> AISemanticEnhancer:
    """
    Get or create AI Semantic Enhancer singleton.

    Returns:
        AISemanticEnhancer instance
    """
    global _enhancer_instance

    if _enhancer_instance is None:
        try:
            _enhancer_instance = AISemanticEnhancer()
            logger.info("AI Semantic Enhancer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AI Semantic Enhancer: {e}")
            raise

    return _enhancer_instance
