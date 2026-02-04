"""
LLM Provider Factory for LangChain.

Provides centralized LLM instantiation for all modules.
Supports multiple providers: OpenAI, Anthropic, Google (Gemini).
"""

import os
from typing import Optional, Dict, Any
from functools import lru_cache
import logging

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

from shared.providers.base_provider import BaseProvider, ProviderConfig
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class LLMProvider(BaseProvider):
    """
    LLM provider factory for LangChain.

    Creates LangChain-compatible LLM instances based on configuration.
    Supports:
    - OpenAI (gpt-4, gpt-3.5-turbo, etc.)
    - Anthropic (claude-3-opus, claude-3-sonnet, etc.)
    - Google (gemini-pro, gemini-1.5-flash, etc.)
    - Custom endpoints (Ollama, vLLM, etc.)

    Example:
        >>> config = ProviderConfig(
        ...     provider_name="anthropic",
        ...     api_key=os.getenv("ANTHROPIC_API_KEY"),
        ...     model="claude-3-5-sonnet-20241022",
        ...     temperature=0.0
        ... )
        >>> provider = LLMProvider(config)
        >>> llm = provider.get_llm()
        >>> response = await llm.ainvoke("Hello!")
    """

    def _validate_config(self) -> None:
        """Validate LLM provider configuration."""
        # Check if Bedrock is enabled for Anthropic
        bedrock_enabled = (
            self.config.provider_name.lower() == "anthropic" and
            self.config.options and
            self.config.options.get('bedrock_enabled', False)
        )

        # Skip API key validation if Bedrock is enabled (uses AWS credentials)
        if not self.config.api_key and not bedrock_enabled:
            raise ValueError(f"API key required for {self.config.provider_name}")

        if not self.config.model:
            raise ValueError("Model name is required")

        # Validate temperature
        if not (0.0 <= self.config.temperature <= 1.0):
            raise ValueError(
                f"Temperature must be between 0.0 and 1.0, got {self.config.temperature}"
            )

    def _initialize_client(self) -> None:
        """Initialize LangChain LLM client."""
        self.llm = self._create_llm()

    def _create_llm(self) -> BaseChatModel:
        """
        Create LangChain LLM instance based on provider.

        Returns:
            LangChain BaseChatModel instance

        Raises:
            ValueError: If provider not supported
        """
        provider = self.config.provider_name.lower()

        if provider == "openai":
            return self._create_openai_llm()
        elif provider == "anthropic":
            return self._create_anthropic_llm()
        elif provider == "google" or provider == "gemini":
            return self._create_google_llm()
        elif provider == "custom":
            return self._create_custom_llm()
        else:
            raise ValueError(
                f"Unsupported LLM provider: {provider}. "
                f"Supported: openai, anthropic, google, custom"
            )

    def _create_openai_llm(self) -> ChatOpenAI:
        """Create OpenAI LLM instance."""
        return ChatOpenAI(
            model=self.config.model,
            temperature=self.config.temperature,
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries,
            **(self.config.options or {})
        )

    def _create_anthropic_llm(self) -> BaseChatModel:
        """
        Create Anthropic LLM instance.

        Supports both direct API and AWS Bedrock.
        """
        # Check if Bedrock is enabled in options
        bedrock_enabled = self.config.options and self.config.options.get('bedrock_enabled', False)

        if bedrock_enabled:
            # AWS Bedrock configuration
            import os
            import boto3

            # Get AWS credentials from environment
            aws_access_key_id = self.config.options.get('aws_access_key_id') or os.getenv("AWS_ACCESS_KEY_ID")
            aws_secret_access_key = self.config.options.get('aws_secret_access_key') or os.getenv("AWS_SECRET_ACCESS_KEY")
            aws_region = self.config.options.get('aws_region') or os.getenv("AWS_REGION", "us-east-1")
            aws_session_token = self.config.options.get('aws_session_token') or os.getenv("AWS_SESSION_TOKEN")

            # Validate AWS credentials
            if not aws_access_key_id or not aws_secret_access_key:
                raise ValueError(
                    "AWS credentials required for Bedrock. Set AWS_ACCESS_KEY_ID and "
                    "AWS_SECRET_ACCESS_KEY environment variables, or provide in config."
                )

            # Create boto3 session for Bedrock
            session_kwargs = {
                'aws_access_key_id': aws_access_key_id,
                'aws_secret_access_key': aws_secret_access_key,
                'region_name': aws_region
            }

            # Add session token if available (for temporary credentials)
            if aws_session_token:
                session_kwargs['aws_session_token'] = aws_session_token

            bedrock_session = boto3.Session(**session_kwargs)

            logger.info(
                f"Creating Anthropic LLM via AWS Bedrock: "
                f"model={self.config.model}, region={aws_region}"
            )

            # Create Bedrock runtime client (not Session)
            bedrock_client = bedrock_session.client('bedrock-runtime')

            # Create ChatAnthropic with Bedrock
            from langchain_aws import ChatBedrock

            # Build model kwargs with deterministic sampling parameters
            model_kwargs = {
                "temperature": self.config.temperature,
            }

            # Add top_k and topP for more deterministic outputs
            if self.config.top_k is not None:
                model_kwargs["top_k"] = self.config.top_k
            if self.config.topP is not None:
                model_kwargs["topP"] = self.config.topP

            # Filter out Bedrock-specific keys from extra_args
            extra_args = self.config.options.get('extra_args') or {}
            bedrock_keys = {'bedrock_enabled', 'aws_access_key_id', 'aws_secret_access_key', 'aws_region', 'aws_session_token', 'extra_args'}
            filtered_args = {k: v for k, v in extra_args.items() if k not in bedrock_keys}

            return ChatBedrock(
                client=bedrock_client,
                model_id=self.config.model,
                **model_kwargs,
                **filtered_args
            )
        else:
            # Direct Anthropic API
            if not self.config.api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY required for direct API. Set environment variable "
                    "or enable Bedrock with bedrock_enabled=true"
                )

            logger.info(f"Creating Anthropic LLM via direct API: model={self.config.model}")

            # Filter out Bedrock-specific options for direct API
            filtered_options = {}
            if self.config.options:
                bedrock_keys = {
                    'bedrock_enabled', 'aws_access_key_id', 'aws_secret_access_key',
                    'aws_region', 'aws_session_token', 'extra_args'
                }
                filtered_options = {k: v for k, v in self.config.options.items() if k not in bedrock_keys}

            # Build model kwargs for direct Anthropic API
            # Note: Anthropic uses 'top_p' (underscore) not 'topP'
            model_kwargs = {
                "model": self.config.model,
                "temperature": self.config.temperature,
                "api_key": self.config.api_key,
                "timeout": self.config.timeout,
                "max_retries": self.config.max_retries,
            }

            # Add top_p for more deterministic outputs (Anthropic uses underscore)
            if self.config.topP is not None:
                model_kwargs["top_p"] = self.config.topP
            if self.config.top_k is not None:
                model_kwargs["top_k"] = self.config.top_k

            return ChatAnthropic(**model_kwargs)

    def _create_google_llm(self) -> BaseChatModel:
        """Create Google/Gemini LLM instance."""
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(
                model=self.config.model,
                temperature=self.config.temperature,
                google_api_key=self.config.api_key,
                timeout=self.config.timeout,
                max_retries=self.config.max_retries,
                **(self.config.options or {})
            )
        except ImportError:
            raise ImportError(
                "langchain-google-genai not installed. "
                "Install with: pip install langchain-google-genai"
            )

    def _create_custom_llm(self) -> ChatOpenAI:
        """
        Create custom LLM instance (e.g., Ollama, vLLM).

        Uses OpenAI-compatible interface.
        """
        if not self.config.base_url:
            raise ValueError("base_url required for custom LLM provider")

        return ChatOpenAI(
            model=self.config.model,
            temperature=self.config.temperature,
            api_key=self.config.api_key or "not-needed",
            base_url=self.config.base_url,
            timeout=self.config.timeout,
            max_retries=self.config.max_retries,
            **(self.config.options or {})
        )

    def get_llm(self) -> BaseChatModel:
        """
        Get LangChain LLM instance.

        Returns:
            LangChain BaseChatModel instance
        """
        return self.llm

    async def health_check(self) -> bool:
        """
        Check LLM provider health.

        Returns:
            True if provider is accessible

        Raises:
            Exception: If health check fails
        """
        try:
            # Try a simple invocation
            response = await self.llm.ainvoke("ping")
            logger.debug(f"LLM health check passed: {response.content[:50]}")
            return True
        except Exception as e:
            logger.error(f"LLM health check failed: {e}")
            raise


