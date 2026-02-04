"""
Universal Insights API Endpoints.

100% config-driven, use-case based REST API for generating insights.
Works for ANY use case: loans, insurance, recruitment, healthcare, etc.

No hardcoding - all structure comes from use case configs.
"""

from fastapi import APIRouter, HTTPException, status, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from pathlib import Path
import logging
from datetime import datetime

from modules.generation.engine import GenerationEngine
from modules.generation.config import GenerationConfig
from modules.insights import InsightsService
from modules.insights.storage.integration import create_insights_storage
from src.database.connection import get_session, get_engine
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(
    prefix="/insights",
    tags=["insights"],
    responses={
        404: {"description": "Document not found"},
        500: {"description": "Internal server error"}
    }
)

# Initialize generation engine (singleton)
_generation_engine: Optional[GenerationEngine] = None


def get_generation_engine() -> GenerationEngine:
    """Get or create generation engine instance."""
    global _generation_engine

    if _generation_engine is None:
        project_root = Path(__file__).parent.parent.parent.parent.parent
        config = GenerationConfig(project_root=project_root)
        _generation_engine = GenerationEngine(config=config)
        logger.info("Generation engine initialized for insights")

    return _generation_engine


# ==============================================================================
# REQUEST/RESPONSE MODELS - 100% Dynamic
# ==============================================================================

class InsightsRequest(BaseModel):
    """Request model for generating insights."""
    document_id: str = Field(
        ...,
        description="Document UUID to generate insights for"
    )
    use_case_id: str = Field(
        default="forms-capital-loan",
        description="Use case identifier (determines which config to use)"
    )
    include_pdf: bool = Field(
        default=True,
        description="Whether to generate PDF report"
    )
    output_format: str = Field(
        default="pdf",
        description="Output format (pdf or json)"
    )


class InsightsResponse(BaseModel):
    """
    Universal response model for insights.

    All fields are dynamic and driven by use case config.
    No hardcoded structure - accepts any use case output.
    """
    success: bool
    document_id: str
    use_case_id: str
    # Dynamic data - structure determined by use case config
    customer_profile: Dict[str, Any]
    risk_assessment: Dict[str, Any]
    product_eligibility: Dict[str, Any]
    recommendations: Dict[str, Any]
    automated_decisions: Dict[str, Any]
    metadata: Dict[str, Any]
    pdf_path: Optional[str] = None
    error: Optional[str] = None

    class Config:
        extra = "allow"


class DocumentListItem(BaseModel):
    """Document list item for UI - minimal common fields."""
    document_id: str
    display_name: str
    document_type: Optional[str] = None
    created_at: str
    # Dynamic metadata from document
    summary: Dict[str, Any] = {}

    class Config:
        extra = "allow"


# ==============================================================================
# API ENDPOINTS
# ==============================================================================

