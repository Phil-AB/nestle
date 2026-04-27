"""
Storage module - Universal document storage system.

Provides flexible, configurable storage for any document type.

Main components:
- StorageEngine: Main orchestrator for storage operations
- StorageBackend: Base interface for storage backends
- Built-in backends: PostgreSQL (JSONB-based)

Usage:
    from modules.extraction.storage import StorageEngine
    
    engine = StorageEngine()
    result = await engine.store("document_type", data)
    
    if result.success:
        print(f"Stored: {result.document_id}")
"""

from modules.extraction.storage.storage_engine import StorageEngine, MultiBackendStorageResult
from modules.extraction.storage.core.backend import StorageBackend, StorageResult
from modules.extraction.storage.core.registry import register_backend, STORAGE_BACKENDS

__all__ = [
    'StorageEngine',
    'MultiBackendStorageResult',
    'StorageBackend',
    'StorageResult',
    'register_backend',
    'STORAGE_BACKENDS',
]
