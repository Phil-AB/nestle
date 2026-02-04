"""
Documents API endpoints.

Handles document upload, extraction, and retrieval.
NOTE: This is a standalone API implementation. Integrate with main services as needed.
"""

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import FileResponse
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
import logging
from pathlib import Path
import shutil
import asyncio

from src.api.v1.models.requests import ExtractionMode
from src.api.v1.models.responses import (
    DocumentResponse,
    UploadResponse,
    ErrorResponse,
    PaginatedResponse,
    ResponseStatus,
    ExtractionStatus,
    DocumentMetadata
)
from src.api.v1.dependencies.auth import verify_api_key
from src.api.v1.dependencies.redis_rate_limiter import upload_rate_limiter, api_rate_limiter
from src.api.config import get_api_settings
from shared.utils.document_type_detector import get_configured_document_types, detect_document_type_from_fields, get_default_document_type, get_document_type_info, validate_document_type
from src.api.services.document_processing_service import get_processing_service
from modules.extraction.storage.universal_document_service import UniversalDocumentStorageService
from modules.extraction.parser.reducto_provider import ReductoProvider
from src.database.connection import get_session
from src.database.repositories.api_document_repository import APIDocumentRepository
from src.database.repositories.document_page_repository import DocumentPageRepository
from sqlalchemy.ext.asyncio import AsyncSession

# Use standard Python logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_api_settings()
router = APIRouter(prefix="/documents", tags=["documents"])

# Processing service instance (can work with or without database)
processing_service = get_processing_service(use_database=False)


async def get_db_session():
    """Dependency to get database session."""
    async with get_session() as session:
        yield session


async def _parse_document_background(document_id: str, file_path: Path, document_type: str, extraction_mode: str):
    """Background task to parse and extract document data."""
    try:
        logger.info(f"Starting background parsing for document: {document_id}")

        # Process the document using the integrated service
        result = await processing_service.process_document(
            file_path=file_path,
            document_type=document_type,
            extraction_mode=extraction_mode
        )

        # Update document in database
        async with get_session() as session:
            repo = APIDocumentRepository(session)

            # Determine extraction status
            if result.get("status") == "failed":
                extraction_status = ExtractionStatus.FAILED
                logger.error(f"Extraction failed: {result.get('metadata', {}).get('error')}")
            elif result.get("status") == "complete":
                extraction_status = ExtractionStatus.COMPLETE
                logger.info(f"Extraction complete: {len(result.get('fields', {}))} fields, {len(result.get('items', []))} items")
            else:
                extraction_status = ExtractionStatus.INCOMPLETE

            # Update extraction results in database
            updated_doc = await repo.update_extraction_result(
                document_id=document_id,
                fields=result.get("fields", {}),
                items=result.get("items", []),
                blocks=result.get("blocks", []),
                metadata=result.get("metadata", {}),
                extraction_status=extraction_status,
                raw_provider_response=result.get("raw_provider_response")
            )

            if updated_doc:
                logger.info(f"Completed parsing for document: {document_id}")
            else:
                logger.warning(f"Document {document_id} not found in database")

    except Exception as e:
        logger.error(f"Background parsing failed for {document_id}: {e}", exc_info=True)
        try:
            async with get_session() as session:
                repo = APIDocumentRepository(session)
                await repo.update(document_id, {
                    "extraction_status": ExtractionStatus.FAILED,
                    "doc_metadata": {"error": str(e)}
                })
        except Exception as db_error:
            logger.error(f"Failed to update error status in database: {db_error}")


