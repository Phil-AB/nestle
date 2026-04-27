"""Core validation engine components"""

from .base import (
    ValidationResult,
    Discrepancy,
    ValidationContext,
    ValidationResultSummary,
    IValidator,
    INormalizer,
    IDiscrepancyClassifier,
    IAutoFixer,
    IVersionComparator,
    IReportGenerator
)

from .engine import ValidationEngine, get_validation_engine
from .session_manager import SessionManager, get_session_manager
from .config_loader import ValidationConfigLoader, get_config_loader
from .result_aggregator import ResultAggregator

__all__ = [
    # Base classes and interfaces
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
    # Engine
    "ValidationEngine",
    "get_validation_engine",
    # Session management
    "SessionManager",
    "get_session_manager",
    # Configuration
    "ValidationConfigLoader",
    "get_config_loader",
    # Result aggregation
    "ResultAggregator",
]
