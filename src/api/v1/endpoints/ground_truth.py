"""
Ground Truth API endpoints.

Provides REST API for managing ground truth (manually verified) data.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from uuid import UUID

from modules.extraction.ground_truth import GroundTruthService
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)

router = APIRouter()


class GroundTruthCreate(BaseModel):
    """Schema for creating ground truth"""
    document_type: str = Field(..., description="Type of document (invoice, packing_list, etc.)")
    verified_data: Dict[str, Any] = Field(..., description="Dictionary of verified field values")
    document_id: Optional[str] = Field(None, description="UUID of the extracted document")
    verified_by: str = Field(..., description="Email/username of who verified")
    verification_method: str = Field(default="manual", description="How it was verified")
    confidence_level: str = Field(default="high", description="Confidence in ground truth")
    notes: Optional[str] = Field(None, description="Additional notes")


class GroundTruthResponse(BaseModel):
    """Schema for ground truth response"""
    id: str
    document_id: Optional[str]
    document_type: str
    verified_data: Dict[str, Any]
    verified_by: str
    verified_at: Optional[str]
    verification_method: str
    confidence_level: str
    notes: Optional[str]


@router.post("/", response_model=Dict[str, str], status_code=status.HTTP_201_CREATED)
async def create_ground_truth(data: GroundTruthCreate):
    """
    Create a new ground truth record.
    
    Stores manually verified data for accuracy validation.
    """
    try:
        service = GroundTruthService()
        
        ground_truth_id = await service.store(
            document_type=data.document_type,
            verified_data=data.verified_data,
            document_id=data.document_id,
            verified_by=data.verified_by,
            verification_method=data.verification_method,
            confidence_level=data.confidence_level,
            notes=data.notes
        )
        
        logger.info(f"Created ground truth: {ground_truth_id} by {data.verified_by}")
        
        return {
            "id": ground_truth_id,
            "message": "Ground truth created successfully"
        }
    
    except Exception as e:
        logger.error(f"Failed to create ground truth: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/{ground_truth_id}", response_model=GroundTruthResponse)
async def get_ground_truth(ground_truth_id: str):
    """
    Get ground truth by ID.
    """
    try:
        service = GroundTruthService()
        result = await service.get(ground_truth_id=ground_truth_id)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ground truth not found"
            )
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get ground truth: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/document/{document_id}", response_model=GroundTruthResponse)
async def get_ground_truth_by_document(document_id: str):
    """
    Get ground truth for a specific document.
    """
    try:
        service = GroundTruthService()
        result = await service.get(document_id=document_id)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ground truth not found for this document"
            )
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get ground truth: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/{ground_truth_id}", response_model=Dict[str, str])
async def update_ground_truth(
    ground_truth_id: str,
    verified_data: Optional[Dict[str, Any]] = None,
    verified_by: Optional[str] = None,
    confidence_level: Optional[str] = None,
    notes: Optional[str] = None
):
    """
    Update existing ground truth record.
    """
    try:
        service = GroundTruthService()
        
        success = await service.update(
            ground_truth_id=ground_truth_id,
            verified_data=verified_data,
            verified_by=verified_by,
            confidence_level=confidence_level,
            notes=notes
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ground truth not found"
            )
        
        return {"message": "Ground truth updated successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update ground truth: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{ground_truth_id}", response_model=Dict[str, str])
async def delete_ground_truth(ground_truth_id: str):
    """
    Delete ground truth record.
    """
    try:
        service = GroundTruthService()
        success = await service.delete(ground_truth_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ground truth not found"
            )
        
        return {"message": "Ground truth deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete ground truth: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/type/{document_type}", response_model=List[GroundTruthResponse])
async def list_ground_truth_by_type(
    document_type: str,
    limit: int = 100,
    offset: int = 0
):
    """
    List all ground truth records for a document type.
    """
    try:
        service = GroundTruthService()
        results = await service.list_by_document_type(
            document_type=document_type,
            limit=limit,
            offset=offset
        )
        
        return results
    
    except Exception as e:
        logger.error(f"Failed to list ground truth: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
