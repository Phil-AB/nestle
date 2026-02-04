"""
Automation API Endpoints.

REST API for triggering and managing automated workflows:
- Automated approval for low-risk applications
- Manual trigger for automation
- Status tracking and history
"""

from fastapi import APIRouter, HTTPException, status, Query, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
import logging

from src.database.connection import get_session
from modules.automation.agents.automated_approval_agent import (
    AutomatedApprovalAgent,
    AutomationTask,
    AutomationResult
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/automation",
    tags=["automation"],
    responses={
        404: {"description": "Document not found"},
        500: {"description": "Internal server error"}
    }
)

# Agent instance (singleton)
_approval_agent: Optional[AutomatedApprovalAgent] = None


def get_approval_agent() -> AutomatedApprovalAgent:
    """Get or create approval agent instance."""
    global _approval_agent
    if _approval_agent is None:
        _approval_agent = AutomatedApprovalAgent()
    return _approval_agent


# ==============================================================================
# REQUEST/RESPONSE MODELS
# ==============================================================================

class AutomationTriggerRequest(BaseModel):
    """Request model for triggering automation."""
    document_id: str = Field(..., description="Document ID to process")
    trigger_event: Literal["insights_generated", "manual", "webhook"] = Field(
        default="manual",
        description="Event that triggered automation"
    )
    trigger_data: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional trigger data"
    )


class AutomationTriggerResponse(BaseModel):
    """Response model for automation trigger."""
    success: bool
    message: str
    document_id: str
    action_taken: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BatchAutomationRequest(BaseModel):
    """Request model for batch automation."""
    document_ids: List[str] = Field(..., description="List of document IDs")
    trigger_event: Literal["batch", "scheduled"] = Field(
        default="batch",
        description="Trigger event type"
    )


class BatchAutomationResponse(BaseModel):
    """Response model for batch automation."""
    success: bool
    total: int
    processed: int
    approved: int
    skipped: int
    failed: int
    results: List[Dict[str, Any]]


class AutomationStatusResponse(BaseModel):
    """Response model for automation status."""
    document_id: str
    approval_status: Optional[str]
    auto_approved: bool
    approved_at: Optional[str]
    risk_score: Optional[int]
    email_sent: bool
    letter_generated: bool


class AutomationConfigResponse(BaseModel):
    """Response model for automation configuration."""
    enabled: bool
    risk_threshold: int
    require_pre_loan_eligible: bool
    require_email: bool
    agent_config: Dict[str, Any]


class AutomationHistoryResponse(BaseModel):
    """Response model for automation history."""
    document_id: str
    automation_log: List[Dict[str, Any]]
    total_automations: int


# ==============================================================================
# API ENDPOINTS
# ==============================================================================

@router.post(
    "/approve",
    response_model=AutomationTriggerResponse,
    summary="Trigger automated approval",
    description="Run automated approval workflow for a single document"
)
async def trigger_automation(
    request: AutomationTriggerRequest,
    background_tasks: BackgroundTasks
):
    """
    Trigger automated approval for a document.

    The agent will:
    1. Check eligibility (risk score >= 70)
    2. Generate approval letter
    3. Send email notification
    4. Update document status
    """
    try:
        agent = get_approval_agent()

        task = AutomationTask(
            document_id=request.document_id,
            trigger_event=request.trigger_event,
            trigger_data=request.trigger_data
        )

        # Run automation
        result: AutomationResult = await agent.execute(task)

        if not result.success:
            return AutomationTriggerResponse(
                success=False,
                message=result.error or "Automation failed",
                document_id=request.document_id,
                action_taken=result.action_taken,
                metadata=result.metadata
            )

        action_text = {
            "auto_approved": "Automatically approved",
            "processed": "Processed",
            "none": "No action taken"
        }.get(result.action_taken or "none", "Processed")

        return AutomationTriggerResponse(
            success=True,
            message=f"{action_text}: {request.document_id}",
            document_id=request.document_id,
            action_taken=result.action_taken,
            metadata=result.metadata
        )

    except Exception as e:
        logger.error(f"Automation trigger failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger automation: {str(e)}"
        )


@router.post(
    "/approve/batch",
    response_model=BatchAutomationResponse,
    summary="Trigger batch automation",
    description="Run automated approval for multiple documents"
)
async def trigger_batch_automation(
    request: BatchAutomationRequest,
    background_tasks: BackgroundTasks
):
    """
    Trigger automated approval for multiple documents.

    Processes all documents and returns summary statistics.
    """
    try:
        agent = get_approval_agent()

        results = []
        approved = 0
        skipped = 0
        failed = 0

        for doc_id in request.document_ids:
            try:
                task = AutomationTask(
                    document_id=doc_id,
                    trigger_event=request.trigger_event,
                    trigger_data={"batch": True}
                )

                result = await agent.execute(task)

                result_dict = {
                    "document_id": doc_id,
                    "success": result.success,
                    "action_taken": result.action_taken,
                    "error": result.error
                }
                results.append(result_dict)

                if result.success and result.action_taken == "auto_approved":
                    approved += 1
                elif result.success and result.action_taken != "auto_approved":
                    skipped += 1
                else:
                    failed += 1

            except Exception as e:
                logger.error(f"Failed to process {doc_id}: {e}")
                results.append({
                    "document_id": doc_id,
                    "success": False,
                    "action_taken": "none",
                    "error": str(e)
                })
                failed += 1

        return BatchAutomationResponse(
            success=True,
            total=len(request.document_ids),
            processed=approved + skipped,
            approved=approved,
            skipped=skipped,
            failed=failed,
            results=results
        )

    except Exception as e:
        logger.error(f"Batch automation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger batch automation: {str(e)}"
        )


