"""
Base Provider Interface.

Abstract base class for all AI/ML service providers.
Enforces consistent interface across different provider implementations.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProviderConfig:
    """
    Configuration for a provider.

    Attributes:
        provider_name: Name of the provider (e.g., "gemini", "openai")
        api_key: API key for authentication
        model: Model identifier
        base_url: Optional base URL for API
        timeout: Request timeout in seconds
        max_retries: Maximum number of retry attempts
        temperature: LLM temperature (0.0-1.0)
        top_k: Top-K sampling parameter (1 for most deterministic)
        topP: Top-P (nucleus) sampling parameter (1.0 for most deterministic)
        options: Additional provider-specific options
    """
    provider_name: str
    api_key: str
    model: str
    base_url: Optional[str] = None
    timeout: int = 120
    max_retries: int = 3
    temperature: float = 0.0
    top_k: Optional[int] = None
    topP: Optional[float] = None
    options: Optional[Dict[str, Any]] = None


@dataclass
class ProviderResponse:
    """
    Standard response from provider operations.

    Attributes:
        success: Whether operation succeeded
        data: Response data (provider-specific)
        error: Error message if failed
        metadata: Additional metadata (tokens used, latency, etc.)
    """
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseProvider(ABC):
    """
    Abstract base class for all providers.

    Enforces consistent interface and provides common functionality:
    - Configuration management
    - Error handling
    - Retry logic
    - Logging

    All providers (Gemini, OpenAI, Anthropic, etc.) must inherit from this.
    """

    def __init__(self, config: ProviderConfig):
        """
        Initialize provider with configuration.

        Args:
            config: Provider configuration
        """
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Validate configuration
        self._validate_config()

        # Initialize provider-specific client
        self._initialize_client()

        self.logger.info(
            f"Initialized {self.config.provider_name} provider "
            f"with model: {self.config.model}"
        )

    @abstractmethod
    def _validate_config(self) -> None:
        """
        Validate provider configuration.

        Raises:
            ValueError: If configuration is invalid
        """
        pass

    @abstractmethod
    def _initialize_client(self) -> None:
        """
        Initialize provider-specific client/SDK.

        This is where providers set up their API clients
        (e.g., genai.configure() for Gemini, OpenAI() for OpenAI, etc.)
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if provider is accessible and healthy.

        Returns:
            True if provider is healthy

        Raises:
            Exception: If health check fails
        """
        pass

    def get_config_summary(self) -> Dict[str, Any]:
        """
        Get sanitized configuration summary for logging.

        Returns:
            Configuration dictionary (with sensitive data masked)
        """
        return {
            "provider": self.config.provider_name,
            "model": self.config.model,
            "timeout": self.config.timeout,
            "max_retries": self.config.max_retries,
            "temperature": self.config.temperature,
            "api_key": "***" + self.config.api_key[-4:] if self.config.api_key else None,
        }

    async def _retry_operation(
        self,
        operation,
        operation_name: str,
        *args,
        **kwargs
    ) -> ProviderResponse:
        """
        Execute operation with retry logic.

        Args:
            operation: Async callable to execute
            operation_name: Name of operation (for logging)
            *args: Positional arguments for operation
            **kwargs: Keyword arguments for operation

        Returns:
            ProviderResponse with result or error
        """
        import asyncio

        last_error = None

        for attempt in range(self.config.max_retries):
            try:
                self.logger.debug(
                    f"Executing {operation_name} (attempt {attempt + 1}/{self.config.max_retries})"
                )

                result = await operation(*args, **kwargs)

                self.logger.debug(f"{operation_name} succeeded on attempt {attempt + 1}")

                return ProviderResponse(
                    success=True,
                    data=result,
                    metadata={"attempts": attempt + 1}
                )

            except Exception as e:
                last_error = e
                self.logger.warning(
                    f"{operation_name} failed on attempt {attempt + 1}: {e}"
                )

                # Don't retry on last attempt
                if attempt < self.config.max_retries - 1:
                    # Exponential backoff
                    wait_time = 2 ** attempt
                    self.logger.debug(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)

        # All retries exhausted
        self.logger.error(
            f"{operation_name} failed after {self.config.max_retries} attempts: {last_error}"
        )

        return ProviderResponse(
            success=False,
            error=str(last_error),
            metadata={"attempts": self.config.max_retries}
        )
