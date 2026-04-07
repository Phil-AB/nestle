"""
Universal Validation Engine

A standalone, config-driven validation engine for document validation.

Features:
- 100% config-driven (no hardcoded validation logic)
- Universal (works for any validation use case)
- Hybrid validation (rule-based + AI-based + statistical)
- Multi-step orchestration with LangGraph
- Version control and comparison
- Pluggable validators with auto-registration
- Production-grade and scalable

Usage:
    from modules.validation_engine import get_validation_engine

    engine = get_validation_engine()

    # Create validation session
    context = await engine.create_validation_session(
        use_case="boe_validation",
        documents={
            "bill_of_entry": {...},
            "invoice": {...},
            "packing_list": {...}
        }
    )

    # Run validation
    summary = await engine.run_validation_workflow(context.session_id)

    # Get report
    report = await engine.get_validation_report(context.session_id)
"""

from .core import (
    # Main engine
    ValidationEngine,
    get_validation_engine,

    # Session management
    SessionManager,
    get_session_manager,

    # Configuration
    ValidationConfigLoader,
    get_config_loader,

    # Base classes
    ValidationResult,
    Discrepancy,
    ValidationContext,
    ValidationResultSummary,
    IValidator,
    INormalizer,
    IDiscrepancyClassifier,
    IAutoFixer,
    IVersionComparator,
    IReportGenerator,

    # Result aggregation
    ResultAggregator,
)

from .validators import (
    ValidatorRegistry,
    get_validator_registry,
)

from .version_control import (
    # Version control
    VersionManager,
    get_version_manager,
    DeltaAnalyzer,
    get_delta_analyzer,
    RevalidationEngine,
    get_revalidation_engine,

    # Version models
    VersionStatus,
    ChangeType,
    VersionMetadata,
    DiscrepancyChange,
    VersionComparison,
    RevalidationRequest,
    RevalidationResult,
)

from .reporting import (
    # Report manager
    ReportManager,
    get_report_manager,

    # Analytics
    AnalyticsEngine,
    get_analytics_engine,

    # Report models
    ReportFormat,
    ReportType,
    ReportRequest,
    ReportMetadata,
    ValidationSummaryReport,
    DiscrepancyDetailReport,
    VersionComparisonReport,
    AuditTrailReport,
    ExecutiveSummaryReport,
    AnalyticsDashboardData,

    # Generators
    get_json_generator,
    get_csv_generator,
    get_pdf_generator,
)

from .utils import (
    # Constants
    ValidationStatus,
    SessionType,
    FinalStatus,
    ValidatorType,
    Severity,
    DiscrepancyType,
    DiscrepancyCategory,
    ResolutionStatus,
    ComparisonStatus,
    WorkflowStep,
    ValidationMode,
    NormalizationStrategy,
    MatchType,
    DocumentRole,
    ConfidenceThreshold,
    ToleranceType,
    Operator,
    ExportFormat,
    LikelyCause,
    AutoFixType,

    # Exceptions
    ValidationEngineException,
    ValidatorNotFoundException,
    ValidatorRegistrationException,
    ValidationConfigException,
    UseCaseNotFoundException,
    SessionNotFoundException,
    ValidationWorkflowException,
    NormalizationException,
    DiscrepancyClassificationException,
    VersionControlException,
    AutoFixException,
)

__version__ = "1.0.0"

__all__ = [
    # Main engine
    "ValidationEngine",
    "get_validation_engine",

    # Session management
    "SessionManager",
    "get_session_manager",

    # Configuration
    "ValidationConfigLoader",
    "get_config_loader",

    # Validators
    "ValidatorRegistry",
    "get_validator_registry",

    # Version control
    "VersionManager",
    "get_version_manager",
    "DeltaAnalyzer",
    "get_delta_analyzer",
    "RevalidationEngine",
    "get_revalidation_engine",
    "VersionStatus",
    "ChangeType",
    "VersionMetadata",
    "DiscrepancyChange",
    "VersionComparison",
    "RevalidationRequest",
    "RevalidationResult",

    # Reporting and Analytics
    "ReportManager",
    "get_report_manager",
    "AnalyticsEngine",
    "get_analytics_engine",
    "ReportFormat",
    "ReportType",
    "ReportRequest",
    "ReportMetadata",
    "ValidationSummaryReport",
    "DiscrepancyDetailReport",
    "VersionComparisonReport",
    "AuditTrailReport",
    "ExecutiveSummaryReport",
    "AnalyticsDashboardData",
    "get_json_generator",
    "get_csv_generator",
    "get_pdf_generator",

    # Base classes
    "ValidationResult",
    "Discrepancy",
    "ValidationContext",
    "ValidationResultSummary",
    "IValidator",
    "INormalizer",
    "IDiscrepancyClassifier",
    "IAutoFixer",
    "IVersionComparator",
    "IReportGenerator",

    # Result aggregation
    "ResultAggregator",

    # Constants
    "ValidationStatus",
    "SessionType",
    "FinalStatus",
    "ValidatorType",
    "Severity",
    "DiscrepancyType",
    "DiscrepancyCategory",
    "ResolutionStatus",
    "ComparisonStatus",
    "WorkflowStep",
    "ValidationMode",
    "NormalizationStrategy",
    "MatchType",
    "DocumentRole",
    "ConfidenceThreshold",
    "ToleranceType",
    "Operator",
    "ExportFormat",
    "LikelyCause",
    "AutoFixType",

    # Exceptions
    "ValidationEngineException",
    "ValidatorNotFoundException",
    "ValidatorRegistrationException",
    "ValidationConfigException",
    "UseCaseNotFoundException",
    "SessionNotFoundException",
    "ValidationWorkflowException",
    "NormalizationException",
    "DiscrepancyClassificationException",
    "VersionControlException",
    "AutoFixException",
]
