"""
Database repositories for data access.

Note: The system now uses GenericDocumentRepository for all document types.
Document-specific repositories have been removed in favor of the universal approach.
"""

from .base import BaseRepository
from .shipment_repository import ShipmentRepository
from .generic_repository import GenericDocumentRepository, get_generic_repository, MODEL_REGISTRY

__all__ = [
    "BaseRepository",
    "ShipmentRepository",
    "GenericDocumentRepository",
    "get_generic_repository",
    "MODEL_REGISTRY",
]
