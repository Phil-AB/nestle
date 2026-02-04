"""
Enhanced LangChain Tools for Population Agent with Pure LLM Intelligence.

Implements intelligent field mapping using:
- Pure LLM reasoning (no embeddings needed)
- Batch mapping in single API call
- Field type validation
- Comprehensive semantic understanding
"""

from typing import Dict, Any, List, Optional, ClassVar
import json
import re
import logging

from langchain.tools import BaseTool
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from shared.providers import get_llm
from shared.utils.logger import setup_logger
from modules.population.agents.field_extractor import RecursiveFieldExtractor

logger = setup_logger(__name__)


# ==============================================================================
# LLM-ONLY FIELD MAPPING TOOL - Pure Intelligence, No Embeddings
# ==============================================================================

class SemanticFieldMappingInput(BaseModel):
    """Input schema for SemanticFieldMappingTool."""
    detected_fields: str = Field(description="JSON string of detected PDF fields")
    database_fields: str = Field(description="JSON string of database fields from all documents")
    fuzzy_threshold: float = Field(default=0.60, description="Confidence threshold for mappings (0.0-1.0)")


class SemanticFieldMappingTool(BaseTool):
    """
    Pure LLM-based intelligent field mapping - no embeddings needed.

    The LLM analyzes all PDF fields and database fields in a single batch request,
    providing intelligent mappings with reasoning and confidence scores.

    Features:
    - Single API call for all mappings (fast and efficient)
    - Deep semantic understanding (better than embeddings)
    - Handles synonyms, abbreviations, transformations
    - Field type awareness (numeric, text, date, code)
    - No threshold tuning required (LLM decides)
    - Comprehensive reasoning for each mapping

    Example:
        >>> tool = SemanticFieldMappingTool(llm=llm)
        >>> result = await tool._arun(
        ...     detected_fields='[{"pdf_field_name": "exporter_address", ...}]',
        ...     database_fields='{"invoice": {"shipper": "Acme Corp"}, ...}'
        ... )
    """

    name: str = "semantic_field_mapping"
    description: str = """Map database fields to PDF form fields using LLM intelligence.
    Input: JSON with 'detected_fields' (JSON string), 'database_fields' (JSON string),
           and optional 'fuzzy_threshold' (float for confidence filtering).
    Output: JSON object mapping pdf_field_name to database field values with confidence scores."""

    llm: Optional[BaseChatModel] = None
    args_schema: type[BaseModel] = SemanticFieldMappingInput

    # Field type patterns for validation (ClassVar to avoid Pydantic validation)
    FIELD_TYPES: ClassVar[Dict[str, List[str]]] = {
        "numeric": ["value", "amount", "total", "price", "weight", "quantity", "rate", "fob", "customs", "duty", "tax"],
        "text": ["name", "address", "description", "place", "remarks", "shipper", "consignee", "exporter", "importer"],
        "date": ["date", "time", "day", "month", "year"],
        "code": ["code", "no", "number", "id", "regime", "hs", "office", "bl", "awb"]
    }

    def __init__(self, llm: Optional[BaseChatModel] = None, **kwargs):
        """Initialize with LLM for intelligent mapping."""
        super().__init__(**kwargs)

        # Initialize LLM if not provided
        if llm is None:
            # Use centralized LLM config for population_tools module
            from shared.utils.llm_config import get_llm_for_module
            self.llm = get_llm_for_module(module_name="population_tools")
        else:
            self.llm = llm

        logger.info("✅ LLM-only field mapping enabled with centralized config")

    async def _arun(
        self,
        detected_fields: str,
        database_fields: str,
        fuzzy_threshold: float = 0.60
    ) -> str:
        """Async implementation of LLM-based field mapping."""

        # Parse inputs
        pdf_fields = json.loads(detected_fields)
        db_data = json.loads(database_fields)

        # Extract fields from all documents using RecursiveFieldExtractor
        all_db_fields = self._extract_all_db_fields(db_data)

        logger.info(
            f"🧠 LLM-only mapping: {len(pdf_fields)} PDF fields → "
            f"{len(all_db_fields)} DB fields (confidence threshold: {fuzzy_threshold})"
        )

        # Categorize PDF fields by type for better LLM understanding
        pdf_fields_categorized = self._categorize_pdf_fields(pdf_fields)

        # Build comprehensive mapping prompt
        prompt = self._build_batch_mapping_prompt(
            pdf_fields_categorized,
            all_db_fields,
            fuzzy_threshold
        )

        logger.info("🚀 Processing PDF fields in batches to avoid LLM timeouts...")

        # Process in batches of 10 fields to avoid timeouts (reduced from 15 for reliability)
        BATCH_SIZE = 10
        MAX_RETRIES = 2  # Retry timed-out batches up to 2 times
        BASE_TIMEOUT = 75  # Base timeout per batch (increased from 60)
        all_mappings = {}

        # Flatten categorized fields into single list
        all_pdf_fields = []
        for field_type, fields in pdf_fields_categorized.items():
            all_pdf_fields.extend(fields)

        total_fields = len(all_pdf_fields)
        num_batches = (total_fields + BATCH_SIZE - 1) // BATCH_SIZE

        logger.info(f"Processing {total_fields} PDF fields in {num_batches} batches of {BATCH_SIZE} (max {MAX_RETRIES} retries per batch)")

        for batch_idx in range(num_batches):
            start_idx = batch_idx * BATCH_SIZE
            end_idx = min((batch_idx + 1) * BATCH_SIZE, total_fields)
            batch_fields = all_pdf_fields[start_idx:end_idx]

            logger.info(f"📦 Batch {batch_idx + 1}/{num_batches}: Processing fields {start_idx + 1}-{end_idx}")

            # Retry loop for each batch
            for retry_num in range(MAX_RETRIES + 1):
                try:
                    # Create batch-specific categorized dict
                    batch_categorized = {"batch": batch_fields}

                    # Build prompt for this batch
                    batch_prompt = self._build_batch_mapping_prompt(
                        batch_categorized,
                        all_db_fields,
                        fuzzy_threshold
                    )

                    # LLM call with progressive timeout (longer on retries)
                    import asyncio
                    timeout = BASE_TIMEOUT + (retry_num * 30)  # 75s, 105s, 135s

                    response = await asyncio.wait_for(
                        self.llm.ainvoke(batch_prompt),
                        timeout=timeout
                    )

                    batch_mappings = self._parse_batch_mapping_response(
                        response.content,
                        all_db_fields,
                        batch_categorized
                    )

                    # Merge into all_mappings
                    all_mappings.update(batch_mappings)

                    if retry_num > 0:
                        logger.info(f"  ✅ Batch {batch_idx + 1} complete on retry {retry_num}: {len(batch_mappings)} mappings")
                    else:
                        logger.info(f"  ✅ Batch {batch_idx + 1} complete: {len(batch_mappings)} mappings")

                    # Success - break out of retry loop
                    break

                except asyncio.TimeoutError:
                    if retry_num < MAX_RETRIES:
                        logger.warning(
                            f"  ⏱️ Batch {batch_idx + 1} timed out after {timeout}s - "
                            f"retry {retry_num + 1}/{MAX_RETRIES}..."
                        )
                        # Continue to next retry
                    else:
                        logger.error(f"  ❌ Batch {batch_idx + 1} timed out after {MAX_RETRIES} retries - skipping")

                except Exception as e:
                    logger.error(f"  ❌ Batch {batch_idx + 1} failed: {e}")
                    # Don't retry on other errors
                    break

        # Filter by confidence threshold
        filtered_mappings = {
            pdf_field: mapping
            for pdf_field, mapping in all_mappings.items()
            if mapping.get("confidence", 0.0) >= fuzzy_threshold
        }

        logger.info(
            f"✅ Total: Mapped {len(filtered_mappings)}/{total_fields} fields "
            f"(threshold: {fuzzy_threshold}, total candidates: {len(all_mappings)})"
        )

        # Log rejected low-confidence mappings
        rejected = len(all_mappings) - len(filtered_mappings)
        if rejected > 0:
            logger.warning(f"⚠️ Rejected {rejected} low-confidence mappings (below {fuzzy_threshold})")

        return json.dumps(filtered_mappings, indent=2)

    def _extract_all_db_fields(self, db_data: Dict) -> List[Dict[str, Any]]:
        """
        Extract all fields recursively and dynamically from database data.

        Uses RecursiveFieldExtractor for comprehensive extraction.
        """
        logger.debug("🔍 Using RecursiveFieldExtractor for comprehensive field extraction")

        # Use recursive extractor
        extractor = RecursiveFieldExtractor(max_depth=10)
        all_fields = extractor.extract_all_fields(db_data, include_metadata=False)

        # Print summary for debugging
        if logger.level <= logging.DEBUG:
            extractor.print_extraction_summary(all_fields)

        # Convert to format expected by LLM
        formatted_fields = []
        for field in all_fields:
            formatted_fields.append({
                "field_name": field["field_name"],
                "value": field["value"],
                "source_path": field["path"],
                "document_type": field["source_document"]
            })

        logger.info(f"📊 Recursive extraction: {len(formatted_fields)} fields extracted")

        return formatted_fields

    def _normalize_pdf_field_name(self, field_name: str) -> tuple:
        """
        Normalize and clean PDF field names before LLM matching.

        Handles:
        - Leading numbers: "2Exporter" → "Exporter"
        - Truncated words: "Loadin" → "Loading", "Consig" → "Consignee"
        - Special characters: "Port/Unloading" → "Port Unloading"
        - Abbreviations: "Fcy" → "Foreign Currency", "Ncy" → "National Currency"

        Args:
            field_name: Original PDF field name

        Returns:
            Tuple of (normalized_name, original_name)
        """
        import re

        original = field_name
        normalized = field_name

        # Remove leading numbers
        normalized = re.sub(r'^\d+', '', normalized).strip()

        # Replace special characters with spaces
        normalized = re.sub(r'[&/\-_]', ' ', normalized)

        # Common truncation repairs (customs/shipping domain)
        truncation_fixes = {
            r'\bLoadin\b': 'Loading',
            r'\bUnloadin\b': 'Unloading',
            r'\bConsig\b': 'Consignee',
            r'\bDestinat\b': 'Destination',
            r'\bLicenc\b': 'Licence',
            r'\bDeclar\b': 'Declaration',
            r'\bManuf\b': 'Manufacturer',
            r'\bXchange\b': 'Exchange',
            r'\bCty\b': 'Country',
            r'\bOrg\b': 'Origin',
            r'\bDest\b': 'Destination',
            r'\bConcess\b': 'Concession',
            r'\bAmnt\b': 'Amount',
            r'\bQty\b': 'Quantity'
        }

        for pattern, replacement in truncation_fixes.items():
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

        # Expand common abbreviations (customs/shipping domain)
        abbreviations = {
            r'\bFcy\b': 'Foreign Currency',
            r'\bNcy\b': 'National Currency',
            r'\bCC\b': 'Cubic Capacity',
            r'\bCPC\b': 'Central Product Classification',
            r'\bCRMS\b': 'Customs Risk Management System',
            r'\bCt\b': 'Country',
            r'\bLn\b': 'Line',
            r'\bM Trans\b': 'Mode of Transport',
            r'\bID\b': 'Identification',
            r'\bNo\b': 'Number',
            r'\bKg\b': 'Kilograms',
            r'\bCL\b': 'Clearance',
            r'\bB L\b': 'Bill of Lading',
            r'\bFOB\b': 'Free On Board'
        }

        for pattern, replacement in abbreviations.items():
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

        # Clean up multiple spaces
        normalized = ' '.join(normalized.split())
        normalized = normalized.strip()

        # If normalization made it too short or empty, use original
        if len(normalized) < 2:
            normalized = original

        return normalized, original

    def _categorize_pdf_fields(self, pdf_fields: List[Dict]) -> Dict[str, List[Dict]]:
        """Categorize PDF fields by detected type for better LLM understanding."""
        categorized = {
            "numeric": [],
            "text": [],
            "date": [],
            "code": []
        }

        for field in pdf_fields:
            field_name = field["pdf_field_name"].lower()
            field_type = "text"  # Default

            # Detect type
            for ftype, patterns in self.FIELD_TYPES.items():
                if any(pattern in field_name for pattern in patterns):
                    field_type = ftype
                    break

            # Normalize field name for better LLM matching
            normalized_name, original_name = self._normalize_pdf_field_name(field["pdf_field_name"])

            categorized[field_type].append({
                "pdf_field_name": original_name,  # Keep original for final mapping
                "normalized_name": normalized_name,  # Use for LLM matching
                "label": field.get("label", field["pdf_field_name"]),
                "type": field_type
            })

        return categorized

    def _build_batch_mapping_prompt(
        self,
        pdf_fields_categorized: Dict[str, List[Dict]],
        all_db_fields: List[Dict],
        confidence_threshold: float
    ) -> str:
        """Build comprehensive prompt for batch field mapping."""

        # Format PDF fields by category (showing NORMALIZED names to LLM)
        pdf_sections = []
        total_pdf_fields = 0
        for field_type, fields in pdf_fields_categorized.items():
            if not fields:
                continue

            total_pdf_fields += len(fields)
            fields_text = "\n".join([
                f"  - {f['normalized_name']} [original: \"{f['pdf_field_name']}\"]"
                for f in fields
            ])
            pdf_sections.append(f"**{field_type.upper()} FIELDS:**\n{fields_text}")

        pdf_fields_text = "\n\n".join(pdf_sections)

        # Format database fields by document type
        db_by_doc_type = {}
        for field in all_db_fields:
            doc_type = field.get("document_type", "unknown")
            if doc_type not in db_by_doc_type:
                db_by_doc_type[doc_type] = []
            db_by_doc_type[doc_type].append(field)

        db_sections = []
        for doc_type, fields in sorted(db_by_doc_type.items()):
            fields_text = "\n".join([
                f"  - {f['field_name']}: \"{str(f['value'])[:60]}{'...' if len(str(f['value'])) > 60 else ''}\""
                for f in fields[:30]  # Limit to 30 fields per doc type to avoid prompt bloat
            ])
            if len(fields) > 30:
                fields_text += f"\n  ... and {len(fields) - 30} more"
            db_sections.append(f"**{doc_type.upper()}** ({len(fields)} fields):\n{fields_text}")

        db_fields_text = "\n\n".join(db_sections)

        prompt = f"""You are an expert customs declaration AI analyzing PDF form fields and database data.

**TASK:** Map each PDF form field to the best matching database field.

**PDF FORM FIELDS** ({total_pdf_fields} total):
{pdf_fields_text}

**DATABASE FIELDS** ({len(all_db_fields)} total):
{db_fields_text}

**MAPPING RULES:**

1. **Pre-processed Field Names:**
   - PDF field names have been AUTOMATICALLY CLEANED and NORMALIZED
   - Leading numbers removed, truncations repaired, abbreviations expanded
   - You're seeing the CLEAN version - original names shown in brackets
   - Focus on SEMANTIC MATCHING between cleaned PDF names and database fields
   - Original field names will be used in final output automatically

2. **Semantic Understanding:**
   - "exporter_address" can map to "exporter" (company name is part of address)
   - "fob_fcy" maps to "fob_value" (FCY = Foreign Currency)
   - "net_wt_kg" maps to "net_weight" (wt = weight)
   - "bl_no" maps to "bill_of_lading_no" or "bl_number"
   - Understand abbreviations, synonyms, and semantic relationships

3. **Field Type Compatibility:**
   - NUMERIC fields (amount, value, weight) → numeric database values
   - TEXT fields (name, address) → text database values
   - DATE fields → date-formatted values
   - CODE fields (id, number) → alphanumeric codes

4. **Prefer Specific Over Generic:**
   - "exporter" > "name" for exporter-related fields
   - "consignee" > "address" for consignee-related fields
   - "shipper" > generic fields

5. **Document Type Relevance:**
   - Invoice fields for financial data (fob, amount, exchange_rate)
   - Bill of Lading for shipping data (vessel, port, shipper, consignee)
   - COO for origin data (exporter, manufacturer, country)
   - Packing List for cargo details (marks, packages, weight)

6. **Confidence Scoring:**
   - 0.90-1.0: Perfect match (exact or strong synonym)
   - 0.70-0.89: Good match (semantic similarity, abbreviation)
   - 0.50-0.69: Acceptable match (possible but uncertain)
   - 0.00-0.49: Poor match (skip - below threshold {confidence_threshold})

**OUTPUT FORMAT (JSON):**

Return a JSON object where each key is a PDF field name and value is the mapping:

```json
{{
  "pdf_field_name_1": {{
    "value": "actual database value to fill in PDF",
    "source": "database_field_name",
    "confidence": 0.95,
    "document_type": "bill_of_lading",
    "reasoning": "Brief explanation of why this mapping is correct"
  }},
  "pdf_field_name_2": {{
    "value": "...",
    "source": "...",
    "confidence": 0.85,
    "document_type": "...",
    "reasoning": "..."
  }}
}}
```

**IMPORTANT:**
- Only include mappings with confidence >= {confidence_threshold}
- For each PDF field, find the BEST database field (not all possible matches)
- If no good match exists, omit the PDF field from output
- Provide clear reasoning for each mapping
- Ensure values are clean (no "Company Name:" labels, just actual values)

Now analyze and create the complete field mapping:"""

        return prompt

    def _parse_batch_mapping_response(
        self,
        response_text: str,
        all_db_fields: List[Dict],
        pdf_fields_categorized: Dict[str, List[Dict]]
    ) -> Dict[str, Dict[str, Any]]:
        """Parse LLM's batch mapping response."""

        try:
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_text = json_match.group(1)
            else:
                # Try to find raw JSON
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if not json_match:
                    raise ValueError("No JSON found in LLM response")
                json_text = json_match.group(0)

            mappings = json.loads(json_text)

            # Map normalized names back to original PDF field names
            # Build reverse lookup: normalized → original
            normalized_to_original = {}
            for field_type, fields in pdf_fields_categorized.items():
                for field in fields:
                    normalized_to_original[field['normalized_name']] = field['pdf_field_name']

            # Validate and remap to original field names
            validated_mappings = {}
            for normalized_field, mapping in mappings.items():
                confidence = mapping.get("confidence", 0.0)
                source = mapping.get("source", "unknown")
                value = mapping.get("value", "")

                # Get original PDF field name
                original_field = normalized_to_original.get(normalized_field, normalized_field)

                logger.info(
                    f"✅ '{original_field}' (normalized: '{normalized_field}') → '{source}' "
                    f"(confidence: {confidence:.2f}) | "
                    f"Value: {str(value)[:50]}{'...' if len(str(value)) > 50 else ''}"
                )

                # Use ORIGINAL field name as key for form filling
                validated_mappings[original_field] = mapping

            return validated_mappings

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LLM response: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            return {}
        except Exception as e:
            logger.error(f"Failed to parse LLM batch mapping response: {e}")
            return {}

    def _run(self, *args, **kwargs) -> str:
        """Sync implementation (not used)."""
        raise NotImplementedError("Use async version (_arun)")
