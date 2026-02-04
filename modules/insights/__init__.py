"""
Universal Insights Module.

100% config-driven, rule-based insights generation system.
Works for any domain: loans, insurance, recruitment, etc.

Quick Start:
    >>> from modules.insights import InsightsService
    >>> service = InsightsService(use_case_id="forms-capital-loan")
    >>> insights = service.generate_insights(raw_extracted_data)
    >>> print(insights["risk_assessment"]["risk_score"])
    72

Architecture:
    - Config-driven: All rules in YAML files (no hardcoding)
    - Rule-based: Fast, deterministic, no LLM dependency
    - Universal: Same engine, different configs for different use cases
    - Modular: Easy to add new use cases

Use Cases:
    - forms-capital-loan: Loan application assessment
    - [Add more use cases by creating config directories]

Components:
    - InsightsService: Main service (public API)
    - ConfigLoader: Loads use-case configs
    - ProfileExtractor: Extracts normalized profiles
    - RuleEngine: Executes business rules
"""

from modules.insights.insights_service import InsightsService
from modules.insights.config_loader import InsightsConfigLoader, load_use_case_config
from modules.insights.profile_extractor import ProfileExtractor
from modules.insights.rule_engine import RuleEngine

__all__ = [
    "InsightsService",
    "InsightsConfigLoader",
    "ProfileExtractor",
    "RuleEngine",
    "load_use_case_config",
]

__version__ = "1.0.0"
