"""
Document Profile Management API Endpoints.

Production-grade REST API for managing document profiles.
Works with real documents only.
"""

from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
import logging

from src.database.connection import get_session
from src.api.v2.services.document_profile_service import (
    DocumentProfileService,
    FormType,
    RiskLevel
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/profiles",
    tags=["document-profiles"],
    responses={
        404: {"description": "Document not found"},
        500: {"description": "Internal server error"}
    }
)


# ==============================================================================
# REQUEST/RESPONSE MODELS
# ==============================================================================

class FormTypeUpdate(BaseModel):
    """Request model for updating form type."""
    document_id: str = Field(..., description="Document ID")
    form_type: FormType = Field(..., description="Form type: handwritten, digital, or unknown")


class RiskLevelUpdate(BaseModel):
    """Request model for updating risk level."""
    document_id: str = Field(..., description="Document ID")
    risk_level: RiskLevel = Field(..., description="Risk level: high, medium, low, or unknown")
    risk_score: Optional[int] = Field(None, ge=0, le=100, description="Optional numeric risk score")


class DisplayOrderUpdate(BaseModel):
    """Request model for updating display order."""
    document_id: str = Field(..., description="Document ID")
    order: int = Field(..., ge=0, description="Display order position")


class ProfileTagsUpdate(BaseModel):
    """Request model for updating profile tags."""
    document_id: str = Field(..., description="Document ID")
    tags: List[str] = Field(..., description="List of tags to apply")


class BulkFormTypeUpdate(BaseModel):
    """Request model for bulk form type update."""
    document_ids: List[str] = Field(..., description="List of document IDs")
    form_type: FormType = Field(..., description="Form type to apply to all")


class ProfileListItem(BaseModel):
    """Profile list item."""
    document_id: str
    name: str
    document_type: Optional[str]
    form_type: str
    risk_level: Optional[str]
    risk_score: Optional[int]
    display_order: Optional[int]
    tags: List[str]
    created_at: Optional[str]


class ProfileListResponse(BaseModel):
    """Response model for profile list."""
    profiles: List[ProfileListItem]
    total: int


class ProfileUpdateResponse(BaseModel):
    """Response model for profile update operations."""
    success: bool
    message: str
    document_id: Optional[str] = None
    updated_count: Optional[int] = None


class ProfileStatsResponse(BaseModel):
    """Response model for profile statistics."""
    total_with_profiles: int
    by_form_type: Dict[str, int]
    by_risk_level: Dict[str, int]


# ==============================================================================
# API ENDPOINTS
# ==============================================================================

@router.get(
    "",
    response_model=ProfileListResponse,
    summary="List document profiles",
    description="List all documents with profile metadata, optionally filtered"
)
async def list_profiles(
    form_type: Optional[FormType] = Query(None, description="Filter by form type"),
    risk_level: Optional[RiskLevel] = Query(None, description="Filter by risk level"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    has_insights: Optional[bool] = Query(None, description="Filter by insights existence"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """List document profiles with optional filtering."""
    try:
        async with get_session() as session:
            service = DocumentProfileService(session)
            profiles, total = await service.list_profiles(
                form_type=form_type,
                risk_level=risk_level,
                tag=tag,
                has_insights=has_insights,
                limit=limit,
                offset=offset
            )

            return ProfileListResponse(
                profiles=[ProfileListItem(**p) for p in profiles],
                total=total
            )

    except Exception as e:
        logger.error(f"Error listing profiles: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list profiles: {str(e)}"
        )


@router.post(
    "/form-type",
    response_model=ProfileUpdateResponse,
    summary="Set document form type",
    description="Tag a document as handwritten, digital, or unknown"
)
async def set_form_type(request: FormTypeUpdate):
    """Set the form type for a document."""
    try:
        async with get_session() as session:
            service = DocumentProfileService(session)
            doc = await service.set_form_type(
                request.document_id,
                request.form_type
            )

            if doc is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document not found: {request.document_id}"
                )

            return ProfileUpdateResponse(
                success=True,
                message=f"Form type set to {request.form_type}",
                document_id=request.document_id
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting form type: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set form type: {str(e)}"
        )


@router.post(
    "/risk-level",
    response_model=ProfileUpdateResponse,
    summary="Set document risk level",
    description="Tag a document with its risk level"
)
async def set_risk_level(request: RiskLevelUpdate):
    """Set the risk level for a document."""
    try:
        async with get_session() as session:
            service = DocumentProfileService(session)
            doc = await service.set_risk_level(
                request.document_id,
                request.risk_level,
                request.risk_score
            )

            if doc is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document not found: {request.document_id}"
                )

            return ProfileUpdateResponse(
                success=True,
                message=f"Risk level set to {request.risk_level}",
                document_id=request.document_id
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting risk level: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set risk level: {str(e)}"
        )


@router.post(
    "/display-order",
    response_model=ProfileUpdateResponse,
    summary="Set display order",
    description="Set the display order for a document in the profile selector"
)
async def set_display_order(request: DisplayOrderUpdate):
    """Set the display order for a document."""
    try:
        async with get_session() as session:
            service = DocumentProfileService(session)
            doc = await service.set_display_order(
                request.document_id,
                request.order
            )

            if doc is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document not found: {request.document_id}"
                )

            return ProfileUpdateResponse(
                success=True,
                message=f"Display order set to {request.order}",
                document_id=request.document_id
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting display order: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set display order: {str(e)}"
        )


