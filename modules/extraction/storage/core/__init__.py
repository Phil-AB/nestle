"""
Storage core module.

Contains base classes, interfaces, and utilities for the storage system.
"""

from modules.extraction.storage.core.backend import StorageBackend, StorageResult
from modules.extraction.storage.core.registry import STORAGE_BACKENDS, register_backend, get_backend

__all__ = [
    'StorageBackend',
    'StorageResult',
    'STORAGE_BACKENDS',
    'register_backend',
    'get_backend',
]
