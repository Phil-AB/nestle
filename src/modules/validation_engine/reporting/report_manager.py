"""Report manager - unified interface for report generation"""

from typing import Dict, Any, Union, Optional
from uuid import UUID

from .generators.json_generator import get_json_generator
from .generators.csv_generator import get_csv_generator
from .generators.pdf_generator import get_pdf_generator
from .analytics.analytics_engine import get_analytics_engine
from .report_models import (
    ReportFormat, ReportType, ReportRequest, ReportMetadata
)
from ..core.session_manager import get_session_manager
from ..version_control import (
    get_version_manager,
    get_delta_analyzer,
    get_revalidation_engine
)
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class ReportManager:
    """
    Unified report manager

    Responsibilities:
    - Route report requests to appropriate generators
    - Manage report generation lifecycle
    - Cache generated reports
    - Track report metadata
    """

    def __init__(self):
        """Initialize report manager"""
        self.session_manager = get_session_manager()
        self.version_manager = get_version_manager()
        self.delta_analyzer = get_delta_analyzer()
        self.analytics_engine = get_analytics_engine()

        # Generators
        self.json_generator = get_json_generator()
        self.csv_generator = get_csv_generator()
        self.pdf_generator = get_pdf_generator()

        # Report cache (in-memory for now)
        self._report_cache: Dict[str, Any] = {}

        logger.info("ReportManager initialized")

    async def generate_report(
        self, request: ReportRequest
    ) -> Dict[str, Any]:
        """
        Generate report based on request

        Args:
            request: Report generation request

        Returns:
            Report data with metadata

        Raises:
            ValueError: If invalid request parameters
        """
        logger.info(
            f"Generating {request.report_type} report in {request.format} format"
        )

        # Route to appropriate report generator
        if request.report_type == ReportType.VALIDATION_SUMMARY:
            report_data = await self._generate_validation_summary(request)
        elif request.report_type == ReportType.DISCREPANCY_DETAIL:
            report_data = await self._generate_discrepancy_detail(request)
        elif request.report_type == ReportType.VERSION_COMPARISON:
            report_data = await self._generate_version_comparison(request)
        elif request.report_type == ReportType.AUDIT_TRAIL:
            report_data = await self._generate_audit_trail(request)
        elif request.report_type == ReportType.EXECUTIVE_SUMMARY:
            report_data = await self._generate_executive_summary(request)
        elif request.report_type == ReportType.ANALYTICS_DASHBOARD:
            report_data = await self._generate_analytics_dashboard(request)
        else:
            raise ValueError(f"Unknown report type: {request.report_type}")

        # Add metadata
        metadata = self._create_metadata(request, report_data)

        return {
            "metadata": metadata.dict(),
            "data": report_data
        }

    async def _generate_validation_summary(
        self, request: ReportRequest
    ) -> Union[str, bytes, Dict[str, Any]]:
        """Generate validation summary report"""
        if request.session_id is None:
            raise ValueError("session_id required for validation summary")

        # Get session context
        context = self.session_manager.get_session(request.session_id)

        # Generate in requested format
        if request.format == ReportFormat.JSON:
            return await self.json_generator.generate(context, ReportFormat.JSON)
        elif request.format == ReportFormat.CSV:
            return await self.csv_generator.generate(context, ReportFormat.CSV)
        elif request.format == ReportFormat.PDF:
            return await self.pdf_generator.generate(context, ReportFormat.PDF)
        else:
            raise ValueError(f"Format {request.format} not supported")

    async def _generate_discrepancy_detail(
        self, request: ReportRequest
    ) -> Dict[str, Any]:
        """Generate detailed discrepancy report"""
        if request.session_id is None:
            raise ValueError("session_id required for discrepancy detail")

        context = self.session_manager.get_session(request.session_id)

        # Group discrepancies
        critical = []
        major = []
        minor = []
        info = []

        for disc in context.discrepancies:
            disc_dict = disc.dict()
            severity = disc.severity.lower()

            if severity == "critical":
                critical.append(disc_dict)
            elif severity == "major":
                major.append(disc_dict)
            elif severity == "minor":
                minor.append(disc_dict)
            elif severity == "info":
                info.append(disc_dict)

        # Group by category
        by_category = {}
        for disc in context.discrepancies:
            category = disc.category
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(disc.dict())

        # Group by document
        by_document = {}
        for disc in context.discrepancies:
            doc = disc.source_document
            if doc not in by_document:
                by_document[doc] = []
            by_document[doc].append(disc.dict())

        # Auto-fixed vs manual review
        auto_fixed = [
            d.dict() for d in context.discrepancies
            if getattr(d, 'auto_fix_applied', False)
        ]
        manual_review = [
            d.dict() for d in context.discrepancies
            if not getattr(d, 'auto_fix_applied', False)
        ]

        # Calculate statistics
        total = len(context.discrepancies)
        resolution_rate = (len(auto_fixed) / total * 100) if total > 0 else 0.0

        confidences = [d.confidence for d in context.discrepancies]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return {
            "session_id": str(request.session_id),
            "use_case": context.use_case,
            "generated_at": context.updated_at.isoformat(),
            "critical_discrepancies": critical,
            "major_discrepancies": major,
            "minor_discrepancies": minor,
            "info_discrepancies": info,
            "by_category": by_category,
            "by_document": by_document,
            "auto_fixed": auto_fixed,
            "manual_review_required": manual_review,
            "total_discrepancies": total,
            "resolution_rate": round(resolution_rate, 2),
            "avg_confidence": round(avg_confidence, 2)
        }

    async def _generate_version_comparison(
        self, request: ReportRequest
    ) -> Dict[str, Any]:
        """Generate version comparison report"""
        if request.v1_session_id is None or request.v2_session_id is None:
            raise ValueError(
                "Both v1_session_id and v2_session_id required for comparison"
            )

        # Get contexts
        v1_context = self.session_manager.get_session(request.v1_session_id)
        v2_context = self.session_manager.get_session(request.v2_session_id)

        # Compare versions
        comparison = await self.delta_analyzer.compare(v1_context, v2_context)

        # Get change summary
        summary = await self.delta_analyzer.get_change_summary(comparison)

        # Build report
        return {
            "v1_session_id": str(request.v1_session_id),
            "v1_version": v1_context.version,
            "v2_session_id": str(request.v2_session_id),
            "v2_version": v2_context.version,
            "compared_at": comparison.compared_at.isoformat(),
            "improvement_rate": comparison.improvement_rate,
            "regression_rate": comparison.regression_rate,
            "v1_accuracy": comparison.v1_accuracy,
            "v2_accuracy": comparison.v2_accuracy,
            "accuracy_delta": comparison.accuracy_delta,
            "fixed_discrepancies": [
                c.dict() for c in comparison.changes
                if c.change_type == "fixed"
            ],
            "new_discrepancies": [
                c.dict() for c in comparison.changes
                if c.change_type == "new"
            ],
            "persistent_discrepancies": [
                c.dict() for c in comparison.changes
                if c.change_type == "persistent"
            ],
            "improved_severity": [
                c.dict() for c in comparison.changes
                if c.change_type == "improved"
            ],
            "worsened_severity": [
                c.dict() for c in comparison.changes
                if c.change_type == "worsened"
            ],
            "assessment": summary["overall_assessment"],
            "recommendations": summary["recommendations"],
            "critical_changes": summary["critical_changes"],
            "v1_summary": self._build_session_summary(v1_context),
            "v2_summary": self._build_session_summary(v2_context)
        }

    async def _generate_audit_trail(
        self, request: ReportRequest
    ) -> Dict[str, Any]:
        """Generate audit trail report"""
        if request.session_id is None:
            raise ValueError("session_id required for audit trail")

        context = self.session_manager.get_session(request.session_id)

        # Get version history
        version_history = await self.version_manager.get_version_history(
            request.session_id
        )

        return {
            "session_id": str(request.session_id),
            "use_case": context.use_case,
            "generated_at": context.updated_at.isoformat(),
            "created_at": context.created_at.isoformat(),
            "updated_at": context.updated_at.isoformat(),
            "created_by": None,  # Would come from auth context
            "workflow_events": [
                {"step": context.current_step, "timestamp": context.updated_at.isoformat()}
            ],
            "validation_steps": [
                {
                    "validator": r.validator_name,
                    "field": r.field_name,
                    "passed": r.passed,
                    "timestamp": context.updated_at.isoformat()
                }
                for r in context.validation_results
            ],
            "user_inputs": [
                {"field": k, "value": v, "timestamp": context.updated_at.isoformat()}
                for k, v in context.user_provided_data.items()
            ],
            "user_confirmations": [
                {"discrepancy_id": k, "confirmed": v, "timestamp": context.updated_at.isoformat()}
                for k, v in context.user_confirmations.items()
            ],
            "version_history": [v.dict() for v in version_history],
            "use_case_config": context.config,
            "tolerance_overrides": context.tolerance_overrides,
            "total_events": (
                len(context.validation_results) +
                len(context.user_provided_data) +
                len(context.user_confirmations)
            ),
            "audit_period_start": context.created_at.isoformat(),
            "audit_period_end": context.updated_at.isoformat()
        }

    async def _generate_executive_summary(
        self, request: ReportRequest
    ) -> Dict[str, Any]:
        """Generate executive summary report"""
        if request.session_id is None:
            raise ValueError("session_id required for executive summary")

        context = self.session_manager.get_session(request.session_id)

        # Calculate key metrics
        total_validations = len(context.validation_results)
        passed = sum(1 for r in context.validation_results if r.passed)
        accuracy = (passed / total_validations * 100) if total_validations > 0 else 0.0

        # Determine status
        severity_counts = {"critical": 0, "major": 0, "minor": 0}
        for disc in context.discrepancies:
            severity = disc.severity.lower()
            if severity in severity_counts:
                severity_counts[severity] += 1

        if severity_counts["critical"] > 0:
            final_status = "failed"
            status_color = "red"
            status_message = "Critical issues detected - immediate action required"
        elif severity_counts["major"] > 0:
            final_status = "partial"
            status_color = "yellow"
            status_message = "Major issues found - review recommended"
        elif severity_counts["minor"] > 0:
            final_status = "warning"
            status_color = "yellow"
            status_message = "Minor issues detected - monitoring advised"
        else:
            final_status = "passed"
            status_color = "green"
            status_message = "All validations passed successfully"

        # Key findings
        key_findings = []
        if severity_counts["critical"] > 0:
            key_findings.append(
                f"{severity_counts['critical']} critical discrepancies require immediate attention"
            )
        if severity_counts["major"] > 0:
            key_findings.append(
                f"{severity_counts['major']} major discrepancies need resolution"
            )
        if accuracy < 70:
            key_findings.append(
                f"Low accuracy ({accuracy:.1f}%) indicates significant data quality issues"
            )
        if not key_findings:
            key_findings.append("No significant issues detected")

        # Recommendations
        recommendations = []
        if severity_counts["critical"] > 0:
            recommendations.append("Resolve critical discrepancies before proceeding")
        if severity_counts["major"] >= 3:
            recommendations.append("Review and address major discrepancies")
        if accuracy < 90:
            recommendations.append("Consider revalidation after data corrections")

        return {
            "session_id": str(request.session_id),
            "use_case": context.use_case,
            "generated_at": context.updated_at.isoformat(),
            "final_status": final_status,
            "accuracy_score": round(accuracy, 2),
            "total_discrepancies": len(context.discrepancies),
            "critical_issues": severity_counts["critical"],
            "status_color": status_color,
            "status_message": status_message,
            "key_findings": key_findings[:5],
            "recommendations": recommendations[:5],
            "documents_validated": len(context.documents),
            "validation_steps_completed": len(context.validation_results),
            "created_at": context.created_at.isoformat(),
            "completed_at": context.updated_at.isoformat(),
            "processing_time": str(context.updated_at - context.created_at),
            "previous_version": None,
            "improvement_summary": None
        }

    async def _generate_analytics_dashboard(
        self, request: ReportRequest
    ) -> Dict[str, Any]:
        """Generate analytics dashboard data"""
        dashboard = await self.analytics_engine.get_dashboard_data(
            start_date=request.start_date,
            end_date=request.end_date,
            use_case=request.use_case
        )

        return dashboard.dict()

    def _build_session_summary(self, context) -> Dict[str, Any]:
        """Build session summary for comparison"""
        total = len(context.validation_results)
        passed = sum(1 for r in context.validation_results if r.passed)
        accuracy = (passed / total * 100) if total > 0 else 0.0

        return {
            "session_id": str(context.session_id),
            "version": context.version,
            "accuracy": round(accuracy, 2),
            "total_discrepancies": len(context.discrepancies),
            "created_at": context.created_at.isoformat()
        }

    def _create_metadata(
        self, request: ReportRequest, report_data: Any
    ) -> ReportMetadata:
        """Create report metadata"""
        from uuid import uuid4
        from datetime import datetime

        return ReportMetadata(
            report_id=str(uuid4()),
            report_type=request.report_type,
            report_format=request.format,
            generated_at=datetime.utcnow(),
            session_id=str(request.session_id) if request.session_id else None,
            use_case=request.use_case,
            parameters=request.dict(exclude_none=True)
        )


# Singleton instance
_report_manager_instance: Optional[ReportManager] = None


def get_report_manager() -> ReportManager:
    """
    Get singleton report manager instance

    Returns:
        ReportManager instance
    """
    global _report_manager_instance
    if _report_manager_instance is None:
        _report_manager_instance = ReportManager()
    return _report_manager_instance