# ==============================================================================
# FACTORY FUNCTION - Convenience wrapper
# ==============================================================================

def get_llm(
    provider: str,
    model: str,
    api_key: Optional[str] = None,
    temperature: float = 0.0,
    base_url: Optional[str] = None,
    timeout: int = 120,
    max_retries: int = 3,
    **options
) -> BaseChatModel:
    """
    Factory function to get LangChain LLM instance.

    Convenience wrapper around LLMProvider for quick LLM creation.

    Args:
        provider: Provider name (openai, anthropic, google, custom)
        model: Model identifier
        api_key: API key (defaults to env variable based on provider)
        temperature: LLM temperature (0.0-1.0)
        base_url: Base URL for custom providers
        timeout: Request timeout in seconds
        max_retries: Maximum retry attempts
        **options: Additional provider-specific options

    Returns:
        LangChain BaseChatModel instance

    Example:
        >>> # OpenAI
        >>> llm = get_llm("openai", "gpt-4", temperature=0.0)

        >>> # Anthropic
        >>> llm = get_llm("anthropic", "claude-3-5-sonnet-20241022")

        >>> # Gemini
        >>> llm = get_llm("google", "gemini-1.5-flash")

        >>> # Custom (Ollama)
        >>> llm = get_llm(
        ...     "custom",
        ...     "llama2",
        ...     base_url="http://localhost:11434/v1"
        ... )
    """
    # Extract top_k, topP, and options from **options kwargs FIRST
    # These are passed from llm_config.py and need to be handled separately
    top_k = options.pop('top_k', None)
    topP = options.pop('topP', None)

    # Handle nested 'options' dict (Bedrock config lives here)
    provider_options = None
    if 'options' in options:
        # Extract the nested 'options' dict (contains bedrock_enabled, AWS creds, etc.)
        provider_options = options.pop('options')
    elif options:
        # If there are remaining options, use them directly
        provider_options = options

    # Check if Bedrock is enabled for Anthropic
    bedrock_enabled = False
    if provider_options and provider.lower() == "anthropic":
        bedrock_enabled = provider_options.get('bedrock_enabled', False)

    # Get API key from environment if not provided (skip if Bedrock enabled)
    if api_key is None and not bedrock_enabled:
        api_key_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google": "GEMINI_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "custom": "CUSTOM_LLM_API_KEY"
        }
        env_var = api_key_map.get(provider.lower())
        if env_var:
            api_key = os.getenv(env_var)
            if not api_key and provider != "custom":
                raise ValueError(
                    f"API key not provided and {env_var} environment variable not set"
                )

    config = ProviderConfig(
        provider_name=provider,
        api_key=api_key or "",
        model=model,
        base_url=base_url,
        timeout=timeout,
        max_retries=max_retries,
        temperature=temperature,
        top_k=top_k,
        topP=topP,
        options=provider_options
    )

    # Create and return LLM
    provider_instance = LLMProvider(config)
    return provider_instance.get_llm()


@lru_cache(maxsize=10)
def get_cached_llm(
    provider: str,
    model: str,
    temperature: float = 0.0
) -> BaseChatModel:
    """
    Get cached LLM instance.

    Caches LLM instances to avoid recreating them.
    Useful for frequently used LLMs.

    Args:
        provider: Provider name
        model: Model identifier
        temperature: LLM temperature

    Returns:
        Cached LangChain BaseChatModel instance

    Note:
        API keys are read from environment variables.
    """
    return get_llm(provider, model, temperature=temperature)
