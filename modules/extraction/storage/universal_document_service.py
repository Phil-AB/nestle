"""
Universal document storage service.

Provider-agnostic service for storing extracted documents.
Works with any provider (Reducto, Google Document AI, etc.) and ANY document type.
"""

from typing import Dict, Any
from datetime import datetime

from modules.extraction.storage.universal_transformer import UniversalTransformer
from src.database.connection import get_session
from src.database.repositories import get_generic_repository
from shared.contracts.responses import SavedDocumentResponse, ExtractionErrorResponse, DocumentStorageResult
from shared.utils.document_config import get_document_config
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class UniversalDocumentStorageService:
    """
    Universal service for storing extracted documents to database.

    Works with normalized universal format from any provider and ANY document type.
    Now fully generic - no type-specific code!
    """

    def __init__(self):
        """Initialize universal document storage service."""
        self.transformer = UniversalTransformer()
        self.config = get_document_config()

    async def save_document(
        self,
        document_type: str,
        universal_data: Dict[str, Any]
    ) -> DocumentStorageResult:
        """
        Transform and save document to database.

        This method is now TRULY universal - works for ANY document type
        defined in config without code changes.

        Args:
            document_type: Type of document (any type defined in config)
            universal_data: Normalized universal format from provider:
                {
                    "fields": {"invoice_number": "INV-001", ...},
                    "items": [{"line_number": 1, ...}],
                    "metadata": {"provider": "reducto", "confidence": 0.95}
                }

        Returns:
            DocumentStorageResult with success status and response

        Raises:
            ValueError: If document_type not found in config

        Example:
            service = UniversalDocumentStorageService()
            result = await service.save_document('invoice', normalized_data)
            result = await service.save_document('purchase_order', normalized_data)  # Works!
        """
        logger.info(f"Saving {document_type} document (universal format)")

        document_type = document_type.lower().strip()

        try:
            # Validate document type exists in config
            self.config.get_document_type_config(document_type)
        except ValueError as e:
            logger.error(f"Invalid document type: {document_type}")
            error_response = ExtractionErrorResponse(
                error_type="validation_error",
                error_message=str(e),
                document_type=document_type
            )
            return DocumentStorageResult(
                success=False,
                error_response=error_response
            )

        try:
            # Transform universal format to database format
            logger.info(f"Transforming {document_type} data (universal format)")
            transformed = self.transformer.transform_document(document_type, universal_data)

            header_data = transformed['header_data']
            items_data = transformed['items_data']
            extraction_status = transformed['extraction_status']
            extraction_confidence = transformed['extraction_confidence']
            raw_data = transformed['raw_data']
            saved_fields = transformed['saved_fields']
            missing_fields = transformed['missing_fields']
            items_count = transformed['items_count']

            # Extract document_id and filename from metadata and add to header_data
            metadata = universal_data.get('metadata', {})
            if metadata.get('document_id'):
                header_data['document_id'] = metadata['document_id']
            if metadata.get('filename'):
                header_data['original_filename'] = metadata['filename']

            # Get unique field name and value from config
            unique_field = self.config.get_unique_field(document_type)
            if not unique_field:
                raise ValueError(f"No unique_field configured for {document_type}")

            unique_value = header_data.get(unique_field)
            if not unique_value:
                raise ValueError(
                    f"Unique field '{unique_field}' not found in transformed data for {document_type}"
                )

            # Add extraction metadata to header
            header_data['extraction_status'] = extraction_status
            header_data['extraction_confidence'] = extraction_confidence

            # Save to database using generic repository
            async with get_session() as session:
                repo = get_generic_repository(session)

                document, was_updated = await repo.create_or_update_by_unique_field(
                    document_type=document_type,
                    unique_value=unique_value,
                    header_data=header_data,
                    items_data=items_data if items_data else None,
                    raw_data=raw_data
                )

                # Session will auto-commit via context manager

                logger.info(
                    f"{document_type.title()} saved: {unique_value} "
                    f"({'updated' if was_updated else 'created'})"
                )

                # Get document number field dynamically (could be different field names)
                # Try common patterns, fallback to unique_field
                document_number = unique_value
                for field_name in [unique_field, 'document_number', 'number']:
                    if hasattr(document, field_name):
                        doc_num_value = getattr(document, field_name)
                        if doc_num_value:
                            document_number = doc_num_value
                            break

                # Build response
                response = SavedDocumentResponse(
                    document_id=document.id,
                    document_number=document_number,
                    document_type=document_type,
                    extraction_status=extraction_status,
                    extraction_confidence=extraction_confidence,
                    saved_fields=saved_fields,
                    missing_fields=missing_fields,
                    items_count=items_count,
                    was_updated=was_updated,
                    created_at=document.created_at
                )

                return DocumentStorageResult(
                    success=True,
                    document_response=response
                )

        except Exception as e:
            logger.error(f"Failed to save {document_type}: {e}", exc_info=True)

            error_response = ExtractionErrorResponse(
                error_type="storage_error",
                error_message=str(e),
                document_type=document_type,
                details={"raw_error": str(e)}
            )

            return DocumentStorageResult(
                success=False,
                error_response=error_response
            )