def _save_uploaded_file(file: UploadFile, document_id: str, page_number: Optional[int] = None) -> Path:
    """Save uploaded file to disk."""
    upload_dir = Path(settings.UPLOAD_DIRECTORY)
    
    # For multi-page documents, create subdirectory
    if page_number is not None:
        upload_dir = upload_dir / document_id
    
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_extension = file.filename.split(".")[-1] if file.filename else "bin"
    
    if page_number is not None:
        file_path = upload_dir / f"page_{page_number}.{file_extension}"
    else:
        file_path = upload_dir / f"{document_id}.{file_extension}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return file_path


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and extract document",
    description="Upload a document file for extraction and processing",
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Document file to upload"),
    document_type: Optional[str] = Query(default=None, description="Type of document from dropdown"),
    document_name: Optional[str] = Query(default=None, description="User-provided document name"),
    extraction_mode: ExtractionMode = Query(default=ExtractionMode.OPEN, description="Extraction mode (forced to OPEN for better structure recognition)"),
    shipment_id: Optional[str] = Query(default=None, description="Optional shipment ID"),
    api_key: str = Depends(verify_api_key),
    _rate_limit: None = Depends(upload_rate_limiter),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Upload a document and start extraction.

    **Supported File Types**: PDF, PNG, JPG, JPEG, TIFF, XLSX, XLS
    **Document Types**: Any string - system handles all document types dynamically
    """
    try:
        # Validate file extension
        if file.filename:
            extension = file.filename.split(".")[-1].lower()
            if extension not in settings.ALLOWED_EXTENSIONS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File type '.{extension}' not allowed. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
                )

        # Validate file size
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)

        if file_size > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE / 1024 / 1024}MB"
            )

        # Generate document ID
        document_id = str(uuid.uuid4())

        # Save file
        file_path = _save_uploaded_file(file, document_id)
        logger.info(f"Saved uploaded file: {file_path}")

        # Create document record in database
        repo = APIDocumentRepository(session)

        document = await repo.create({
            "document_id": document_id,
            "document_type": document_type,
            "document_name": document_name or file.filename or "unknown",
            "filename": file.filename,
            "file_path": str(file_path),
            "file_size": file_size,
            "extraction_mode": extraction_mode,
            "extraction_status": ExtractionStatus.PROCESSING,
            "shipment_id": shipment_id,
            "fields": {},
            "items": [],
            "blocks": [],
            "doc_metadata": {},
            "items_count": 0,
            "fields_count": 0,
        })

        # Start background parsing
        background_tasks.add_task(
            _parse_document_background,
            document_id=document_id,
            file_path=file_path,
            document_type=document_type,
            extraction_mode=extraction_mode
        )

        logger.info(f"Document uploaded: {document_id} ({document_type}), parsing started in background")

        return UploadResponse(
            status=ResponseStatus.SUCCESS,
            message="Document uploaded successfully. Extraction in progress.",
            document_id=document_id,
            job_id=f"job-{document_id}",
            webhook_registered=False
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document"
        )

# IMPORTANT: Specific routes must come BEFORE path parameters like /{document_id}
@router.get(
    "/document-types",
    summary="Get available document types",
    description="Get list of all configured document types with their metadata",
)
async def get_document_types(api_key: str = Depends(verify_api_key)):
    """
    Get all configured document types with their metadata.

    Returns:
        Dictionary with document types array and categories
    """
    try:
        # Get all document type configs
        document_types_info = get_document_type_info("all")

        # Transform to frontend format: array of types with id field
        types_array = []
        categories_set = set()

        for doc_id, doc_info in document_types_info.items():
            types_array.append({
                "id": doc_id,
                "display_name": doc_info.get("display_name", doc_id),
                "description": doc_info.get("description", ""),
                "category": doc_info.get("category", "other"),
                "icon": doc_info.get("icon", "file")
            })
            categories_set.add(doc_info.get("category", "other"))

        # Sort alphabetically by display name
        types_array.sort(key=lambda x: x["display_name"].lower())

        return {
            "types": types_array,
            "categories": sorted(list(categories_set))
        }
    except Exception as e:
        logger.error(f"Failed to get document types: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document types"
        )


@router.get(
    "/stats",
    summary="Get document statistics",
    description="Get dashboard statistics including document counts, success rates, and recent activity",
)
async def get_document_stats(
    api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Get document statistics for the dashboard.

    Returns:
        Dictionary with total documents, status breakdown, success rate,
        and recent documents
    """
    try:
        repo = APIDocumentRepository(session)

        # Get base statistics
        stats = await repo.get_stats()

        # Calculate success rate
        total = stats.get("total", 0)
        complete = stats.get("by_status", {}).get("complete", 0)
        success_rate = round((complete / total * 100) if total > 0 else 0, 1)

        # Get recent documents (last 5)
        recent_docs, _ = await repo.list_documents(limit=5, offset=0)

        # Build recent activity list
        recent_activity = []
        for doc in recent_docs:
            status_label = {
                "processing": "Document Processing",
                "complete": "Document Processed",
                "failed": "Processing Failed",
                "incomplete": "Processing Incomplete",
            }.get(doc.extraction_status, "Document Updated")

            recent_activity.append({
                "activity": status_label,
                "document_id": doc.document_id,
                "document_name": doc.document_name or doc.filename,
                "document_type": doc.document_type,
                "status": doc.extraction_status,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
            })

        # Get documents generated count (from approved documents)
        approved_count = stats.get("by_status", {}).get("complete", 0)

        return {
            "status": ResponseStatus.SUCCESS,
            "data": {
                "total_documents": total,
                "extraction_success": success_rate,
                "documents_generated": approved_count,
                "pending_documents": stats.get("by_status", {}).get("processing", 0),
                "by_status": stats.get("by_status", {}),
                "by_type": stats.get("by_type", {}),
            },
            "recent_activity": recent_activity,
        }

    except Exception as e:
        logger.error(f"Failed to get document stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document statistics"
        )


