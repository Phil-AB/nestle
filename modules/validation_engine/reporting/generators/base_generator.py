"""Base report generator"""

from typing import Dict, Any, Union
from abc import ABC, abstractmethod

from ...core.base import IReportGenerator, ValidationContext
from ..report_models import ReportFormat, ValidationSummaryReport
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class BaseReportGenerator(IReportGenerator):
    """
    Base report generator with common functionality

    All format-specific generators inherit from this class
    """

    def __init__(self):
        """Initialize base report generator"""
        self.supported_formats = []
        logger.info(f"{self.__class__.__name__} initialized")

    async def generate(
        self,
        context: ValidationContext,
        format: str
    ) -> Union[str, bytes, Dict[str, Any]]:
        """
        Generate validation report

        Args:
            context: Validation context with results
            format: Output format

        Returns:
            Report in requested format

        Raises:
            ValueError: If format not supported
        """
        if format not in self.supported_formats:
            raise ValueError(
                f"Format '{format}' not supported. "
                f"Supported: {', '.join(self.supported_formats)}"
            )

        logger.info(
            f"Generating {format} report for session {context.session_id}"
        )

        # Build report data
        report_data = await self._build_report_data(context)

        # Format-specific generation
        if format == ReportFormat.JSON:
            return await self._generate_json(report_data, context)
        elif format == ReportFormat.CSV:
            return await self._generate_csv(report_data, context)
        elif format == ReportFormat.PDF:
            return await self._generate_pdf(report_data, context)
        elif format == ReportFormat.HTML:
            return await self._generate_html(report_data, context)
        elif format == ReportFormat.EXCEL:
            return await self._generate_excel(report_data, context)
        else:
            raise ValueError(f"Unknown format: {format}")

    async def _build_report_data(
        self, context: ValidationContext
    ) -> Dict[str, Any]:
        """
        Build common report data structure

        Args:
            context: Validation context

        Returns:
            Report data dictionary
        """
        # Calculate summary statistics
        total_validations = len(context.validation_results)
        passed_validations = sum(
            1 for r in context.validation_results if r.passed
        )
        failed_validations = total_validations - passed_validations

        accuracy = 0.0
        if total_validations > 0:
            accuracy = round((passed_validations / total_validations) * 100, 2)

        # Group discrepancies by severity
        severity_counts = {"critical": 0, "major": 0, "minor": 0, "info": 0}
        for disc in context.discrepancies:
            severity = disc.severity.lower()
            if severity in severity_counts:
                severity_counts[severity] += 1

        # Determine final status
        if severity_counts["critical"] > 0:
            final_status = "failed"
        elif severity_counts["major"] > 0:
            final_status = "partial"
        elif severity_counts["minor"] > 0:
            final_status = "warning"
        else:
            final_status = "passed"

        # Group results by category
        results_by_category = {}
        for result in context.validation_results:
            validator = result.validator_name
            if validator not in results_by_category:
                results_by_category[validator] = {
                    "total": 0,
                    "passed": 0,
                    "failed": 0
                }

            results_by_category[validator]["total"] += 1
            if result.passed:
                results_by_category[validator]["passed"] += 1
            else:
                results_by_category[validator]["failed"] += 1

        # Get top discrepancies (sorted by severity)
        severity_order = {"critical": 4, "major": 3, "minor": 2, "info": 1}
        top_discrepancies = sorted(
            context.discrepancies,
            key=lambda d: (
                -severity_order.get(d.severity.lower(), 0),
                -d.confidence
            )
        )[:10]

        # Count auto-fixes
        auto_fixed_count = sum(
            1 for disc in context.discrepancies
            if getattr(disc, 'auto_fix_applied', False)
        )

        return {
            "session_id": str(context.session_id),
            "use_case": context.use_case,
            "version": context.version,
            "created_at": context.created_at,
            "updated_at": context.updated_at,
            "total_validations": total_validations,
            "passed_validations": passed_validations,
            "failed_validations": failed_validations,
            "accuracy_score": accuracy,
            "final_status": final_status,
            "total_discrepancies": len(context.discrepancies),
            "critical_count": severity_counts["critical"],
            "major_count": severity_counts["major"],
            "minor_count": severity_counts["minor"],
            "info_count": severity_counts["info"],
            "auto_fixed_count": auto_fixed_count,
            "user_confirmed_count": len(context.user_confirmations),
            "documents": {
                name: "document" for name in context.documents.keys()
            },
            "primary_document": context.primary_document,
            "supporting_documents": context.supporting_documents,
            "top_discrepancies": [d.dict() for d in top_discrepancies],
            "results_by_category": results_by_category,
            "workflow_steps": [context.current_step],
            "all_results": [r.dict() for r in context.validation_results],
            "all_discrepancies": [d.dict() for d in context.discrepancies]
        }

    # Format-specific methods (to be overridden by subclasses)

    async def _generate_json(
        self, data: Dict[str, Any], context: ValidationContext
    ) -> Dict[str, Any]:
        """Generate JSON report"""
        raise NotImplementedError

    async def _generate_csv(
        self, data: Dict[str, Any], context: ValidationContext
    ) -> str:
        """Generate CSV report"""
        raise NotImplementedError

    async def _generate_pdf(
        self, data: Dict[str, Any], context: ValidationContext
    ) -> bytes:
        """Generate PDF report"""
        raise NotImplementedError

    async def _generate_html(
        self, data: Dict[str, Any], context: ValidationContext
    ) -> str:
        """Generate HTML report"""
        raise NotImplementedError

    async def _generate_excel(
        self, data: Dict[str, Any], context: ValidationContext
    ) -> bytes:
        """Generate Excel report"""
        raise NotImplementedError