@router.post(
    "/tags",
    response_model=ProfileUpdateResponse,
    summary="Set profile tags",
    description="Set custom profile tags for a document"
)
async def set_profile_tags(request: ProfileTagsUpdate):
    """Set profile tags for a document."""
    try:
        async with get_session() as session:
            service = DocumentProfileService(session)
            doc = await service.set_profile_tags(
                request.document_id,
                request.tags
            )

            if doc is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document not found: {request.document_id}"
                )

            return ProfileUpdateResponse(
                success=True,
                message=f"Tags updated: {', '.join(request.tags)}",
                document_id=request.document_id
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set tags: {str(e)}"
        )


@router.post(
    "/bulk/form-type",
    response_model=ProfileUpdateResponse,
    summary="Bulk update form types",
    description="Update form type for multiple documents at once"
)
async def bulk_update_form_types(request: BulkFormTypeUpdate):
    """Bulk update form types for multiple documents."""
    try:
        async with get_session() as session:
            service = DocumentProfileService(session)
            updated_count = await service.bulk_update_form_types(
                request.document_ids,
                request.form_type
            )

            return ProfileUpdateResponse(
                success=True,
                message=f"Updated {updated_count} documents to {request.form_type}",
                updated_count=updated_count
            )

    except Exception as e:
        logger.error(f"Error bulk updating form types: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to bulk update: {str(e)}"
        )


@router.get(
    "/stats",
    response_model=ProfileStatsResponse,
    summary="Get profile statistics",
    description="Get statistics about document profiles"
)
async def get_profile_stats():
    """Get profile statistics."""
    try:
        async with get_session() as session:
            service = DocumentProfileService(session)
            stats = await service.get_profile_stats()

            return ProfileStatsResponse(**stats)

    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )


@router.delete(
    "/{document_id}",
    response_model=ProfileUpdateResponse,
    summary="Clear profile metadata",
    description="Clear all profile metadata from a document"
)
async def clear_profile_metadata(document_id: str):
    """Clear profile metadata from a document."""
    try:
        async with get_session() as session:
            from src.database.repositories.api_document_repository import APIDocumentRepository
            repo = APIDocumentRepository(session)
            doc = await repo.get_by_document_id(document_id)

            if doc is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document not found: {document_id}"
                )

            # Clear profile-related metadata
            metadata = doc.doc_metadata or {}
            keys_to_remove = ["form_type", "risk_level", "risk_score", "display_order", "profile_tags"]
            for key in keys_to_remove:
                metadata.pop(key, None)

            await repo.update(document_id, {"doc_metadata": metadata})

            return ProfileUpdateResponse(
                success=True,
                message="Profile metadata cleared",
                document_id=document_id
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing metadata: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear metadata: {str(e)}"
        )


@router.get(
    "/health",
    summary="Health check for profiles service",
    description="Check the health status of the profiles service"
)
async def health_check():
    """Health check for profiles service."""
    return {
        "status": "healthy",
        "service": "document-profiles",
        "version": "1.0.0",
        "capabilities": [
            "form_type_tagging",
            "risk_level_tagging",
            "profile_tagging",
            "display_order",
            "bulk_operations",
            "profile_statistics"
        ]
    }
