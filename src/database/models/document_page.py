"""
Document Page Model.

Represents individual pages of multi-page documents.
"""

from sqlalchemy import Column, String, Integer, BigInteger, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.database.schema import Base


class DocumentPage(Base):
    """
    Document page model for multi-page documents.
    
    Each page belongs to a parent APIDocument and stores:
    - Page-specific file information
    - Page number and ordering
    - Individual extraction results
    - Page-level status and errors
    """
    
    __tablename__ = "document_pages"
    
    # Primary key
    page_id = Column(String(36), primary_key=True)
    
    # Foreign key to parent document
    document_id = Column(String(36), ForeignKey("api_documents.document_id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Page information
    page_number = Column(Integer, nullable=False, index=True)
    file_path = Column(String(512), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(BigInteger, nullable=True)
    mime_type = Column(String(100), nullable=True)
    
    # Extraction results
    extraction_status = Column(String(50), nullable=False, default="pending")
    extraction_result = Column(JSON, nullable=True)  # Raw extraction data for this page
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationship to parent document
    document = relationship("APIDocument", back_populates="pages")
    
    def __repr__(self):
        return f"<DocumentPage(page_id={self.page_id}, document_id={self.document_id}, page_number={self.page_number})>"
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "page_id": self.page_id,
            "document_id": self.document_id,
            "page_number": self.page_number,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "extraction_status": self.extraction_status,
            "extraction_result": self.extraction_result,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
