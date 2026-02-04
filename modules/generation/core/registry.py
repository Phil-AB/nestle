"""
Registry pattern implementation for generation components.

Components self-register with these registries.
Zero core code changes when adding new components.
"""

from typing import Dict, Callable, Any, Optional, List
from modules.generation.core.interfaces import IRenderer, IDataProvider, IMapper
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


# ==============================================================================
# RENDERER REGISTRY
# ==============================================================================

class RendererRegistry:
    """
    Registry for template renderers.
    
    Renderers self-register using @register_renderer decorator.
    """
    
    _REGISTRY: Dict[str, Callable[[dict], IRenderer]] = {}
    
    @classmethod
    def register(
        cls,
        name: str,
        factory_func: Callable[[dict], IRenderer]
    ) -> None:
        """
        Register a renderer factory function.
        
        Args:
            name: Renderer name (docx, pdf, excel, etc.)
            factory_func: Function that takes config and returns IRenderer
        
        Example:
            def _create_docx_renderer(config: dict) -> IRenderer:
                return DocxRenderer(config)
            
            RendererRegistry.register("docx", _create_docx_renderer)
        """
        if name in cls._REGISTRY:
            logger.warning(f"Renderer '{name}' already registered, overwriting")
        
        cls._REGISTRY[name] = factory_func
        logger.info(f"✅ Registered renderer: {name}")
    
    @classmethod
    def get(cls, name: str, config: Dict[str, Any], **kwargs) -> IRenderer:
        """
        Get renderer instance from registry.
        
        Args:
            name: Renderer name
            config: Renderer configuration
            **kwargs: Additional dependencies to inject (e.g., project_root)
        
        Returns:
            IRenderer instance
        
        Raises:
            ValueError: If renderer not registered
        """
        factory_func = cls._REGISTRY.get(name)
        
        if not factory_func:
            available = list(cls._REGISTRY.keys())
            raise ValueError(
                f"Renderer '{name}' not registered. "
                f"Available: {available}. "
                f"Make sure the renderer module has been imported."
            )
        
        logger.debug(f"Creating renderer instance: {name}")
        
        # Pass kwargs to factory for dependency injection
        try:
            return factory_func(config, **kwargs)
        except TypeError:
            # Fallback for old-style factories that don't accept kwargs
            return factory_func(config)
    
    @classmethod
    def list_renderers(cls) -> List[str]:
        """Get list of registered renderers"""
        return list(cls._REGISTRY.keys())
    
    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if renderer is registered"""
        return name in cls._REGISTRY


def register_renderer(name: str):
    """
    Decorator to register a renderer.

    Usage:
        @register_renderer("docx")
        class DocxRenderer(IRenderer):
            def __init__(self, config, project_root=None):
                super().__init__(config)

            async def render(self, template_path, data, options=None):
                # Implementation
    """
    def decorator(cls):
        def factory(config, **kwargs):
            return cls(config, **kwargs)
        RendererRegistry.register(name, factory)
        return cls
    return decorator


# ==============================================================================
# DATA PROVIDER REGISTRY
# ==============================================================================

class DataProviderRegistry:
    """
    Registry for data providers.
    
    Data providers self-register using @register_data_provider decorator.
    """
    
    _REGISTRY: Dict[str, Callable[[dict], IDataProvider]] = {}
    
    @classmethod
    def register(
        cls,
        name: str,
        factory_func: Callable[[dict], IDataProvider]
    ) -> None:
        """Register a data provider factory function"""
        if name in cls._REGISTRY:
            logger.warning(f"Data provider '{name}' already registered, overwriting")
        
        cls._REGISTRY[name] = factory_func
        logger.info(f"✅ Registered data provider: {name}")
    
    @classmethod
    def get(cls, name: str, config: Dict[str, Any], **kwargs) -> IDataProvider:
        """
        Get data provider instance from registry.
        
        Args:
            name: Provider name
            config: Provider configuration
            **kwargs: Additional dependencies to inject (e.g., db_connection)
        
        Returns:
            IDataProvider instance
        """
        factory_func = cls._REGISTRY.get(name)
        
        if not factory_func:
            available = list(cls._REGISTRY.keys())
            raise ValueError(
                f"Data provider '{name}' not registered. "
                f"Available: {available}. "
                f"Make sure the provider module has been imported."
            )
        
        logger.debug(f"Creating data provider instance: {name}")
        
        # Pass kwargs to factory for dependency injection
        try:
            return factory_func(config, **kwargs)
        except TypeError:
            # Fallback for old-style factories that don't accept kwargs
            return factory_func(config)
    
    @classmethod
    def list_providers(cls) -> List[str]:
        """Get list of registered data providers"""
        return list(cls._REGISTRY.keys())
    
    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if data provider is registered"""
        return name in cls._REGISTRY


def register_data_provider(name: str):
    """
    Decorator to register a data provider.

    Usage:
        @register_data_provider("postgres")
        class PostgresDataProvider(IDataProvider):
            async def fetch_data(self, query, options=None):
                # Implementation
    """
    def decorator(cls):
        def factory(config, **kwargs):
            return cls(config, **kwargs)
        DataProviderRegistry.register(name, factory)
        return cls
    return decorator


# ==============================================================================
# MAPPER REGISTRY
# ==============================================================================

class MapperRegistry:
    """
    Registry for data mappers.
    
    Mappers self-register using @register_mapper decorator.
    """
    
    _REGISTRY: Dict[str, Callable[[dict], IMapper]] = {}
    
    @classmethod
    def register(
        cls,
        name: str,
        factory_func: Callable[[dict], IMapper]
    ) -> None:
        """Register a mapper factory function"""
        if name in cls._REGISTRY:
            logger.warning(f"Mapper '{name}' already registered, overwriting")
        
        cls._REGISTRY[name] = factory_func
        logger.info(f"✅ Registered mapper: {name}")
    
    @classmethod
    def get(cls, name: str, config: Dict[str, Any]) -> IMapper:
        """Get mapper instance from registry"""
        factory_func = cls._REGISTRY.get(name)
        
        if not factory_func:
            available = list(cls._REGISTRY.keys())
            raise ValueError(
                f"Mapper '{name}' not registered. "
                f"Available: {available}. "
                f"Make sure the mapper module has been imported."
            )
        
        logger.debug(f"Creating mapper instance: {name}")
        return factory_func(config)
    
    @classmethod
    def list_mappers(cls) -> List[str]:
        """Get list of registered mappers"""
        return list(cls._REGISTRY.keys())
    
    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if mapper is registered"""
        return name in cls._REGISTRY


def register_mapper(name: str):
    """
    Decorator to register a mapper.

    Usage:
        @register_mapper("field")
        class FieldMapper(IMapper):
            async def map_data(self, source_data, mapping_config, context=None):
                # Implementation
    """
    def decorator(cls):
        def factory(config, **kwargs):
            return cls(config, **kwargs)
        MapperRegistry.register(name, factory)
        return cls
    return decorator
