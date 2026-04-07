"""CSV report generator"""

from typing import Dict, Any
import csv
import io

from .base_generator import BaseReportGenerator
from ...core.base import ValidationContext
from ..report_models import ReportFormat
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class CSVReportGenerator(BaseReportGenerator):
    """
    Generates validation reports in CSV format

    Features:
    - Tabular data export
    - Multiple CSV sheets (discrepancies, results, summary)
    - Excel-compatible
    - Easy import to databases/analytics tools
    """

    def __init__(self):
        """Initialize CSV report generator"""
        super().__init__()
        self.supported_formats = [ReportFormat.CSV]

    async def _generate_csv(
        self, data: Dict[str, Any], context: ValidationContext
    ) -> str:
        """
        Generate CSV report

        Creates multiple CSV sections:
        1. Summary section
        2. Discrepancies table
        3. Validation results table

        Args:
            data: Report data
            context: Validation context

        Returns:
            CSV string with multiple sections
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Section 1: Summary
        writer.writerow(["VALIDATION SUMMARY REPORT"])
        writer.writerow([])
        writer.writerow(["Session ID", data["session_id"]])
        writer.writerow(["Use Case", data["use_case"]])
        writer.writerow(["Version", data["version"]])
        writer.writerow(["Created At", data["created_at"].isoformat()])
        writer.writerow(["Final Status", data["final_status"]])
        writer.writerow(["Accuracy Score", f"{data['accuracy_score']}%"])
        writer.writerow([])

        # Validation counts
        writer.writerow(["VALIDATION COUNTS"])
        writer.writerow(["Total Validations", data["total_validations"]])
        writer.writerow(["Passed", data["passed_validations"]])
        writer.writerow(["Failed", data["failed_validations"]])
        writer.writerow([])

        # Discrepancy counts
        writer.writerow(["DISCREPANCY COUNTS"])
        writer.writerow(["Total Discrepancies", data["total_discrepancies"]])
        writer.writerow(["Critical", data["critical_count"]])
        writer.writerow(["Major", data["major_count"]])
        writer.writerow(["Minor", data["minor_count"]])
        writer.writerow(["Info", data["info_count"]])
        writer.writerow(["Auto-Fixed", data["auto_fixed_count"]])
        writer.writerow([])

        # Section 2: Discrepancies Detail
        writer.writerow(["DISCREPANCIES DETAIL"])
        writer.writerow([])
        writer.writerow([
            "Field Name",
            "Severity",
            "Category",
            "Source Document",
            "Target Document",
            "Source Value",
            "Target Value",
            "Discrepancy Type",
            "Likely Cause",
            "Confidence",
            "Auto-Fixed"
        ])

        for disc in data["all_discrepancies"]:
            writer.writerow([
                disc.get("field_name", ""),
                disc.get("severity", ""),
                disc.get("category", ""),
                disc.get("source_document", ""),
                disc.get("target_document", ""),
                disc.get("source_value", ""),
                disc.get("target_value", ""),
                disc.get("discrepancy_type", ""),
                disc.get("likely_cause", ""),
                disc.get("confidence", ""),
                disc.get("auto_fix_applied", False)
            ])

        writer.writerow([])

        # Section 3: Validation Results
        writer.writerow(["VALIDATION RESULTS"])
        writer.writerow([])
        writer.writerow([
            "Validator Name",
            "Field Name",
            "Passed",
            "Confidence",
            "Message"
        ])

        for result in data["all_results"]:
            writer.writerow([
                result.get("validator_name", ""),
                result.get("field_name", ""),
                "Yes" if result.get("passed") else "No",
                result.get("confidence", ""),
                result.get("message", "")
            ])

        writer.writerow([])

        # Section 4: Validation by Category
        writer.writerow(["VALIDATION BY CATEGORY"])
        writer.writerow([])
        writer.writerow(["Validator", "Total", "Passed", "Failed"])

        for validator, stats in data["results_by_category"].items():
            writer.writerow([
                validator,
                stats["total"],
                stats["passed"],
                stats["failed"]
            ])

        csv_content = output.getvalue()
        output.close()

        logger.info(
            f"Generated CSV report for session {data['session_id']}: "
            f"{len(data['all_discrepancies'])} discrepancies, "
            f"{len(data['all_results'])} results"
        )

        return csv_content


# Singleton instance
_csv_generator_instance = None


def get_csv_generator() -> CSVReportGenerator:
    """
    Get singleton CSV report generator

    Returns:
        CSVReportGenerator instance
    """
    global _csv_generator_instance
    if _csv_generator_instance is None:
        _csv_generator_instance = CSVReportGenerator()
    return _csv_generator_instance
