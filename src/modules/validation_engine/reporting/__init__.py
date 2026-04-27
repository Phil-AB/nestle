"""Reporting module for validation engine"""

from .report_models import (
    ReportFormat,
    ReportType,
    ValidationSummaryReport,
    DiscrepancyDetailReport,
    VersionComparisonReport,
    AuditTrailReport,
    ExecutiveSummaryReport,
    AnalyticsDashboardData,
    ReportMetadata,
    ReportRequest
)
from .report_manager import ReportManager, get_report_manager
from .generators.json_generator import JSONReportGenerator, get_json_generator
from .generators.csv_generator import CSVReportGenerator, get_csv_generator
from .generators.pdf_generator import PDFReportGenerator, get_pdf_generator
from .analytics.analytics_engine import AnalyticsEngine, get_analytics_engine

__all__ = [
    # Enums
    "ReportFormat",
    "ReportType",

    # Models
    "ValidationSummaryReport",
    "DiscrepancyDetailReport",
    "VersionComparisonReport",
    "AuditTrailReport",
    "ExecutiveSummaryReport",
    "AnalyticsDashboardData",
    "ReportMetadata",
    "ReportRequest",

    # Main Manager
    "ReportManager",
    "get_report_manager",

    # Generators
    "JSONReportGenerator",
    "get_json_generator",
    "CSVReportGenerator",
    "get_csv_generator",
    "PDFReportGenerator",
    "get_pdf_generator",

    # Analytics
    "AnalyticsEngine",
    "get_analytics_engine",
]
