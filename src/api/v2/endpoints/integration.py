"""
Pre-Loan Integration API Endpoints.

REST API for integrating the pre-loan qualification app
with the main document processing system.

All endpoints work with real data - no hardcoded values.
"""

from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
import logging

from src.database.connection import get_session
from src.api.v2.services.pre_loan_integration_service import (
    PreLoanIntegrationService,
    PreLoanSessionManager,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/integration",
    tags=["pre-loan-integration"],
    responses={
        404: {"description": "Document not found"},
        500: {"description": "Internal server error"}
    }
)

# Session manager for linking pre-loan to document upload
session_manager = PreLoanSessionManager()


# ==============================================================================
# REQUEST/RESPONSE MODELS
# ==============================================================================

class PreLoanDataRequest(BaseModel):
    """Request model for storing pre-loan qualification data."""
    document_id: str = Field(..., description="Document ID to link pre-loan data to")
    session_id: str = Field(..., description="Pre-loan session identifier")
    pre_loan_status: Literal["eligible", "discuss_with_officer", "not_eligible"] = Field(
        ...,
        description="Outcome of pre-loan qualification"
    )
    pre_loan_date: str = Field(..., description="When pre-loan check was completed")
    answers: Dict[str, Any] = Field(default_factory=dict, description="User's answers to pre-loan questions")
    risk_assessment: Optional[Dict[str, Any]] = Field(None, description="Pre-loan risk assessment")

class PreLoanSessionCreateRequest(BaseModel):
    """Request model for creating a new pre-loan session."""
    answers: Dict[str, Any] = Field(..., description="User's answers to pre-loan questions")
    pre_loan_status: Literal["eligible", "discuss_with_officer", "not_eligible"] = Field(
        ...,
        description="Outcome of pre-loan qualification"
    )
    risk_assessment: Optional[Dict[str, Any]] = Field(None, description="Risk assessment from pre-loan check")

class DocumentLinkRequest(BaseModel):
    """Request model for linking a pre-loan session to a document."""
    session_id: str = Field(..., description="Pre-loan session ID from pre-loan app")
    document_id: str = Field(..., description="Document ID from full application upload")

class PreLoanStatusResponse(BaseModel):
    """Response model for pre-loan status."""
    document_id: str
    customer_name: str
    pre_loan_status: Optional[str]
    pre_loan_date: Optional[str]
    session_id: Optional[str]
    created_at: Optional[str]

class PreLoanListResponse(BaseModel):
    """Response model for listing pre-qualified documents."""
    documents: List[PreLoanStatusResponse]
    total: int

class CombinedAssessmentResponse(BaseModel):
    """Response model for combined assessment."""
    document_id: str
    pre_loan_status: Optional[str]
    pre_loan_risk_score: Optional[int]
    insights_risk_score: Optional[int]
    combined_status: str
    pre_loan_date: Optional[str]
    session_id: Optional[str]

class SessionCreateResponse(BaseModel):
    """Response model for session creation."""
    session_id: str
    expires_at: str
    document_id: Optional[str] = None


class IntegrationStatusResponse(BaseModel):
    """Response model for integration status."""
    service: str
    version: str
    capabilities: List[str]
    active_sessions: int


# ==============================================================================
# API ENDPOINTS
# ==============================================================================

@router.post(
    "/store",
    response_model=Dict[str, Any],
    summary="Store pre-loan qualification data",
    description="Store pre-loan qualification results for a document"
)
async def store_pre_loan_data(request: PreLoanDataRequest):
    """Store pre-loan qualification data for a document."""
    try:
        async with get_session() as session:
            service = PreLoanIntegrationService(session)

            pre_loan_data = {
                "session_id": request.session_id,
                "pre_loan_status": request.pre_loan_status,
                "pre_loan_date": request.pre_loan_date,
                "answers": request.answers,
                "risk_assessment": request.risk_assessment,
            }

            doc = await service.store_pre_loan_data(request.document_id, pre_loan_data)

            if doc is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document not found: {request.document_id}"
                )

            return {
                "success": True,
                "message": "Pre-loan data stored successfully",
                "document_id": request.document_id,
                "pre_loan_status": request.pre_loan_status,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error storing pre-loan data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store pre-loan data: {str(e)}"
        )


@router.post(
    "/session/create",
    response_model=SessionCreateResponse,
    summary="Create pre-loan session",
    description="Create a new pre-loan qualification session"
)
async def create_pre_loan_session(request: PreLoanSessionCreateRequest):
    """Create a new pre-loan qualification session."""
    try:
        session_id = session_manager.create_session({
            "answers": request.answers,
            "pre_loan_status": request.pre_loan_status,
            "risk_assessment": request.risk_assessment,
        })

        session = session_manager.get_session(session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create session"
            )

        return SessionCreateResponse(
            session_id=session_id,
            expires_at=session["expires_at"].isoformat(),
        )

    except Exception as e:
        logger.error(f"Error creating session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}"
        )


