"""Report data models"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from enum import Enum


class ReportFormat(str, Enum):
    """Report format enumeration"""
    JSON = "json"
    PDF = "pdf"
    CSV = "csv"
    HTML = "html"
    EXCEL = "excel"


class ReportType(str, Enum):
    """Report type enumeration"""
    VALIDATION_SUMMARY = "validation_summary"
    DISCREPANCY_DETAIL = "discrepancy_detail"
    VERSION_COMPARISON = "version_comparison"
    AUDIT_TRAIL = "audit_trail"
    EXECUTIVE_SUMMARY = "executive_summary"
    ANALYTICS_DASHBOARD = "analytics_dashboard"


class ValidationSummaryReport(BaseModel):
    """Comprehensive validation summary report"""

    # Session information
    session_id: str
    use_case: str
    version: int
    created_at: datetime
    updated_at: datetime

    # Validation overview
    total_validations: int
    passed_validations: int
    failed_validations: int
    accuracy_score: float
    final_status: str

    # Discrepancy summary
    total_discrepancies: int
    critical_count: int
    major_count: int
    minor_count: int
    info_count: int

    # Auto-fix summary
    auto_fixed_count: int
    user_confirmed_count: int

    # Document information
    documents: Dict[str, str]  # document_name: type
    primary_document: Optional[str]
    supporting_documents: List[str]

    # Top discrepancies
    top_discrepancies: List[Dict[str, Any]]

    # Validation results by category
    results_by_category: Dict[str, Dict[str, Any]]

    # Processing metrics
    processing_time_ms: Optional[int] = None
    workflow_steps: List[str] = Field(default_factory=list)

    class Config:
        use_enum_values = True


class DiscrepancyDetailReport(BaseModel):
    """Detailed discrepancy report"""

    session_id: str
    use_case: str
    generated_at: datetime

    # Discrepancies grouped by severity
    critical_discrepancies: List[Dict[str, Any]]
    major_discrepancies: List[Dict[str, Any]]
    minor_discrepancies: List[Dict[str, Any]]
    info_discrepancies: List[Dict[str, Any]]

    # Discrepancies grouped by category
    by_category: Dict[str, List[Dict[str, Any]]]

    # Discrepancies grouped by document
    by_document: Dict[str, List[Dict[str, Any]]]

    # Auto-fix details
    auto_fixed: List[Dict[str, Any]]
    manual_review_required: List[Dict[str, Any]]

    # Statistics
    total_discrepancies: int
    resolution_rate: float  # % of auto-fixed
    avg_confidence: float

    class Config:
        use_enum_values = True


class VersionComparisonReport(BaseModel):
    """Version comparison report"""

    v1_session_id: str
    v1_version: int
    v2_session_id: str
    v2_version: int
    compared_at: datetime

    # Summary metrics
    improvement_rate: float
    regression_rate: float
    v1_accuracy: float
    v2_accuracy: float
    accuracy_delta: float

    # Change breakdown
    fixed_discrepancies: List[Dict[str, Any]]
    new_discrepancies: List[Dict[str, Any]]
    persistent_discrepancies: List[Dict[str, Any]]
    improved_severity: List[Dict[str, Any]]
    worsened_severity: List[Dict[str, Any]]

    # Overall assessment
    assessment: str
    recommendations: List[str]
    critical_changes: List[Dict[str, Any]]

    # Side-by-side comparison
    v1_summary: Dict[str, Any]
    v2_summary: Dict[str, Any]

    class Config:
        use_enum_values = True


class AuditTrailReport(BaseModel):
    """Audit trail report"""

    session_id: str
    use_case: str
    generated_at: datetime

    # Session lifecycle
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]

    # Validation timeline
    workflow_events: List[Dict[str, Any]]
    validation_steps: List[Dict[str, Any]]

    # User interactions
    user_inputs: List[Dict[str, Any]]
    user_confirmations: List[Dict[str, Any]]

    # Version history
    version_history: List[Dict[str, Any]]

    # Configuration
    use_case_config: Dict[str, Any]
    tolerance_overrides: Dict[str, float]

    # Audit metadata
    total_events: int
    audit_period_start: datetime
    audit_period_end: datetime

    class Config:
        use_enum_values = True


class ExecutiveSummaryReport(BaseModel):
    """Executive summary report (high-level overview)"""

    session_id: str
    use_case: str
    generated_at: datetime

    # Key metrics
    final_status: str
    accuracy_score: float
    total_discrepancies: int
    critical_issues: int

    # Status indicator
    status_color: str  # green, yellow, red
    status_message: str

    # Key findings (top 3-5)
    key_findings: List[str]

    # Recommendations (top 3-5)
    recommendations: List[str]

    # Document summary
    documents_validated: int
    validation_steps_completed: int

    # Time metrics
    created_at: datetime
    completed_at: Optional[datetime]
    processing_time: Optional[str]  # Human-readable

    # Comparison with previous (if available)
    previous_version: Optional[Dict[str, Any]]
    improvement_summary: Optional[str]

    class Config:
        use_enum_values = True


class AnalyticsDashboardData(BaseModel):
    """Data for analytics dashboard"""

    # Time period
    period_start: datetime
    period_end: datetime
    generated_at: datetime

    # Overall metrics
    total_sessions: int
    total_validations: int
    avg_accuracy: float
    avg_processing_time_ms: float

    # Status distribution
    status_distribution: Dict[str, int]  # passed, partial, failed

    # Discrepancy trends
    discrepancy_trends: Dict[str, int]  # by severity
    discrepancy_by_category: Dict[str, int]

    # Top issues
    most_common_discrepancies: List[Dict[str, Any]]
    recurring_issues: List[Dict[str, Any]]

    # Use case breakdown
    sessions_by_use_case: Dict[str, int]
    accuracy_by_use_case: Dict[str, float]

    # Version analytics
    revalidation_rate: float  # % of sessions revalidated
    avg_improvement_rate: float

    # Time series data
    daily_sessions: List[Dict[str, Any]]
    daily_accuracy: List[Dict[str, Any]]

    class Config:
        use_enum_values = True


class ReportMetadata(BaseModel):
    """Report metadata"""

    report_id: str
    report_type: ReportType
    report_format: ReportFormat
    generated_at: datetime
    generated_by: Optional[str]

    # Session information
    session_id: Optional[str]
    use_case: Optional[str]

    # Report parameters
    parameters: Dict[str, Any] = Field(default_factory=dict)

    # File information (for exports)
    filename: Optional[str]
    file_size_bytes: Optional[int]
    file_path: Optional[str]

    class Config:
        use_enum_values = True


class ReportRequest(BaseModel):
    """Report generation request"""

    report_type: ReportType
    format: ReportFormat = ReportFormat.JSON

    # Session filters
    session_id: Optional[UUID] = None
    use_case: Optional[str] = None

    # Time filters
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

    # Comparison (for version comparison reports)
    v1_session_id: Optional[UUID] = None
    v2_session_id: Optional[UUID] = None

    # Options
    include_raw_data: bool = False
    include_metadata: bool = True
    max_discrepancies: Optional[int] = None  # Limit discrepancies in report

    # Export options
    compress: bool = False  # Compress output (zip)
    watermark: Optional[str] = None  # PDF watermark

    class Config:
        use_enum_values = True
