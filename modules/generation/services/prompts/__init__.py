"""
Insights Service Prompts.

LLM prompt templates for banking insights generation.
"""

from modules.generation.services.prompts.insights_prompts import (
    build_risk_assessment_prompt,
    build_product_eligibility_prompt,
    build_recommendations_prompt,
    build_automated_decisions_prompt,
)

__all__ = [
    "build_risk_assessment_prompt",
    "build_product_eligibility_prompt",
    "build_recommendations_prompt",
    "build_automated_decisions_prompt",
]
