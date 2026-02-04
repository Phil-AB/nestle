"""
API request models.

Pydantic models for validating incoming API requests.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# DocumentType is now a string - accepts ANY document type
# The system will handle unknown types with fallback configuration
DocumentType = str  # Type alias for clarity


class ExtractionMode(str, Enum):
    """Extraction modes."""
    OPEN = "open"  # Extract everything
    FOCUSED = "focused"  # Extract specific fields from schema


class RenderMode(str, Enum):
    """Render modes for document output."""
    FULL = "full"
    COMPACT = "compact"
    TABLE_ONLY = "table_only"
    FIELDS_ONLY = "fields_only"


class DocumentUploadRequest(BaseModel):
    """
    Document upload request.

    Used for uploading a document for extraction.
    """

    document_type: str = Field(
        ...,
        description="Type of document being uploaded (any string - system handles all types dynamically)",
        min_length=1,
        max_length=100
    )

    extraction_mode: ExtractionMode = Field(
        default=ExtractionMode.FOCUSED,
        description="Extraction mode (open or focused)"
    )

    shipment_id: Optional[str] = Field(
        default=None,
        description="Optional shipment ID to associate document with"
    )

    webhook_url: Optional[str] = Field(
        default=None,
        description="Optional webhook URL for async notification"
    )

    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional custom metadata"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "document_type": "invoice",
                "extraction_mode": "focused",
                "shipment_id": "SHIP-001",
                "webhook_url": "https://example.com/webhook",
                "metadata": {"uploaded_by": "user@example.com"}
            }
        }


class DocumentRetrievalRequest(BaseModel):
    """
    Document retrieval request with filters.
    """

    document_type: Optional[str] = Field(
        default=None,
        description="Filter by document type"
    )

    shipment_id: Optional[str] = Field(
        default=None,
        description="Filter by shipment ID"
    )

    status: Optional[str] = Field(
        default=None,
        description="Filter by extraction status"
    )

    date_from: Optional[datetime] = Field(
        default=None,
        description="Filter documents from this date"
    )

    date_to: Optional[datetime] = Field(
        default=None,
        description="Filter documents until this date"
    )

    page: int = Field(
        default=1,
        ge=1,
        description="Page number for pagination"
    )

    page_size: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Number of results per page"
    )


class ValidationRequest(BaseModel):
    """
    Request to validate a BOE document.
    """

    boe_id: str = Field(
        ...,
        description="BOE document ID to validate"
    )

    invoice_id: Optional[str] = Field(
        default=None,
        description="Optional invoice ID for validation"
    )

    strict_mode: bool = Field(
        default=False,
        description="Enable strict validation mode"
    )


class ExportRequest(BaseModel):
    """
    Request to export document data.
    """

    document_id: str = Field(
        ...,
        description="Document ID to export"
    )

    format: str = Field(
        default="json",
        description="Export format (json, csv, excel)"
    )

    include_metadata: bool = Field(
        default=True,
        description="Include metadata in export"
    )

    include_layout: bool = Field(
        default=False,
        description="Include layout information"
    )

    @validator("format")
    def validate_format(cls, v):
        """Validate export format."""
        allowed_formats = ["json", "csv", "excel", "pdf"]
        if v.lower() not in allowed_formats:
            raise ValueError(f"Format must be one of: {', '.join(allowed_formats)}")
        return v.lower()


class RenderRequest(BaseModel):
    """
    Request to render document data.
    """

    document_id: str = Field(
        ...,
        description="Document ID to render"
    )

    mode: RenderMode = Field(
        default=RenderMode.FULL,
        description="Render mode"
    )

    show_metadata: bool = Field(
        default=True,
        description="Include metadata in rendering"
    )

    show_layout: bool = Field(
        default=False,
        description="Include layout visualization"
    )


class WebhookRequest(BaseModel):
    """
    Webhook configuration request.
    """

    url: str = Field(
        ...,
        description="Webhook URL to call"
    )

    events: List[str] = Field(
        default=["extraction.completed", "extraction.failed"],
        description="Events to trigger webhook"
    )

    headers: Optional[Dict[str, str]] = Field(
        default=None,
        description="Custom headers for webhook requests"
    )

    active: bool = Field(
        default=True,
        description="Whether webhook is active"
    )

    @validator("url")
    def validate_url(cls, v):
        """Validate webhook URL."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Webhook URL must start with http:// or https://")
        return v


class BatchUploadRequest(BaseModel):
    """
    Batch upload request for multiple documents.
    """

    documents: List[DocumentUploadRequest] = Field(
        ...,
        description="List of documents to upload",
        min_length=1,
        max_length=10
    )

    process_async: bool = Field(
        default=True,
        description="Process documents asynchronously"
    )

    webhook_url: Optional[str] = Field(
        default=None,
        description="Webhook URL for batch completion notification"
    )


class DocumentFieldUpdateRequest(BaseModel):
    """
    Request to update document field values.
    Universal model that works with any document type.
    """

    field_updates: Dict[str, Any] = Field(
        ...,
        description="Dictionary of field keys and their new values",
        min_length=1
    )

    update_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata about the update (e.g., user who made changes, reason)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "field_updates": {
                    "invoice_number": "INV-2024-001",
                    "total_amount": "1500.00",
                    "vendor_name": "Acme Corp"
                },
                "update_metadata": {
                    "updated_by": "user@example.com",
                    "update_reason": "manual_correction"
                }
            }
        }
