"""
Universal Analytics Module.

100% config-driven, use-case based analytics system.
Works for any domain: loans, insurance, recruitment, healthcare, etc.

Quick Start:
    >>> from modules.analytics import AnalyticsService
    >>> service = AnalyticsService(use_case_id="forms-capital-loan", session=db_session)
    >>> dashboard = await service.get_dashboard()
    >>> print(dashboard["overview"]["total_documents"])
    150

Architecture:
    - Config-driven: All metrics, dimensions, thresholds in YAML (no hardcoding)
    - Use-case based: Same engine, different configs for different domains
    - Universal: Works with any document structure
    - Modular: Easy to add new metrics and aggregations

Use Cases:
    - forms-capital-loan: Loan application analytics
    - [Add more use cases by creating config directories]

Components:
    - AnalyticsService: Main service (public API)
    - ConfigLoader: Loads use-case configs
    - MetricsCalculator: Calculates defined metrics
    - DimensionAggregator: Aggregates by dimensions
"""

from modules.analytics.analytics_service import AnalyticsService
from modules.analytics.config_loader import AnalyticsConfigLoader

__all__ = [
    "AnalyticsService",
    "AnalyticsConfigLoader",
]

__version__ = "1.0.0"
