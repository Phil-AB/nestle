"""
Banking Insights Configuration Module.

Provides centralized configuration loading and access for insights generation.
"""

from .insights_config import (
    InsightsConfig,
    get_insights_config,
    reload_insights_config,
)

__all__ = [
    "InsightsConfig",
    "get_insights_config",
    "reload_insights_config",
]
