"""
Provider configuration loader.

Loads provider configuration from config/providers.yaml.
"""

import os
import yaml
from functools import lru_cache
from typing import Dict, Any, Optional
from pathlib import Path

from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class ProviderConfig:
    """Provider configuration loader and accessor."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize provider configuration.

        Args:
            config_path: Path to providers.yaml (defaults to config/providers.yaml)
        """
        if config_path is None:
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config" / "providers.yaml"

        self.config_path = Path(config_path)
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """
        Load provider configuration from YAML file.

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML is invalid
        """
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Provider configuration not found: {self.config_path}"
            )

        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)

            logger.info(f"Loaded provider configuration from: {self.config_path}")
            return config

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse provider config YAML: {e}")
            raise

    def get_active_provider(self) -> str:
        """
        Get the active provider name.

        Returns:
            Active provider name (e.g., 'reducto', 'google_document_ai')
        """
        provider = self._config.get('active_provider', 'reducto')
        logger.debug(f"Active provider: {provider}")
        return provider

    def get_provider_config(self, provider_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific provider.

        Args:
            provider_name: Name of provider (reducto, google_document_ai, etc.)

        Returns:
            Provider configuration dictionary

        Raises:
            ValueError: If provider not found in config
        """
        providers = self._config.get('providers', {})

        if provider_name not in providers:
            raise ValueError(
                f"Provider '{provider_name}' not found in config. "
                f"Available providers: {', '.join(providers.keys())}"
            )

        config = providers[provider_name]

        # Check if provider is enabled
        if not config.get('enabled', True):
            logger.warning(f"Provider '{provider_name}' is disabled in config")

        return config

    def get_provider_api_key(self, provider_name: str) -> str:
        """
        Get API key for a provider from environment variable.

        Args:
            provider_name: Name of provider

        Returns:
            API key value

        Raises:
            ValueError: If API key environment variable not set
        """
        config = self.get_provider_config(provider_name)

        api_key_env = config.get('api_key_env')
        if not api_key_env:
            raise ValueError(
                f"No 'api_key_env' specified for provider '{provider_name}'"
            )

        api_key = os.getenv(api_key_env)
        if not api_key:
            raise ValueError(
                f"Environment variable '{api_key_env}' not set for provider '{provider_name}'"
            )

        return api_key

    def get_provider_base_url(self, provider_name: str) -> Optional[str]:
        """
        Get base URL for a provider.

        Args:
            provider_name: Name of provider

        Returns:
            Base URL or None if not applicable
        """
        config = self.get_provider_config(provider_name)
        return config.get('base_url')

    def get_provider_timeout(self, provider_name: str) -> int:
        """
        Get timeout for a provider.

        Args:
            provider_name: Name of provider

        Returns:
            Timeout in seconds (default: 120)
        """
        config = self.get_provider_config(provider_name)
        return config.get('timeout', 120)

    def get_provider_options(self, provider_name: str) -> Dict[str, Any]:
        """
        Get provider-specific options.

        Args:
            provider_name: Name of provider

        Returns:
            Dictionary of provider options
        """
        config = self.get_provider_config(provider_name)
        return config.get('options', {})

    def get_provider_capabilities(self, provider_name: str) -> Dict[str, Any]:
        """
        Get capabilities for a provider.

        Args:
            provider_name: Name of provider

        Returns:
            Capabilities dictionary
        """
        capabilities = self._config.get('capabilities', {})
        return capabilities.get(provider_name, {})

    def get_retry_policy(self) -> Dict[str, Any]:
        """
        Get retry policy configuration.

        Returns:
            Retry policy dictionary
        """
        return self._config.get('retry_policy', {
            'max_retries': 3,
            'retry_delay_seconds': 2,
            'exponential_backoff': True,
            'backoff_multiplier': 2
        })

    def get_timeout_policy(self) -> Dict[str, Any]:
        """
        Get timeout policy configuration.

        Returns:
            Timeout policy dictionary
        """
        return self._config.get('timeout_policy', {
            'upload_timeout': 30,
            'extraction_timeout': 120,
            'health_check_timeout': 5
        })


@lru_cache()
def get_provider_config() -> ProviderConfig:
    """
    Get cached provider configuration instance.

    Returns:
        ProviderConfig singleton
    """
    return ProviderConfig()
