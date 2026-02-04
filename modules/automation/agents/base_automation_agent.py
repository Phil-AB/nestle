"""
Base Automation Agent.

Abstract base class for automation agents.
Provides common functionality for automated workflows.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

from langchain_core.language_models import BaseChatModel
from shared.providers import get_llm
from shared.utils.logger import setup_logger
from shared.utils.llm_config import get_llm_for_module

logger = setup_logger(__name__)


@dataclass
class AutomationTask:
    """
    Task specification for automation.

    Attributes:
        document_id: Document ID to process
        trigger_event: Event that triggered automation
        trigger_data: Additional data from trigger
        options: Additional options
    """
    document_id: str
    trigger_event: str
    trigger_data: Optional[Dict[str, Any]] = None
    options: Optional[Dict[str, Any]] = None


@dataclass
class AutomationResult:
    """
    Result from automation agent.

    Attributes:
        success: Whether automation succeeded
        document_id: Document ID processed
        action_taken: Action that was performed
        metadata: Additional metadata
        error: Error message if failed
        completed_at: Completion timestamp
    """
    success: bool
    document_id: str
    action_taken: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    completed_at: str = None

    def __post_init__(self):
        if self.completed_at is None:
            self.completed_at = datetime.utcnow().isoformat()


class BaseAutomationAgent(ABC):
    """
    Abstract base class for automation agents.

    Provides common functionality:
    - LLM initialization
    - Configuration management
    - Error handling
    - Logging
    - Result tracking

    All automation agents must inherit from this class.
    """

    def __init__(
        self,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        temperature: float = 0.0,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize automation agent.

        Uses centralized LLM configuration from config/llm.yaml by default.
        Module name: "automation_agent"

        Args:
            llm_provider: Override LLM provider (anthropic, google, openai)
            llm_model: Override LLM model identifier
            temperature: LLM temperature (0.0 for deterministic)
            config: Additional agent configuration
        """
        # Use centralized config if provider not specified
        if llm_provider is None or llm_model is None:
            self.llm = get_llm_for_module(
                module_name="automation_agent",
                provider=llm_provider,
                temperature=temperature
            )
            # Store for reference
            from shared.utils.llm_config import get_llm_config_manager
            manager = get_llm_config_manager()
            module_config = manager.get_module_config("automation_agent")
            self.llm_provider = module_config.provider
            provider_config = manager.config.get("providers", {}).get(module_config.provider, {})
            models_config = provider_config.get("models", {})
            model_config = models_config.get(
                module_config.model_variant,
                models_config.get("default", {})
            )
            self.llm_model = model_config.get("model_id", "claude-3-5-sonnet-20241022")
        else:
            self.llm_provider = llm_provider
            self.llm_model = llm_model
            self.llm = self._get_llm()

        self.temperature = temperature
        self.config = config or {}

        logger.info(
            f"Initialized {self.__class__.__name__} with "
            f"{self.llm_provider}/{self.llm_model}"
        )

    def _get_llm(self) -> BaseChatModel:
        """Get LangChain LLM instance."""
        return get_llm(
            provider=self.llm_provider,
            model=self.llm_model,
            temperature=self.temperature,
            max_retries=self.config.get("max_retries", 3),
            timeout=self.config.get("timeout", 120)
        )

    @abstractmethod
    async def execute(
        self,
        task: AutomationTask
    ) -> AutomationResult:
        """
        Execute automation workflow.

        This is the main method that agents must implement.
        Agents should:
        1. Check preconditions
        2. Execute workflow steps
        3. Update database/status
        4. Send notifications
        5. Return result

        Args:
            task: Automation task specification

        Returns:
            AutomationResult with action taken and metadata
        """
        pass

    async def health_check(self) -> bool:
        """
        Check agent health.

        Returns:
            True if agent is healthy
        """
        try:
            response = await self.llm.ainvoke("ping")
            logger.debug(f"Agent health check passed")
            return True
        except Exception as e:
            logger.error(f"Agent health check failed: {e}")
            raise

    def get_config_summary(self) -> Dict[str, Any]:
        """Get agent configuration summary."""
        return {
            "agent_type": self.__class__.__name__,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "temperature": self.temperature,
            "config": self.config
        }