@router.get(
    "/{document_id}",
    summary="Get document by ID",
    description="Retrieve a specific document and its extracted data. Use format=raw for original Reducto structure.",
)
async def get_document(
    document_id: str,
    format: str = Query(default="normalized", description="Response format: 'normalized' (processed, for UI) or 'raw' (original Reducto)"),
    include_raw_data: bool = Query(default=False, description="Include raw parser data"),
    include_layout: bool = Query(default=False, description="Include layout data"),
    api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_db_session),
):
    """Get a specific document by ID. Returns normalized format by default for UI compatibility."""

    repo = APIDocumentRepository(session)
    document = await repo.get_by_document_id(document_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found"
        )

    # Return RAW Reducto format if explicitly requested
    if format == "raw" and document.raw_provider_response:
        return document.raw_provider_response

    # Otherwise return normalized format
    fields = document.fields or {}
    items = document.items or []
    blocks = document.blocks or []

    return DocumentResponse(
        status=ResponseStatus.SUCCESS,
        document_id=document.document_id,
        document_type=document.document_type,
        document_number=fields.get("document_number") or fields.get("invoice_number"),
        extraction_status=document.extraction_status,
        fields=fields,
        items=items,
        blocks=blocks if blocks else None,
        fields_count=len(fields),
        items_count=len(items),
        saved_fields=list(fields.keys()),
        missing_fields=[],
        created_at=document.created_at,
        updated_at=document.updated_at,
        metadata=DocumentMetadata(
            provider=document.doc_metadata.get("provider", "api") if document.doc_metadata else "api",
            extraction_duration=document.doc_metadata.get("extraction_duration") if document.doc_metadata else None,
            confidence=document.extraction_confidence,
            page_count=document.doc_metadata.get("page_count") if document.doc_metadata else None,
            job_id=document.doc_metadata.get("job_id") if document.doc_metadata else None
        )
    )


@router.get(
    "/",
    response_model=PaginatedResponse,
    summary="List documents",
    description="Get a paginated list of documents with optional filtering",
)
async def list_documents(
    document_type: Optional[str] = Query(default=None, description="Filter by document type"),
    extraction_status: Optional[ExtractionStatus] = Query(default=None, description="Filter by status"),
    shipment_id: Optional[str] = Query(default=None, description="Filter by shipment ID"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=100, description="Items per page"),
    api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_db_session),
):
    """List all documents with optional filtering."""

    repo = APIDocumentRepository(session)

    # Get paginated documents from database
    api_docs, total = await repo.list_documents(
        document_type=document_type,
        extraction_status=extraction_status,
        shipment_id=shipment_id,
        limit=page_size,
        offset=(page - 1) * page_size
    )

    # Convert to response format
    documents = []
    for doc in api_docs:
        fields = doc.fields or {}
        documents.append({
            "document_id": doc.document_id,  # Fixed: Use document_id instead of id for consistency
            "document_type": doc.document_type,
            "document_name": doc.document_name,
            "document_number": fields.get("document_number") or fields.get("invoice_number"),
            "extraction_status": doc.extraction_status,
            "items_count": doc.items_count or 0,
            "fields_count": len(fields) if fields else 0,  # Add fields_count
            "is_multi_page": doc.is_multi_page if hasattr(doc, 'is_multi_page') else False,  # Add multi-page flag
            "total_pages": doc.total_pages if hasattr(doc, 'total_pages') else 1,  # Add total pages
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None
        })

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return PaginatedResponse(
        status=ResponseStatus.SUCCESS,
        data=documents,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_previous=page > 1
    )


