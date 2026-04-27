"""
Storage backends module.

Contains all storage backend implementations.
All backends are automatically registered via decorators.
"""

# Import all backends to trigger registration
from modules.extraction.storage.backends import postgresql_backend

__all__ = ['postgresql_backend']