@router.post(
    "/session/{session_id}/link",
    response_model=Dict[str, Any],
    summary="Link session to document",
    description="Link a pre-loan session to a newly uploaded document"
)
async def link_session_to_document(request: DocumentLinkRequest):
    """Link a pre-loan qualification session to a document."""
    try:
        async with get_session() as session:
            service = PreLoanIntegrationService(session)

            # Link the session to the document
            doc = await service.link_pre_loan_to_document(
                request.session_id,
                request.document_id
            )

            # Update session manager
            linked = session_manager.link_document(request.session_id, request.document_id)

            if not doc or not linked:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Session or document not found"
                )

            return {
                "success": True,
                "message": "Session linked to document successfully",
                "session_id": request.session_id,
                "document_id": request.document_id,
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error linking session to document: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to link session: {str(e)}"
        )


@router.get(
    "/session/{session_id}",
    response_model=Dict[str, Any],
    summary="Get pre-loan session data",
    description="Retrieve pre-loan session data by session ID"
)
async def get_pre_loan_session(session_id: str):
    """Get pre-loan session data."""
    try:
        session = session_manager.get_session(session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found or expired: {session_id}"
            )

        return {
            "session_id": session_id,
            "status": "active",
            "pre_loan_status": session["data"]["pre_loan_status"],
            "answers": session["data"]["answers"],
            "risk_assessment": session["data"].get("risk_assessment"),
            "created_at": session["created_at"].isoformat(),
            "expires_at": session["expires_at"].isoformat(),
            "document_id": session.get("document_id"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session: {str(e)}"
        )


@router.get(
    "/documents/{document_id}/pre-loan-status",
    response_model=PreLoanStatusResponse,
    summary="Get pre-loan status for a document",
    description="Retrieve pre-loan qualification data for a document"
)
async def get_pre_loan_status(document_id: str):
    """Get pre-loan qualification status for a document."""
    try:
        async with get_session() as session:
            service = PreLoanIntegrationService(session)
            pre_loan_data = await service.get_pre_loan_status(document_id)

            if not pre_loan_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No pre-loan data found for document: {document_id}"
                )

            # Get document for customer name
            doc = await service.document_repo.get_by_document_id(document_id)
            if not doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document not found: {document_id}"
                )

            fields = doc.fields or {}
            customer_name = service._extract_customer_name(fields)

            return PreLoanStatusResponse(
                document_id=document_id,
                customer_name=customer_name,
                pre_loan_status=pre_loan_data.get("status"),
                pre_loan_date=pre_loan_data.get("date"),
                session_id=pre_loan_data.get("session_id"),
                created_at=doc.created_at.isoformat() if doc.created_at else None,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pre-loan status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pre-loan status: {str(e)}"
        )


@router.get(
    "/documents/pre-qualified",
    response_model=PreLoanListResponse,
    summary="List pre-qualified documents",
    description="List all documents with pre-loan qualification data"
)
async def list_pre_qualified_documents(
    limit: int = Query(50, ge=1, le=100)
):
    """List documents that have pre-loan qualification data."""
    try:
        async with get_session() as session:
            service = PreLoanIntegrationService(session)
            documents = await service.list_pre_qualified_documents(limit)

            return PreLoanListResponse(
                documents=[PreLoanStatusResponse(**d) for d in documents],
                total=len(documents)
            )

    except Exception as e:
        logger.error(f"Error listing pre-qualified documents: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list pre-qualified documents: {str(e)}"
        )


@router.get(
    "/documents/{document_id}/combined-assessment",
    response_model=CombinedAssessmentResponse,
    summary="Get combined assessment",
    description="Get combined assessment from pre-loan check and full insights"
)
async def get_combined_assessment(document_id: str):
    """Get combined assessment from pre-loan and full insights."""
    try:
        async with get_session() as session:
            service = PreLoanIntegrationService(session)
            combined = await service.get_combined_assessment(document_id)

            if not combined:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No assessment data found for document: {document_id}"
                )

            return CombinedAssessmentResponse(**combined)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting combined assessment: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get combined assessment: {str(e)}"
        )


@router.get(
    "/status",
    response_model=IntegrationStatusResponse,
    summary="Get integration status",
    description="Check the health status of the pre-loan integration"
)
async def get_integration_status():
    """Get pre-loan integration status."""
    session_manager.cleanup_expired_sessions()

    return IntegrationStatusResponse(
        service="pre-loan-integration",
        version="1.0.0",
        capabilities=[
            "pre_loan_data_storage",
            "session_management",
            "document_linking",
            "pre_qualified_listings",
            "combined_assessment",
            "session_expiration"
        ],
        active_sessions=len(session_manager.sessions)
    )


@router.delete(
    "/session/{session_id}",
    response_model=Dict[str, Any],
    summary="Delete pre-loan session",
    description="Delete a pre-loan qualification session"
)
async def delete_pre_loan_session(session_id: str):
    """Delete a pre-loan qualification session."""
    try:
        deleted = session_manager.sessions.pop(session_id, False)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {session_id}"
            )

        return {
            "success": True,
            "message": "Session deleted successfully",
            "session_id": session_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete session: {str(e)}"
        )
