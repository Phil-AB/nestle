"""Reporting and analytics endpoints."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException

from modules.validation_engine.reporting import (
    get_report_manager,
    get_analytics_engine,
    ReportFormat,
    ReportType,
    ReportRequest,
)
from shared.utils.logger import get_logger

from .validation_models import ValidationReportResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/validation", tags=["validation"])


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

@router.post("/reports/generate")
async def generate_report(
    report_type: ReportType,
    format: ReportFormat = ReportFormat.JSON,
    session_id: Optional[UUID] = None,
    use_case: Optional[str] = None,
    v1_session_id: Optional[UUID] = None,
    v2_session_id: Optional[UUID] = None,
    include_raw_data: bool = False,
    max_discrepancies: Optional[int] = None,
):
    """
    Generate a validation report.

    Supports multiple report types:
    - validation_summary: Comprehensive validation summary
    - discrepancy_detail: Detailed discrepancy report
    - version_comparison: Compare two versions
    - audit_trail: Audit trail with all events
    - executive_summary: High-level executive summary
    - analytics_dashboard: Analytics dashboard data
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
            max_discrepancies=max_discrepancies,
        )

        return await report_manager.generate_report(request)

    except ValueError as e:
        logger.error(f"Invalid report request: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Report generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/sessions/{session_id}/summary")
async def get_validation_summary_report(
    session_id: UUID,
    format: ReportFormat = ReportFormat.JSON,
):
    try:
        report_manager = get_report_manager()
        request = ReportRequest(
            report_type=ReportType.VALIDATION_SUMMARY,
            format=format,
            session_id=session_id,
        )
        return await report_manager.generate_report(request)
    except Exception as e:
        logger.error(f"Failed to generate summary report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/sessions/{session_id}/discrepancies")
async def get_discrepancy_detail_report(session_id: UUID):
    try:
        report_manager = get_report_manager()
        request = ReportRequest(
            report_type=ReportType.DISCREPANCY_DETAIL,
            format=ReportFormat.JSON,
            session_id=session_id,
        )
        return await report_manager.generate_report(request)
    except Exception as e:
        logger.error(f"Failed to generate discrepancy report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/sessions/{session_id}/audit-trail")
async def get_audit_trail_report(session_id: UUID):
    try:
        report_manager = get_report_manager()
        request = ReportRequest(
            report_type=ReportType.AUDIT_TRAIL,
            format=ReportFormat.JSON,
            session_id=session_id,
        )
        return await report_manager.generate_report(request)
    except Exception as e:
        logger.error(f"Failed to generate audit trail: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/sessions/{session_id}/executive-summary")
async def get_executive_summary_report(session_id: UUID):
    try:
        report_manager = get_report_manager()
        request = ReportRequest(
            report_type=ReportType.EXECUTIVE_SUMMARY,
            format=ReportFormat.JSON,
            session_id=session_id,
        )
        return await report_manager.generate_report(request)
    except Exception as e:
        logger.error(f"Failed to generate executive summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reports/comparison")
async def get_version_comparison_report(
    v1_session_id: UUID,
    v2_session_id: UUID,
):
    try:
        report_manager = get_report_manager()
        request = ReportRequest(
            report_type=ReportType.VERSION_COMPARISON,
            format=ReportFormat.JSON,
            v1_session_id=v1_session_id,
            v2_session_id=v2_session_id,
        )
        return await report_manager.generate_report(request)
    except Exception as e:
        logger.error(f"Failed to generate comparison report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@router.get("/analytics/dashboard")
async def get_analytics_dashboard(
    days: int = 30,
    use_case: Optional[str] = None,
):
    try:
        analytics_engine = get_analytics_engine()

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        dashboard = await analytics_engine.get_dashboard_data(
            start_date=start_date,
            end_date=end_date,
            use_case=use_case,
        )
        return dashboard.dict()

    except Exception as e:
        logger.error(f"Failed to generate analytics dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/use-cases/{use_case}")
async def get_use_case_analytics(use_case: str):
    try:
        analytics_engine = get_analytics_engine()
        return await analytics_engine.get_use_case_analytics(use_case)
    except Exception as e:
        logger.error(f"Failed to generate use case analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/discrepancy-trends")
async def get_discrepancy_trends(days: int = 30):
    try:
        analytics_engine = get_analytics_engine()
        return await analytics_engine.get_discrepancy_trends(days=days)
    except Exception as e:
        logger.error(f"Failed to generate discrepancy trends: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Listings (report formats & types)
# ---------------------------------------------------------------------------

@router.get("/reports/formats")
async def list_report_formats():
    return {
        "formats": [
            {"name": "JSON", "value": "json", "description": "Structured JSON output"},
            {"name": "CSV", "value": "csv", "description": "Comma-separated values"},
            {"name": "PDF", "value": "pdf", "description": "PDF document (requires weasyprint)"},
            {"name": "HTML", "value": "html", "description": "HTML document"},
            {"name": "Excel", "value": "excel", "description": "Excel spreadsheet"},
        ]
    }


@router.get("/reports/types")
async def list_report_types():
    return {
        "types": [
            {
                "name": "Validation Summary",
                "value": "validation_summary",
                "description": "Comprehensive validation summary with all metrics",
                "requires": ["session_id"],
            },
            {
                "name": "Discrepancy Detail",
                "value": "discrepancy_detail",
                "description": "Detailed discrepancy breakdown by severity and category",
                "requires": ["session_id"],
            },
            {
                "name": "Version Comparison",
                "value": "version_comparison",
                "description": "Compare two validation versions",
                "requires": ["v1_session_id", "v2_session_id"],
            },
            {
                "name": "Audit Trail",
                "value": "audit_trail",
                "description": "Complete audit trail with all events",
                "requires": ["session_id"],
            },
            {
                "name": "Executive Summary",
                "value": "executive_summary",
                "description": "High-level executive summary",
                "requires": ["session_id"],
            },
            {
                "name": "Analytics Dashboard",
                "value": "analytics_dashboard",
                "description": "Aggregated analytics across sessions",
                "requires": [],
            },
        ]
    }
