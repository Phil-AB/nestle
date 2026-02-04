"""
API response models.

Pydantic models for API responses.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ResponseStatus(str, Enum):
    """Response status values."""
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"
    PROCESSING = "processing"


class ExtractionStatus(str, Enum):
    """Document extraction status."""
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    FAILED = "failed"
    PROCESSING = "processing"


class ErrorResponse(BaseModel):
    """
    Standard error response.
    """

    status: ResponseStatus = Field(default=ResponseStatus.ERROR)
    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    detail: Optional[str] = Field(default=None, description="Detailed error information")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "status": "error",
                "error": "invalid_document_type",
                "message": "The specified document type is not supported",
                "detail": "Supported types: invoice, boe, packing_list, coo, freight",
                "timestamp": "2024-01-20T10:30:00Z"
            }
        }


class DocumentMetadata(BaseModel):
    """
    Document extraction metadata.
    """

    provider: str = Field(..., description="Parser provider used")
    extraction_duration: Optional[float] = Field(None, description="Extraction time in seconds")
    confidence: Optional[float] = Field(None, description="Overall confidence score")
    page_count: Optional[int] = Field(None, description="Number of pages")
    job_id: Optional[str] = Field(None, description="Provider job ID")


class DocumentResponse(BaseModel):
    """
    Document extraction response.
    """

    status: ResponseStatus = Field(default=ResponseStatus.SUCCESS)
    document_id: str = Field(..., description="Unique document identifier")
    document_type: Optional[str] = Field(default=None, description="Type of document")
    document_number: Optional[str] = Field(None, description="Document number (invoice number, etc.)")

    extraction_status: ExtractionStatus = Field(..., description="Extraction completeness status")
    extraction_confidence: Optional[float] = Field(None, description="Extraction confidence (0-1)")

    fields: Dict[str, Any] = Field(default_factory=dict, description="Extracted header fields")
    items: List[Dict[str, Any]] = Field(default_factory=list, description="Extracted line items")
    blocks: Optional[List[Dict[str, Any]]] = Field(default=None, description="Raw content blocks for full document rendering")

    fields_count: int = Field(..., description="Number of fields extracted")
    items_count: int = Field(..., description="Number of line items extracted")

    saved_fields: List[str] = Field(default_factory=list, description="List of successfully saved fields")
    missing_fields: List[str] = Field(default_factory=list, description="List of missing required fields")

    metadata: Optional[DocumentMetadata] = Field(None, description="Extraction metadata")

    layout: Optional[Dict[str, Any]] = Field(None, description="Document layout structure")
    raw_data: Optional[Dict[str, Any]] = Field(None, description="Raw parser output")

    created_at: datetime = Field(..., description="Document creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    mime_type: Optional[str] = Field(None, description="MIME type of the original file")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "document_id": "doc-123-abc",
                "document_type": "invoice",
                "document_number": "INV-2024-001",
                "extraction_status": "complete",
                "extraction_confidence": 0.95,
                "fields": {
                    "invoice_number": "INV-2024-001",
                    "invoice_date": "2024-01-15",
                    "total_fob_value": 10000.00
                },
                "items": [
                    {
                        "line_number": 1,
                        "product_description": "Coffee Beans",
                        "quantity": 100,
                        "unit_price": 50.00
                    }
                ],
                "fields_count": 10,
                "items_count": 5,
                "saved_fields": ["invoice_number", "invoice_date"],
                "missing_fields": [],
                "metadata": {
                    "provider": "reducto",
                    "extraction_duration": 2.5,
                    "confidence": 0.95,
                    "page_count": 1
                },
                "created_at": "2024-01-20T10:30:00Z"
            }
        }


class UploadResponse(BaseModel):
    """
    File upload response.
    """

    status: ResponseStatus = Field(default=ResponseStatus.SUCCESS)
    message: str = Field(..., description="Response message")
    document_id: str = Field(..., description="Assigned document ID")
    job_id: Optional[str] = Field(None, description="Background job ID if async")
    webhook_registered: bool = Field(default=False, description="Whether webhook was registered")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Document uploaded and extraction started",
                "document_id": "doc-123-abc",
                "job_id": "job-456-def",
                "webhook_registered": True
            }
        }


# Validation Response Model (COMMENTED OUT - not used for now)
# class ValidationResponse(BaseModel):
#     """
#     Document validation response.
#     """
#
#     status: ResponseStatus = Field(default=ResponseStatus.SUCCESS)
#     validation_id: str = Field(..., description="Validation result ID")
#     validation_type: str = Field(..., description="Type of validation performed")
#
#     passed: bool = Field(..., description="Overall validation result")
#     accuracy_percentage: float = Field(..., description="Validation accuracy percentage")
#
#     total_checks: int = Field(..., description="Total validation checks performed")
#     passed_checks: int = Field(..., description="Number of checks passed")
#     failed_checks: int = Field(..., description="Number of checks failed")
#
#     errors: List[Dict[str, Any]] = Field(default_factory=list, description="Validation errors")
#     warnings: List[Dict[str, Any]] = Field(default_factory=list, description="Validation warnings")
#
#     validated_at: datetime = Field(default_factory=datetime.utcnow)
#
#     class Config:
#         json_schema_extra = {
#             "example": {
#                 "status": "success",
#                 "validation_id": "val-789-ghi",
#                 "validation_type": "boe_invoice_validation",
#                 "passed": False,
#                 "accuracy_percentage": 85.5,
#                 "total_checks": 20,
#                 "passed_checks": 17,
#                 "failed_checks": 3,
#                 "errors": [
#                     {
#                         "field": "total_fob_value",
#                         "error_type": "value_mismatch",
#                         "expected": 10000.00,
#                         "actual": 9500.00,
#                         "severity": "high"
#                     }
#                 ],
#                 "validated_at": "2024-01-20T10:30:00Z"
#             }
#         }


class PaginatedResponse(BaseModel):
    """
    Paginated list response.
    """

    status: ResponseStatus = Field(default=ResponseStatus.SUCCESS)
    data: List[Any] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_previous: bool = Field(..., description="Whether there is a previous page")


class JobStatusResponse(BaseModel):
    """
    Background job status response.
    """

    status: ResponseStatus
    job_id: str = Field(..., description="Job identifier")
    job_status: str = Field(..., description="Job processing status")
    progress: Optional[float] = Field(None, description="Job progress percentage (0-100)")
    result: Optional[Any] = Field(None, description="Job result if completed")
    error: Optional[str] = Field(None, description="Error message if failed")
    created_at: datetime = Field(..., description="Job creation time")
    started_at: Optional[datetime] = Field(None, description="Job start time")
    completed_at: Optional[datetime] = Field(None, description="Job completion time")


class HealthResponse(BaseModel):
    """
    Health check response.
    """

    status: str = Field(..., description="Overall health status")
    version: str = Field(..., description="API version")
    environment: str = Field(..., description="Environment name")
    services: Dict[str, str] = Field(
        default_factory=dict,
        description="Status of dependent services"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ExportResponse(BaseModel):
    """
    Export response with file download information.
    """

    status: ResponseStatus = Field(default=ResponseStatus.SUCCESS)
    message: str = Field(..., description="Export status message")
    download_url: Optional[str] = Field(None, description="URL to download exported file")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    format: str = Field(..., description="Export format")
    expires_at: Optional[datetime] = Field(None, description="Download link expiration")
