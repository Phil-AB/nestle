"""
Provider factory for creating parser provider instances.

Uses a registry pattern for 100% plug-and-play modularity.
Providers self-register, no factory code changes needed to add new providers.
"""

from typing import Optional, Callable, Dict
from modules.extraction.parser.base import IParserProvider
from shared.utils.provider_config import get_provider_config
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class ProviderFactory:
    """
    Factory for creating parser provider instances using registry pattern.

    Providers self-register by calling register_provider().
    Adding a new provider requires ZERO changes to this factory.

    Example of adding a new provider:
        1. Create my_provider.py implementing IParserProvider
        2. At bottom of file, call ProviderFactory.register_provider()
        3. Done! No factory changes needed.
    """

    # Provider registry: name -> factory function
    _PROVIDER_REGISTRY: Dict[str, Callable[[dict], IParserProvider]] = {}

    @classmethod
    def register_provider(
        cls,
        name: str,
        factory_func: Callable[[dict], IParserProvider]
    ) -> None:
        """
        Register a provider factory function.

        Providers call this to register themselves with the factory.
        This enables 100% plug-and-play modularity.

        Args:
            name: Provider name (must match name in config/providers.yaml)
            factory_func: Function that takes provider_config dict and returns IParserProvider

        Example:
            def _create_my_provider(provider_config: dict) -> IParserProvider:
                return MyProvider(api_key=provider_config['api_key'])

            ProviderFactory.register_provider("my_provider", _create_my_provider)
        """
        if name in cls._PROVIDER_REGISTRY:
            logger.warning(f"Provider '{name}' already registered, overwriting")

        cls._PROVIDER_REGISTRY[name] = factory_func
        logger.info(f"Registered provider: {name}")

    @classmethod
    def get_registered_providers(cls) -> list:
        """
        Get list of all registered providers.

        Returns:
            List of provider names that have been registered
        """
        return list(cls._PROVIDER_REGISTRY.keys())

    @staticmethod
    def create_provider(provider_name: Optional[str] = None) -> IParserProvider:
        """
        Create a parser provider instance from registry.

        Args:
            provider_name: Optional provider name override.
                          If not provided, uses active_provider from config.

        Returns:
            IParserProvider implementation

        Raises:
            ValueError: If provider is not registered

        Examples:
            # Use active provider from config
            provider = ProviderFactory.create_provider()

            # Use specific provider
            provider = ProviderFactory.create_provider("reducto")
        """
        config = get_provider_config()

        # Determine which provider to use
        if provider_name is None:
            provider_name = config.get_active_provider()

        logger.info(f"Creating provider instance: {provider_name}")

        # Look up provider in registry
        factory_func = ProviderFactory._PROVIDER_REGISTRY.get(provider_name)

        if not factory_func:
            available = list(ProviderFactory._PROVIDER_REGISTRY.keys())
            raise ValueError(
                f"Provider '{provider_name}' is not registered. "
                f"Available providers: {available}. "
                f"Make sure the provider module has been imported and registered."
            )

        # Get provider configuration
        provider_config = config.get_provider_config(provider_name)

        # Call the registered factory function
        logger.debug(f"Calling factory function for provider: {provider_name}")
        return factory_func(provider_config)


def get_active_provider() -> IParserProvider:
    """
    Get the active provider instance based on configuration.

    This is a convenience function for getting the default provider.

    Returns:
        Active provider instance

    Example:
        async with get_active_provider() as provider:
            result = await provider.extract_fields(file_bytes, schema)
    """
    return ProviderFactory.create_provider()
