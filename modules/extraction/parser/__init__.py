"""
Parser service module.

Provides document parsing capabilities with swappable providers.

All providers auto-register with ProviderFactory when imported.
Adding a new provider requires ZERO changes to factory code.
"""

from .base import (
    IParserProvider,
    ParsedDocument,
    ParserException,
    ParserConnectionError,
    ParserValidationError,
    ParserTimeoutError,
)

# Universal components (recommended)
from .schema_generator import SchemaGenerator
from .provider_factory import ProviderFactory, get_active_provider

# ==============================================================================
# Provider implementations - importing these auto-registers them
# ==============================================================================
# Each provider file calls ProviderFactory.register_provider() at import time
# This enables 100% plug-and-play modularity - no factory changes needed!

from .reducto_provider import ReductoProvider
from .google_provider import GoogleDocumentAIProvider

# Note: To add a new provider:
# 1. Create your_provider.py implementing IParserProvider
# 2. Call ProviderFactory.register_provider() at bottom of file
# 3. Import it here
# 4. Done! No factory changes needed.

__all__ = [
    # Base interfaces
    "IParserProvider",
    "ParsedDocument",
    "ParserException",
    "ParserConnectionError",
    "ParserValidationError",
    "ParserTimeoutError",
    # Universal components (recommended)
    "SchemaGenerator",
    "ProviderFactory",
    "get_active_provider",
    # Provider implementations
    "ReductoProvider",
    "GoogleDocumentAIProvider",
]
