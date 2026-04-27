"""
Shared Provider Infrastructure.

This module provides centralized provider implementations for LLM and vision services.
All modules (extraction, population, form_generator) can use these providers
without creating inter-module dependencies.

Key Providers:
- GeminiProvider: Vision + text capabilities using Google Gemini API
- LLMProvider: Factory for LangChain LLM instances (OpenAI, Anthropic, Google)
- BaseProvider: Abstract base class for all providers

Design Principles:
- No inter-module dependencies (modules don't depend on each other)
- No code duplication (single source of truth for provider logic)
- 100% configurable (all settings from config files)
- Production-grade error handling and retries
"""

from shared.providers.base_provider import BaseProvider
from shared.providers.llm_provider import LLMProvider, get_llm
from shared.providers.gemini_provider import GeminiProvider

__all__ = [
    "BaseProvider",
    "LLMProvider",
    "GeminiProvider",
    "get_llm",
]