@router.patch(
    "/{document_id}/fields",
    response_model=DocumentResponse,
    summary="Update document fields",
    description="Update specific field values in a document. Works universally with any document type.",
)
async def update_document_fields(
    document_id: str,
    update_request: Dict[str, Any],
    api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Update document field values.

    This is a universal endpoint that works with ANY document type.
    Accepts a dictionary of field updates and applies them to the document.
    """

    repo = APIDocumentRepository(session)
    doc = await repo.get_by_document_id(document_id)

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found"
        )

    # Get field updates from request
    field_updates = update_request.get("field_updates", {})
    update_metadata = update_request.get("update_metadata", {})

    if not field_updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No field updates provided"
        )

    # Get current fields and update them
    fields = doc.fields or {}

    # Apply field updates
    for field_key, new_value in field_updates.items():
        # Update the field value while preserving metadata (bbox, confidence, etc.)
        if field_key in fields:
            # Field exists - update its value
            if isinstance(fields[field_key], dict) and "value" in fields[field_key]:
                fields[field_key]["value"] = new_value
            else:
                fields[field_key] = new_value
        else:
            # New field - just set the value
            fields[field_key] = new_value

    # Update blocks if they contain the changed fields
    blocks = doc.blocks or []
    if blocks:
        import re
        for block in blocks:
            if block.get("type") in ["Key Value", "Text"]:
                # Update field values in block content
                content = block.get("content", "")
                for field_key, new_value in field_updates.items():
                    # Match "Field Name: old_value" and replace with new value
                    pattern = rf"({re.escape(field_key)}:\s*)([^\n]*)"
                    content = re.sub(pattern, rf"\1{new_value}", content, flags=re.IGNORECASE)
                block["content"] = content

    # Add update history to metadata
    metadata = doc.doc_metadata or {}
    if "update_history" not in metadata:
        metadata["update_history"] = []

    metadata["update_history"].append({
        "timestamp": datetime.utcnow().isoformat(),
        "field_updates": field_updates,
        "metadata": update_metadata
    })

    # Update document in database
    await repo.update(document_id, {
        "fields": fields,
        "blocks": blocks,
        "doc_metadata": metadata,
        "fields_count": len(fields)
    })

    logger.info(f"Document {document_id} fields updated: {list(field_updates.keys())}")

    # Get updated document
    updated_doc = await repo.get_by_document_id(document_id)
    fields = updated_doc.fields or {}

    return DocumentResponse(
        status=ResponseStatus.SUCCESS,
        document_id=updated_doc.document_id,
        document_type=updated_doc.document_type,
        document_number=fields.get("document_number") or fields.get("invoice_number"),
        extraction_status=ExtractionStatus(updated_doc.extraction_status),
        fields=updated_doc.fields,
        items=updated_doc.items,
        blocks=updated_doc.blocks,
        metadata=DocumentMetadata(
            provider=updated_doc.doc_metadata.get("provider", "unknown") if updated_doc.doc_metadata else "unknown",
            extraction_duration=updated_doc.doc_metadata.get("extraction_duration") if updated_doc.doc_metadata else None,
            confidence=updated_doc.extraction_confidence,
            page_count=updated_doc.doc_metadata.get("page_count") if updated_doc.doc_metadata else None,
            job_id=updated_doc.doc_metadata.get("job_id") if updated_doc.doc_metadata else None,
        ) if updated_doc.doc_metadata else None,
        created_at=updated_doc.created_at,
        updated_at=updated_doc.updated_at,
        message=f"Updated {len(field_updates)} field(s)"
    )


@router.post(
    "/{document_id}/approve",
    response_model=DocumentResponse,
    summary="Approve and save document",
    description="Approve the document and save all extracted data (with edits) to the database",
)
async def approve_document(
    document_id: str,
    approval_data: Dict[str, Any],
    api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Approve and save document to database.

    This endpoint:
    1. Saves all extracted data (original + edits)
    2. Marks document as approved
    3. Persists to database

    Request body should contain:
    {
        "blocks": [...],  # All document blocks with edits
        "metadata": {...}  # Approval metadata
    }
    """

    repo = APIDocumentRepository(session)
    doc = await repo.get_by_document_id(document_id)

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found"
        )

    try:
        # Extract data from approval request
        blocks = approval_data.get("blocks", [])
        approval_metadata = approval_data.get("metadata", {})

        # Get existing document metadata for AI enhancement tracking
        doc_metadata = doc.doc_metadata or {}

        # RE-EXTRACT fields and items from edited blocks
        # This ensures any user edits in the UI are reflected in all database columns
        logger.info(f"Re-extracting fields and items from {len(blocks)} edited blocks")
        reducto_provider = ReductoProvider()

        # Create a parse_result structure that matches what _extract_from_parse_chunks expects
        mock_parse_result = {
            "chunks": [{
                "blocks": blocks
            }]
        }

        # Extract fields, items, and blocks from the edited content
        extracted_fields, extracted_items, _ = reducto_provider._extract_from_parse_chunks(mock_parse_result)

        logger.info(f"Re-extracted {len(extracted_fields)} fields and {len(extracted_items)} items from edited blocks")

        # AI Semantic Enhancement - Add intelligent parsing for section-based content
        # This adds fields like exporter_name, consignee_address that Reducto misses
        try:
            from modules.extraction.parser.ai_semantic_enhancer import get_ai_enhancer

            ai_enhancer = get_ai_enhancer()
            if ai_enhancer:
                logger.info("🤖 Running AI Semantic Enhancement on approve flow...")

                # Prepare data for AI enhancement
                raw_extraction = {
                    "fields": extracted_fields,
                    "items": extracted_items,
                    "blocks": blocks
                }

                # Run AI enhancement
                enhancement_result = await ai_enhancer.enhance_extraction(
                    raw_extraction,
                    doc.document_type
                )

                # Merge AI-enhanced fields
                enhanced_fields = enhancement_result.get("fields", {})
                if enhanced_fields:
                    original_count = len(extracted_fields)
                    extracted_fields.update(enhanced_fields)
                    new_count = len(extracted_fields)

                    logger.info(
                        f"✅ AI Enhancement added {new_count - original_count} fields "
                        f"({original_count} → {new_count} total)"
                    )

                    # Update metadata with AI enhancement info
                    doc_metadata["ai_enhancement"] = enhancement_result.get("metadata", {})

        except Exception as ai_error:
            logger.warning(f"AI Enhancement failed in approve flow (continuing without): {ai_error}")
            # Don't fail the approve process if AI enhancement fails

        # Update document metadata with approval info
        doc_metadata["approval_metadata"] = approval_metadata
        doc_metadata["approved"] = True
        doc_metadata["approved_at"] = datetime.utcnow().isoformat()

        # Update document in database with edited blocks AND re-extracted fields/items
        await repo.update(document_id, {
            "blocks": blocks,
            "fields": extracted_fields,
            "items": extracted_items,
            "fields_count": len(extracted_fields),
            "items_count": len(extracted_items),
            "doc_metadata": doc_metadata
        })

        # Save to actual database (universal document storage)
        try:
            storage_service = UniversalDocumentStorageService()

            # Detect document type from extracted fields
            detected_type = doc.document_type.lower()

            # TODO(human): Replace hardcoded document type detection with configurable rules from document_types.yaml
            # Map generic "document" to specific type based on configurable detection rules
            if detected_type == "document" or detected_type not in get_configured_document_types():
                # Use re-extracted fields for type detection
                detected_type = detect_document_type_from_fields(extracted_fields)
                if not detected_type:
                    # Default to configurable fallback type
                    default_type = get_default_document_type()
                    logger.warning(f"Could not determine document type, defaulting to '{default_type}'")
                    detected_type = default_type

            logger.info(f"Document type detected/confirmed as: {detected_type}")

            # Prepare data for database storage with RE-EXTRACTED fields and items
            universal_data = {
                "fields": extracted_fields,  # Use re-extracted fields
                "items": extracted_items,    # Use re-extracted items
                "metadata": {
                    "document_id": doc.document_id,
                    "filename": doc.filename,
                    "provider": doc_metadata.get("provider", "api"),
                    "confidence": doc.extraction_confidence,
                    "extraction_duration": doc_metadata.get("extraction_duration"),
                    "page_count": doc_metadata.get("page_count"),
                    "approved": True,
                    "approved_at": doc_metadata["approved_at"],
                    "blocks": blocks
                }
            }

            # Save to database
            result = await storage_service.save_document(
                document_type=detected_type,
                universal_data=universal_data
            )

            if result.success:
                logger.info(f"Document {document_id} approved and saved to database ({len(blocks)} blocks)")
            else:
                logger.warning(f"Document {document_id} approved but database save failed: {result.error_response}")

        except Exception as db_error:
            logger.error(f"Database save error for {document_id}: {db_error}", exc_info=True)

        logger.info(f"Document {document_id} processing complete ({len(blocks)} blocks)")

        # Get updated document
        updated_doc = await repo.get_by_document_id(document_id)
        fields = updated_doc.fields or {}
        items = updated_doc.items or []

        return DocumentResponse(
            status=ResponseStatus.SUCCESS,
            document_id=updated_doc.document_id,
            document_type=updated_doc.document_type,
            document_number=fields.get("document_number") or fields.get("invoice_number"),
            extraction_status=ExtractionStatus(updated_doc.extraction_status),
            fields=fields,
            items=items,
            blocks=blocks,
            fields_count=len(fields),
            items_count=len(items),
            saved_fields=list(fields.keys()),
            missing_fields=[],
            metadata=DocumentMetadata(
                provider=updated_doc.doc_metadata.get("provider", "unknown") if updated_doc.doc_metadata else "unknown",
                extraction_duration=updated_doc.doc_metadata.get("extraction_duration") if updated_doc.doc_metadata else None,
                confidence=updated_doc.extraction_confidence,
                page_count=updated_doc.doc_metadata.get("page_count") if updated_doc.doc_metadata else None,
                job_id=updated_doc.doc_metadata.get("job_id") if updated_doc.doc_metadata else None,
            ) if updated_doc.doc_metadata else None,
            created_at=updated_doc.created_at,
            updated_at=updated_doc.updated_at,
            message=f"Document approved and saved ({len(blocks)} blocks)"
        )

    except Exception as e:
        logger.error(f"Failed to approve document {document_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve document: {str(e)}"
        )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete document",
    description="Delete a document and its associated data",
)
async def delete_document(
    document_id: str,
    api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_db_session),
):
    """Delete a document."""

    repo = APIDocumentRepository(session)
    doc = await repo.get_by_document_id(document_id)

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found"
        )

    # Delete file if exists
    if doc.file_path:
        file_path = Path(doc.file_path)
        if file_path.exists():
            file_path.unlink()

    # Remove from database
    deleted = await repo.delete(document_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document from database"
        )

    logger.info(f"Document deleted: {document_id}")
    return None


