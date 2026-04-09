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

    def _post_process_bol(self, fields: dict, blocks: list, raw_response: dict = None, items: list = None) -> None:
        """
        Deterministic post-processing for bill_of_lading fields.

        Fills gaps that AI enhancement may miss due to LLM variability:
        - bl_number: fall back to booking_number, or scan all content for BL labels
        - container_numbers: scan all content for 4-letter+7-digit container ID pattern
        """
        import re

        def _val(v):
            """Unwrap Reducto dict-wrapped values."""
            if isinstance(v, dict) and "value" in v:
                return v["value"]
            return v

        def _block_text(b) -> str:
            if isinstance(b, dict):
                return str(b.get("text") or b.get("content") or b.get("value") or "")
            return str(b)

        # Build a comprehensive list of all text content from ALL Reducto blocks/chunks
        all_content: list = list(blocks)  # start with the stored blocks
        if raw_response:
            result_data = raw_response.get("result", raw_response)
            if isinstance(result_data, list):
                result_data = result_data[0] if result_data else {}
            for chunk in result_data.get("chunks", []):
                for raw_block in chunk.get("blocks", []):
                    content = raw_block.get("content", "")
                    if content:
                        all_content.append({"content": content})

        logger.debug(f"BOL post-process: fields={len(fields)}, blocks={len(blocks)}, total_content={len(all_content)}, items={len(items) if items else 0}")

        # ── bl_number fallback ────────────────────────────────────────────────
        if not _val(fields.get("bl_number")):
            # 1) Fall back to booking_number if present in fields
            booking = _val(fields.get("booking_number"))
            if booking:
                fields["bl_number"] = booking
                logger.info(f"BOL post-process: bl_number ← booking_number ({booking})")
            else:
                # 2) Scan ALL content (blocks + raw Reducto chunks) for BL/Booking label + value
                bl_pattern = re.compile(
                    r'(?:booking\s*no\.?|b/?l\s*no\.?|bill\s+of\s+lading\s+no\.?|bl\s+no\.?)\s*[:\-]?\s*([A-Z0-9\-\/]+)',
                    re.IGNORECASE
                )
                for block in all_content:
                    text = _block_text(block)
                    m = bl_pattern.search(text)
                    if m:
                        val = m.group(1).strip()
                        if val:
                            fields["bl_number"] = val
                            fields.setdefault("booking_number", val)
                            logger.info(f"BOL post-process: bl_number ← block scan ({val})")
                            break

                # 3) Scan table items — BL/Booking ref may be split across cells in the same row
                # (e.g. label cell: "Booking no." + value cell: "S328717359")
                if not _val(fields.get("bl_number")) and items:
                    _bl_label_cell_re = re.compile(
                        r'^(?:booking\s*no\.?|b/?l\s*no\.?|bill\s+of\s+lading\s+no\.?|bl\s+no\.?)$',
                        re.IGNORECASE
                    )
                    _bl_value_re = re.compile(r'^[A-Z0-9][A-Z0-9\-\/]{4,}$')
                    for item in items:
                        if isinstance(item, dict):
                            cell_texts = [str(_val(v) or "").strip() for v in item.values()]
                            # a) Inline: label+value in same cell text
                            for text in cell_texts:
                                m = bl_pattern.search(text)
                                if m:
                                    val = m.group(1).strip()
                                    if val:
                                        fields["bl_number"] = val
                                        fields.setdefault("booking_number", val)
                                        logger.info(f"BOL post-process: bl_number ← item inline ({val})")
                                        break
                            # b) Cross-cell: one cell is a BL label, another is the value
                            if not _val(fields.get("bl_number")):
                                has_label = any(_bl_label_cell_re.match(t) for t in cell_texts)
                                if has_label:
                                    for t in cell_texts:
                                        if not _bl_label_cell_re.match(t) and _bl_value_re.match(t):
                                            fields["bl_number"] = t
                                            fields.setdefault("booking_number", t)
                                            logger.info(f"BOL post-process: bl_number ← item cross-cell ({t})")
                                            break
                        if _val(fields.get("bl_number")):
                            break

                # 4) Scan text_block_* field values (label in one field, value in next)
                if not _val(fields.get("bl_number")):
                    # Match labels like "Bl. No.", "B/L No.", "Booking No.", "BL Number"
                    _bl_label_re = re.compile(
                        r'^(?:bl\.?\s*no\.?|b/?l\s*no\.?|bill\s+of\s+lading\s+no\.?'
                        r'|booking\s*no\.?|booking\s+number|bl\s+number)$',
                        re.IGNORECASE
                    )
                    sorted_keys = sorted(
                        (k for k in fields if k.startswith("text_block_")),
                        key=lambda k: float(k.split("_", 2)[-1]) if k.count("_") >= 2 else 0
                    )
                    for i, key in enumerate(sorted_keys):
                        raw = str(_val(fields[key]) or "").strip()
                        if _bl_label_re.match(raw):
                            for next_key in sorted_keys[i + 1:i + 5]:
                                candidate = str(_val(fields[next_key]) or "").strip()
                                if candidate and not _bl_label_re.match(candidate):
                                    fields["bl_number"] = candidate
                                    fields.setdefault("booking_number", candidate)
                                    logger.info(f"BOL post-process: bl_number ← {next_key} ({candidate})")
                                    break
                            break

        # ── container_numbers fallback ────────────────────────────────────────
        if not _val(fields.get("container_numbers")):
            container_pattern = re.compile(r'\b[A-Z]{4}\d{7}\b')
            found = []
            seen: set = set()

            # Scan fields
            for val in fields.values():
                raw = str(_val(val) or "")
                for match in container_pattern.findall(raw):
                    if match not in seen:
                        seen.add(match)
                        found.append(match)

            # Scan all content (blocks + raw Reducto chunks)
            for block in all_content:
                raw = _block_text(block)
                for match in container_pattern.findall(raw):
                    if match not in seen:
                        seen.add(match)
                        found.append(match)

            if found:
                fields["container_numbers"] = ", ".join(found)
                if not _val(fields.get("container_count")):
                    fields["container_count"] = len(found)
                logger.info(f"BOL post-process: container_numbers ← {fields['container_numbers']}")

    def _derive_party_names(self, fields: dict) -> None:
        """
        Deterministic fallback: derive shipper_name / consignee_name from their
        address fields when the name field is absent.

        Even with structured outputs, the LLM may return null for shipper_name
        on documents where the shipper block is redacted (XXXXXXXXXX) or missing.
        When that happens, the first line of shipper_address is the company name.
        """
        def _val(v):
            return v.get("value") if isinstance(v, dict) and "value" in v else v

        def _is_empty(v) -> bool:
            raw = _val(v)
            return raw is None or str(raw).strip() in ("", "<empty>", "-", "—")

        for name_field, addr_field in (
            ("shipper_name", "shipper_address"),
            ("consignee_name", "consignee_address"),
        ):
            if _is_empty(fields.get(name_field)) and not _is_empty(fields.get(addr_field)):
                raw_addr = str(_val(fields[addr_field])).strip()
                first_line = raw_addr.split("\n")[0].strip()
                if first_line:
                    fields[name_field] = first_line
                    logger.info(
                        f"Party name fallback: {name_field} ← first line of "
                        f"{addr_field} ({first_line!r})"
                    )

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

                            # Merge: Enhanced fields take priority for richer semantic data
                            result["fields"].update(enhanced_fields)

                            new_field_count = len(result["fields"])
                            added_count = new_field_count - original_field_count

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

            # BOL Post-Processing — deterministic fallback for bill_of_lading fields that
            # AI enhancement may miss due to LLM variability.
            if document_type.lower().replace("-", "_").replace(" ", "_") == "bill_of_lading":
                raw_response = result.get("raw_provider_response") or {}
                self._post_process_bol(
                    result["fields"],
                    result.get("blocks", []),
                    raw_response,
                    result.get("items", [])
                )

            # Party name fallback — for all document types.
            # When structured output returns null for shipper_name / consignee_name
            # but the address field is populated, extract the company name from
            # the first line of the address.
            self._derive_party_names(result["fields"])

            # BOE Section Extraction — runs for bill_of_entry documents after AI enhancement.
            # Extracts structured sections (16, 21, 25, 31, 40) from Ghana GRA BOE forms
            # and flattens key fields into result["fields"] so validators can reference them.
            if document_type.lower().replace("-", "_").replace(" ", "_") in ("bill_of_entry", "boe"):
                try:
                    from modules.extraction.parser.boe_section_extractor import BOESectionExtractor
                    boe_extractor = BOESectionExtractor()
                    # Use the flat-field extractor first — it handles GRA BOE key-name
                    # encoding and multi-value strings.  Then also build the legacy
                    # structured object for metadata storage.
                    flat_fields = boe_extractor.extract_flat_fields(result.get("fields", {}))
                    boe_data = boe_extractor.extract_sections(result.get("fields", {}))

                    # Merge flat fields into result["fields"].
                    # BOE section extractor values are authoritative for GRA BOE format —
                    # they correctly decode key-name encoding and normalize formats that
                    # Reducto/AI cannot (e.g. hs_code: 1901902000 → 1901.90, gross_weight
                    # decoded from key names).  Always overwrite with extractor values.
                    for field, value in flat_fields.items():
                        if value is not None:
                            result["fields"][field] = value

                    # Structured section data fills fields not covered by flat_fields.
                    # Only fill gaps here (don't overwrite known-good extractor values).
                    def _is_empty(v: Any) -> bool:
                        if v is None:
                            return True
                        if isinstance(v, dict) and "value" in v:
                            v = v["value"]
                        if v is None:
                            return True
                        return str(v).strip() in ("", "<empty>", "-", "—")

                    section_fields: Dict[str, Any] = {}
                    if boe_data.section_16:
                        section_fields["exchange_rate"] = boe_data.section_16.exchange_rate
                        section_fields["currency_code"] = boe_data.section_16.currency_code
                    if boe_data.section_21:
                        section_fields["mode_of_transport"] = boe_data.section_21.mode_of_transport
                        section_fields["entry_exit_code"] = boe_data.section_21.entry_exit_code
                    for field, value in section_fields.items():
                        if value is not None:
                            if _is_empty(result["fields"].get(field)):
                                result["fields"][field] = value

                    # Store full structured BOE data in metadata for downstream use
                    result.setdefault("metadata", {})["boe_sections"] = boe_data.dict()

                    logger.info(
                        f"BOE sections extracted: s16={boe_data.section_16 is not None}, "
                        f"s21={boe_data.section_21 is not None}, "
                        f"s25={len(boe_data.section_25)} items, "
                        f"s31={len(boe_data.section_31)} items, "
                        f"s40={len(boe_data.section_40)} items"
                    )
                except Exception as e:
                    logger.error(f"BOE section extraction failed (continuing): {e}")

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
