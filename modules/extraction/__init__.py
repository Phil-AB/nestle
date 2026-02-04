"""
Extraction Module

Universal document extraction system.
Parses documents and extracts structured data.
"""

__version__ = "1.0.0"

from modules.extraction.parser.base import IParserProvider
from modules.extraction.parser.provider_factory import ProviderFactory, get_active_provider

__all__ = [
    "IParserProvider",
    "ProviderFactory",
    "get_active_provider",
]
