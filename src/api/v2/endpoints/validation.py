"""Core validation session CRUD endpoints."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, HTTPException

from modules.validation_engine import get_validation_engine
from shared.utils.logger import get_logger

from .validation_models import (
    CreateValidationSessionRequest,
    CreateValidationSessionResponse,
    ValidationStatusResponse,
    RunValidationRequest,
    UserConfirmationRequest,
    UserDataRequest,
    ValidationReportResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/validation", tags=["validation"])


@router.post("/sessions", response_model=CreateValidationSessionResponse)
async def create_validation_session(request: CreateValidationSessionRequest):
    """Create a new validation session."""
    try:
        logger.info(f"Creating validation session for use case: {request.use_case}")

        engine = get_validation_engine()

        context = await engine.create_validation_session(
            use_case=request.use_case,
            documents=request.documents,
            tolerance_overrides=request.tolerance_overrides,
            user_provided_data=request.user_provided_data,
        )

        return CreateValidationSessionResponse(
            session_id=str(context.session_id),
            use_case=context.use_case,
            version=context.version,
            status="created",
            message="Validation session created successfully",
        )

    except Exception as e:
        logger.error(f"Failed to create validation session: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{session_id}/validate")
async def run_validation(
    session_id: UUID,
    request: RunValidationRequest = None,
):
    """Run validation workflow for a session."""
    try:
        logger.info(f"Running validation for session {session_id}")

        from shared.utils.token_tracker import create_tracker, set_step

        token_tracker = create_tracker()
        set_step("validation_normalization")

        from modules.validation_engine.orchestration import get_validation_workflow
        from modules.validation_engine.core.session_manager import get_session_manager

        workflow = get_validation_workflow()
        engine = get_validation_engine()
        session_manager = get_session_manager()
        context = await session_manager.get_session(session_id)

        set_step("validation_workflow")
        final_state = await workflow.run(
            session_id=session_id,
            documents=context.documents,
            config=context.config,
            primary_document=context.primary_document,
            supporting_documents=context.supporting_documents,
            tolerance_overrides=context.tolerance_overrides,
        )

        summary = await session_manager.get_summary(session_id)

        updated_context = await session_manager.get_session(session_id)

        from modules.validation_engine.version_control import get_version_manager
        version_manager = get_version_manager()
        version_metadata = await version_manager.create_version_metadata(
            updated_context,
            notes=f"Validation completed with status: {final_state.get('final_status')}",
        )

        logger.info(
            f"Created version metadata: V{version_metadata.version} "
            f"for session {session_id}"
        )

        return {
            "session_id": str(session_id),
            "version": version_metadata.version,
            "workflow_status": final_state.get("workflow_status"),
            "final_status": final_state.get("final_status"),
            "summary": summary.dict(),
            "completed_steps": final_state.get("completed_steps", []),
            "messages": final_state.get("messages", []),
            "token_usage": token_tracker.get_summary(),
        }

    except Exception as e:
        logger.error(f"Validation failed for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}", response_model=ValidationStatusResponse)
async def get_session_status(session_id: UUID):
    """Get validation session status."""
    try:
        engine = get_validation_engine()
        status = engine.get_session_status(session_id)
        return ValidationStatusResponse(**status)
    except Exception as e:
        logger.error(f"Failed to get session status: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Session not found: {str(e)}")


@router.post("/sessions/{session_id}/user-input")
async def submit_user_input(
    session_id: UUID,
    request: UserDataRequest,
):
    """Submit user-provided data for missing fields."""
    try:
        logger.info(
            f"Adding user data for session {session_id}: "
            f"{request.field_name} = {request.value}"
        )

        engine = get_validation_engine()
        await engine.add_user_data(
            session_id=session_id,
            field_name=request.field_name,
            value=request.value,
        )

        return {
            "session_id": str(session_id),
            "field_name": request.field_name,
            "message": "User data added successfully",
        }

    except Exception as e:
        logger.error(f"Failed to add user data: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{session_id}/confirm-discrepancies")
async def confirm_discrepancies(
    session_id: UUID,
    confirmations: List[UserConfirmationRequest],
):
    """Submit user confirmations for discrepancies."""
    try:
        logger.info(
            f"Processing {len(confirmations)} discrepancy confirmations "
            f"for session {session_id}"
        )

        engine = get_validation_engine()

        for confirmation in confirmations:
            await engine.add_user_confirmation(
                session_id=session_id,
                discrepancy_id=confirmation.discrepancy_id,
                confirmed=confirmation.confirmed,
                comment=confirmation.comment,
            )

        return {
            "session_id": str(session_id),
            "confirmations_processed": len(confirmations),
            "message": "Discrepancy confirmations processed successfully",
        }

    except Exception as e:
        logger.error(f"Failed to process confirmations: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions/{session_id}/report", response_model=ValidationReportResponse)
async def get_validation_report(
    session_id: UUID,
    format: str = "json",
):
    """Get validation report."""
    try:
        logger.info(f"Generating {format} report for session {session_id}")

        engine = get_validation_engine()
        report = await engine.get_validation_report(
            session_id=session_id,
            format=format,
        )

        if format == "json":
            return ValidationReportResponse(**report)
        else:
            return {"report": report, "format": format}

    except Exception as e:
        logger.error(f"Failed to generate report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/discrepancies")
async def get_discrepancies(session_id: UUID):
    """Get all discrepancies for a session."""
    try:
        from modules.validation_engine.core.session_manager import get_session_manager
        from modules.validation_engine.core.result_aggregator import ResultAggregator

        session_manager = get_session_manager()
        context = await session_manager.get_session(session_id)

        aggregator = ResultAggregator()
        grouped = aggregator.group_discrepancies_by_severity(context.discrepancies)

        return {
            "session_id": str(session_id),
            "total": len(context.discrepancies),
            "by_severity": {
                severity: [d.dict() for d in discs]
                for severity, discs in grouped.items()
            },
        }

    except Exception as e:
        logger.error(f"Failed to get discrepancies: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/use-cases")
async def list_use_cases():
    """List all available validation use cases."""
    try:
        engine = get_validation_engine()
        use_cases = engine.list_use_cases()
        return {"use_cases": use_cases, "count": len(use_cases)}
    except Exception as e:
        logger.error(f"Failed to list use cases: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validators")
async def list_validators():
    """List all registered validators."""
    try:
        engine = get_validation_engine()
        validators = engine.list_validators()
        return {"validators": validators, "count": len(validators)}
    except Exception as e:
        logger.error(f"Failed to list validators: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
