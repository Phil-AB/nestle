"""
Response schemas for API and service responses.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class SavedDocumentResponse(BaseModel):
    """Response schema for saved document operations."""

    document_id: str = Field(..., description="UUID of the saved document")
    document_number: Optional[str] = Field(None, description="Document number (invoice_number, declaration_number, etc.)")
    document_type: str = Field(..., description="Type of document (invoice, boe, packing_list, coo, freight)")

    extraction_status: str = Field(..., description="Extraction status (complete, incomplete, failed)")
    extraction_confidence: Optional[float] = Field(None, description="Overall confidence score (0-100)")

    saved_fields: List[str] = Field(default_factory=list, description="List of fields that had values and were saved")
    missing_fields: List[str] = Field(default_factory=list, description="List of required fields that were missing")

    items_count: int = Field(..., description="Number of line items saved")

    was_updated: bool = Field(..., description="True if existing record was updated, False if new record created")
    created_at: datetime = Field(..., description="Timestamp when document was created")

    class Config:
        from_attributes = True


class ExtractionErrorResponse(BaseModel):
    """Response schema for extraction errors."""

    success: bool = Field(default=False)
    error_type: str = Field(..., description="Type of error (validation_error, transformation_error, storage_error)")
    error_message: str = Field(..., description="Human-readable error message")
    document_type: Optional[str] = Field(None, description="Document type that failed")
    details: Optional[dict] = Field(None, description="Additional error details")


class DocumentStorageResult(BaseModel):
    """Unified result for document storage operations."""

    success: bool
    document_response: Optional[SavedDocumentResponse] = None
    error_response: Optional[ExtractionErrorResponse] = None

    class Config:
        from_attributes = True
