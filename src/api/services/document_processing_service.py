"""
Document processing service for API.

Integrates with the existing parser and storage services.
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
import os

logger = logging.getLogger(__name__)


class DocumentProcessingService:
    """
    Service that orchestrates document processing using existing system components.

    This service can work in two modes:
    1. With database - Full integration with parser, storage, and database
    2. Without database - Parser only (returns extracted data without saving)
    """

    def __init__(self, use_database: bool = False, use_ai_enhancement: bool = True):
        """
        Initialize document processing service.

        Args:
            use_database: Whether to use database integration
            use_ai_enhancement: Whether to use AI semantic enhancement (default: True)
        """
        self.use_database = use_database
        self.use_ai_enhancement = use_ai_enhancement
        self._parser_provider = None
        self._schema_generator = None
        self._storage_service = None
        self._ai_enhancer = None

        logger.info(
            f"Initialized DocumentProcessingService "
            f"(database: {use_database}, AI enhancement: {use_ai_enhancement})"
        )

    def _get_parser_provider(self):
        """Lazy load parser provider to avoid import errors if not configured."""
        if self._parser_provider is None:
            try:
                from modules.extraction.parser.provider_factory import get_active_provider
                self._parser_provider = get_active_provider()
                logger.info("Parser provider initialized successfully")
            except Exception as e:
                logger.warning(f"Could not initialize parser provider: {e}")
                self._parser_provider = None
        return self._parser_provider

    def _get_schema_generator(self):
        """Lazy load schema generator."""
        if self._schema_generator is None:
            try:
                from modules.extraction.parser.schema_generator import SchemaGenerator
                self._schema_generator = SchemaGenerator()
                logger.info("Schema generator initialized successfully")
            except Exception as e:
                logger.warning(f"Could not initialize schema generator: {e}")
                self._schema_generator = None
        return self._schema_generator

    def _get_storage_service(self):
        """Lazy load storage service (only if database mode)."""
        if not self.use_database:
            return None

        if self._storage_service is None:
            try:
                from modules.extraction.storage.universal_document_service import UniversalDocumentStorageService
                self._storage_service = UniversalDocumentStorageService()
                logger.info("Storage service initialized successfully")
            except Exception as e:
                logger.warning(f"Could not initialize storage service: {e}")
                self._storage_service = None
        return self._storage_service

    def _get_ai_enhancer(self):
        """Lazy load AI semantic enhancer (only if AI enhancement enabled)."""
        if not self.use_ai_enhancement:
            return None

        if self._ai_enhancer is None:
            try:
                from modules.extraction.parser.ai_semantic_enhancer import get_ai_enhancer
                self._ai_enhancer = get_ai_enhancer()
                logger.info("AI Semantic Enhancer initialized successfully")
            except Exception as e:
                logger.warning(f"Could not initialize AI Semantic Enhancer: {e}")
                self._ai_enhancer = None
        return self._ai_enhancer

    async def process_document(
        self,
        file_path: Path,
        document_type: str,
        extraction_mode: str = "open"
    ) -> Dict[str, Any]:
        """
        Process a document: parse, extract, and optionally save to database.

        Supports ANY document type - works with:
        - Configured document types (uses config for validation)
        - Unknown document types (uses open extraction, preserves all structure)

        Args:
            file_path: Path to uploaded file
            document_type: Type of document (any string - system handles all types)
            extraction_mode: "focused" (requires config) or "open" (extracts everything)

        Returns:
            Extracted data in universal format with structure preserved:
            {
                "fields": {...},  # All extracted fields
                "items": [...],   # Line items if detected
                "metadata": {
                    "provider": "reducto",
                    "layout": {...},  # Structure preserved: bboxes, pages, tables
                    "has_config": true/false
                },
                "status": "complete/failed"
            }
        """
        try:
            logger.info(
                f"Processing document: {file_path} "
                f"(type: {document_type}, mode: {extraction_mode})"
            )

            # Get components
            parser = self._get_parser_provider()
            schema_gen = self._get_schema_generator()

            if not parser or not schema_gen:
                logger.error("Parser or schema generator not available")
                return {
                    "fields": {},
                    "items": [],
                    "metadata": {"error": "Parser not configured"},
                    "status": "failed"
                }

            # Read file
            with open(file_path, 'rb') as f:
                file_bytes = f.read()

            file_name = file_path.name

            # Force OPEN mode for better structure recognition
            # OPEN mode extracts everything without schema constraints, resulting in:
            # - Better table structure recognition (exporter/consignee as proper columns)
            # - More complete field extraction
            # - Document type is still used for classification, not extraction limitation
            forced_mode = "open"
            if extraction_mode != "open":
                logger.info(
                    f"⚠️ Forcing OPEN extraction mode (requested: {extraction_mode}) "
                    f"for better structure recognition. Document type '{document_type}' "
                    f"will be used for classification only, not extraction constraints."
                )

            logger.info(f"Generating schema for {document_type} in OPEN mode")
            try:
                schema = schema_gen.generate_schema(document_type, "open")
                logger.debug(f"Schema generated successfully for {document_type} (OPEN mode)")
            except Exception as e:
                logger.warning(f"Schema generation issue for {document_type}: {e}. Using open mode fallback.")
                schema = schema_gen.generate_schema(document_type, "open")

            # Extract fields using parser
            logger.info(f"Extracting fields from {file_name}")
            result = await parser.extract_fields(
                file_bytes=file_bytes,
                schema=schema,
                document_type=document_type,
                file_name=file_name
            )

            # Result is already in universal format from parser
            logger.info(f"Extraction complete. Fields: {len(result.get('fields', {}))}, Items: {len(result.get('items', []))}")

            # AI Semantic Enhancement (if enabled)
            if self.use_ai_enhancement:
                enhancer = self._get_ai_enhancer()
                if enhancer:
                    logger.info("🤖 Running AI Semantic Enhancement...")
                    try:
                        enhancement_result = await enhancer.enhance_extraction(
                            result,
                            document_type
                        )

                        # Merge enhanced fields with original fields
                        enhanced_fields = enhancement_result.get("fields", {})
                        if enhanced_fields:
                            original_field_count = len(result.get("fields", {}))

                            # DEBUG: Log what we're merging
                            logger.info(f"📊 Enhanced fields to merge: {list(enhanced_fields.keys())}")
                            logger.info(f"📊 Sample enhanced field: {list(enhanced_fields.items())[0] if enhanced_fields else 'none'}")

                            # Merge: Enhanced fields take priority for richer semantic data
                            result["fields"].update(enhanced_fields)

                            new_field_count = len(result["fields"])
                            added_count = new_field_count - original_field_count

                            # DEBUG: Verify merge worked
                            logger.info(f"📊 Fields after merge: {list(result['fields'].keys())[:10]}...")
                            logger.info(f"📊 Checking for exporter_name in fields: {'exporter_name' in result['fields']}")

                            logger.info(
                                f"✅ AI Enhancement complete: "
                                f"{added_count} fields added/updated "
                                f"({original_field_count} → {new_field_count} total)"
                            )

                            # Add AI metadata
                            result["metadata"]["ai_enhancement"] = enhancement_result.get("metadata", {})

                    except Exception as e:
                        logger.error(f"AI Enhancement failed (continuing with original extraction): {e}")
                        # Don't fail the whole process if AI enhancement fails

            # Save to database if enabled
            if self.use_database:
                storage = self._get_storage_service()
                if storage:
                    logger.info(f"Saving {document_type} to database")
                    storage_result = await storage.save_document(document_type, result)

                    if storage_result.success:
                        logger.info(f"Document saved successfully: {storage_result.document_response.document_id}")
                        result["metadata"]["database_id"] = storage_result.document_response.document_id
                        result["metadata"]["saved"] = True
                    else:
                        logger.warning(f"Failed to save document: {storage_result.error_response}")
                        result["metadata"]["saved"] = False
                        result["metadata"]["save_error"] = storage_result.error_response.error_message

            result["status"] = "complete"
            return result

        except Exception as e:
            logger.error(f"Document processing failed: {e}", exc_info=True)
            return {
                "fields": {},
                "items": [],
                "metadata": {
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                "status": "failed"
            }


# Singleton instance
_processing_service: Optional[DocumentProcessingService] = None


def get_processing_service(use_database: bool = False) -> DocumentProcessingService:
    """
    Get or create processing service instance.

    Args:
        use_database: Whether to enable database integration
    """
    global _processing_service

    # Check if we should use database based on environment
    if use_database and not _processing_service:
        # Check if database is configured
        db_configured = all([
            os.getenv('DB_HOST'),
            os.getenv('DB_NAME'),
            os.getenv('REDUCTO_API_KEY')
        ])

        if not db_configured:
            logger.warning("Database or Reducto not configured, using parser-only mode")
            use_database = False

    if _processing_service is None:
        _processing_service = DocumentProcessingService(use_database=use_database)

    return _processing_service
