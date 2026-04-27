"""
Document processing service for API.

Integrates with the existing parser and storage services.
"""

import logging
from decimal import Decimal
from typing import Dict, Any, Optional
from pathlib import Path
import os

logger = logging.getLogger(__name__)


def _sanitize_for_json(obj: Any) -> Any:
    """
    Recursively convert types that are not JSON-serializable to safe equivalents.

    - decimal.Decimal  → float
    - bytes            → base64 string (shouldn't appear, but safe to handle)
    - Everything else passes through unchanged.
    """
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    if isinstance(obj, Decimal):
        return float(obj)
    return obj


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

    def _resolve_extraction_mode(self, requested_mode: str) -> str:
        """
        Resolve the effective extraction mode.

        Reads the configured mode from providers.yaml when the caller
        passes the default ("open"). If the provider config specifies
        "focused", the checklist schema is used instead.

        Args:
            requested_mode: Mode passed by the caller.

        Returns:
            "open" or "focused"
        """
        try:
            from shared.utils.provider_config import get_provider_config
            pc = get_provider_config()
            active = pc.get_active_provider()
            options = pc.get_provider_options(active)
            configured_mode = options.get("extraction_mode", "open")
        except Exception as e:
            logger.debug("Could not load provider config, defaulting to 'open' mode: %s", e)
            configured_mode = "open"

        if requested_mode != "open":
            return requested_mode

        return configured_mode

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

        - bl_number / booking_number: validate against BL ref pattern; fall back
          to bl_no / booking_no when the extracted value is a stamp phrase like
          "N-NEGOTIABLE" rather than a real reference number.
        - container_numbers: scan all content for 4-letter+7-digit container IDs.
        - page-split containers: merge items where container_no ends with
          "(continued)" back into their base container row.
        """
        import re

        # Valid BL / booking reference: alphanumeric, no spaces, 4-20 chars
        _bl_ref_re = re.compile(r'^[A-Z0-9][A-Z0-9\-/]{3,19}$', re.IGNORECASE)

        def _is_valid_bl_ref(v) -> bool:
            if not v:
                return False
            s = str(v).strip()
            return bool(_bl_ref_re.match(s)) and ' ' not in s

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

        logger.debug("BOL post-process: fields=%d, blocks=%d, total_content=%d, items=%d", len(fields), len(blocks), len(all_content), len(items) if items else 0)

        # ── bl_number fallback ────────────────────────────────────────────────
        # Also accept bl_no / booking_no as authoritative sources so we can
        # overwrite an invalid value (e.g. "N-NEGOTIABLE" from a stamp).
        for src_key in ("bl_no", "booking_no"):
            src_val = _val(fields.get(src_key))
            if _is_valid_bl_ref(src_val):
                if not _is_valid_bl_ref(_val(fields.get("bl_number"))):
                    fields["bl_number"] = src_val
                    logger.info(f"BOL post-process: bl_number ← {src_key} ({src_val})")
                if not _is_valid_bl_ref(_val(fields.get("booking_number"))):
                    fields["booking_number"] = src_val
                    logger.info(f"BOL post-process: booking_number ← {src_key} ({src_val})")
                break

        if not _is_valid_bl_ref(_val(fields.get("bl_number"))):
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

        # ── merge page-split container items ─────────────────────────────────
        # When a container spans two pages, Claude produces two items: the base
        # row (missing seal/tare/net) and a "(continued)" row (missing gross/qty).
        # Merge the continuation into its base row and remove it.
        if items:
            i = 0
            while i < len(items):
                item = items[i]
                raw_cno = str(item.get("container_no") or "")
                if "(continued)" in raw_cno.lower():
                    base_no = raw_cno.lower().replace("(continued)", "").strip()
                    merged = False
                    for j in range(i - 1, -1, -1):
                        prev_cno = str(items[j].get("container_no") or "").strip()
                        if prev_cno.lower() == base_no:
                            for field, value in item.items():
                                if field == "container_no":
                                    continue
                                if items[j].get(field) is None and value is not None:
                                    items[j][field] = value
                            items.pop(i)
                            merged = True
                            logger.info(
                                f"BOL post-process: merged page-split container "
                                f"{prev_cno} (continued) into base row"
                            )
                            break
                    if not merged:
                        i += 1
                else:
                    i += 1

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

    def _post_process_packing_list(self, fields: dict) -> None:
        """
        Deterministic post-processing for packing_list fields.

        On a packing list the top-left address block is the BILL-TO (consignee),
        not the shipper. Claude labels it shipper_* in OPEN mode because it sits
        in the top-left position. Rename those keys to bill_to_* to reflect the
        correct role. The actual shipper/exporter is the issuing party (often
        redacted or in the document header, not the buyer address block).
        """
        renames = {
            "shipper_name":         "bill_to_name",
            "shipper_address":      "bill_to_address",
            "shipper_address_line1":"bill_to_address_line1",
            "shipper_address_line2":"bill_to_address_line2",
            "shipper_city":         "bill_to_city",
            "shipper_country":      "bill_to_country",
        }
        for old_key, new_key in renames.items():
            if old_key in fields:
                fields[new_key] = fields.pop(old_key)
                logger.info(f"PL post-process: {old_key} → {new_key}")

    def _apply_value_cleanups(self, fields: dict, document_type: str) -> None:
        """
        Config-driven value-level cleanup applied after extraction.

        Reads regex cleanup rules from normalization.yaml under
        ``value_cleanups.rules.<document_type>`` and applies them to
        field values. Handles both plain values and {value, confidence} envelopes.

        This fixes VALUE content issues (container preamble, contact details,
        currency duplication) — field name normalization is handled by the
        SynonymMapper separately.
        """
        import re
        try:
            from modules.validation_engine.core.config_loader import get_config_loader
            config_loader = get_config_loader()
            norm_config = config_loader.load_normalization_config()
        except Exception:
            logger.debug("Could not load normalization config for value cleanups")
            return

        cleanup_config = norm_config.get("value_cleanups", {})
        if not cleanup_config.get("enabled", True):
            return

        rules = cleanup_config.get("rules", {}).get(document_type, {})
        if not rules:
            return

        for field_name, cleanups in rules.items():
            if field_name not in fields:
                continue

            raw = fields[field_name]
            # Unwrap value from {value, confidence} envelope
            if isinstance(raw, dict) and "value" in raw:
                val_str = str(raw["value"]) if raw["value"] is not None else ""
                wrapper = raw
            else:
                val_str = str(raw) if raw is not None else ""
                wrapper = None

            if not val_str:
                continue

            cleaned = val_str
            for cleanup in cleanups:
                pattern = cleanup.get("pattern", "")
                replacement = cleanup.get("replacement", "")
                if pattern:
                    cleaned = re.sub(pattern, replacement, cleaned).strip()

            if cleaned != val_str:
                if wrapper is not None:
                    wrapper["value"] = cleaned
                else:
                    fields[field_name] = cleaned
                logger.info(
                    f"Value cleanup ({document_type}): cleaned {field_name} "
                    f"[{len(val_str)} → {len(cleaned)} chars]"
                )

    def _derive_party_names(self, fields: dict) -> None:
        """
        Deterministic fallback: derive party names from address fields when
        the name field is absent.

        Looks for whatever field names Claude actually extracted — does not
        assume canonical names like ``shipper_name`` or ``consignee_name``.
        For each party role, checks all known field-name variants and
        extracts the first line of the address block as the company name.
        """
        def _val(v):
            return v.get("value") if isinstance(v, dict) and "value" in v else v

        def _is_empty(v) -> bool:
            raw = _val(v)
            return raw is None or str(raw).strip() in ("", "<empty>", "-", "—")

        # Map: name variants → address variants.
        # The first non-empty name variant found is treated as the canonical
        # name field; the first non-empty address variant as the address source.
        party_roles = {
            "shipper": {
                "name_keys": ["shipper_name", "shipper", "exporter_name", "exporter", "seller_name", "seller"],
                "addr_keys": ["shipper_address", "shipper_block", "exporter_address", "seller_address"],
            },
            "consignee": {
                "name_keys": ["consignee_name", "consignee", "buyer_name", "buyer"],
                "addr_keys": ["consignee_address", "consignee_block", "buyer_address", "bill_to_address", "ship_to_address", "delivery_address"],
            },
        }

        for role, keys in party_roles.items():
            # Find the existing name field (if any)
            name_key = None
            for nk in keys["name_keys"]:
                if not _is_empty(fields.get(nk)):
                    name_key = nk
                    break

            # If name is already present, nothing to do
            if name_key and not _is_empty(fields.get(name_key)):
                continue

            # Find the address field to derive from
            addr_key = None
            for ak in keys["addr_keys"]:
                if not _is_empty(fields.get(ak)):
                    addr_key = ak
                    break

            if not addr_key:
                continue

            raw_addr = str(_val(fields[addr_key])).strip()
            first_line = raw_addr.split("\n")[0].strip()
            if first_line:
                # Write back to the SAME key Claude used for the name, or
                # fall back to the first name variant if no name key exists.
                target = name_key or keys["name_keys"][0]
                fields[target] = first_line
                logger.info(
                    f"Party name fallback: {target} ← first line of "
                    f"{addr_key} ({first_line!r})"
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

            # Create request-scoped token tracker
            from shared.utils.token_tracker import create_tracker, set_step
            token_tracker = create_tracker()

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

            # Resolve extraction mode from provider config if caller used default
            effective_mode = self._resolve_extraction_mode(extraction_mode)
            logger.info(
                f"Extraction mode: {effective_mode} "
                f"(requested: {extraction_mode}) for {document_type}"
            )

            # Generate schema based on mode
            try:
                if effective_mode == "focused":
                    schema = schema_gen.generate_checklist_schema(document_type)
                else:
                    schema = schema_gen.generate_schema(document_type, "open")
                logger.debug(
                    f"Schema generated for {document_type} ({effective_mode} mode)"
                )
            except Exception as e:
                logger.warning(
                    f"Schema generation issue for {document_type}: {e}. "
                    f"Falling back to open mode."
                )
                schema = schema_gen.generate_schema(document_type, "open")

            # Extract fields using parser
            logger.info(f"Extracting fields from {file_name}")
            set_step("document_extraction")
            result = await parser.extract_fields(
                file_bytes=file_bytes,
                schema=schema,
                document_type=document_type,
                file_name=file_name
            )

            # Result is already in universal format from parser
            logger.info(f"Extraction complete. Fields: {len(result.get('fields', {}))}, Items: {len(result.get('items', []))}")

            # AI Semantic Enhancement — skip when the active provider is Claude.
            # Claude already performs semantic extraction in one pass; running the
            # enhancer would be a redundant second Claude call on top of Claude's output.
            provider = self._get_parser_provider()
            provider_name = getattr(provider, 'provider_name', '') or type(provider).__name__
            is_claude_provider = 'claude' in provider_name.lower()

            if is_claude_provider:
                logger.info("Skipping AI Semantic Enhancement — active provider is Claude (redundant).")

            if self.use_ai_enhancement and not is_claude_provider:
                enhancer = self._get_ai_enhancer()
                if enhancer:
                    logger.info("🤖 Running AI Semantic Enhancement...")
                    set_step("ai_semantic_enhancement")
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

            # Packing list post-processing — rename bill-to address fields that
            # Claude mislabels as shipper_* in OPEN mode.
            if document_type.lower().replace("-", "_").replace(" ", "_") == "packing_list":
                self._post_process_packing_list(result["fields"])

            # Value-level cleanup from config (container preamble, contact details, currency dedup)
            dt_norm = document_type.lower().replace("-", "_").replace(" ", "_")
            self._apply_value_cleanups(result["fields"], dt_norm)

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
                    flat_fields = boe_extractor.extract_flat_fields(
                        result.get("fields", {}),
                        items=result.get("items", []),
                        blocks=result.get("blocks", []),
                    )
                    boe_data = boe_extractor.extract_sections(result.get("fields", {}))

                    # Merge flat fields into result["fields"].
                    # BOE section extractor values are authoritative for GRA BOE format —
                    # they correctly decode key-name encoding and normalize formats that
                    # Reducto/AI cannot (e.g. hs_code: 1901902000 → 1901.90, gross_weight
                    # decoded from key names).  Always overwrite with extractor values.
                    for field, value in flat_fields.items():
                        if value is not None:
                            result["fields"][field] = value

                    # Remove noise/garbage fields that the extractor flagged for removal
                    # (stray single letters, page numbers, etc.)
                    for noise_key in ("f", "page_no", "items_count"):
                        result["fields"].pop(noise_key, None)

                    # Filter items: remove attached-document reference rows and tax
                    # rows that Claude sometimes dumps into the items array.
                    result["items"] = boe_extractor.filter_goods_items(
                        result.get("items", [])
                    )

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

            # Deterministic confidence scoring — replaces Claude's self-assessed
            # visual scores with computed scores based on verifiable signals
            # (presence, format match, cross-document validation potential).
            # Must run after all post-processing so fields are in final state.
            from modules.extraction.parser.confidence_scorer import score_fields, score_items
            score_fields(result["fields"])
            score_items(result.get("items", []))
            logger.info(f"Confidence scoring applied to {len(result['fields'])} fields")

            # Strip provider-level block confidence (Reducto parse_confidence /
            # extract_confidence). These are OCR quality scores for entire blocks,
            # not per-field scores. They predate our deterministic scorer and
            # produce misleading badges on every cell in the UI.
            for block in result.get("blocks", []):
                block.pop("confidence", None)
                block.pop("granular_confidence", None)

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
            result["token_usage"] = token_tracker.get_summary()
            # Sanitize before returning — Decimal values (from BOE section extractor,
            # CET lookups, Pydantic .dict() calls) are not JSON-serializable and will
            # cause JSONB insert failures in PostgreSQL.
            return _sanitize_for_json(result)

        except Exception as e:
            logger.error(f"Document processing failed: {e}", exc_info=True)
            # Still return any tokens consumed before the failure
            try:
                partial_usage = token_tracker.get_summary()
            except Exception as tracker_err:
                logger.debug("Could not retrieve token usage after failure: %s", tracker_err)
                partial_usage = {}
            return {
                "fields": {},
                "items": [],
                "metadata": {
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                "token_usage": partial_usage,
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