@router.post(
    "/generate",
    response_model=InsightsResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate insights for a document",
    description="""
    Generate config-driven insights for any document type.

    This endpoint:
    1. Fetches document data from the database
    2. Loads use case configuration
    3. Generates rule-based insights with optional LLM enhancement
    4. Returns comprehensive insights with optional PDF report

    The response structure is determined by the use case config.
    """
)
async def generate_insights(request: InsightsRequest):
    """Generate insights for a document using use case config."""
    try:
        logger.info(f"Processing insights request for document: {request.document_id}, use_case: {request.use_case_id}")

        engine = get_engine()
        async with get_session() as session:
            # Get document data first (needed for PDF generation regardless of cache)
            result = await session.execute(
                text("SELECT fields, document_type, created_at FROM api_documents WHERE document_id = :document_id"),
                {"document_id": request.document_id}
            )
            row = result.fetchone()
            result.close()

            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document not found: {request.document_id}"
                )

            fields_data = row[0]
            document_type = row[1]

            # Check if insights already exist in database
            insights_storage = await create_insights_storage(
                engine, session, request.use_case_id
            )
            existing_insights = await insights_storage.get(request.document_id)

            if existing_insights:
                logger.info(f"Found existing insights for document: {request.document_id}")

                # Reconstruct insights from stored data
                insights = _reconstruct_insights_from_storage(existing_insights)

                logger.info(
                    f"Using stored insights: "
                    f"risk_score={existing_insights.get('risk_score')}, "
                    f"risk_level={existing_insights.get('risk_level')}"
                )
            else:
                # No existing insights - generate new ones
                logger.info(f"No existing insights found, generating new insights...")

                # Generate insights using the universal insights service
                service = InsightsService(use_case_id=request.use_case_id)
                insights = service.generate_insights(fields_data)

                logger.info(
                    f"Generated insights for document {request.document_id}: "
                    f"risk_score={insights['risk_assessment']['risk_score']}, "
                    f"use_case={request.use_case_id}"
                )

                # Save insights to database (both dedicated table and doc_metadata)
                try:
                    await insights_storage.save(request.document_id, insights)
                    await _save_insights_to_metadata(session, request.document_id, insights)
                    logger.info(f"Insights saved to database for document: {request.document_id}")
                except Exception as e:
                    logger.error(f"Failed to save insights to database: {e}", exc_info=True)
                    # Continue - don't fail the request if storage fails

        # Generate PDF if requested
        pdf_path = None
        if request.include_pdf and request.output_format == "pdf":
            pdf_path = await _generate_pdf(
                request.document_id,
                request.use_case_id,
                fields_data,
                insights
            )

        # Return universal response - structure from InsightsService
        return InsightsResponse(
            success=True,
            document_id=request.document_id,
            use_case_id=request.use_case_id,
            customer_profile=insights.get("customer_profile", {}),
            risk_assessment=insights.get("risk_assessment", {}),
            product_eligibility=insights.get("product_eligibility", {}),
            recommendations=insights.get("recommendations", {}),
            automated_decisions=insights.get("automated_decisions", {}),
            metadata=insights.get("metadata", {}),
            pdf_path=pdf_path
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error generating insights: {e}", exc_info=True)
        return InsightsResponse(
            success=False,
            document_id=request.document_id,
            use_case_id=request.use_case_id,
            customer_profile={},
            risk_assessment={},
            product_eligibility={},
            recommendations={},
            automated_decisions={},
            metadata={"error_time": datetime.utcnow().isoformat()},
            error=str(e)
        )


def _reconstruct_insights_from_storage(stored_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reconstruct insights dictionary from stored database record.

    First tries to use the full_insights JSONB column (preserves everything).
    Reorders customer_profile to match config-defined order.
    Falls back to reconstruction from individual fields for backward compatibility.

    Args:
        stored_data: Record from insights table

    Returns:
        Insights dictionary in the format expected by the API
    """
    # Define the correct field order from field_mapping.yaml
    CUSTOMER_PROFILE_ORDER = [
        "full_name",
        "age",
        "gender",
        "marital_status",
        "nationality",
        "occupation",
        "employment_status",
        "employer",
        "monthly_income",
        "email",
        "contact_number",
        "debt_to_income_ratio",
        "disposable_income"
    ]

    # First, try to use the full_insights JSONB column
    full_insights = stored_data.get("full_insights")
    if full_insights and isinstance(full_insights, dict):
        # Update metadata to indicate it came from cache
        if "metadata" not in full_insights:
            full_insights["metadata"] = {}
        full_insights["metadata"]["source"] = "database_cache"
        full_insights["metadata"]["generated_at"] = stored_data.get("created_at")

        # Reorder customer_profile to match config-defined order
        if "customer_profile" in full_insights and isinstance(full_insights["customer_profile"], dict):
            original_profile = full_insights["customer_profile"]
            ordered_profile = {}
            for key in CUSTOMER_PROFILE_ORDER:
                if key in original_profile:
                    ordered_profile[key] = original_profile[key]
            # Add any extra fields not in our predefined order
            for key, value in original_profile.items():
                if key not in ordered_profile:
                    ordered_profile[key] = value
            full_insights["customer_profile"] = ordered_profile

        return full_insights

    # Fallback: reconstruct from individual fields (backward compatibility)
    import json

    recommendations = stored_data.get("recommendations")
    if recommendations and isinstance(recommendations, str):
        try:
            recommendations = json.loads(recommendations)
        except (json.JSONDecodeError, TypeError):
            pass

    reasoning = stored_data.get("reasoning")
    if reasoning and isinstance(reasoning, str):
        try:
            reasoning = json.loads(reasoning)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "use_case_id": stored_data.get("use_case_id"),
        "customer_profile": {
            "full_name": stored_data.get("full_name"),
            "age": stored_data.get("age"),
            "monthly_income": stored_data.get("monthly_income"),
            "occupation": stored_data.get("occupation"),
            "employment_status": stored_data.get("employment_status"),
            "debt_to_income_ratio": stored_data.get("debt_to_income_ratio"),
            "disposable_income": stored_data.get("disposable_income"),
        },
        "risk_assessment": {
            "risk_score": stored_data.get("risk_score"),
            "risk_level": stored_data.get("risk_level"),
            "breakdown": stored_data.get("risk_factors"),
            "reasoning": reasoning,
        },
        "product_eligibility": stored_data.get("eligible_products", {}),
        "recommendations": recommendations or {},
        "automated_decisions": {
            "loan_approval": {
                "decision": stored_data.get("auto_approval_status") or "UNKNOWN",
                "message": f"Auto-approval status: {stored_data.get('auto_approval_status', 'Unknown')}",
                "confidence": 1.0
            },
            "loan_amount_recommendation": {
                "value": stored_data.get("max_loan_amount"),
                "rule_name": "stored_value",
                "confidence": 1.0
            }
        },
        "metadata": {
            "generated_at": stored_data.get("created_at"),
            "engine": stored_data.get("engine_type", "hybrid"),
            "processing_time_seconds": stored_data.get("processing_time_ms", 0) / 1000,
            "config_version": stored_data.get("config_version"),
            "source": "database_cache_fallback"
        }
    }


async def _save_insights_to_metadata(
    session,
    document_id: str,
    insights: Dict[str, Any]
):
    """
    Save insights summary to api_documents.doc_metadata for fast analytics queries.

    This allows the analytics service to query insights data efficiently without
    joining to the insights table.
    """
    try:
        # Extract key metrics from insights
        risk_assessment = insights.get("risk_assessment", {})
        profile = insights.get("customer_profile", {})
        decisions = insights.get("automated_decisions", {})

        # Build metadata summary
        metadata_update = {
            "risk_score": risk_assessment.get("risk_score"),
            "risk_level": risk_assessment.get("risk_level"),
            "auto_approval_status": decisions.get("auto_approval_status"),
            "max_loan_amount": decisions.get("max_loan_amount"),
            "customer_name": profile.get("full_name"),
            "monthly_income": profile.get("monthly_income"),
            "age": profile.get("age"),
            "employment_status": profile.get("employment_status"),
            "insights_generated_at": insights.get("metadata", {}).get("generated_at"),
            "insights_engine": insights.get("metadata", {}).get("engine"),
        }

        # Remove None values
        metadata_update = {k: v for k, v in metadata_update.items() if v is not None}

        # Update doc_metadata using jsonb_set for each field
        # Build the UPDATE query dynamically
        set_clauses = []
        params = {"document_id": document_id}

        for key, value in metadata_update.items():
            param_key = f"val_{key}"
            # Use jsonb_set to add/update each field
            set_clauses.append(f"doc_metadata = jsonb_set(COALESCE(doc_metadata, '{{}}'), '{{ {key} }}', to_jsonb(:{param_key}))")
            params[param_key] = value

        if set_clauses:
            update_query = f"""
                UPDATE api_documents
                SET {', '.join(set_clauses)}
                WHERE document_id = :document_id
            """
            await session.execute(text(update_query), params)
            await session.commit()

            logger.debug(f"Updated doc_metadata for document {document_id}")

    except Exception as e:
        logger.error(f"Error saving insights to metadata: {e}", exc_info=True)
        # Don't raise - this is a supplementary operation


async def _generate_pdf(
    document_id: str,
    use_case_id: str,
    fields_data: Dict[str, Any],
    insights: Dict[str, Any]
) -> Optional[str]:
    """Generate PDF report for insights."""
    try:
        engine = get_generation_engine()

        # Get display name from profile
        profile = insights.get("customer_profile", {})
        display_name = (
            profile.get("full_name") or
            profile.get("name") or
            profile.get("customer_name") or
            "document"
        )

        # Create output filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c for c in str(display_name) if c.isalnum() or c in ('_', '-')).strip()
        if not safe_name:
            safe_name = "document"
        output_filename = f"insights_{safe_name}_{timestamp}.pdf"
        output_path = f"generated_documents/{output_filename}"

        # Prepare data for PDF generation
        pdf_data = {
            "fields": fields_data,
            "insights": insights,
            "metadata": {
                "source": "api",
                "document_id": document_id,
                "use_case_id": use_case_id,
                "generated_at": insights.get("metadata", {}).get("generated_at", datetime.now().isoformat())
            }
        }

        # Generate PDF - template determined by use case
        # TODO: Make template_id configurable per use case
        gen_request = {
            "template_id": "banking_customer_insights_report_v2",
            "mapping_id": "banking_customer_insights_report_v2",
            "data_source": {
                "provider": "static",
                "query": {"data": pdf_data}
            },
            "options": {
                "output_format": "pdf",
                "output_path": output_path
            }
        }

        result = await engine.generate(gen_request)

        if result.success:
            logger.info(f"PDF generated: {output_path}")
            return f"/api/v2/insights/download/{output_filename}"
        else:
            logger.warning(f"PDF generation failed: {result.error_message}")
            return None

    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        return None


@router.get(
    "/documents",
    response_model=List[DocumentListItem],
    summary="List documents for insights generation",
    description="Get a list of all documents available for insights generation."
)
async def list_documents(
    use_case_id: str = Query(default="forms-capital-loan", description="Use case for document list display"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    """List all documents available for insights generation."""
    try:
        async with get_session() as session:
            result = await session.execute(
                text("""
                    SELECT
                        document_id,
                        fields,
                        document_type,
                        created_at
                    FROM api_documents
                    ORDER BY created_at DESC
                    LIMIT :limit OFFSET :offset
                """),
                {"limit": limit, "offset": offset}
            )
            rows = result.fetchall()

            documents = []
            for row in rows:
                fields_data = row[1] or {}

                # Extract display name dynamically
                display_name = _extract_display_name(fields_data, row[2])

                # Build summary from config-driven display fields
                summary = _build_document_summary(fields_data, use_case_id)

                documents.append(DocumentListItem(
                    document_id=row[0],
                    display_name=display_name,
                    document_type=row[2],
                    created_at=row[3].isoformat() if row[3] else "",
                    summary=summary
                ))

            logger.info(f"Listed {len(documents)} documents for use case: {use_case_id}")
            return documents

    except Exception as e:
        logger.error(f"Error listing documents: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list documents: {str(e)}"
        )


def _extract_display_name(fields: Dict[str, Any], fallback: str) -> str:
    """Extract display name from document fields dynamically."""
    # Common name field patterns
    name_fields = [
        "full_name", "name", "customer_name", "applicant_name",
        "first_name", "surname", "last_name"
    ]

    for field in name_fields:
        value = _get_field_value(fields, field)
        if value:
            return value

    # Try combining first + last name
    first = _get_field_value(fields, "first_name") or _get_field_value(fields, "first_names_and_other_names")
    last = _get_field_value(fields, "surname") or _get_field_value(fields, "last_name")
    if first or last:
        return f"{first or ''} {last or ''}".strip()

    return fallback or "Unknown"


def _get_field_value(fields: Dict[str, Any], field_name: str) -> Optional[str]:
    """Get field value handling nested structures."""
    field = fields.get(field_name)
    if field is None:
        return None

    if isinstance(field, dict) and "value" in field:
        value = field.get("value", "")
    else:
        value = str(field) if field else ""

    # Treat empty markers as None
    if value in ["<empty>", "N/A", "n/a", "null", "None", ""]:
        return None

    return value


def _build_document_summary(fields: Dict[str, Any], use_case_id: str = "forms-capital-loan") -> Dict[str, Any]:
    """
    Build a summary of key fields from document.

    Now use case dependent - loads config to determine which fields to display.

    Args:
        fields: Document fields data
        use_case_id: Use case identifier (determines which config to use)

    Returns:
        Dictionary of display fields for the document list
    """
    from modules.insights.config_loader import InsightsConfigLoader

    summary = {}

    try:
        # Load use case config
        config_loader = InsightsConfigLoader(use_case_id)
        configs = config_loader.load_all()
        criteria_config = configs.get("criteria", {})

        # Get document list summary config
        display_config = criteria_config.get("document_list_summary", {})
        display_fields = display_config.get("display_fields", [])

        for field_config in display_fields:
            label = field_config.get("label")
            source_fields = field_config.get("source_fields", [])
            field_type = field_config.get("type", "text")

            # Try each source field until we find a value
            value = None
            for source_field in source_fields:
                extracted = _get_field_value(fields, source_field)
                if extracted:
                    value = extracted
                    break

            # Format value based on type
            if value:
                if field_type == "number":
                    # Extract numeric value
                    import re
                    numbers = re.findall(r'[\d,]+\.?\d*', str(value))
                    if numbers:
                        # Format with comma separator for thousands
                        try:
                            num_val = float(numbers[0].replace(',', ''))
                            summary[label] = f"{num_val:,.0f}"
                        except:
                            summary[label] = str(numbers[0])
                    else:
                        summary[label] = str(value)
                else:
                    summary[label] = str(value)

    except FileNotFoundError:
        logger.warning(f"No document_list_summary config found for use_case: {use_case_id}, using fallback")

        # Fallback to common fields if config not found
        fallback_fields = {
            "Phone": ["contact_number", "phone", "mobile_number"],
            "Age": ["age"],
            "Income": ["monthly_income", "net_salary"]
        }

        for label, field_options in fallback_fields.items():
            for field_name in field_options:
                value = _get_field_value(fields, field_name)
                if value:
                    summary[label] = value
                    break

    return summary


@router.get(
    "/download/{filename}",
    summary="Download insights PDF",
    description="Download a generated insights PDF report.",
    response_class=FileResponse
)
async def download_insights_pdf(filename: str):
    """Download an insights PDF file."""
    # Security: validate filename
    if not filename.endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename: must be a PDF file"
        )

    # Prevent directory traversal
    if '..' in filename or filename.startswith('/'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename"
        )

    file_path = Path("generated_documents") / filename

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {filename}"
        )

    logger.info(f"Serving insights PDF: {filename}")
    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=filename
    )


@router.get(
    "/use-cases",
    summary="List available use cases",
    description="Get a list of available use case configurations."
)
async def list_use_cases():
    """List available use case configurations."""
    # TODO: Implement dynamic use case discovery from config
    return {
        "use_cases": [
            {
                "id": "forms-capital-loan",
                "name": "Forms Capital Loan Application",
                "type": "loan_assessment",
                "description": "Loan application risk assessment and eligibility"
            }
        ]
    }


@router.get(
    "/health",
    summary="Health check for insights module",
    description="Check the health status of the insights module."
)
async def health_check():
    """Health check for insights module."""
    return {
        "status": "healthy",
        "service": "universal-insights",
        "version": "2.0.0",
        "capabilities": [
            "config_driven_assessment",
            "rule_based_scoring",
            "llm_enhanced_reasoning",
            "dynamic_product_eligibility",
            "automated_decisions",
            "pdf_generation"
        ]
    }


# Backward compatibility alias
@router.get(
    "/customers",
    response_model=List[DocumentListItem],
    summary="List documents (alias for /documents)",
    description="Alias for /documents endpoint for backward compatibility."
)
async def list_customers(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    """Backward compatible alias for list_documents."""
    return await list_documents(use_case_id=None, limit=limit, offset=offset)
