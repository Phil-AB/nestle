"""
Core components for generation module.
"""

from modules.generation.core.interfaces import (
    IRenderer,
    IDataProvider,
    IMapper,
    ITemplateRegistry,
    GenerationResult,
    MappingResult,
    TemplateMetadata,
    GenerationStatus,
)

from modules.generation.core.registry import (
    RendererRegistry,
    DataProviderRegistry,
    MapperRegistry,
    register_renderer,
    register_data_provider,
    register_mapper,
)

from modules.generation.core.exceptions import (
    GenerationException,
    RendererException,
    DataProviderException,
    MappingException,
    TemplateNotFoundException,
    TemplateValidationException,
)

__all__ = [
    # Interfaces
    "IRenderer",
    "IDataProvider",
    "IMapper",
    "ITemplateRegistry",
    # Results
    "GenerationResult",
    "MappingResult",
    "TemplateMetadata",
    "GenerationStatus",
    # Registries
    "RendererRegistry",
    "DataProviderRegistry",
    "MapperRegistry",
    # Decorators
    "register_renderer",
    "register_data_provider",
    "register_mapper",
    # Exceptions
    "GenerationException",
    "RendererException",
    "DataProviderException",
    "MappingException",
    "TemplateNotFoundException",
    "TemplateValidationException",
]
