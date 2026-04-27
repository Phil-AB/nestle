"""
Shared database utilities.

Dynamic schema management for universal, config-driven database tables.
"""

from shared.database.schema_manager import SchemaManager
from shared.database.universal_repository import UniversalRepository

__all__ = [
    "SchemaManager",
    "UniversalRepository",
]