@router.get(
    "/{document_id}/file",
    summary="Get original document file",
    description="Retrieve the original uploaded document file for viewing",
)
async def get_document_file(
    document_id: str,
    api_key: str = Query(None, description="API key for authentication"),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Serve original document file for viewing.

    Returns the original uploaded file (PDF, image, etc.) for display in the UI.
    Supports PDF, PNG, JPG, JPEG, TIFF formats with proper MIME types.

    Note: Authentication is relaxed for this endpoint since it's proxied through Next.js.
    In production, implement proper session-based authentication.
    """

    repo = APIDocumentRepository(session)
    doc = await repo.get_by_document_id(document_id)

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found"
        )

    file_path = Path(doc.file_path)

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found on disk"
        )

    # Determine MIME type from file extension
    ext = file_path.suffix.lower()
    mime_types = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
    }

    mime_type = mime_types.get(ext, "application/octet-stream")
    original_filename = doc.filename or f"document{ext}"

    logger.info(f"Serving file for document {document_id}: {original_filename} ({mime_type})")

    return FileResponse(
        path=file_path,
        media_type=mime_type,
        filename=original_filename,
        headers={
            "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
        }
    )


# ==============================================================================
# UNIVERSAL DOCUMENT TYPE ENDPOINTS
# ==============================================================================

@router.post(
    "/multi-page",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload multi-page document",
    description="Upload multiple files as pages of a single document",
)
async def upload_multi_page_document(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(..., description="Document pages to upload"),
    document_type: str = Query(..., description="Type of document"),
    extraction_mode: ExtractionMode = Query(default=ExtractionMode.OPEN, description="Extraction mode (forced to OPEN for better structure recognition)"),
    shipment_id: Optional[str] = Query(default=None, description="Optional shipment ID"),
    document_name: Optional[str] = Query(default=None, description="Optional document name"),
    api_key: str = Depends(verify_api_key),
    _rate_limit: None = Depends(upload_rate_limiter),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Upload multiple pages as a single document.
    
    Pages will be processed in the order they are uploaded.
    Results will be merged into a single document.
    """
    try:
        if not files or len(files) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one file is required"
            )
        
        # Generate document ID
        document_id = str(uuid.uuid4())
        
        # Validate all files first
        total_size = 0
        for idx, file in enumerate(files):
            if file.filename:
                extension = file.filename.split(".")[-1].lower()
                if extension not in settings.ALLOWED_EXTENSIONS:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"File {idx + 1} type '.{extension}' not allowed"
                    )
            
            # Get file size
            file.file.seek(0, 2)
            file_size = file.file.tell()
            file.file.seek(0)
            total_size += file_size
        
        if total_size > settings.MAX_UPLOAD_SIZE * len(files):
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Total file size too large"
            )
        
        # Create parent document record
        repo = APIDocumentRepository(session)
        document = await repo.create({
            "document_id": document_id,
            "document_type": document_type,
            "document_name": document_name or f"multipage_{len(files)}_pages",
            "filename": f"{len(files)}_pages.pdf",
            "file_path": str(Path(settings.UPLOAD_DIRECTORY) / document_id),
            "file_size": total_size,
            "extraction_mode": extraction_mode,
            "extraction_status": ExtractionStatus.PROCESSING,
            "shipment_id": shipment_id,
            "is_multi_page": True,
            "total_pages": len(files),
            "fields": {},
            "items": [],
            "blocks": [],
            "doc_metadata": {},
            "items_count": 0,
            "fields_count": 0,
        })
        
        # Save pages and create page records
        page_repo = DocumentPageRepository(session)
        page_paths = []
        
        for page_number, file in enumerate(files, start=1):
            # Save file
            file_path = _save_uploaded_file(file, document_id, page_number)
            page_paths.append(file_path)
            
            # Get file size
            file.file.seek(0, 2)
            file_size = file.file.tell()
            file.file.seek(0)
            
            # Create page record
            await page_repo.create_page(
                document_id=document_id,
                page_number=page_number,
                file_path=str(file_path),
                file_name=file.filename or f"page_{page_number}",
                file_size=file_size,
                mime_type=file.content_type
            )
            
            logger.info(f"Saved page {page_number}/{len(files)} for document {document_id}")
        
        await session.commit()
        
        # Start background extraction for all pages
        background_tasks.add_task(
            _parse_multi_page_document_background,
            document_id=document_id,
            page_paths=page_paths,
            document_type=document_type,
            extraction_mode=extraction_mode
        )
        
        logger.info(f"Multi-page document uploaded: {document_id} ({len(files)} pages)")
        
        return UploadResponse(
            status=ResponseStatus.SUCCESS,
            message=f"Multi-page document uploaded successfully. {len(files)} pages being processed.",
            document_id=document_id,
            job_id=f"job-{document_id}",
            webhook_registered=False
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Multi-page upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload multi-page document"
        )


