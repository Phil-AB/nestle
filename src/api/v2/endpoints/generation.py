"""
Generation API endpoints.

Handles document generation requests.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from pathlib import Path

# Import providers/renderers/mappers FIRST to trigger registration
import modules.generation.data_providers
import modules.generation.renderers
import modules.generation.mappers

from modules.generation.engine import GenerationEngine
from src.api.v1.dependencies.auth import verify_api_key
from shared.utils.logger import setup_logger
from modules.generation.config import GenerationConfig
from pathlib import Path

logger = setup_logger(__name__)
router = APIRouter(prefix="/generation", tags=["generation"])

# Initialize generation engine with correct project root
# Backend runs from src/api/, so go up 2 levels to project root
project_root = Path(__file__).resolve().parents[4]  # generation.py -> endpoints -> v2 -> api -> src -> PROJECT_ROOT
config = GenerationConfig(project_root=project_root)
generation_engine = GenerationEngine(config=config)

logger.info(f"Generation engine initialized with project_root: {project_root}")


# ==============================================================================
# REQUEST/RESPONSE MODELS
# ==============================================================================

class DataSourceModel(BaseModel):
    """Data source configuration"""
    provider: str = "postgres"
    query: Dict[str, Any]  # Can contain 'document_id' (single) or 'document_ids' (multi-source)
    merge_strategy: Optional[str] = "prioritized"  # For multi-source: 'prioritized', 'best_available', 'all_required'
    options: Optional[Dict[str, Any]] = None


class GenerationRequest(BaseModel):
    """Request to generate document"""
    template_id: str
    data_source: DataSourceModel
    mapping_id: Optional[str] = None
    options: Optional[Dict[str, Any]] = None


class BatchGenerationRequest(BaseModel):
    """Request for batch generation"""
    template_id: str
    data_sources: List[DataSourceModel]
    mapping_id: Optional[str] = None
    options: Optional[Dict[str, Any]] = None


class GenerationResponse(BaseModel):
    """Response from generation request"""
    success: bool
    job_id: str
    status: str
    message: str
    download_url: Optional[str] = None
    generation_time_ms: Optional[float] = None


class JobStatusResponse(BaseModel):
    """Job status response"""
    job_id: str
    status: str
    created_at: float
    completed_at: Optional[float] = None
    error: Optional[str] = None


class TemplateListResponse(BaseModel):
    """Template list response"""
    templates: List[Dict[str, Any]]
    total: int


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    renderers: Dict[str, bool]
    data_providers: Dict[str, bool]
    templates_loaded: int


# ==============================================================================
# ENDPOINTS
# ==============================================================================

@router.post("/generate", response_model=GenerationResponse)
async def generate_document(
    request: GenerationRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Generate document from template and data.

    Single-source example:
    ```json
    {
        "template_id": "example_invoice_v1",
        "data_source": {
            "provider": "postgres",
            "query": {"document_id": "550e8400-e29b-41d4-a716-446655440000"}
        },
        "mapping_id": "example_invoice_mapping",
        "options": {
            "output_format": "docx"
        }
    }
    ```

    Multi-source example (combine multiple documents):
    ```json
    {
        "template_id": "boe_v1",
        "data_source": {
            "provider": "postgres",
            "query": {
                "document_ids": [
                    "invoice-123",
                    "packing-list-456",
                    "coo-789"
                ]
            },
            "merge_strategy": "prioritized"
        },
        "mapping_id": "boe_mapping",
        "options": {
            "output_format": "pdf"
        }
    }
    ```

    Merge strategies:
    - `prioritized` (default): First document wins for field conflicts
    - `best_available`: Most complete value wins
    - `all_required`: Only include fields present in ALL documents
    """
    try:
        logger.info(f"Generation request received: template_id={request.template_id}, mapping_id={request.mapping_id}")
        logger.info(f"Data source: provider={request.data_source.provider}, query={request.data_source.query}")
        
        # Convert Pydantic model to dict
        request_dict = {
            "template_id": request.template_id,
            "data_source": request.data_source.dict(),
            "mapping_id": request.mapping_id,
            "options": request.options or {}
        }
        
        # Start generation
        result = await generation_engine.generate(request_dict)
        
        if result.success:
            download_url = f"/api/v2/generation/download/{result.job_id}"
            
            return GenerationResponse(
                success=True,
                job_id=result.job_id,
                status="completed",
                message="Document generated successfully",
                download_url=download_url,
                generation_time_ms=result.generation_time_ms
            )
        else:
            return GenerationResponse(
                success=False,
                job_id=result.job_id,
                status="failed",
                message=result.error_message or "Generation failed"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generation failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch", response_model=Dict[str, Any])
async def generate_batch(
    request: BatchGenerationRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Generate multiple documents in batch.
    
    Example request:
    ```json
    {
        "template_id": "example_invoice_v1",
        "data_sources": [
            {"provider": "postgres", "query": {"document_id": "123"}},
            {"provider": "postgres", "query": {"document_id": "456"}}
        ],
        "mapping_id": "example_invoice_mapping"
    }
    ```
    """
    try:
        logger.info(f"Batch generation request: {len(request.data_sources)} documents")
        
        request_dict = {
            "template_id": request.template_id,
            "data_sources": [ds.dict() for ds in request.data_sources],
            "mapping_id": request.mapping_id,
            "options": request.options or {}
        }
        
        results = await generation_engine.generate_batch(request_dict)
        
        successful = sum(1 for r in results if r.success)
        job_ids = [r.job_id for r in results]
        
        return {
            "success": True,
            "batch_id": f"batch_{results[0].job_id[:8] if results else 'unknown'}",
            "total": len(results),
            "successful": successful,
            "failed": len(results) - successful,
            "job_ids": job_ids
        }
    
    except Exception as e:
        logger.error(f"Batch generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Get generation job status."""
    status = await generation_engine.get_job_status(job_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatusResponse(**status)


@router.get("/download/{job_id}")
async def download_generated_document(
    job_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Download generated document."""
    file_path = await generation_engine.get_output_path(job_id)
    
    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Determine media type based on file extension
    extension = Path(file_path).suffix.lower()
    media_types = {
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.pdf': 'application/pdf',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.html': 'text/html',
    }
    media_type = media_types.get(extension, 'application/octet-stream')
    
    return FileResponse(
        path=file_path,
        filename=Path(file_path).name,
        media_type=media_type
    )


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(
    format: Optional[str] = None,
    api_key: str = Depends(verify_api_key)
):
    """List available templates."""
    logger.info(f"Listing templates with format filter: {format}")
    templates = await generation_engine.list_templates(format=format)
    logger.info(f"Found {len(templates)} templates")
    return TemplateListResponse(templates=templates, total=len(templates))


@router.get("/templates/{template_id}")
async def get_template_details(
    template_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Get template details."""
    metadata = await generation_engine.template_registry.get_template_metadata(template_id)
    
    if not metadata:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return metadata.to_dict()


@router.get("/renderers")
async def list_renderers(api_key: str = Depends(verify_api_key)):
    """List available renderers."""
    from modules.generation.core.registry import RendererRegistry
    
    renderers = RendererRegistry.list_renderers()
    return {
        "renderers": renderers,
        "default": "docx"
    }


@router.get("/data-providers")
async def list_data_providers(api_key: str = Depends(verify_api_key)):
    """List available data providers."""
    from modules.generation.core.registry import DataProviderRegistry
    
    providers = DataProviderRegistry.list_providers()
    return {
        "providers": providers,
        "default": "postgres"
    }


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check generation module health."""
    health = await generation_engine.health_check()
    return HealthResponse(**health)
