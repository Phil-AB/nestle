"""
Base Population Agent.

Abstract base class for PDF form population agents.
Mirrors the pattern from extraction module's BaseExtractor.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

from langchain_core.language_models import BaseChatModel
from shared.providers import get_llm
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class PopulationTask:
    """
    Task specification for form population.

    Attributes:
        form_id: Form template identifier
        document_ids: List of document IDs to extract data from
        template_path: Path to blank PDF template
        options: Additional options (merge_strategy, flatten_form, etc.)
    """
    form_id: str
    document_ids: List[str]
    template_path: str
    options: Optional[Dict[str, Any]] = None


@dataclass
class PopulationResult:
    """
    Result from population agent.

    Attributes:
        success: Whether population succeeded
        output_path: Path to populated PDF
        field_mappings: Dictionary of {pdf_field: value}
        confidence: Overall confidence score
        metadata: Additional metadata
        error: Error message if failed
    """
    success: bool
    output_path: Optional[str] = None
    field_mappings: Optional[Dict[str, Any]] = None
    confidence: float = 1.0
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class BasePopulationAgent(ABC):
    """
    Abstract base class for population agents.

    Provides common functionality:
    - LLM initialization
    - Configuration management
    - Error handling
    - Logging

    All population agents must inherit from this class.
    """

    def __init__(
        self,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        temperature: float = 0.0,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize population agent.

        Uses centralized LLM configuration from config/llm.yaml by default.
        Module name: "population_agent"

        Args:
            llm_provider: Override LLM provider (anthropic, google, openai)
            llm_model: Override LLM model identifier
            temperature: LLM temperature (0.0 for deterministic)
            config: Additional agent configuration
        """
        # Use centralized config if provider not specified
        if llm_provider is None or llm_model is None:
            from shared.utils.llm_config import get_llm_for_module

            self.llm = get_llm_for_module(
                module_name="population_agent",
                provider=llm_provider,
                temperature=temperature
            )
            # Store for reference
            provider_config = self._get_llm_config_from_manager()
            self.llm_provider = provider_config.get("provider", "anthropic")
            self.llm_model = provider_config.get("model", "claude-3-5-sonnet-20241022")
        else:
            self.llm_provider = llm_provider
            self.llm_model = llm_model

        self.temperature = temperature
        self.config = config or {}

        # Initialize LLM after temperature is set
        if llm_provider is not None and llm_model is not None:
            self.llm = self._get_llm()

        logger.info(
            f"Initialized {self.__class__.__name__} with "
            f"{self.llm_provider}/{self.llm_model}"
        )

    def _get_llm_config_from_manager(self) -> Dict[str, str]:
        """Get LLM config from centralized manager."""
        from shared.utils.llm_config import get_llm_config_manager

        manager = get_llm_config_manager()
        module_config = manager.get_module_config("population_agent")

        # Get the actual model ID from provider config
        provider_config = manager.config.get("providers", {}).get(module_config.provider, {})
        models_config = provider_config.get("models", {})
        model_config = models_config.get(
            module_config.model_variant,
            models_config.get("default", {})
        )

        return {
            "provider": module_config.provider,
            "model": model_config.get("model_id", "claude-3-5-sonnet-20241022")
        }

    def _get_llm(self) -> BaseChatModel:
        """
        Get LangChain LLM instance.

        Returns:
            BaseChatModel instance
        """
        return get_llm(
            provider=self.llm_provider,
            model=self.llm_model,
            temperature=self.temperature,
            max_retries=self.config.get("max_retries", 3),
            timeout=self.config.get("timeout", 120)
        )

    @abstractmethod
    async def populate(
        self,
        task: PopulationTask
    ) -> PopulationResult:
        """
        Populate PDF form with intelligent field mapping.

        This is the main method that agents must implement.
        Agents should:
        1. Analyze template PDF (detect field positions)
        2. Query database for document data
        3. Intelligently map data to fields
        4. Validate mappings
        5. Render filled PDF

        Args:
            task: Population task specification

        Returns:
            PopulationResult with output path and metadata
        """
        pass

    async def health_check(self) -> bool:
        """
        Check agent health.

        Returns:
            True if agent is healthy

        Raises:
            Exception: If health check fails
        """
        try:
            # Test LLM connection
            response = await self.llm.ainvoke("ping")
            logger.debug(f"Agent health check passed")
            return True
        except Exception as e:
            logger.error(f"Agent health check failed: {e}")
            raise

    def get_config_summary(self) -> Dict[str, Any]:
        """
        Get agent configuration summary.

        Returns:
            Configuration dictionary
        """
        return {
            "agent_type": self.__class__.__name__,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "temperature": self.temperature,
            "config": self.config
        }
