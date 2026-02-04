"""
LangChain Tools for Population Agent.

Implements tools that the population agent uses for intelligent form filling:
- GeminiVisionTool: Detect field positions on PDF templates
- DatabaseQueryTool: Fetch document data from PostgreSQL
- FieldMappingTool: Intelligent field name matching
- ValidationTool: Validate mapped data

Each tool is a LangChain tool that the agent can invoke.
"""

from typing import Dict, Any, List, Optional
import json
import re
from pathlib import Path

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from shared.providers import GeminiProvider
from shared.providers.base_provider import ProviderConfig
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


# ==============================================================================
# PDF FIELD INSPECTION TOOL - Extract Actual Form Field Names
# ==============================================================================

class PDFFieldInspectionToolInput(BaseModel):
    """Input schema for PDFFieldInspectionTool."""
    pdf_path: str = Field(description="Path to fillable PDF template file")


class PDFFieldInspectionTool(BaseTool):
    """
    Extract actual field names from fillable PDF forms.

    This tool reads the AcroForm structure of a fillable PDF and returns
    all available field names and their types. More reliable than vision
    detection for fillable forms.

    Example:
        >>> tool = PDFFieldInspectionTool()
        >>> result = await tool.arun(pdf_path="form.pdf")
        >>> print(result)  # JSON with actual PDF field names
    """

    name: str = "pdf_field_inspection"
    description: str = """Extract actual field names from a fillable PDF form.
    Input: JSON with 'pdf_path' (string).
    Output: JSON array of fields with their actual PDF field names and types."""

    args_schema: type[BaseModel] = PDFFieldInspectionToolInput

    async def _arun(self, pdf_path: str) -> str:
        """Async implementation of PDF field inspection."""
        logger.info(f"Inspecting fillable PDF form: {pdf_path}")

        from pypdf import PdfReader

        try:
            reader = PdfReader(pdf_path)

            # Check if PDF has AcroForm
            if "/AcroForm" not in reader.trailer["/Root"]:
                return json.dumps({
                    "error": "PDF is not a fillable form (no AcroForm)",
                    "fields": []
                })

            # Extract field information
            form = reader.trailer["/Root"]["/AcroForm"]
            if "/Fields" not in form:
                return json.dumps({
                    "error": "No fields in AcroForm",
                    "fields": []
                })

            fields = []
            for field_ref in form["/Fields"]:
                try:
                    field_obj = field_ref.get_object()
                    field_name = str(field_obj.get("/T", ""))
                    field_type = str(field_obj.get("/FT", ""))

                    if field_name:
                        fields.append({
                            "pdf_field_name": field_name,
                            "field_type": field_type,
                            "label": field_name.replace("_", " ").title()
                        })
                except Exception as e:
                    logger.warning(f"Error reading field: {e}")
                    continue

            logger.info(f"Extracted {len(fields)} fields from PDF")
            return json.dumps(fields, indent=2)

        except Exception as e:
            logger.error(f"PDF inspection failed: {e}")
            return json.dumps({
                "error": str(e),
                "fields": []
            })

    def _run(self, pdf_path: str) -> str:
        """Sync implementation (not used for async agents)."""
        raise NotImplementedError("Use async version (_arun)")


# ==============================================================================
# GEMINI VISION TOOL - Field Position Detection (Legacy - for non-fillable PDFs)
# ==============================================================================

class GeminiVisionToolInput(BaseModel):
    """Input schema for GeminiVisionTool."""
    pdf_path: str = Field(description="Path to PDF template file")
    page_num: int = Field(default=0, description="Page number to analyze (0-indexed)")


