"""
Document extraction agents using LangChain.

Note: The system now uses universal config-driven extraction.
Individual document-specific extractors have been removed.
Use BaseExtractor to create custom extractors if needed.
"""

from .base_extractor import BaseExtractor

__all__ = [
    "BaseExtractor",
]
