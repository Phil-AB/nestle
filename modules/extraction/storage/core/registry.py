"""
Storage backend registry system.

Provides decorator-based registration for storage backends.
This allows for pluggable storage backends without modifying core code.
"""

from typing import Dict, Type, Optional
from modules.extraction.storage.core.backend import StorageBackend
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)

# Global registry of all storage backends
STORAGE_BACKENDS: Dict[str, Type[StorageBackend]] = {}


def register_backend(name: str):
    """
    Decorator to register a storage backend in the global registry.
    
    Usage:
        @register_backend("postgresql")
        class PostgreSQLBackend(StorageBackend):
            async def store(self, document_type, data):
                ...
    
    Args:
        name: Unique name for the backend (used in configuration)
    
    Returns:
        Decorator function
    """
    def decorator(cls: Type[StorageBackend]):
        if name in STORAGE_BACKENDS:
            logger.warning(
                f"Storage backend '{name}' is already registered. "
                f"Overwriting with {cls.__name__}"
            )
        
        STORAGE_BACKENDS[name] = cls
        logger.debug(f"Registered storage backend: {name} -> {cls.__name__}")
        return cls
    
    return decorator


def get_backend(name: str) -> Optional[Type[StorageBackend]]:
    """
    Get storage backend class by name from registry.
    
    Args:
        name: Backend name
    
    Returns:
        Backend class or None if not found
    """
    return STORAGE_BACKENDS.get(name)


def list_backends() -> Dict[str, str]:
    """
    List all registered storage backends.
    
    Returns:
        Dictionary mapping backend names to class names
    """
    return {
        name: cls.__name__
        for name, cls in STORAGE_BACKENDS.items()
    }


def is_registered(name: str) -> bool:
    """
    Check if a storage backend is registered.
    
    Args:
        name: Backend name
    
    Returns:
        True if registered, False otherwise
    """
    return name in STORAGE_BACKENDS