class GeminiVisionTool(BaseTool):
    """
    Detect form field positions using Gemini vision.

    This tool analyzes a PDF template and returns the positions and types
    of all detected form fields.

    Example:
        >>> tool = GeminiVisionTool(gemini_api_key="...")
        >>> result = await tool.arun(pdf_path="form.pdf", page_num=0)
        >>> print(result)  # JSON with detected fields
    """

    name: str = "gemini_vision"
    description: str = """Detect form fields and their positions in a PDF template.
    Input: JSON with 'pdf_path' (string) and optional 'page_num' (int).
    Output: JSON array of detected fields with positions, types, and labels."""

    gemini_provider: Optional[GeminiProvider] = None
    args_schema: type[BaseModel] = GeminiVisionToolInput

    def __init__(self, gemini_api_key: Optional[str] = None, **kwargs):
        """Initialize Gemini vision tool."""
        super().__init__(**kwargs)

        # Initialize Gemini provider
        import os
        config = ProviderConfig(
            provider_name="gemini",
            api_key=gemini_api_key or os.getenv("GEMINI_API_KEY"),
            model="gemini-1.5-flash",
            temperature=0.1,
            max_retries=3
        )
        self.gemini_provider = GeminiProvider(config)

    async def _arun(self, pdf_path: str, page_num: int = 0) -> str:
        """Async implementation of vision analysis."""
        logger.info(f"Analyzing PDF template: {pdf_path}, page {page_num}")

        # Get page info
        page_info = self.gemini_provider.get_page_info(pdf_path, page_num)

        # Build detection prompt
        prompt = self._build_prompt(page_info)

        # Analyze PDF
        result = await self.gemini_provider.analyze_pdf(
            pdf_path=pdf_path,
            prompt=prompt,
            page_num=page_num,
            dpi=300
        )

        # Extract JSON from response
        json_data = self._extract_json(result.text)

        logger.info(f"Detected {len(json_data)} fields")

        return json.dumps(json_data, indent=2)

    def _run(self, pdf_path: str, page_num: int = 0) -> str:
        """Sync implementation (not used for async agents)."""
        raise NotImplementedError("Use async version (_arun)")

    def _build_prompt(self, page_info: Dict[str, Any]) -> str:
        """Build prompt for field detection."""
        return f"""Analyze this PDF form and detect ALL fillable fields.

For each field, provide:
1. **pdf_field_name**: Unique identifier for the field (lowercase, underscores)
2. **label**: The visible label text next to the field
3. **field_type**: "text", "number", "date", or "checkbox"
4. **position**: Coordinates as percentages (x, y, width, height) from 0-100
5. **confidence**: Your confidence (0.0 to 1.0)

Page dimensions: {page_info['width']} x {page_info['height']} points

Return ONLY a JSON array:
```json
[
  {{
    "pdf_field_name": "company_name",
    "label": "Company Name",
    "field_type": "text",
    "position": {{"x": 10.0, "y": 15.0, "width": 45.0, "height": 3.5}},
    "confidence": 0.95
  }}
]
```"""

    def _extract_json(self, text: str) -> List[Dict[str, Any]]:
        """Extract JSON array from Gemini response."""
        # Extract JSON from markdown code blocks
        json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if json_match:
            json_text = json_match.group(1)
        else:
            # Try to find JSON array directly
            json_match = re.search(r'\[\s*\{.*?\}\s*\]', text, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
            else:
                raise ValueError(f"No JSON found in response: {text[:200]}")

        return json.loads(json_text)


# ==============================================================================
# DATABASE QUERY TOOL - Fetch Document Data
# ==============================================================================

class DatabaseQueryToolInput(BaseModel):
    """Input schema for DatabaseQueryTool."""
    document_ids: List[str] = Field(description="List of document IDs to fetch")
    merge_strategy: str = Field(
        default="prioritized",
        description="Merge strategy: prioritized, best_available, or combine"
    )


class DatabaseQueryTool(BaseTool):
    """
    Fetch extracted document data from PostgreSQL.

    Queries the database for document data and merges multi-document data
    according to the specified strategy.

    Example:
        >>> tool = DatabaseQueryTool(db_config={...})
        >>> result = await tool.arun(
        ...     document_ids=["id1", "id2"],
        ...     merge_strategy="best_available"
        ... )
    """

    name: str = "database_query"
    description: str = """Fetch extracted data from documents in the database.
    Input: JSON with 'document_ids' (list of strings) and 'merge_strategy' (string).
    Output: JSON with merged document data (fields and items)."""

    data_provider: Optional[Any] = None
    args_schema: type[BaseModel] = DatabaseQueryToolInput

    def __init__(self, data_provider, **kwargs):
        """Initialize database query tool."""
        super().__init__(**kwargs)
        self.data_provider = data_provider

    async def _arun(
        self,
        document_ids: List[str],
        merge_strategy: str = "prioritized"
    ) -> str:
        """Async implementation of database query."""
        logger.info(
            f"Fetching data for {len(document_ids)} documents "
            f"with strategy: {merge_strategy}"
        )

        # Fetch and merge document data
        data = await self.data_provider.get_documents_data(
            document_ids=document_ids,
            merge_strategy=merge_strategy
        )

        logger.info(
            f"Retrieved {len(data.get('fields', {}))} fields, "
            f"{len(data.get('items', []))} items"
        )

        return json.dumps(data, indent=2)

    def _run(self, document_ids: List[str], merge_strategy: str = "prioritized") -> str:
        """Sync implementation (not used)."""
        raise NotImplementedError("Use async version (_arun)")


# ==============================================================================
# FIELD MAPPING TOOL - Intelligent Field Matching
# ==============================================================================

class FieldMappingToolInput(BaseModel):
    """Input schema for FieldMappingTool."""
    detected_fields: str = Field(description="JSON string of detected PDF fields")
    database_fields: str = Field(description="JSON string of database fields")
    fuzzy_threshold: float = Field(
        default=0.8,
        description="Fuzzy matching threshold (0.0-1.0)"
    )


class FieldMappingTool(BaseTool):
    """
    Intelligent field mapping between database and PDF fields.

    Uses fuzzy string matching and semantic similarity to map database
    field names to PDF form field names.

    Example:
        >>> tool = FieldMappingTool()
        >>> result = await tool.arun(
        ...     detected_fields='[{"pdf_field_name": "company_name", ...}]',
        ...     database_fields='{"exporter_shipper": "Acme Corp", ...}'
        ... )
    """

    name: str = "field_mapping"
    description: str = """Map database fields to PDF form fields intelligently.
    Input: JSON with 'detected_fields' (JSON string), 'database_fields' (JSON string),
           and optional 'fuzzy_threshold' (float).
    Output: JSON object mapping pdf_field_name to database field values."""

    args_schema: type[BaseModel] = FieldMappingToolInput

    async def _arun(
        self,
        detected_fields: str,
        database_fields: str,
        fuzzy_threshold: float = 0.8
    ) -> str:
        """Async implementation of field mapping."""
        from fuzzywuzzy import fuzz

        # Parse inputs
        pdf_fields = json.loads(detected_fields)
        db_data = json.loads(database_fields)
        db_fields = db_data.get("fields", {})

        logger.info(
            f"Mapping {len(pdf_fields)} PDF fields to "
            f"{len(db_fields)} database fields"
        )

        mappings = {}

        for pdf_field in pdf_fields:
            pdf_name = pdf_field["pdf_field_name"]
            pdf_label = pdf_field["label"]

            # Find best matching database field
            best_match = None
            best_score = 0.0

            for db_field_name, db_value in db_fields.items():
                # Extract actual value if db_value is a complex object
                actual_value = db_value
                if isinstance(db_value, dict) and 'value' in db_value:
                    actual_value = db_value['value']

                # Skip if no value
                if not actual_value or actual_value == 'null':
                    continue

                # Calculate fuzzy match score
                score = max(
                    fuzz.ratio(pdf_name, db_field_name) / 100.0,
                    fuzz.ratio(pdf_label.lower(), db_field_name) / 100.0,
                    fuzz.partial_ratio(pdf_label.lower(), db_field_name) / 100.0
                )

                if score > best_score:
                    best_score = score
                    best_match = (db_field_name, actual_value)

            # Use match if above threshold
            if best_match and best_score >= fuzzy_threshold:
                mappings[pdf_name] = {
                    "value": best_match[1],
                    "source": best_match[0],
                    "confidence": best_score
                }
                logger.debug(
                    f"Mapped '{pdf_name}' -> '{best_match[0]}' "
                    f"(confidence: {best_score:.2f})"
                )

        logger.info(f"Mapped {len(mappings)}/{len(pdf_fields)} fields")

        return json.dumps(mappings, indent=2)

    def _run(
        self,
        detected_fields: str,
        database_fields: str,
        fuzzy_threshold: float = 0.8
    ) -> str:
        """Sync implementation (not used)."""
        raise NotImplementedError("Use async version (_arun)")


# ==============================================================================
# VALIDATION TOOL - Data Validation
# ==============================================================================

class ValidationToolInput(BaseModel):
    """Input schema for ValidationTool."""
    field_mappings: str = Field(description="JSON string of field mappings to validate")
    strict_mode: bool = Field(
        default=True,
        description="Whether to use strict validation"
    )


class ValidationTool(BaseTool):
    """
    Validate mapped field data.

    Checks field types, formats, and constraints before rendering.

    Example:
        >>> tool = ValidationTool()
        >>> result = await tool.arun(field_mappings='{...}', strict_mode=True)
    """

    name: str = "validation"
    description: str = """Validate field mappings before rendering.
    Input: JSON with 'field_mappings' (JSON string) and 'strict_mode' (bool).
    Output: JSON with validation results (valid, errors, warnings)."""

    args_schema: type[BaseModel] = ValidationToolInput

    async def _arun(
        self,
        field_mappings: str,
        strict_mode: bool = True
    ) -> str:
        """Async implementation of validation."""
        mappings = json.loads(field_mappings)

        logger.info(f"Validating {len(mappings)} field mappings")

        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "validated_count": 0
        }

        for field_name, field_data in mappings.items():
            value = field_data.get("value")
            confidence = field_data.get("confidence", 1.0)

            # Check confidence threshold
            if strict_mode and confidence < 0.9:
                validation_result["warnings"].append({
                    "field": field_name,
                    "message": f"Low confidence mapping: {confidence:.2f}",
                    "value": value
                })

            # Check for empty values
            if not value or value == "":
                validation_result["warnings"].append({
                    "field": field_name,
                    "message": "Empty value",
                    "value": value
                })

            validation_result["validated_count"] += 1

        # Set valid to False if there are errors
        if validation_result["errors"]:
            validation_result["valid"] = False

        logger.info(
            f"Validation complete: {validation_result['validated_count']} fields, "
            f"{len(validation_result['errors'])} errors, "
            f"{len(validation_result['warnings'])} warnings"
        )

        return json.dumps(validation_result, indent=2)

    def _run(self, field_mappings: str, strict_mode: bool = True) -> str:
        """Sync implementation (not used)."""
        raise NotImplementedError("Use async version (_arun)")