@router.get(
    "/{document_id}/pages",
    summary="Get document pages",
    description="Get all pages for a multi-page document",
)
async def get_document_pages(
    document_id: str,
    api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_db_session),
):
    """Get all pages for a multi-page document."""
    try:
        # Check document exists
        repo = APIDocumentRepository(session)
        document = await repo.get_by_id(document_id)
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        # Get pages
        page_repo = DocumentPageRepository(session)
        pages = await page_repo.get_document_pages(document_id)
        
        return {
            "status": "success",
            "document_id": document_id,
            "is_multi_page": document.is_multi_page,
            "total_pages": document.total_pages,
            "pages": [page.to_dict() for page in pages]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pages: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve pages"
        )


@router.put(
    "/{document_id}/pages/reorder",
    summary="Reorder document pages",
    description="Change the order of pages in a multi-page document",
)
async def reorder_document_pages(
    document_id: str,
    page_order: List[str],
    api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_db_session),
):
    """
    Reorder pages for a document.
    
    Args:
        document_id: Document ID
        page_order: List of page IDs in desired order
    """
    try:
        # Check document exists
        repo = APIDocumentRepository(session)
        document = await repo.get_by_id(document_id)
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )
        
        if not document.is_multi_page:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document is not multi-page"
            )
        
        # Reorder pages
        page_repo = DocumentPageRepository(session)
        success = await page_repo.reorder_pages(document_id, page_order)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reorder pages"
            )
        
        await session.commit()
        
        return {
            "status": "success",
            "message": "Pages reordered successfully",
            "document_id": document_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reorder pages: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reorder pages"
        )


