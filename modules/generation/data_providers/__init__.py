"""
Data providers for generation module.

Providers fetch data from various sources.
"""

# Import all providers to trigger self-registration
from modules.generation.data_providers.postgres_provider import PostgresDataProvider
from modules.generation.data_providers.static_provider import StaticDataProvider
from modules.generation.data_providers.db_interface import (
    IDatabaseConnection,
    DefaultDatabaseConnection,
    CustomDatabaseConnection,
)
from modules.generation.data_providers.data_transformer import DataTransformer

__all__ = [
    "PostgresDataProvider",
    "StaticDataProvider",
    "IDatabaseConnection",
    "DefaultDatabaseConnection",
    "CustomDatabaseConnection",
    "DataTransformer",
]
