"""
Insights Service Models.

Pydantic models for structured LLM output validation in banking insights generation.
"""

from modules.generation.services.models.insights_models import (
    RiskAssessmentResponse,
    ProductEligibilityResponse,
    RecommendationItem,
    RecommendationsResponse,
    AutomatedDecisionsResponse,
)

__all__ = [
    "RiskAssessmentResponse",
    "ProductEligibilityResponse",
    "RecommendationItem",
    "RecommendationsResponse",
    "AutomatedDecisionsResponse",
]
