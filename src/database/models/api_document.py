"""
SQLAlchemy model for API document metadata storage.

Replaces in-memory _documents_storage dict for production scalability.
"""

from sqlalchemy import Column, String, Integer, DateTime, Text, Float, TIMESTAMP, JSON, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from src.database.connection import Base


class APIDocument(Base):
    """
    Model for storing document metadata from API uploads.

    This replaces the in-memory _documents_storage dictionary,
    enabling multi-worker scalability and persistence.
    """

    __tablename__ = "api_documents"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Document identification
    document_id = Column(String(100), unique=True, nullable=False, index=True)
    document_type = Column(String(100), nullable=True, index=True)  # Make nullable since user will select
    document_name = Column(String(255))  # User-provided document name
    filename = Column(String(255))

    # File storage
    file_path = Column(Text, nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String(100))  # MIME type for proper file rendering

    # Multi-page support
    is_multi_page = Column(Boolean, default=False, nullable=False)
    total_pages = Column(Integer, default=1, nullable=False)

    # Extraction configuration
    extraction_mode = Column(String(50))  # 'open' or 'focused'
    extraction_status = Column(String(50), nullable=False, index=True)  # 'processing', 'complete', 'failed', 'incomplete'

    # Relationships
    shipment_id = Column(String(100), index=True)  # Optional link to shipment

    # Extracted data (JSONB for efficient querying)
    fields = Column(JSONB, default=dict)  # Extracted field key-value pairs
    items = Column(JSONB, default=list)  # Line items array
    blocks = Column(JSONB, default=list)  # Content blocks for document rendering
    doc_metadata = Column(JSONB, default=dict)  # Provider metadata, errors, etc.
    raw_provider_response = Column(JSONB, default=dict)  # Original raw response from provider (Reducto/Google AI)

    # Counts (for quick filtering)
    items_count = Column(Integer, default=0)
    fields_count = Column(Integer, default=0)

    # Confidence and quality metrics
    extraction_confidence = Column(Float)

    # Timestamps
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    parsed_at = Column(TIMESTAMP(timezone=True))
    
    # Relationships
    pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan", order_by="DocumentPage.page_number")

    def __repr__(self):
        return (
            f"<APIDocument("
            f"id={self.document_id}, "
            f"type={self.document_type}, "
            f"status={self.extraction_status}"
            f")>"
        )

    def to_dict(self, include_pages: bool = False, include_raw_response: bool = False) -> dict:
        """Convert model to dictionary for API responses."""
        result = {
            "id": str(self.id),
            "document_id": self.document_id,
            "document_type": self.document_type,
            "document_name": self.document_name,
            "filename": self.filename,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "extraction_mode": self.extraction_mode,
            "extraction_status": self.extraction_status,
            "shipment_id": self.shipment_id,
            "fields": self.fields or {},
            "items": self.items or [],
            "blocks": self.blocks or [],
            "metadata": self.doc_metadata or {},
            "items_count": self.items_count or 0,
            "fields_count": self.fields_count or 0,
            "extraction_confidence": self.extraction_confidence,
            "is_multi_page": self.is_multi_page,
            "total_pages": self.total_pages,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "parsed_at": self.parsed_at.isoformat() if self.parsed_at else None,
        }

        if include_pages and self.pages:
            result["pages"] = [page.to_dict() for page in self.pages]

        # Include raw provider response if requested (useful for debugging/comparison)
        if include_raw_response:
            result["raw_provider_response"] = self.raw_provider_response or {}

        return result
