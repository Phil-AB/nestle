"""
PDF Form Population API Endpoints.

REST API for the standalone PDF form population module.
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from pathlib import Path
import logging

from modules.population.core.engine import PopulationEngine
from modules.population.core.types import PopulationResult

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(
    prefix="/population",
    tags=["population"],
    responses={
        404: {"description": "Form or document not found"},
        500: {"description": "Internal server error"}
    }
)

# Initialize population engine (singleton)
_population_engine: Optional[PopulationEngine] = None


def get_population_engine() -> PopulationEngine:
    """
    Get or create population engine instance.

    Returns:
        PopulationEngine instance
    """
    global _population_engine

    if _population_engine is None:
        _population_engine = PopulationEngine()
        logger.info("Population engine initialized")

    return _population_engine


# ==============================================================================
# REQUEST/RESPONSE MODELS
# ==============================================================================

class PopulationRequest(BaseModel):
    """
    Request model for PDF form population.

    Example:
        {
            "form_id": "boe_gra_v1",
            "document_ids": ["abc-123", "def-456", "ghi-789"],
            "merge_strategy": "prioritized",
            "flatten_form": true
        }
    """

    form_id: str = Field(
        ...,
        description="Form template identifier (e.g., 'boe_gra_v1')",
        example="boe_gra_v1"
    )

    document_ids: List[str] = Field(
        ...,
        description="List of document UUIDs to extract data from",
        min_length=1,
        example=["550e8400-e29b-41d4-a716-446655440000"]
    )

    merge_strategy: Optional[str] = Field(
        default="prioritized",
        description="Strategy for merging multi-document data",
        example="prioritized"
    )

    flatten_form: Optional[bool] = Field(
        default=True,
        description="Make filled PDF read-only (flatten form fields)",
        example=True
    )

    validate_required: Optional[bool] = Field(
        default=True,
        description="Validate that required fields are populated",
        example=True
    )


class PopulationResponse(BaseModel):
    """
    Response model for agent-based PDF form population.

    Example:
        {
            "success": true,
            "output_path": "/output/population/boe_gra_v1_20240615_143022.pdf",
            "form_id": "boe_gra_v1",
            "metadata": {
                "document_ids": ["abc-123", "def-456"],
                "mode": "agent",
                "confidence": 0.92,
                "field_count": 87,
                "agent_metadata": {
                    "workflow_messages": [...],
                    "validation": {...}
                }
            }
        }
    """

    success: bool = Field(..., description="Whether population succeeded")
    output_path: Optional[str] = Field(None, description="Path to populated PDF")
    form_id: str = Field(..., description="Form template ID used")
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Agent metadata including confidence scores, validation results, and workflow details"
    )
    error: Optional[str] = Field(None, description="Error message if failed")


class FormInfo(BaseModel):
    """Information about a form template."""

    form_id: str = Field(..., description="Form template identifier")
    form_name: str = Field(..., description="Human-readable form name")
    description: str = Field(default="", description="Form description")
    template_path: str = Field(..., description="Path to PDF template")
    field_count: int = Field(default=0, description="Number of form fields")
    required_document_types: List[str] = Field(default=[], description="Required document types")
    created_at: str = Field(default="", description="Creation timestamp")
    updated_at: str = Field(default="", description="Last update timestamp")


class HealthCheckResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Overall status (healthy/degraded/unhealthy)")
    components: Dict[str, str] = Field(..., description="Component health status")


# ==============================================================================
# API ENDPOINTS
# ==============================================================================

@router.post(
    "/populate",
    response_model=PopulationResponse,
    status_code=status.HTTP_200_OK,
    summary="Populate PDF form with intelligent agent-based mapping",
    description="""
    Populate a PDF form template with data extracted from documents using
    AI-powered intelligent field mapping (LangGraph agent).

    **Agent-Based Population (Mandatory):**
    This endpoint ALWAYS uses LangGraph-based intelligent population for maximum
    accuracy. The agent workflow:
    1. Inspects PDF form fields (extracts actual field names from AcroForm)
    2. Fetches extracted data from specified documents in the database
    3. Intelligently maps database fields to PDF fields using fuzzy matching
    4. Validates mappings with confidence scores
    5. Fills PDF form fields programmatically
    6. Returns populated PDF with detailed metadata

    **Benefits of Agent Mode:**
    - ✅ Intelligent field name matching (handles variations and synonyms)
    - ✅ Confidence scores for each field mapping
    - ✅ Adaptive to new/custom forms without manual mapping configuration
    - ✅ Better handling of multi-document data merging

    The populated PDF can be:
    - Editable (if flatten_form=false) - user can edit in browser
    - Read-only (if flatten_form=true) - locked for final submission
    """
)
async def populate_form(request: PopulationRequest):
    """
    Populate PDF form with extracted document data.

    Args:
        request: Population request parameters

    Returns:
        PopulationResponse with output path and metadata

    Raises:
        HTTPException: If form not found, documents not found, or population fails
    """
    try:
        logger.info(
            f"Population request: form={request.form_id}, "
            f"docs={len(request.document_ids)}, "
            f"strategy={request.merge_strategy}"
        )

        # Get population engine
        engine = get_population_engine()

        # Populate form
        result = await engine.populate(
            form_id=request.form_id,
            document_ids=request.document_ids,
            options={
                "flatten_form": request.flatten_form,
                "merge_strategy": request.merge_strategy,
                "validate_required": request.validate_required
            }
        )

        # Return response
        response = PopulationResponse(**result.dict())

        if result.success:
            logger.info(f"Population successful: {result.output_path}")
        else:
            logger.error(f"Population failed: {result.error}")

        return response

    except FileNotFoundError as e:
        logger.error(f"Form or document not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Form or document not found: {str(e)}"
        )

    except ValueError as e:
        logger.error(f"Invalid request: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except Exception as e:
        logger.error(f"Population error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Population failed: {str(e)}"
        )


@router.get(
    "/forms",
    response_model=List[FormInfo],
    summary="List available PDF form templates",
    description="Returns a list of all available PDF form templates that can be populated."
)
async def list_forms():
    """
    List available PDF form templates.

    Returns:
        List of form metadata dictionaries

    Raises:
        HTTPException: If forms directory not accessible
    """
    try:
        engine = get_population_engine()
        forms = engine.list_forms()

        logger.info(f"Listed {len(forms)} available forms")
        return forms

    except Exception as e:
        logger.error(f"Error listing forms: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list forms: {str(e)}"
        )


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Health check for population module",
    description="Check the health status of the population module and its dependencies."
)
async def health_check():
    """
    Check health of population module components.

    Returns:
        Health status dictionary

    Raises:
        HTTPException: If health check fails
    """
    try:
        engine = get_population_engine()
        health = await engine.health_check()

        logger.info(f"Health check: {health['status']}")
        return health

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Health check failed: {str(e)}"
        )


@router.get(
    "/forms/{form_id}",
    response_model=FormInfo,
    summary="Get form template information",
    description="Get detailed information about a specific form template."
)
async def get_form_info(form_id: str):
    """
    Get information about a specific form template.

    Args:
        form_id: Form template identifier

    Returns:
        Form metadata

    Raises:
        HTTPException: If form not found
    """
    try:
        engine = get_population_engine()
        forms = engine.list_forms()

        # Find form by ID
        for form in forms:
            if form["form_id"] == form_id:
                logger.info(f"Retrieved form info: {form_id}")
                return form

        # Form not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Form not found: {form_id}"
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error getting form info: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get form info: {str(e)}"
        )


@router.get(
    "/download/{filename}",
    summary="Download populated PDF",
    description="Download a populated PDF file by filename.",
    response_class=FileResponse
)
async def download_populated_pdf(filename: str):
    """
    Download a populated PDF file.

    Args:
        filename: Name of the PDF file to download

    Returns:
        FileResponse with PDF file

    Raises:
        HTTPException: If file not found or access denied
    """
    try:
        # Security: only allow alphanumeric, dash, underscore, and .pdf extension
        if not filename.endswith('.pdf') or not all(c.isalnum() or c in '.-_' for c in filename):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid filename"
            )

        # Construct file path (relative to project root)
        file_path = Path("output/population") / filename

        # Check if file exists
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {filename}"
            )

        # Return file
        logger.info(f"Serving PDF file: {filename}")
        return FileResponse(
            path=str(file_path),
            media_type="application/pdf",
            filename=filename
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error serving PDF: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to serve PDF: {str(e)}"
        )
