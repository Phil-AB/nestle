"""JSON report generator"""

from typing import Dict, Any
import json

from .base_generator import BaseReportGenerator
from ...core.base import ValidationContext
from ..report_models import ReportFormat, ValidationSummaryReport
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class JSONReportGenerator(BaseReportGenerator):
    """
    Generates validation reports in JSON format

    Features:
    - Structured JSON output
    - Complete data preservation
    - Pretty-printed format
    - Nested structure support
    """

    def __init__(self):
        """Initialize JSON report generator"""
        super().__init__()
        self.supported_formats = [ReportFormat.JSON]

    async def _generate_json(
        self, data: Dict[str, Any], context: ValidationContext
    ) -> Dict[str, Any]:
        """
        Generate JSON report

        Args:
            data: Report data
            context: Validation context

        Returns:
            JSON report dictionary
        """
        report = {
            "report_metadata": {
                "report_type": "validation_summary",
                "format": "json",
                "generated_at": data["updated_at"].isoformat(),
                "session_id": data["session_id"],
                "use_case": data["use_case"],
                "version": data["version"]
            },
            "validation_summary": {
                "total_validations": data["total_validations"],
                "passed_validations": data["passed_validations"],
                "failed_validations": data["failed_validations"],
                "accuracy_score": data["accuracy_score"],
                "final_status": data["final_status"]
            },
            "discrepancy_summary": {
                "total_discrepancies": data["total_discrepancies"],
                "by_severity": {
                    "critical": data["critical_count"],
                    "major": data["major_count"],
                    "minor": data["minor_count"],
                    "info": data["info_count"]
                },
                "auto_fixed": data["auto_fixed_count"],
                "user_confirmed": data["user_confirmed_count"]
            },
            "documents": {
                "primary": data["primary_document"],
                "supporting": data["supporting_documents"],
                "all_documents": data["documents"]
            },
            "top_discrepancies": data["top_discrepancies"][:10],
            "validation_results": {
                "by_validator": data["results_by_category"],
                "all_results": data["all_results"]
            },
            "workflow_info": {
                "current_step": data["workflow_steps"][-1] if data["workflow_steps"] else None,
                "completed_steps": data["workflow_steps"]
            },
            "timestamps": {
                "created_at": data["created_at"].isoformat(),
                "updated_at": data["updated_at"].isoformat()
            }
        }

        logger.info(
            f"Generated JSON report for session {data['session_id']}: "
            f"{data['total_discrepancies']} discrepancies, "
            f"{data['accuracy_score']}% accuracy"
        )

        return report

    def to_pretty_json(self, report: Dict[str, Any], indent: int = 2) -> str:
        """
        Convert report to pretty-printed JSON string

        Args:
            report: Report dictionary
            indent: Indentation spaces

        Returns:
            Pretty-printed JSON string
        """
        return json.dumps(report, indent=indent, ensure_ascii=False)


# Singleton instance
_json_generator_instance = None


def get_json_generator() -> JSONReportGenerator:
    """
    Get singleton JSON report generator

    Returns:
        JSONReportGenerator instance
    """
    global _json_generator_instance
    if _json_generator_instance is None:
        _json_generator_instance = JSONReportGenerator()
    return _json_generator_instance