@router.get(
    "/documents/{document_id}/automation-status",
    response_model=AutomationStatusResponse,
    summary="Get automation status",
    description="Retrieve automation status for a document"
)
async def get_automation_status(document_id: str):
    """Get automation status for a document."""
    try:
        from src.database.repositories.api_document_repository import APIDocumentRepository

        async with get_session() as session:
            repo = APIDocumentRepository(session)
            doc = await repo.get_by_document_id(document_id)

            if not doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document not found: {document_id}"
                )

            metadata = doc.doc_metadata or {}
            automation = metadata.get("automation", {})
            auto_approval = automation.get("auto_approval", {})

            return AutomationStatusResponse(
                document_id=document_id,
                approval_status=metadata.get("approval_status"),
                auto_approved=auto_approval.get("approved", False),
                approved_at=auto_approval.get("approved_at"),
                risk_score=auto_approval.get("risk_score"),
                email_sent=auto_approval.get("email_sent", False),
                letter_generated=auto_approval.get("letter_generated", False)
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting automation status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get automation status: {str(e)}"
        )


@router.get(
    "/eligible",
    summary="List eligible documents",
    description="List documents eligible for automated approval"
)
async def list_eligible_documents(
    limit: int = Query(50, ge=1, le=100),
    include_processed: bool = Query(False, description="Include already processed documents")
):
    """
    List documents eligible for automated approval.

    Eligibility criteria:
    - Extraction status = complete
    - Has banking insights with risk score >= 70
    - Pre-loan status = eligible (if available)
    - Not already auto-approved
    """
    try:
        from sqlalchemy import select, and_
        from src.database.models.api_document import APIDocument

        async with get_session() as session:
            query = select(APIDocument).where(
                and_(
                    APIDocument.extraction_status == "complete",
                    APIDocument.doc_metadata["banking_insights"]["risk_assessment"]["risk_score"].astext.cast(
                        int) >= 70
                )
            )

            if not include_processed:
                query = query.where(
                    APIDocument.doc_metadata["approval_status"].astext != "auto_approved"
                )

            query = query.order_by(APIDocument.created_at.desc()).limit(limit)

            result = await session.execute(query)
            documents = result.scalars().all()

            eligible_list = []
            for doc in documents:
                metadata = doc.doc_metadata or {}
                insights = metadata.get("banking_insights", {})
                risk_assessment = insights.get("risk_assessment", {})

                eligible_list.append({
                    "document_id": doc.document_id,
                    "customer_name": risk_assessment.get("customer_name", "Unknown"),
                    "risk_score": risk_assessment.get("risk_score", 0),
                    "risk_level": risk_assessment.get("risk_level", "unknown"),
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                    "already_processed": metadata.get("approval_status") == "auto_approved"
                })

            return {
                "total": len(eligible_list),
                "documents": eligible_list
            }

    except Exception as e:
        logger.error(f"Error listing eligible documents: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list eligible documents: {str(e)}"
        )


@router.get(
    "/config",
    response_model=AutomationConfigResponse,
    summary="Get automation configuration",
    description="Retrieve current automation configuration"
)
async def get_automation_config():
    """Get automation configuration."""
    try:
        agent = get_approval_agent()

        return AutomationConfigResponse(
            enabled=True,
            risk_threshold=70,
            require_pre_loan_eligible=False,
            require_email=False,
            agent_config=agent.get_config_summary()
        )

    except Exception as e:
        logger.error(f"Error getting automation config: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get automation config: {str(e)}"
        )


@router.get(
    "/health",
    summary="Health check",
    description="Check automation agent health"
)
async def health_check():
    """Check automation agent health."""
    try:
        agent = get_approval_agent()
        healthy = await agent.health_check()

        return {
            "status": "healthy" if healthy else "unhealthy",
            "service": "automation-agent",
            "agent_type": "AutomatedApprovalAgent",
            "config": agent.get_config_summary()
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unhealthy: {str(e)}"
        )


@router.post(
    "/documents/{document_id}/retry",
    response_model=AutomationTriggerResponse,
    summary="Retry automation",
    description="Retry automation for a specific document"
)
async def retry_automation(document_id: str):
    """Retry automation for a document."""
    try:
        agent = get_approval_agent()

        task = AutomationTask(
            document_id=document_id,
            trigger_event="manual",
            trigger_data={"retry": True}
        )

        result = await agent.execute(task)

        if not result.success:
            return AutomationTriggerResponse(
                success=False,
                message=result.error or "Retry failed",
                document_id=document_id,
                action_taken=result.action_taken
            )

        return AutomationTriggerResponse(
            success=True,
            message=f"Retry successful: {document_id}",
            document_id=document_id,
            action_taken=result.action_taken,
            metadata=result.metadata
        )

    except Exception as e:
        logger.error(f"Retry failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry automation: {str(e)}"
        )
