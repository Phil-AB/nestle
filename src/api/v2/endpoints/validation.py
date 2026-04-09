"""Validation API endpoints"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel

from modules.validation_engine import get_validation_engine
from modules.validation_engine.orchestration import get_validation_workflow
from modules.validation_engine.core.config_loader import get_config_loader
from modules.validation_engine.discrepancy import (
    get_discrepancy_classifier,
    get_auto_fixer
)
from modules.validation_engine.version_control import (
    get_version_manager,
    get_revalidation_engine,
    get_delta_analyzer,
    RevalidationRequest
)
from modules.validation_engine.reporting import (
    get_report_manager,
    get_analytics_engine,
    ReportFormat,
    ReportType,
    ReportRequest
)
from shared.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/validation", tags=["validation"])


# Request/Response models
class CreateValidationSessionRequest(BaseModel):
    """Request to create validation session"""
    use_case: str
    documents: Dict[str, Dict[str, Any]]
    tolerance_overrides: Optional[Dict[str, float]] = None
    user_provided_data: Optional[Dict[str, Any]] = None


class CreateValidationSessionResponse(BaseModel):
    """Response with session info"""
    session_id: str
    use_case: str
    version: int
    status: str
    message: str


class ValidationStatusResponse(BaseModel):
    """Validation session status"""
    session_id: str
    use_case: str
    version: int
    current_step: str
    workflow_status: str
    final_status: Optional[str]
    summary: Dict[str, Any]
    created_at: str
    updated_at: str


class RunValidationRequest(BaseModel):
    """Request to run validation"""
    skip_steps: Optional[List[str]] = None


class UserConfirmationRequest(BaseModel):
    """User confirmation request"""
    discrepancy_id: str
    confirmed: bool
    comment: Optional[str] = None


class UserDataRequest(BaseModel):
    """User data input request"""
    field_name: str
    value: Any


class ValidationReportResponse(BaseModel):
    """Validation report"""
    session_id: str
    use_case: str
    final_status: str
    summary: Dict[str, Any]
    results: Dict[str, Any]
    discrepancies: Dict[str, Any]
    accuracy: Dict[str, Any]
    top_discrepancies: List[Dict[str, Any]]


# Endpoints

@router.post("/sessions", response_model=CreateValidationSessionResponse)
async def create_validation_session(request: CreateValidationSessionRequest):
    """
    Create a new validation session

    Creates a validation session with the specified use case and documents.

    Args:
        request: Session creation request

    Returns:
        Session creation response with session_id

    Raises:
        HTTPException: If use case not found or creation fails
    """
    try:
        logger.info(f"Creating validation session for use case: {request.use_case}")

        # Get validation engine
        engine = get_validation_engine()

        # Create session
        context = await engine.create_validation_session(
            use_case=request.use_case,
            documents=request.documents,
            tolerance_overrides=request.tolerance_overrides,
            user_provided_data=request.user_provided_data
        )

        return CreateValidationSessionResponse(
            session_id=str(context.session_id),
            use_case=context.use_case,
            version=context.version,
            status="created",
            message=f"Validation session created successfully"
        )

    except Exception as e:
        logger.error(f"Failed to create validation session: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{session_id}/validate")
async def run_validation(
    session_id: UUID,
    request: Optional[RunValidationRequest] = None
):
    """
    Run validation workflow for a session

    Executes the complete validation workflow including normalization,
    validation, and discrepancy analysis.

    Args:
        session_id: Session UUID
        request: Optional validation parameters

    Returns:
        Validation summary

    Raises:
        HTTPException: If session not found or validation fails
    """
    try:
        logger.info(f"Running validation for session {session_id}")

        # Get workflow
        workflow = get_validation_workflow()
        engine = get_validation_engine()

        # Get session context
        from modules.validation_engine.core.session_manager import get_session_manager
        session_manager = get_session_manager()
        context = await session_manager.get_session(session_id)

        # Run workflow
        final_state = await workflow.run(
            session_id=session_id,
            documents=context.documents,
            config=context.config,
            primary_document=context.primary_document,
            supporting_documents=context.supporting_documents,
            tolerance_overrides=context.tolerance_overrides
        )

        # Get summary
        summary = await session_manager.get_summary(session_id)

        # Create version metadata after validation completes
        updated_context = await session_manager.get_session(session_id)
        version_manager = get_version_manager()
        version_metadata = await version_manager.create_version_metadata(
            updated_context,
            notes=f"Validation completed with status: {final_state.get('final_status')}"
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
            "messages": final_state.get("messages", [])
        }

    except Exception as e:
        logger.error(f"Validation failed for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}", response_model=ValidationStatusResponse)
async def get_session_status(session_id: UUID):
    """
    Get validation session status

    Returns the current status and progress of a validation session.

    Args:
        session_id: Session UUID

    Returns:
        Session status and summary

    Raises:
        HTTPException: If session not found
    """
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
    request: UserDataRequest
):
    """
    Submit user-provided data for missing fields

    Allows users to provide values for fields that were not found
    in the documents (e.g., freight_value, insurance_value).

    Args:
        session_id: Session UUID
        request: User data input

    Returns:
        Success message

    Raises:
        HTTPException: If session not found
    """
    try:
        logger.info(
            f"Adding user data for session {session_id}: "
            f"{request.field_name} = {request.value}"
        )

        engine = get_validation_engine()

        await engine.add_user_data(
            session_id=session_id,
            field_name=request.field_name,
            value=request.value
        )

        return {
            "session_id": str(session_id),
            "field_name": request.field_name,
            "message": "User data added successfully"
        }

    except Exception as e:
        logger.error(f"Failed to add user data: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{session_id}/confirm-discrepancies")
async def confirm_discrepancies(
    session_id: UUID,
    confirmations: List[UserConfirmationRequest]
):
    """
    Submit user confirmations for discrepancies

    Allows users to confirm or reject detected discrepancies.
    Confirmed discrepancies will trigger correction emails (if configured).

    Args:
        session_id: Session UUID
        confirmations: List of user confirmations

    Returns:
        Success message with confirmation count

    Raises:
        HTTPException: If session not found
    """
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
                comment=confirmation.comment
            )

        return {
            "session_id": str(session_id),
            "confirmations_processed": len(confirmations),
            "message": "Discrepancy confirmations processed successfully"
        }

    except Exception as e:
        logger.error(f"Failed to process confirmations: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/sessions/{session_id}/report", response_model=ValidationReportResponse)
async def get_validation_report(
    session_id: UUID,
    format: str = "json"
):
    """
    Get validation report

    Generates a comprehensive validation report with results,
    discrepancies, and accuracy metrics.

    Args:
        session_id: Session UUID
        format: Report format (json, pdf, csv) - default: json

    Returns:
        Validation report

    Raises:
        HTTPException: If session not found
    """
    try:
        logger.info(f"Generating {format} report for session {session_id}")

        engine = get_validation_engine()

        report = await engine.get_validation_report(
            session_id=session_id,
            format=format
        )

        if format == "json":
            return ValidationReportResponse(**report)
        else:
            # For PDF/CSV, return raw data (would need additional processing)
            return {"report": report, "format": format}

    except Exception as e:
        logger.error(f"Failed to generate report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/discrepancies")
async def get_discrepancies(session_id: UUID):
    """
    Get all discrepancies for a session

    Returns all detected discrepancies with severity, category,
    and auto-fix status.

    Args:
        session_id: Session UUID

    Returns:
        List of discrepancies

    Raises:
        HTTPException: If session not found
    """
    try:
        from modules.validation_engine.core.session_manager import get_session_manager
        session_manager = get_session_manager()

        context = await session_manager.get_session(session_id)

        # Group discrepancies by severity
        from modules.validation_engine.core.result_aggregator import ResultAggregator
        aggregator = ResultAggregator()

        grouped = aggregator.group_discrepancies_by_severity(context.discrepancies)

        return {
            "session_id": str(session_id),
            "total": len(context.discrepancies),
            "by_severity": {
                severity: [d.dict() for d in discs]
                for severity, discs in grouped.items()
            }
        }

    except Exception as e:
        logger.error(f"Failed to get discrepancies: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/use-cases")
async def list_use_cases():
    """
    List all available validation use cases

    Returns all configured validation use cases with metadata.

    Returns:
        List of use case information
    """
    try:
        engine = get_validation_engine()
        use_cases = engine.list_use_cases()

        return {
            "use_cases": use_cases,
            "count": len(use_cases)
        }

    except Exception as e:
        logger.error(f"Failed to list use cases: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validators")
async def list_validators():
    """
    List all registered validators

    Returns all validators registered in the validator registry.

    Returns:
        List of validator information
    """
    try:
        engine = get_validation_engine()
        validators = engine.list_validators()

        return {
            "validators": validators,
            "count": len(validators)
        }

    except Exception as e:
        logger.error(f"Failed to list validators: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Version Control Endpoints

@router.post("/sessions/{session_id}/revalidate")
async def create_revalidation(
    session_id: UUID,
    reason: str,
    updated_documents: Optional[Dict[str, Dict[str, Any]]] = None,
    tolerance_overrides: Optional[Dict[str, float]] = None,
    notes: Optional[str] = None,
    tags: Optional[List[str]] = None
):
    """
    Create a new validation version (revalidation)

    Creates a new validation version based on an existing session,
    optionally with updated documents. Compares V1 vs V2 and provides
    delta analysis.

    Args:
        session_id: Original session UUID
        reason: Reason for revalidation
        updated_documents: Optional updated documents
        tolerance_overrides: Optional tolerance overrides
        notes: Optional notes for this version
        tags: Optional tags

    Returns:
        Revalidation result with comparison

    Raises:
        HTTPException: If original session not found or revalidation fails
    """
    try:
        logger.info(f"Creating revalidation for session {session_id}")

        revalidation_engine = get_revalidation_engine()

        request = RevalidationRequest(
            original_session_id=session_id,
            revalidation_reason=reason,
            updated_documents=updated_documents,
            tolerance_overrides=tolerance_overrides,
            notes=notes,
            tags=tags or []
        )

        result = await revalidation_engine.create_revalidation(request)

        return {
            "new_session_id": str(result.new_session_id),
            "new_version": result.new_version,
            "original_session_id": str(result.original_session_id),
            "original_version": result.original_version,
            "status": result.status,
            "workflow_status": result.workflow_status,
            "final_status": result.final_status,
            "comparison": result.comparison.dict() if result.comparison else None,
            "summary": {
                "total_discrepancies": result.total_discrepancies,
                "fixed": result.fixed_count,
                "new": result.new_count,
                "persistent": result.persistent_count
            },
            "messages": result.messages
        }

    except ValueError as e:
        logger.error(f"Revalidation failed: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Revalidation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/versions")
async def get_version_history(session_id: UUID):
    """
    Get version history for a session

    Returns all validation versions for a session with summaries.

    Args:
        session_id: Session UUID

    Returns:
        List of version metadata

    Raises:
        HTTPException: If session not found
    """
    try:
        version_manager = get_version_manager()

        versions = await version_manager.get_version_history(session_id)

        return {
            "session_id": str(session_id),
            "total_versions": len(versions),
            "versions": [v.dict() for v in versions]
        }

    except Exception as e:
        logger.error(f"Failed to get version history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/versions/{version}")
async def get_version_summary(session_id: UUID, version: int):
    """
    Get detailed version summary

    Returns comprehensive summary for a specific version including
    lineage, statistics, and metadata.

    Args:
        session_id: Session UUID
        version: Version number

    Returns:
        Version summary

    Raises:
        HTTPException: If version not found
    """
    try:
        version_manager = get_version_manager()

        summary = await version_manager.get_version_summary(session_id, version)

        if not summary:
            raise HTTPException(
                status_code=404,
                detail=f"Version {version} not found for session {session_id}"
            )

        return summary

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get version summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/versions/compare")
async def compare_versions(
    v1_session_id: UUID,
    v2_session_id: UUID
):
    """
    Compare two validation versions

    Performs delta analysis between two validation versions,
    identifying fixed, new, and persistent discrepancies.

    Args:
        v1_session_id: First version session UUID
        v2_session_id: Second version session UUID

    Returns:
        Detailed version comparison

    Raises:
        HTTPException: If sessions not found
    """
    try:
        logger.info(f"Comparing versions: {v1_session_id} vs {v2_session_id}")

        revalidation_engine = get_revalidation_engine()
        delta_analyzer = get_delta_analyzer()

        comparison = await revalidation_engine.compare_versions(
            v1_session_id, v2_session_id
        )

        # Get change summary
        summary = await delta_analyzer.get_change_summary(comparison)

        return {
            "comparison": comparison.dict(),
            "summary": summary
        }

    except ValueError as e:
        logger.error(f"Version comparison failed: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Version comparison failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/revalidation-history")
async def get_revalidation_history(session_id: UUID):
    """
    Get revalidation history

    Returns chronological history of all revalidations for a session
    with comparison summaries.

    Args:
        session_id: Session UUID

    Returns:
        Revalidation history

    Raises:
        HTTPException: If session not found
    """
    try:
        revalidation_engine = get_revalidation_engine()

        history = await revalidation_engine.get_revalidation_history(session_id)

        return {
            "session_id": str(session_id),
            "total_revalidations": len(history) - 1,  # Exclude original
            "history": history
        }

    except Exception as e:
        logger.error(f"Failed to get revalidation history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/revalidation-suggestion")
async def get_revalidation_suggestion(session_id: UUID):
    """
    Get revalidation suggestion

    Analyzes session and suggests whether revalidation is recommended
    based on discrepancy severity and accuracy.

    Args:
        session_id: Session UUID

    Returns:
        Revalidation suggestion with reasoning

    Raises:
        HTTPException: If session not found
    """
    try:
        revalidation_engine = get_revalidation_engine()

        suggestion = await revalidation_engine.suggest_revalidation(session_id)

        return {
            "session_id": str(session_id),
            **suggestion
        }

    except Exception as e:
        logger.error(f"Failed to get revalidation suggestion: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/lineage")
async def get_version_lineage(session_id: UUID, version: int):
    """
    Get version lineage (ancestry chain)

    Returns the complete ancestry chain for a version, showing
    how it evolved from earlier versions.

    Args:
        session_id: Session UUID
        version: Version number

    Returns:
        Version lineage from oldest to newest

    Raises:
        HTTPException: If version not found
    """
    try:
        version_manager = get_version_manager()

        lineage = await version_manager.get_lineage(session_id, version)

        return {
            "session_id": str(session_id),
            "version": version,
            "lineage_depth": len(lineage),
            "lineage": lineage
        }

    except Exception as e:
        logger.error(f"Failed to get version lineage: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Reporting and Analytics Endpoints

@router.post("/reports/generate")
async def generate_report(
    report_type: ReportType,
    format: ReportFormat = ReportFormat.JSON,
    session_id: Optional[UUID] = None,
    use_case: Optional[str] = None,
    v1_session_id: Optional[UUID] = None,
    v2_session_id: Optional[UUID] = None,
    include_raw_data: bool = False,
    max_discrepancies: Optional[int] = None
):
    """
    Generate a validation report

    Supports multiple report types:
    - validation_summary: Comprehensive validation summary
    - discrepancy_detail: Detailed discrepancy report
    - version_comparison: Compare two versions
    - audit_trail: Audit trail with all events
    - executive_summary: High-level executive summary
    - analytics_dashboard: Analytics dashboard data

    Args:
        report_type: Type of report to generate
        format: Output format (json, csv, pdf, html, excel)
        session_id: Session UUID (for single-session reports)
        use_case: Use case filter (for analytics)
        v1_session_id: First version for comparison
        v2_session_id: Second version for comparison
        include_raw_data: Include raw validation data
        max_discrepancies: Limit number of discrepancies

    Returns:
        Generated report with metadata

    Raises:
        HTTPException: If report generation fails
    """
    try:
        logger.info(f"Generating {report_type} report in {format} format")

        report_manager = get_report_manager()

        request = ReportRequest(
            report_type=report_type,
            format=format,
            session_id=session_id,
            use_case=use_case,
            v1_session_id=v1_session_id,
            v2_session_id=v2_session_id,
            include_raw_data=include_raw_data,
            max_discrepancies=max_discrepancies
        )

        report = await report_manager.generate_report(request)

        return report

    except ValueError as e:
        logger.error(f"Invalid report request: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Report generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/sessions/{session_id}/summary")
async def get_validation_summary_report(
    session_id: UUID,
    format: ReportFormat = ReportFormat.JSON
):
    """
    Get validation summary report for a session

    Args:
        session_id: Session UUID
        format: Output format (json, csv, pdf)

    Returns:
        Validation summary report

    Raises:
        HTTPException: If session not found or report generation fails
    """
    try:
        report_manager = get_report_manager()

        request = ReportRequest(
            report_type=ReportType.VALIDATION_SUMMARY,
            format=format,
            session_id=session_id
        )

        report = await report_manager.generate_report(request)

        return report

    except Exception as e:
        logger.error(f"Failed to generate summary report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/sessions/{session_id}/discrepancies")
async def get_discrepancy_detail_report(session_id: UUID):
    """
    Get detailed discrepancy report

    Returns discrepancies grouped by:
    - Severity (critical, major, minor, info)
    - Category (hs_code, weight, duty, etc.)
    - Document (which document has the issue)
    - Auto-fix status

    Args:
        session_id: Session UUID

    Returns:
        Detailed discrepancy report

    Raises:
        HTTPException: If session not found
    """
    try:
        report_manager = get_report_manager()

        request = ReportRequest(
            report_type=ReportType.DISCREPANCY_DETAIL,
            format=ReportFormat.JSON,
            session_id=session_id
        )

        report = await report_manager.generate_report(request)

        return report

    except Exception as e:
        logger.error(f"Failed to generate discrepancy report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/sessions/{session_id}/audit-trail")
async def get_audit_trail_report(session_id: UUID):
    """
    Get audit trail report

    Includes:
    - All workflow events
    - Validation steps
    - User interactions
    - Version history
    - Configuration used

    Args:
        session_id: Session UUID

    Returns:
        Audit trail report

    Raises:
        HTTPException: If session not found
    """
    try:
        report_manager = get_report_manager()

        request = ReportRequest(
            report_type=ReportType.AUDIT_TRAIL,
            format=ReportFormat.JSON,
            session_id=session_id
        )

        report = await report_manager.generate_report(request)

        return report

    except Exception as e:
        logger.error(f"Failed to generate audit trail: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/sessions/{session_id}/executive-summary")
async def get_executive_summary_report(session_id: UUID):
    """
    Get executive summary report

    High-level overview with:
    - Final status and accuracy
    - Key findings (top 3-5)
    - Recommendations (top 3-5)
    - Status indicator (green/yellow/red)

    Args:
        session_id: Session UUID

    Returns:
        Executive summary report

    Raises:
        HTTPException: If session not found
    """
    try:
        report_manager = get_report_manager()

        request = ReportRequest(
            report_type=ReportType.EXECUTIVE_SUMMARY,
            format=ReportFormat.JSON,
            session_id=session_id
        )

        report = await report_manager.generate_report(request)

        return report

    except Exception as e:
        logger.error(f"Failed to generate executive summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reports/comparison")
async def get_version_comparison_report(
    v1_session_id: UUID,
    v2_session_id: UUID
):
    """
    Get version comparison report

    Compares V1 vs V2 with:
    - Fixed discrepancies
    - New discrepancies
    - Persistent discrepancies
    - Severity changes
    - Overall assessment
    - Recommendations

    Args:
        v1_session_id: First version session UUID
        v2_session_id: Second version session UUID

    Returns:
        Version comparison report

    Raises:
        HTTPException: If sessions not found
    """
    try:
        report_manager = get_report_manager()

        request = ReportRequest(
            report_type=ReportType.VERSION_COMPARISON,
            format=ReportFormat.JSON,
            v1_session_id=v1_session_id,
            v2_session_id=v2_session_id
        )

        report = await report_manager.generate_report(request)

        return report

    except Exception as e:
        logger.error(f"Failed to generate comparison report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/dashboard")
async def get_analytics_dashboard(
    days: int = 30,
    use_case: Optional[str] = None
):
    """
    Get analytics dashboard data

    Provides aggregated metrics:
    - Total sessions and validations
    - Average accuracy
    - Status distribution
    - Discrepancy trends
    - Most common issues
    - Use case breakdown
    - Time series data

    Args:
        days: Number of days to analyze (default: 30)
        use_case: Filter by use case (optional)

    Returns:
        Analytics dashboard data

    Raises:
        HTTPException: If analytics generation fails
    """
    try:
        from datetime import datetime, timedelta

        analytics_engine = get_analytics_engine()

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        dashboard = await analytics_engine.get_dashboard_data(
            start_date=start_date,
            end_date=end_date,
            use_case=use_case
        )

        return dashboard.dict()

    except Exception as e:
        logger.error(f"Failed to generate analytics dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/use-cases/{use_case}")
async def get_use_case_analytics(use_case: str):
    """
    Get analytics for a specific use case

    Args:
        use_case: Use case name

    Returns:
        Use case analytics

    Raises:
        HTTPException: If analytics generation fails
    """
    try:
        analytics_engine = get_analytics_engine()

        analytics = await analytics_engine.get_use_case_analytics(use_case)

        return analytics

    except Exception as e:
        logger.error(f"Failed to generate use case analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/discrepancy-trends")
async def get_discrepancy_trends(days: int = 30):
    """
    Get discrepancy trends over time

    Returns daily discrepancy counts by severity.

    Args:
        days: Number of days to analyze (default: 30)

    Returns:
        Discrepancy trends

    Raises:
        HTTPException: If analytics generation fails
    """
    try:
        analytics_engine = get_analytics_engine()

        trends = await analytics_engine.get_discrepancy_trends(days=days)

        return trends

    except Exception as e:
        logger.error(f"Failed to generate discrepancy trends: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/formats")
async def list_report_formats():
    """
    List available report formats

    Returns:
        Available report formats
    """
    return {
        "formats": [
            {"name": "JSON", "value": "json", "description": "Structured JSON output"},
            {"name": "CSV", "value": "csv", "description": "Comma-separated values"},
            {"name": "PDF", "value": "pdf", "description": "PDF document (requires weasyprint)"},
            {"name": "HTML", "value": "html", "description": "HTML document"},
            {"name": "Excel", "value": "excel", "description": "Excel spreadsheet"}
        ]
    }


@router.get("/reports/types")
async def list_report_types():
    """
    List available report types

    Returns:
        Available report types
    """
    return {
        "types": [
            {
                "name": "Validation Summary",
                "value": "validation_summary",
                "description": "Comprehensive validation summary with all metrics",
                "requires": ["session_id"]
            },
            {
                "name": "Discrepancy Detail",
                "value": "discrepancy_detail",
                "description": "Detailed discrepancy breakdown by severity and category",
                "requires": ["session_id"]
            },
            {
                "name": "Version Comparison",
                "value": "version_comparison",
                "description": "Compare two validation versions",
                "requires": ["v1_session_id", "v2_session_id"]
            },
            {
                "name": "Audit Trail",
                "value": "audit_trail",
                "description": "Complete audit trail with all events",
                "requires": ["session_id"]
            },
            {
                "name": "Executive Summary",
                "value": "executive_summary",
                "description": "High-level executive summary",
                "requires": ["session_id"]
            },
            {
                "name": "Analytics Dashboard",
                "value": "analytics_dashboard",
                "description": "Aggregated analytics across sessions",
                "requires": []
            }
        ]
    }


# ============================================================================
# Pipeline Endpoints — Shipment-linked Step 2 and Step 6 workflows
# ============================================================================

# --- Shipment creation -----------------------------------------------------

class CreateShipmentRequest(BaseModel):
    """Request to create a new shipment record."""
    shipment_number: str
    supplier_name: Optional[str] = None
    consignee_name: Optional[str] = None
    incoterm: Optional[str] = None
    transport_mode: Optional[str] = None


@router.post("/shipments", tags=["pipeline"])
async def create_shipment(request: CreateShipmentRequest):
    """
    Create a Shipment record.

    Must be called before uploading vendor documents or a BOE.
    Returns a ``shipment_id`` that ties all documents and validation
    sessions together.
    """
    try:
        from src.database.connection import get_session as get_db_session
        from src.database.schema import Shipment
        from src.database.repositories.shipment_repository import ShipmentRepository

        async with get_db_session() as db:
            repo = ShipmentRepository(db)
            existing = await repo.get_by_number(request.shipment_number)
            if existing:
                return {
                    "shipment_id": existing.id,
                    "shipment_number": existing.shipment_number,
                    "status": existing.status,
                    "message": "Shipment already exists",
                }

            shipment = Shipment(
                shipment_number=request.shipment_number,
                supplier_name=request.supplier_name,
                consignee_name=request.consignee_name,
                incoterm=request.incoterm,
                transport_mode=request.transport_mode,
                status="pending",
            )
            db.add(shipment)
            await db.commit()
            await db.refresh(shipment)

        logger.info(f"Created shipment {shipment.id} ({request.shipment_number})")
        return {
            "shipment_id": shipment.id,
            "shipment_number": shipment.shipment_number,
            "status": shipment.status,
            "message": "Shipment created",
        }

    except Exception as e:
        logger.error(f"Failed to create shipment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- List shipments --------------------------------------------------------

@router.get("/shipments", tags=["pipeline"])
async def list_shipments(limit: int = 50, offset: int = 0):
    """Return a list of shipments from the database, newest first."""
    try:
        from src.database.connection import get_session as get_db_session
        from src.database.schema import Shipment
        from src.database.models.api_document import APIDocument
        from sqlalchemy import select, desc, func

        async with get_db_session() as db:
            result = await db.execute(
                select(Shipment)
                .order_by(desc(Shipment.created_at))
                .limit(limit)
                .offset(offset)
            )
            shipments = result.scalars().all()

            # Count vendor docs per shipment to show step 2 status
            shipment_ids = [s.id for s in shipments]
            doc_counts: dict = {}
            if shipment_ids:
                count_result = await db.execute(
                    select(
                        APIDocument.shipment_id,
                        func.count(APIDocument.id).label("doc_count")
                    )
                    .where(APIDocument.shipment_id.in_(shipment_ids))
                    .where(APIDocument.extraction_status == "complete")
                    .group_by(APIDocument.shipment_id)
                )
                for row in count_result:
                    doc_counts[row.shipment_id] = row.doc_count

        return {
            "shipments": [
                {
                    "shipment_id": s.id,
                    "shipment_number": s.shipment_number,
                    "supplier_name": s.supplier_name,
                    "consignee_name": s.consignee_name,
                    "incoterm": s.incoterm,
                    "transport_mode": s.transport_mode,
                    "status": s.status,
                    "vendor_docs_count": doc_counts.get(s.id, 0),
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in shipments
            ],
            "total": len(shipments),
        }

    except Exception as e:
        logger.error(f"Failed to list shipments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Step 2: Vendor document validation ------------------------------------

@router.post("/shipments/{shipment_id}/validate-vendor-docs", tags=["pipeline"])
async def validate_vendor_docs(
    shipment_id: str,
    invoice_file: UploadFile = File(...),
    packing_list_file: UploadFile = File(...),
    bill_of_lading_file: Optional[UploadFile] = File(None),
    freight_manifest_file: Optional[UploadFile] = File(None),
    certificate_of_origin_file: Optional[UploadFile] = File(None),
):
    """
    Step 2 — Vendor Document Pre-Validation.

    Accepts the invoice and packing list (required) plus optional freight
    manifest and certificate of origin.  Extracts all files, stores the
    resulting ``APIDocument`` records linked to the shipment, then runs the
    ``vendor_document_validation`` workflow.

    If critical or major discrepancies are found the response includes the
    discrepancies and a ``session_id`` for HITL review via the resume
    endpoint.  When everything passes, returns the final status directly.
    """
    import asyncio
    import tempfile
    from pathlib import Path
    from src.api.services.document_processing_service import get_processing_service
    from src.database.connection import get_session as get_db_session
    from src.database.models.api_document import APIDocument

    try:
        processing_service = get_processing_service(use_database=False)

        # --- Extract all uploaded files concurrently ----------------------
        file_map = {
            "invoice": invoice_file,
            "packing_list": packing_list_file,
        }
        if bill_of_lading_file:
            file_map["bill_of_lading"] = bill_of_lading_file
        if freight_manifest_file:
            file_map["freight_manifest"] = freight_manifest_file
        if certificate_of_origin_file:
            file_map["certificate_of_origin"] = certificate_of_origin_file

        async def _extract_one(doc_type: str, upload: UploadFile):
            content = await upload.read()
            with tempfile.NamedTemporaryFile(
                suffix=Path(upload.filename).suffix, delete=False
            ) as tmp:
                tmp.write(content)
                tmp_path = Path(tmp.name)
            try:
                result = await processing_service.process_document(
                    file_path=tmp_path, document_type=doc_type
                )
            finally:
                tmp_path.unlink(missing_ok=True)
            return doc_type, result

        extraction_results = await asyncio.gather(
            *[_extract_one(dt, f) for dt, f in file_map.items()]
        )

        # --- Persist extracted documents to DB (linked to shipment) -------
        extracted_docs: Dict[str, Dict[str, Any]] = {}
        async with get_db_session() as db:
            for doc_type, result in extraction_results:
                if result.get("status") != "complete":
                    raise HTTPException(
                        status_code=422,
                        detail=f"Extraction failed for {doc_type}: "
                               f"{result.get('metadata', {}).get('error', 'unknown error')}",
                    )
                extracted_docs[doc_type] = {
                    **result.get("fields", {}),
                    "items": result.get("items", []),
                }
                api_doc = APIDocument(
                    document_id=str(uuid4()),
                    document_type=doc_type,
                    shipment_id=shipment_id,
                    fields=result.get("fields", {}),
                    items=result.get("items", []),
                    blocks=result.get("blocks", []),
                    extraction_status="complete",
                    metadata=result.get("metadata", {}),
                )
                db.add(api_doc)
            await db.commit()

        # --- Run validation workflow ---------------------------------------
        from modules.validation_engine.core.session_manager import get_session_manager
        from modules.validation_engine.orchestration import get_validation_workflow

        session_manager = get_session_manager()
        workflow = get_validation_workflow()

        context = await session_manager.create_session(
            use_case="vendor_document_validation",
            documents=extracted_docs,
            primary_document="invoice",
            supporting_documents=[dt for dt in extracted_docs if dt != "invoice"],
            shipment_id=shipment_id,
        )

        final_state = await workflow.run(
            session_id=context.session_id,
            documents=extracted_docs,
            config=context.config,
            primary_document="invoice",
            supporting_documents=context.supporting_documents,
        )

        workflow_status = final_state.get("workflow_status")
        discrepancies   = final_state.get("discrepancies", []) or []
        critical        = final_state.get("critical_discrepancies", []) or []
        validation_results = final_state.get("validation_results", []) or []

        # Derive final_status if the workflow didn't set it
        final_status = final_state.get("final_status") or ""
        if not final_status:
            if final_state.get("all_validations_passed"):
                final_status = "passed"
            elif critical:
                final_status = "failed"
            elif discrepancies:
                final_status = "requires_attention"
            else:
                final_status = "passed"

        # Build summary counts
        total  = len(validation_results)
        passed = sum(1 for r in validation_results if r.get("passed"))
        summary = {
            "total_checks": total,
            "passed_checks": passed,
            "failed_checks": total - passed,
            "total_discrepancies": len(discrepancies),
            "critical": len(critical),
            "major": sum(1 for d in discrepancies if d.get("severity") == "major"),
            "minor": sum(1 for d in discrepancies if d.get("severity") == "minor"),
            "documents_processed": list(extracted_docs.keys()),
            "messages": final_state.get("messages", []),
        }

        # Workflow paused for HITL — return discrepancies for review
        if str(workflow_status) in ("awaiting_user", "WorkflowStatus.AWAITING_USER"):
            return {
                "session_id": str(context.session_id),
                "shipment_id": shipment_id,
                "workflow_status": "awaiting_user",
                "final_status": final_status,
                "summary": summary,
                "discrepancies": discrepancies,
                "critical_discrepancies": critical,
                "validation_results": validation_results,
            }

        return {
            "session_id": str(context.session_id),
            "shipment_id": shipment_id,
            "workflow_status": "completed",
            "final_status": final_status,
            "summary": summary,
            "discrepancies": discrepancies,
            "validation_results": validation_results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vendor doc validation failed for shipment {shipment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- Step 6: BOE cross-verification ----------------------------------------

@router.post("/shipments/{shipment_id}/validate-boe", tags=["pipeline"])
async def validate_boe(
    shipment_id: str,
    boe_file: UploadFile = File(...),
):
    """
    Step 6 — BOE Cross-Verification.

    Accepts only the BOE file.  Retrieves the vendor documents that were
    stored during Step 2 from the database (no re-upload required).

    Validates the BOE against the stored invoice, packing list, and any
    other vendor documents that were uploaded at Step 2.
    """
    import tempfile
    from pathlib import Path
    from src.api.services.document_processing_service import get_processing_service
    from src.database.connection import get_session as get_db_session
    from src.database.repositories.api_document_repository import APIDocumentRepository
    from src.database.models.api_document import APIDocument

    try:
        processing_service = get_processing_service(use_database=False)

        # --- Retrieve stored vendor documents for this shipment -----------
        async with get_db_session() as db:
            repo = APIDocumentRepository(db)
            vendor_doc_types = ("invoice", "packing_list", "freight_manifest", "certificate_of_origin")
            vendor_docs_raw, _ = await repo.list_documents(
                shipment_id=shipment_id,
                extraction_status="complete",
                limit=20,
            )

        vendor_docs = {
            d.document_type: {**d.fields, "items": d.items or []}
            for d in vendor_docs_raw
            if d.document_type in vendor_doc_types
        }

        if "invoice" not in vendor_docs:
            raise HTTPException(
                status_code=422,
                detail=f"Invoice not found for shipment {shipment_id}. Run Step 2 first.",
            )
        if "packing_list" not in vendor_docs:
            raise HTTPException(
                status_code=422,
                detail=f"Packing list not found for shipment {shipment_id}. Run Step 2 first.",
            )

        # --- Extract BOE file ---------------------------------------------
        boe_content = await boe_file.read()
        with tempfile.NamedTemporaryFile(
            suffix=Path(boe_file.filename).suffix, delete=False
        ) as tmp:
            tmp.write(boe_content)
            tmp_path = Path(tmp.name)

        try:
            boe_result = await processing_service.process_document(
                file_path=tmp_path, document_type="bill_of_entry"
            )
        finally:
            tmp_path.unlink(missing_ok=True)

        if boe_result.get("status") != "complete":
            raise HTTPException(
                status_code=422,
                detail=f"BOE extraction failed: "
                       f"{boe_result.get('metadata', {}).get('error', 'unknown error')}",
            )

        # --- Build documents dict and run validation ----------------------
        documents = {
            **vendor_docs,
            "bill_of_entry": {
                **boe_result.get("fields", {}),
                "items": boe_result.get("items", []),
            },
        }

        from modules.validation_engine.core.session_manager import get_session_manager
        from modules.validation_engine.orchestration import get_validation_workflow

        session_manager = get_session_manager()
        workflow = get_validation_workflow()

        context = await session_manager.create_session(
            use_case="boe_validation",
            documents=documents,
            primary_document="bill_of_entry",
            supporting_documents=[dt for dt in documents if dt != "bill_of_entry"],
            shipment_id=shipment_id,
        )

        final_state = await workflow.run(
            session_id=context.session_id,
            documents=documents,
            config=context.config,
            primary_document="bill_of_entry",
            supporting_documents=context.supporting_documents,
        )

        workflow_status = final_state.get("workflow_status")
        discrepancies      = final_state.get("discrepancies", []) or []
        critical           = final_state.get("critical_discrepancies", []) or []
        validation_results = final_state.get("validation_results", []) or []

        # Derive final_status
        final_status = final_state.get("final_status") or ""
        if not final_status:
            if final_state.get("all_validations_passed"):
                final_status = "passed"
            elif critical:
                final_status = "failed"
            elif discrepancies:
                final_status = "requires_attention"
            else:
                final_status = "passed"

        # Build summary counts
        total  = len(validation_results)
        passed = sum(1 for r in validation_results if r.get("passed"))
        summary = {
            "total_checks": total,
            "passed_checks": passed,
            "failed_checks": total - passed,
            "total_discrepancies": len(discrepancies),
            "critical": len(critical),
            "major": sum(1 for d in discrepancies if d.get("severity") == "major"),
            "minor": sum(1 for d in discrepancies if d.get("severity") == "minor"),
            "documents_processed": list(documents.keys()),
            "messages": final_state.get("messages", []),
        }

        # Workflow paused for HITL (awaiting_user or analyzing with discrepancies)
        needs_review = str(workflow_status) in (
            "awaiting_user", "WorkflowStatus.AWAITING_USER",
            "analyzing", "WorkflowStatus.ANALYZING",
        ) or (critical or discrepancies)

        if needs_review and (critical or discrepancies):
            return {
                "session_id": str(context.session_id),
                "shipment_id": shipment_id,
                "workflow_status": "awaiting_user",
                "final_status": final_status,
                "summary": summary,
                "discrepancies": discrepancies,
                "critical_discrepancies": critical,
                "validation_results": validation_results,
            }

        return {
            "session_id": str(context.session_id),
            "shipment_id": shipment_id,
            "workflow_status": "completed",
            "final_status": final_status,
            "summary": summary,
            "discrepancies": discrepancies,
            "validation_results": validation_results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"BOE validation failed for shipment {shipment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- HITL Resume -----------------------------------------------------------

class DiscrepancyConfirmation(BaseModel):
    """Single discrepancy confirmation from the user."""
    discrepancy_id: str
    confirmed: bool
    comment: Optional[str] = None


class ResumeSessionRequest(BaseModel):
    """Request body for resuming a paused validation session."""
    confirmations: List[DiscrepancyConfirmation] = []
    user_input: Optional[Dict[str, Any]] = None


@router.post("/sessions/{session_id}/resume", tags=["pipeline"])
async def resume_validation_session(
    session_id: UUID,
    request: ResumeSessionRequest,
):
    """
    Resume a validation session that is waiting for human input.

    Accepts the user's discrepancy confirmations and any missing field
    values, then continues the LangGraph workflow from the saved
    checkpoint.

    Works for both Step 2 (vendor_document_validation) and Step 6
    (boe_validation) sessions.
    """
    try:
        from modules.validation_engine.orchestration import get_validation_workflow

        workflow = get_validation_workflow()

        user_confirmations = {
            c.discrepancy_id: {"confirmed": c.confirmed, "comment": c.comment}
            for c in request.confirmations
        }

        final_state = await workflow.resume(
            session_id=session_id,
            user_confirmations=user_confirmations,
            user_input=request.user_input,
        )

        return {
            "session_id": str(session_id),
            "workflow_status": str(final_state.get("workflow_status")),
            "final_status": final_state.get("final_status"),
            "message": "Session resumed.",
            "messages": final_state.get("messages", []),
        }

    except Exception as e:
        logger.error(f"Session resume failed for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
