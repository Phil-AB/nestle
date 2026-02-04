"""
Generation Module

Universal document generation system.
Populates templates with data from any source.
"""

__version__ = "1.0.0"

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

# Import implementations to trigger registration
import modules.generation.data_providers
import modules.generation.renderers
import modules.generation.mappers

# Export configuration
from modules.generation.config import (
    GenerationConfig,
    get_generation_config,
    set_generation_config,
)

# Export storage
from modules.generation.storage import (
    IJobStorage,
    InMemoryJobStorage,
    JobData,
)

# Export database interface
from modules.generation.data_providers.db_interface import (
    IDatabaseConnection,
    DefaultDatabaseConnection,
    CustomDatabaseConnection,
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
    # Configuration
    "GenerationConfig",
    "get_generation_config",
    "set_generation_config",
    # Storage
    "IJobStorage",
    "InMemoryJobStorage",
    "JobData",
    # Database
    "IDatabaseConnection",
    "DefaultDatabaseConnection",
    "CustomDatabaseConnection",
]
