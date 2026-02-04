"""
LLM Config Loader - Centralized LLM configuration management.

Loads LLM settings from config/llm.yaml and provides a simple interface
for getting configured LLM instances using the LLMProvider factory.
"""

import os
from typing import Optional, Dict, Any
from pathlib import Path
import logging

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from shared.providers.llm_provider import get_llm
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class LLMModuleConfig(BaseModel):
    """Configuration for a specific module's LLM usage."""
    provider: str
    model_variant: str = "default"
    description: Optional[str] = None


class LLMConfigManager:
    """
    Manages LLM configuration from config/llm.yaml.

    Provides centralized LLM instance creation for all modules.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize LLM config manager.

        Args:
            config_path: Path to llm.yaml config file (defaults to config/llm.yaml)
        """
        if config_path is None:
            # Default to config/llm.yaml in project root
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "llm.yaml"

        self.config_path = config_path
        self.config = self._load_config()

        logger.info(f"LLM Config Manager initialized from {config_path}")
        logger.info(f"Active provider: {self.active_provider}")

    def _load_config(self) -> Dict[str, Any]:
        """Load LLM configuration from YAML file."""
        import yaml

        if not self.config_path.exists():
            logger.warning(f"LLM config file not found: {self.config_path}")
            logger.info("Using default configuration (Gemini 2.0 Flash)")
            return self._get_default_config()

        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.debug(f"Loaded LLM config from {self.config_path}")
            return config
        except Exception as e:
            logger.error(f"Failed to load LLM config: {e}")
            logger.info("Using default configuration")
            return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default LLM configuration when config file is missing."""
        return {
            "active_provider": "google",
            "providers": {
                "google": {
                    "enabled": True,
                    "api_key_env": "GEMINI_API_KEY",
                    "models": {
                        "default": {
                            "model_id": "gemini-2.0-flash-exp",
                            "temperature": 0.0,
                            "max_tokens": 8192,
                            "timeout": 120,
                            "max_retries": 3
                        }
                    }
                }
            },
            "modules": {}
        }

    @property
    def active_provider(self) -> str:
        """Get the globally active LLM provider."""
        return self.config.get("active_provider", "google")

    def get_module_config(self, module_name: str) -> LLMModuleConfig:
        """
        Get LLM configuration for a specific module.

        Args:
            module_name: Module name (e.g., "ai_semantic_enhancer", "population_agent")

        Returns:
            LLMModuleConfig with provider and model_variant
        """
        modules_config = self.config.get("modules", {})

        if module_name in modules_config:
            module_config = modules_config[module_name]
            return LLMModuleConfig(
                provider=module_config.get("provider", self.active_provider),
                model_variant=module_config.get("model_variant", "default"),
                description=module_config.get("description")
            )

        # Default to active provider with default model
        return LLMModuleConfig(
            provider=self.active_provider,
            model_variant="default",
            description=f"Default config for {module_name}"
        )

    def get_llm(
        self,
        module_name: str = "default",
        provider: Optional[str] = None,
        model_variant: Optional[str] = None,
        **kwargs
    ) -> BaseChatModel:
        """
        Get configured LLM instance for a module.

        Args:
            module_name: Module name (uses module-specific config if available)
            provider: Override provider (optional)
            model_variant: Override model variant (optional)
            **kwargs: Additional LLM parameters

        Returns:
            Configured LangChain LLM instance

        Example:
            >>> # Get LLM for AI semantic enhancer (uses module config)
            >>> llm = manager.get_llm("ai_semantic_enhancer")
            >>>
            >>> # Override provider
            >>> llm = manager.get_llm("population_agent", provider="anthropic")
        """
        # Get module config or use defaults
        if provider is None or model_variant is None:
            module_config = self.get_module_config(module_name)
            provider = provider or module_config.provider
            model_variant = model_variant or module_config.model_variant

        # Get provider-specific model config
        provider_config = self.config.get("providers", {}).get(provider, {})
        if not provider_config:
            logger.warning(f"Provider {provider} not found in config, using defaults")
            # Fallback to basic config
            return self._create_llm_directly(provider, model_variant, **kwargs)

        models_config = provider_config.get("models", {})
        model_config = models_config.get(model_variant, models_config.get("default", {}))

        if not model_config:
            logger.warning(f"Model variant {model_variant} not found for {provider}")
            model_config = {
                "model_id": f"{provider}-default",
                "temperature": 0.0,
                "max_tokens": 4096,
                "timeout": 120,
                "max_retries": 3
            }

        # Get API key from environment
        api_key_env = provider_config.get("api_key_env")
        if api_key_env:
            api_key = os.getenv(api_key_env)
            if not api_key:
                logger.warning(
                    f"API key environment variable {api_key_env} not set for {provider}"
                )
        else:
            api_key = None

        # Collect additional options (for Bedrock, custom endpoints, etc.)
        extra_options = {}

        # Bedrock-specific options
        if provider == "anthropic" and provider_config.get("bedrock_enabled", False):
            extra_options["bedrock_enabled"] = True

            # Get AWS credentials from environment or config
            def _get_env_value(env_var_or_value):
                """Get value from environment variable name or direct value."""
                if env_var_or_value is None:
                    return None
                if os.getenv(env_var_or_value):
                    return os.getenv(env_var_or_value)
                # If it looks like an env var name (all caps with underscores), return it
                # Otherwise return the value as-is
                return os.getenv(env_var_or_value, env_var_or_value)

            # Map Bedrock credential env vars
            for key in ["aws_access_key_id_env", "aws_secret_access_key_env", "aws_region_env", "aws_session_token_env"]:
                env_var_name = provider_config.get(key)
                if env_var_name:
                    # Remove _env suffix for the option key
                    option_key = key.replace("_env", "")
                    # Get the actual value from the environment variable
                    actual_value = os.getenv(env_var_name)
                    if actual_value:
                        extra_options[option_key] = actual_value

            logger.info(f"🔑 AWS Bedrock enabled for Anthropic LLM")

        # Add any other provider-specific options from config
        if "extra_args" in provider_config:
            extra_options["extra_args"] = provider_config["extra_args"]

        # Use model ID from config (no environment variable override)
        model_id = model_config.get("model_id")

        # Merge model config with kwargs (kwargs take precedence)
        final_config = {
            "provider": provider,
            "model": model_id,
            "api_key": api_key,
            "temperature": kwargs.get("temperature", model_config.get("temperature", 0.0)),
            "top_k": kwargs.get("top_k", model_config.get("top_k")),
            "topP": kwargs.get("topP", model_config.get("topP")),
            "timeout": kwargs.get("timeout", model_config.get("timeout", 120)),
            "max_retries": kwargs.get("max_retries", model_config.get("max_retries", 3)),
            "base_url": kwargs.get("base_url", provider_config.get("base_url")),
            "options": extra_options if extra_options else None
        }

        # Remove None values
        final_config = {k: v for k, v in final_config.items() if v is not None}

        logger.info(
            f"Creating LLM: module={module_name}, provider={provider}, "
            f"model={final_config['model']}, variant={model_variant}"
        )

        # Use the LLMProvider factory
        try:
            llm = get_llm(**final_config)
            return llm
        except Exception as e:
            logger.error(f"Failed to create LLM: {e}")
            raise

    def _create_llm_directly(
        self,
        provider: str,
        model_variant: str,
        **kwargs
    ) -> BaseChatModel:
        """Create LLM directly without detailed config (fallback)."""
        model_map = {
            "anthropic": "claude-3-5-sonnet-20241022",
            "google": "gemini-2.0-flash-exp",
            "openai": "gpt-4o",
            "gemini": "gemini-2.0-flash-exp"
        }

        return get_llm(
            provider=provider,
            model=kwargs.get("model", model_map.get(provider, "gemini-2.0-flash-exp")),
            temperature=kwargs.get("temperature", 0.0),
            timeout=kwargs.get("timeout", 120),
            max_retries=kwargs.get("max_retries", 3)
        )

    def list_available_providers(self) -> list[str]:
        """List all configured LLM providers."""
        providers = []
        for provider_name, config in self.config.get("providers", {}).items():
            if config.get("enabled", False):
                providers.append(provider_name)
        return providers

    def validate_api_keys(self) -> Dict[str, bool]:
        """
        Validate that API keys are configured for enabled providers.

        Returns:
            Dictionary mapping provider names to key availability status
        """
        status = {}

        for provider in self.list_available_providers():
            provider_config = self.config.get("providers", {}).get(provider, {})
            api_key_env = provider_config.get("api_key_env")

            if api_key_env:
                has_key = bool(os.getenv(api_key_env))
                status[provider] = has_key

                if not has_key:
                    logger.warning(f"API key missing for {provider}: {api_key_env} not set")
                else:
                    logger.debug(f"API key found for {provider}: {api_key_env}")
            else:
                status[provider] = True  # No key required (e.g., custom/local)

        return status


# Singleton instance
_llm_config_manager: Optional[LLMConfigManager] = None


def get_llm_config_manager() -> LLMConfigManager:
    """
    Get or create the LLM config manager singleton.

    Returns:
        LLMConfigManager instance
    """
    global _llm_config_manager

    if _llm_config_manager is None:
        _llm_config_manager = LLMConfigManager()

    return _llm_config_manager


def get_llm_for_module(module_name: str = "default", **kwargs) -> BaseChatModel:
    """
    Convenience function to get LLM for a specific module.

    Args:
        module_name: Module name (uses module-specific config from llm.yaml)
        **kwargs: Override parameters

    Returns:
        Configured LangChain LLM instance

    Example:
        >>> # Get LLM for AI semantic enhancer
        >>> llm = get_llm_for_module("ai_semantic_enhancer")
        >>>
        >>> # Get LLM with override
        >>> llm = get_llm_for_module("population_agent", provider="anthropic")
    """
    manager = get_llm_config_manager()
    return manager.get_llm(module_name, **kwargs)


def validate_llm_configuration() -> Dict[str, bool]:
    """
    Validate LLM API keys for all enabled providers.

    Returns:
        Dictionary mapping provider names to key availability
    """
    manager = get_llm_config_manager()
    return manager.validate_api_keys()