@router.get(
    "/{document_id}/pages/{page_number}/file",
    response_class=FileResponse,
    summary="Download page file",
    description="Download the original file for a specific page",
)
async def download_page_file(
    document_id: str,
    page_number: int,
    api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_db_session),
):
    """Download the original file for a specific page."""
    try:
        page_repo = DocumentPageRepository(session)
        page = await page_repo.get_page_by_number(document_id, page_number)
        
        if not page:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Page not found"
            )
        
        file_path = Path(page.file_path)
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Page file not found on disk"
            )
        
        return FileResponse(
            path=str(file_path),
            filename=page.file_name,
            media_type=page.mime_type or "application/octet-stream"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download page file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download page file"
        )


async def _parse_multi_page_document_background(
    document_id: str,
    page_paths: List[Path],
    document_type: str,
    extraction_mode: str
):
    """Background task to parse multi-page document."""
    try:
        logger.info(f"Starting multi-page extraction for document: {document_id} ({len(page_paths)} pages)")
        
        async with get_session() as session:
            page_repo = DocumentPageRepository(session)
            pages = await page_repo.get_document_pages(document_id)
            
            # Extract each page
            page_results = []
            for page, page_path in zip(pages, page_paths):
                try:
                    # Update page status to processing
                    await page_repo.update_page_status(page.page_id, "processing")
                    await session.commit()
                    
                    # Process page
                    result = await processing_service.process_document(
                        file_path=page_path,
                        document_type=document_type,
                        extraction_mode=extraction_mode
                    )
                    
                    # Store page result
                    if result.get("status") == "complete":
                        await page_repo.update_page_status(
                            page.page_id,
                            "completed",
                            extraction_result=result
                        )
                        page_results.append(result)
                    else:
                        await page_repo.update_page_status(
                            page.page_id,
                            "failed",
                            error_message=result.get("metadata", {}).get("error", "Extraction failed")
                        )
                    
                    await session.commit()
                    logger.info(f"Completed extraction for page {page.page_number}/{len(pages)}")
                    
                except Exception as e:
                    logger.error(f"Failed to extract page {page.page_number}: {e}")
                    await page_repo.update_page_status(page.page_id, "failed", error_message=str(e))
                    await session.commit()
            
            # Merge results
            merged_result = _merge_page_results(page_results)
            
            # Update parent document
            repo = APIDocumentRepository(session)
            extraction_status = ExtractionStatus.COMPLETE if len(page_results) == len(pages) else ExtractionStatus.INCOMPLETE
            
            await repo.update(document_id, {
                "extraction_status": extraction_status,
                "fields": merged_result.get("fields", {}),
                "items": merged_result.get("items", []),
                "blocks": merged_result.get("blocks", []),
                "doc_metadata": merged_result.get("metadata", {}),
                "fields_count": len(merged_result.get("fields", {})),
                "items_count": len(merged_result.get("items", [])),
                "parsed_at": datetime.now()
            })
            
            await session.commit()
            logger.info(f"Multi-page extraction complete: {document_id} ({len(page_results)}/{len(pages)} pages succeeded)")
            
    except Exception as e:
        logger.error(f"Multi-page extraction failed: {e}", exc_info=True)
        try:
            async with get_session() as session:
                repo = APIDocumentRepository(session)
                await repo.update(document_id, {
                    "extraction_status": ExtractionStatus.FAILED,
                    "doc_metadata": {"error": str(e)}
                })
                await session.commit()
        except Exception as db_error:
            logger.error(f"Failed to update error status: {db_error}")


def _merge_page_results(page_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge extraction results from multiple pages.
    
    Strategy:
    - Fields: Use first page for header fields, merge unique fields
    - Items: Concatenate all items across pages
    - Blocks: Concatenate all blocks with page markers
    """
    if not page_results:
        return {"fields": {}, "items": [], "blocks": [], "metadata": {}}
    
    # Start with first page fields as base
    merged_fields = page_results[0].get("fields", {}).copy()
    
    # Merge unique fields from other pages
    for result in page_results[1:]:
        for key, value in result.get("fields", {}).items():
            # Only add if not in merged yet (prioritize first page)
            if key not in merged_fields:
                merged_fields[key] = value
    
    # Concatenate all items
    merged_items = []
    for result in page_results:
        merged_items.extend(result.get("items", []))
    
    # Concatenate blocks with page markers
    merged_blocks = []
    for page_num, result in enumerate(page_results, start=1):
        # Add page marker block
        merged_blocks.append({
            "type": "page_marker",
            "page_number": page_num,
            "text": f"--- Page {page_num} ---"
        })
        merged_blocks.extend(result.get("blocks", []))
    
    # Merge metadata
    merged_metadata = {
        "total_pages": len(page_results),
        "pages_processed": len(page_results),
        "merge_strategy": "first_page_fields_with_concatenated_items"
    }
    
    return {
        "fields": merged_fields,
        "items": merged_items,
        "blocks": merged_blocks,
        "metadata": merged_metadata,
        "status": "complete"
    }


@router.get(
    "/document-types/{document_type}",
    summary="Get document type details",
    description="Get detailed information about a specific document type",
)
async def get_document_type_details(
    document_type: str,
    api_key: str = Depends(verify_api_key)
):
    """
    Get detailed information about a specific document type.

    Args:
        document_type: Document type identifier

    Returns:
        Document type configuration and schema
    """
    try:
        # Validate document type exists
        if not validate_document_type(document_type):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document type '{document_type}' not found"
            )

        # Get document type info
        type_info = get_document_type_info(document_type)

        # Get extraction schema
        from shared.contracts.reducto_schemas import get_schema
        schema = get_schema(document_type)

        return {
            "status": "success",
            "document_type": document_type,
            "info": type_info,
            "extraction_schema": schema,
            "detection_rules": get_detection_rules_for_type(document_type)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document type details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document type details"
        )


def get_detection_rules_for_type(document_type: str) -> Dict[str, Any]:
    """Get detection rules for a specific document type."""
    try:
        from shared.utils.document_type_detector import _load_document_types_config
        config = _load_document_types_config()
        detection_rules = config.get('detection_rules', {})
        return detection_rules.get(document_type, {})
    except:
        return {}
