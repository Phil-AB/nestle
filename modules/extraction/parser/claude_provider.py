"""
Anthropic Claude implementation of the parser provider interface.

Uses Claude's native vision/document understanding to extract structured
data from PDFs and images without any intermediate OCR step.

Supports both direct Anthropic API and AWS Bedrock (bearer token auth).
"""

import base64
import asyncio
import json
import os
import time
from typing import Dict, Any, Optional, List
from pathlib import Path

from .base import (
    IParserProvider,
    ParsedDocument,
    ParserException,
    ParserConnectionError,
    ParserTimeoutError,
)
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)

# Supported file formats and their MIME types
_MIME_TYPES = {
    ".pdf":  "application/pdf",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif":  "image/gif",
    ".webp": "image/webp",
    ".tiff": "image/tiff",
    ".tif":  "image/tiff",
}

# Maximum document size for direct base64 embedding (32 MB)
_MAX_INLINE_BYTES = 32 * 1024 * 1024


class ClaudeProvider(IParserProvider):
    """
    Anthropic Claude provider for document parsing and field extraction.

    Sends documents (PDFs, images) directly to Claude using the native
    vision / document API — no intermediate OCR layer required.

    Supports:
    - PDF documents   → ``document`` content block (native PDF understanding)
    - Images          → ``image`` content block  (vision)

    Authentication (in priority order):
    1. AWS Bedrock via bearer token  (``bedrock_enabled=True`` + ``AWS_BEARER_TOKEN_BEDROCK``)
    2. Direct Anthropic API          (``ANTHROPIC_API_KEY``)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 32768,
        timeout: int = 300,
        bedrock_enabled: bool = False,
        aws_region: str = "us-east-1",
        bedrock_model_id: Optional[str] = None,
    ):
        """
        Initialise the Claude provider.

        Args:
            api_key: Anthropic API key (falls back to ANTHROPIC_API_KEY env var).
            model: Claude model ID for direct API calls.
            max_tokens: Maximum tokens in Claude's response.
            timeout: HTTP request timeout in seconds.
            bedrock_enabled: Route requests through AWS Bedrock instead of direct API.
            aws_region: AWS region for Bedrock (default: us-east-1).
            bedrock_model_id: Bedrock model ID override (e.g. "global.anthropic.claude-sonnet-4-6").
        """
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.bedrock_enabled = bedrock_enabled
        self.aws_region = aws_region

        self._client = self._build_client(api_key, bedrock_enabled, aws_region, bedrock_model_id)

        logger.info(
            f"ClaudeProvider initialised: model={self.model}, "
            f"bedrock={bedrock_enabled}, region={aws_region}"
        )

    # ------------------------------------------------------------------
    # Client construction
    # ------------------------------------------------------------------

    def _build_client(
        self,
        api_key: Optional[str],
        bedrock_enabled: bool,
        aws_region: str,
        bedrock_model_id: Optional[str],
    ):
        """
        Build and return the appropriate Anthropic client.

        Returns either an ``anthropic.Anthropic`` (direct API) or an
        ``anthropic.AnthropicBedrock`` client (AWS Bedrock).
        """
        try:
            import anthropic as _anthropic
        except ImportError as exc:
            raise ImportError(
                "The 'anthropic' package is required for ClaudeProvider. "
                "Install it with: pip install anthropic"
            ) from exc

        if bedrock_enabled:
            bearer_token = os.getenv("AWS_BEARER_TOKEN_BEDROCK")
            if not bearer_token:
                raise ValueError(
                    "AWS_BEARER_TOKEN_BEDROCK is not set. "
                    "This system uses Bedrock API key authentication exclusively."
                )

            import boto3
            from botocore import UNSIGNED
            from botocore.config import Config as BotocoreConfig

            bedrock_client = boto3.client(
                "bedrock-runtime",
                region_name=aws_region,
                aws_access_key_id="bedrock-api-key",
                aws_secret_access_key="not-used",
                config=BotocoreConfig(
                    signature_version=UNSIGNED,
                    read_timeout=self.timeout,
                    connect_timeout=30,
                    retries={"max_attempts": 2, "mode": "standard"},
                ),
            )

            _token = bearer_token

            def _inject_bearer(request, **kwargs):
                request.headers["Authorization"] = f"Bearer {_token}"

            bedrock_client.meta.events.register(
                "before-send.bedrock-runtime.*", _inject_bearer
            )

            if bedrock_model_id:
                self.model = bedrock_model_id

            logger.info(
                f"ClaudeProvider using AWS Bedrock: model={self.model}, region={aws_region}"
            )

            # Use AnthropicBedrock wrapper if available, else fall back to direct SDK
            # by monkey-patching the boto3 client through _anthropic.AnthropicBedrock
            # Note: we store the raw bedrock client for direct invocation
            self._bedrock_client = bedrock_client
            return None  # Bedrock calls made via self._bedrock_client

        # Direct Anthropic API
        resolved_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not resolved_key:
            raise ValueError(
                "Anthropic API key not found. Set ANTHROPIC_API_KEY env var "
                "or pass api_key to ClaudeProvider."
            )
        return _anthropic.Anthropic(api_key=resolved_key, timeout=self.timeout)

    # ------------------------------------------------------------------
    # IParserProvider interface
    # ------------------------------------------------------------------

    async def parse_document(
        self,
        file_bytes: bytes,
        file_name: str,
        document_type: str,
        **options,
    ) -> ParsedDocument:
        """
        Parse a document using Claude's vision / document understanding.

        Args:
            file_bytes: Raw document bytes.
            file_name: Original file name (used for MIME-type detection).
            document_type: Semantic document type (invoice, boe, packing_list, …).
            **options: Additional options (``model``, ``max_tokens``, …).

        Returns:
            ParsedDocument with all extracted content.
        """
        try:
            logger.info(f"Parsing document with Claude: {file_name} (type={document_type})")
            start = time.monotonic()

            content_block = self._build_document_block(file_bytes, file_name)

            system_prompt = self._build_parse_system_prompt(document_type)
            user_message = (
                f"Extract all information from this {document_type} document. "
                "Return a JSON object with these top-level keys:\n"
                "- ``fields``: flat key-value pairs for header/summary fields\n"
                "- ``items``: array of line-item objects (empty array if none)\n"
                "- ``tables``: array of raw table objects with ``headers`` and ``rows``\n"
                "- ``raw_text``: full plain-text representation of the document\n\n"
                "Use snake_case for all field names. "
                "Return ONLY valid JSON — no markdown fences, no commentary."
            )

            raw_response = await asyncio.to_thread(
                self._invoke,
                system_prompt,
                [content_block, {"type": "text", "text": user_message}],
                options,
            )

            elapsed = time.monotonic() - start
            parsed = self._parse_json_response(raw_response)

            doc = ParsedDocument(
                document_id=f"claude-{int(time.time())}",
                document_type=document_type,
                raw_text=parsed.get("raw_text", ""),
                structured_data={"fields": parsed.get("fields", {}), "items": parsed.get("items", [])},
                tables=parsed.get("tables", []),
                metadata={
                    "provider": "claude",
                    "model": self.model,
                    "extraction_duration": round(elapsed, 2),
                    "confidence": 1.0,
                },
                page_count=None,
            )

            logger.info(
                f"Claude parse complete: {file_name} "
                f"({len(parsed.get('fields', {}))} fields, "
                f"{len(parsed.get('items', []))} items) in {elapsed:.1f}s"
            )
            return doc

        except (TimeoutError, ConnectionError) as exc:
            raise ParserTimeoutError(f"Claude request timed out: {exc}") from exc
        except Exception as exc:
            logger.error(f"Claude parse_document failed: {exc}")
            raise ParserException(f"Failed to parse document with Claude: {exc}") from exc

    async def extract_fields(
        self,
        file_bytes: bytes,
        schema: Dict[str, Any],
        **options,
    ) -> Dict[str, Any]:
        """
        Extract structured fields from a document using the provided schema.

        The universal schema is translated into a Claude prompt that instructs
        the model on exactly which fields to look for.

        Args:
            file_bytes: Raw document bytes.
            schema: Universal extraction schema (see ``translate_schema``).
            **options: Additional options (``file_name``, ``document_type``, …).

        Returns:
            Normalised extraction result in universal format.
        """
        try:
            file_name = options.get("file_name", "document.pdf")
            document_type = options.get("document_type", "unknown")

            logger.info(
                f"Extracting fields with Claude: file={file_name}, "
                f"doc_type={document_type}, mode={schema.get('mode', 'focused')}"
            )
            start = time.monotonic()

            content_block = self._build_document_block(file_bytes, file_name)
            claude_schema = self.translate_schema(schema)

            system_prompt = self._build_extract_system_prompt(document_type)
            user_message = self._build_extract_user_message(claude_schema, schema)

            raw_response = await asyncio.to_thread(
                self._invoke,
                system_prompt,
                [content_block, {"type": "text", "text": user_message}],
                options,
            )

            elapsed = time.monotonic() - start
            parsed = self._parse_json_response(raw_response)

            normalized = self.normalize_response(parsed, document_type, schema=claude_schema)
            normalized["raw_provider_response"] = parsed
            normalized["metadata"]["extraction_duration"] = round(elapsed, 2)

            logger.info(
                f"Claude extraction complete: "
                f"{len(normalized.get('fields', {}))} fields, "
                f"{len(normalized.get('items', []))} items in {elapsed:.1f}s"
            )
            return normalized

        except Exception as exc:
            logger.error(f"Claude extract_fields failed: {exc}")
            raise ParserException(f"Failed to extract fields with Claude: {exc}") from exc

    def translate_schema(self, universal_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translate the universal schema into a Claude-friendly prompt schema.

        Open mode  → return empty dict (Claude extracts everything it finds).
        Focused mode → build a structured description of required fields.

        Args:
            universal_schema: Universal schema produced by SchemaGenerator.

        Returns:
            Claude prompt schema dict with ``fields`` and optionally ``items``.
        """
        mode = universal_schema.get("mode", "focused")

        if mode == "open":
            logger.info("Using OPEN mode — Claude will extract all discovered fields")
            return {"mode": "open"}

        logger.debug("Translating focused schema to Claude prompt schema")

        claude_schema: Dict[str, Any] = {"mode": "focused", "fields": {}, "items": None}

        # Header / summary fields
        for field_name, field_def in universal_schema.get("fields", {}).items():
            claude_schema["fields"][field_name] = {
                "type": field_def.get("type", "string"),
                "required": field_def.get("required", False),
                "description": field_def.get("description", ""),
            }

        # Line-item fields
        items_def = universal_schema.get("items")
        if items_def:
            field_name = items_def.get("field_name", "items")
            item_fields = {}
            for ifield, idef in items_def.get("fields", {}).items():
                item_fields[ifield] = {
                    "type": idef.get("type", "string"),
                    "required": idef.get("required", False),
                    "description": idef.get("description", ""),
                }
            claude_schema["items"] = {"field_name": field_name, "fields": item_fields}

        logger.debug(
            f"Translated schema: {len(claude_schema['fields'])} header fields, "
            f"items={'yes' if claude_schema['items'] else 'no'}"
        )
        return claude_schema

    def normalize_response(
        self,
        provider_response: Dict[str, Any],
        document_type: str,
        schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Normalise Claude's JSON response into the universal extraction format.

        Args:
            provider_response: Parsed JSON returned by Claude.
            document_type: Semantic document type.
            schema: Optional translated schema (used for mode detection).

        Returns:
            Universal format dict with ``fields``, ``items``, ``blocks``,
            ``layout``, ``metadata``, and ``raw_provider_response``.
        """
        logger.info(f"Normalising Claude response for {document_type}")

        mode = (schema or {}).get("mode", "focused")

        # --- Fields ---
        fields: Dict[str, Any] = {}
        raw_fields = provider_response.get("fields", {})
        if isinstance(raw_fields, dict):
            for k, v in raw_fields.items():
                norm_key = self._normalize_key(k)
                if norm_key:
                    fields[norm_key] = v

        # In OPEN mode also flatten any top-level scalar keys that aren't reserved
        if mode == "open":
            _reserved = {"fields", "items", "tables", "raw_text", "blocks", "layout", "metadata"}
            for k, v in provider_response.items():
                if k not in _reserved and isinstance(v, (str, int, float, bool, type(None))):
                    norm_key = self._normalize_key(k)
                    if norm_key and norm_key not in fields:
                        fields[norm_key] = v

        # --- Items ---
        items: List[Dict[str, Any]] = []
        raw_items = provider_response.get("items", [])
        if isinstance(raw_items, list):
            for row in raw_items:
                if isinstance(row, dict):
                    items.append({self._normalize_key(k): v for k, v in row.items() if self._normalize_key(k)})

        # --- Blocks (raw text chunks for downstream rendering) ---
        blocks: List[Dict[str, Any]] = []
        raw_text = provider_response.get("raw_text", "")
        if raw_text:
            blocks.append({"type": "Text", "content": raw_text})

        # Also carry over any table blocks
        for tbl in provider_response.get("tables", []):
            blocks.append({"type": "Table", "content": tbl})

        # --- Layout (minimal — Claude doesn't return bounding boxes) ---
        layout: Dict[str, Any] = {
            "pages": [],
            "total_pages": 0,
            "has_form_fields": False,
            "has_tables": bool(provider_response.get("tables")),
        }

        # --- Metadata ---
        metadata: Dict[str, Any] = {
            "provider": "claude",
            "model": self.model,
            "confidence": 1.0,
            "extraction_duration": None,
        }

        normalized = {
            "fields": fields,
            "items": items,
            "blocks": blocks,
            "layout": layout,
            "metadata": metadata,
            "raw_provider_response": provider_response,
        }

        logger.info(
            f"Normalised: {len(fields)} fields, {len(items)} items, {len(blocks)} blocks"
        )
        return normalized

    async def health_check(self) -> bool:
        """
        Verify that the Claude API / Bedrock endpoint is reachable.

        Returns:
            True if healthy, False otherwise.
        """
        try:
            response = self._invoke(
                system="You are a health check assistant.",
                content_blocks=[{"type": "text", "text": "Reply with the single word: OK"}],
                options={"max_tokens": 10},
            )
            healthy = "ok" in response.strip().lower()
            logger.info(f"Claude health check: {'pass' if healthy else 'fail'}")
            return healthy
        except Exception as exc:
            logger.warning(f"Claude health check failed: {exc}")
            return False

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _invoke(
        self,
        system: str,
        content_blocks: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Send a synchronous request to Claude (direct API or Bedrock).

        Args:
            system: System prompt string.
            content_blocks: List of content blocks for the user turn.
            options: Override dict (e.g. ``{"max_tokens": 512}``).

        Returns:
            Raw text response from Claude.
        """
        options = options or {}
        max_tokens = options.get("max_tokens", self.max_tokens)

        if self.bedrock_enabled:
            return self._invoke_bedrock(system, content_blocks, max_tokens)

        # Direct Anthropic API
        message = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": content_blocks}],
        )

        # Record token usage
        try:
            from shared.utils.token_tracker import record_tokens
            usage = message.usage
            record_tokens(
                provider="anthropic",
                model=self.model,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
            )
        except Exception:
            pass

        return message.content[0].text

    def _to_bedrock_blocks(self, content_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert Anthropic SDK content blocks to AWS Bedrock Converse API tagged-union format.

        Anthropic SDK format:  ``{"type": "document", "source": {"type": "base64", "data": "..."}}``
        Bedrock Converse format: ``{"document": {"format": "pdf", "name": "doc", "source": {"bytes": b"..."}}}``

        Args:
            content_blocks: Blocks in Anthropic SDK format.

        Returns:
            Blocks in Bedrock Converse tagged-union format.
        """
        bedrock_blocks = []
        for block in content_blocks:
            block_type = block.get("type")

            if block_type == "text":
                bedrock_blocks.append({"text": block["text"]})

            elif block_type == "document":
                source = block.get("source", {})
                raw_bytes = base64.standard_b64decode(source.get("data", ""))
                bedrock_blocks.append({
                    "document": {
                        "format": "pdf",
                        "name": "document",
                        "source": {"bytes": raw_bytes},
                    }
                })

            elif block_type == "image":
                source = block.get("source", {})
                media_type = source.get("media_type", "image/png")
                fmt = media_type.split("/")[-1]
                # Bedrock uses "jpeg" not "jpg"
                if fmt == "jpg":
                    fmt = "jpeg"
                raw_bytes = base64.standard_b64decode(source.get("data", ""))
                bedrock_blocks.append({
                    "image": {
                        "format": fmt,
                        "source": {"bytes": raw_bytes},
                    }
                })

            else:
                # Fallback: treat unknown block as plain text
                bedrock_blocks.append({"text": str(block)})

        return bedrock_blocks

    def _invoke_bedrock(
        self,
        system: str,
        content_blocks: List[Dict[str, Any]],
        max_tokens: int,
    ) -> str:
        """
        Invoke Claude via the AWS Bedrock ``converse`` API.

        Converts Anthropic SDK content blocks to Bedrock tagged-union format
        before sending.

        Args:
            system: System prompt.
            content_blocks: User-turn content blocks in Anthropic SDK format.
            max_tokens: Maximum response tokens.

        Returns:
            Raw text from Bedrock response.
        """
        bedrock_blocks = self._to_bedrock_blocks(content_blocks)

        response = self._bedrock_client.converse(
            modelId=self.model,
            system=[{"text": system}],
            messages=[{"role": "user", "content": bedrock_blocks}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": 0.0},
        )

        # Record token usage
        try:
            from shared.utils.token_tracker import record_tokens
            bedrock_usage = response.get("usage", {})
            input_tokens = bedrock_usage.get("inputTokens", 0)
            output_tokens = bedrock_usage.get("outputTokens", 0)
            if input_tokens or output_tokens:
                record_tokens(
                    provider="anthropic",
                    model=self.model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
        except Exception:
            pass

        output = response.get("output", {})
        message = output.get("message", {})
        content = message.get("content", [{}])
        return content[0].get("text", "")

    def _build_document_block(self, file_bytes: bytes, file_name: str) -> Dict[str, Any]:
        """
        Build the correct Anthropic content block for the given file.

        - PDF files   → ``{"type": "document", "source": {...}}``
        - Images      → ``{"type": "image",    "source": {...}}``

        Args:
            file_bytes: Raw bytes of the document.
            file_name: Original file name (used to resolve MIME type).

        Returns:
            Content block dict ready for the Anthropic messages API.

        Raises:
            ParserException: If the file format is not supported.
        """
        if len(file_bytes) > _MAX_INLINE_BYTES:
            raise ParserException(
                f"Document too large for inline embedding "
                f"({len(file_bytes) / 1024 / 1024:.1f} MB > "
                f"{_MAX_INLINE_BYTES / 1024 / 1024:.0f} MB limit). "
                "Consider splitting the document before extraction."
            )

        ext = Path(file_name).suffix.lower()
        mime_type = _MIME_TYPES.get(ext)
        if not mime_type:
            # Default to PDF for unknown extensions
            logger.warning(f"Unknown extension '{ext}', treating as PDF")
            mime_type = "application/pdf"

        encoded = base64.standard_b64encode(file_bytes).decode("utf-8")

        if mime_type == "application/pdf":
            return {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": mime_type,
                    "data": encoded,
                },
            }

        # Image content block
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mime_type,
                "data": encoded,
            },
        }

    def _build_parse_system_prompt(self, document_type: str) -> str:
        """Build the system prompt for full document parsing."""
        return (
            f"You are an expert document data-extraction engine specialising in "
            f"trade and logistics documents, specifically {document_type} documents.\n\n"
            "Your task is to extract ALL information from the document provided.\n"
            "Rules:\n"
            "1. Return ONLY a single valid JSON object — no markdown, no explanation.\n"
            "2. Use snake_case for every key.\n"
            "3. Preserve original values exactly (do not normalise dates, amounts, or codes).\n"
            "4. If a field is absent, omit it rather than returning null.\n"
            "5. Capture every line item in the 'items' array.\n"
            "6. Include full raw text of the document in the 'raw_text' field.\n"
            "7. For each field in 'fields', return an object with 'value' and 'confidence' "
            "instead of a raw value. Confidence (0.0–1.0) reflects extraction certainty:\n"
            "   - 1.0: clear printed text, unambiguous\n"
            "   - 0.9: printed but slightly obscured or requires minor interpretation\n"
            "   - 0.7: handwritten, faded, or requires interpretation\n"
            "   - 0.5: inferred or uncertain\n"
            "   - 0.3 or lower: barely visible, context-guessed\n"
            "   Example: {\"value\": \"INV-12345\", \"confidence\": 0.97}\n"
            "8. If a field's label is visible but its value is visually redacted "
            "(black bar, [REDACTED] stamp, white-out patch, or any obscured region), "
            "return that field as {\"value\": null, \"redacted\": true} — do NOT omit it.\n"
        )

    def _build_extract_system_prompt(self, document_type: str) -> str:
        """Build the system prompt for schema-guided field extraction."""
        base = (
            f"You are a precise document data-extraction engine for {document_type} documents.\n\n"
            "Extract the requested fields from the document following the schema exactly.\n"
            "Rules:\n"
            "1. Return ONLY a single valid JSON object — no markdown, no explanation.\n"
            "2. Use the EXACT field label as printed on the document, converted to snake_case. "
            "Do NOT rename, re-label, or semantically map a field to a different name. "
            "If the document says 'Total Excl. VAT', the key is 'total_excl_vat' — "
            "NOT 'total_fob_value'. If it says 'Your Order Number', the key is "
            "'your_order_number' — NOT 'po_number'. If it says 'Seller', the key is "
            "'seller' — NOT 'shipper_name'.\n"
            "3. Preserve original values — do not normalise dates, currencies, or codes.\n"
            "4. For missing fields return null rather than omitting them.\n"
            "5. For array fields (items/line items) extract every row from the document.\n"
            "6. For each header field (in 'fields'), return an object with 'value' and "
            "'confidence' instead of a raw value. Confidence (0.0–1.0) reflects how clearly "
            "the field was readable and unambiguous:\n"
            "   - 1.0: clear printed text, exact match to label\n"
            "   - 0.9: printed but slightly obscured or minor interpretation needed\n"
            "   - 0.7: handwritten, faded, or requires interpretation\n"
            "   - 0.5: inferred or uncertain\n"
            "   - 0.3 or lower: barely visible or context-guessed\n"
            "   Example: {\"value\": \"INV-12345\", \"confidence\": 0.97}\n"
            "   For missing fields still use null (not a confidence object).\n"
            "7. If a field's label is visible but its value is visually redacted "
            "(black bar, [REDACTED] stamp, white-out patch, or any obscured region), "
            "return {\"value\": null, \"redacted\": true} for that field instead of null.\n"
        )

        # Add document-type-specific structural guidance
        dt = document_type.lower().replace("-", "_").replace(" ", "_")
        if dt in ("bill_of_entry", "boe"):
            base += (
                "\nBOE-SPECIFIC RULES:\n"
                "This is a Ghana GRA Customs Declaration (Bill of Entry). The form has "
                "numbered sections (Field 1, Field 2, …). IMPORTANT:\n"
                "- The section NUMBER is NOT a field value. 'Field 1 — Regime: 40' means "
                "regime=40, NOT regime=1. The number before the dash is the section label.\n"
                "- 'items' must ONLY contain goods line-item rows (Section 31/Item No 0001). "
                "Attached document references (INVOICE, BILL OF LADING, etc.) go in 'tables', "
                "NOT in 'items'.\n"
                "- Tax computation rows (Tax Code 01, 02, etc.) go in 'tables', NOT 'items'.\n"
                "- Tax summary rows (Import Duty, Import VAT, etc.) go in 'tables', NOT 'items'.\n"
                "- If the form has a 'Manifest No' field and its value is blank or 'N/A', "
                "extract it as null, NOT as a number from an adjacent field.\n"
            )

        return base

    def _build_extract_user_message(
        self, claude_schema: Dict[str, Any], universal_schema: Dict[str, Any]
    ) -> str:
        """
        Build the user-turn extraction instruction based on the translated schema.

        Args:
            claude_schema: Translated Claude schema dict.
            universal_schema: Original universal schema (for mode detection).

        Returns:
            Instruction string to append after the document content block.
        """
        mode = claude_schema.get("mode", "focused")

        if mode == "open":
            return (
                "Extract all information from this document and return a JSON object with these keys:\n\n"
                "- ``fields``: object where each entry is an explicitly-labeled header/summary field. "
                "CRITICAL: Use the EXACT field label as printed on the document, converted to "
                "snake_case. Do NOT rename, re-label, or semantically map a field to a different "
                "name. Examples: 'Total Excl. VAT' → 'total_excl_vat' (NOT 'total_fob_value'); "
                "'Your Order Number' → 'your_order_number' (NOT 'po_number'); "
                "'Shipping Condition' → 'shipping_condition' (NOT 'incoterm'); "
                "'Seller' → 'seller' (NOT 'shipper_name'); "
                "'Buyer' → 'buyer' (NOT 'consignee_name').\n"
                "Address blocks: Extract every named address block as a separate field using "
                "the block's label as the key (e.g. 'Delivery address' → 'delivery_address', "
                "'Bill-to address' → 'bill_to_address', 'Ship-to' → 'ship_to'). "
                "The value is the full multi-line address text joined with ', '. "
                "If the document has multiple address blocks, extract ALL of them — "
                "do NOT merge or drop any.\n"
                "For EVERY field, return {\"value\": <extracted_value>, \"confidence\": <0.0-1.0>} "
                "instead of a raw value. Confidence reflects how clearly the field was readable "
                "(1.0 = clear printed text; 0.9 = minor obscuring; 0.7 = handwritten/faded; "
                "0.5 = inferred; 0.3 or lower = barely visible). "
                "Do NOT add computed, inferred, or document-type metadata fields. "
                "Do NOT duplicate the same value under multiple key names. "
                "If a field label is visible but its value is redacted (black bar, [REDACTED] stamp, "
                "white-out, or any obscured region), include it as {\"value\": null, \"redacted\": true} "
                "rather than a confidence object.\n\n"
                "- ``items``: array of row-level objects. Every line item, container row, and batch "
                "detail row must be a separate object in this array. Each object must be a flat dict "
                "with enough context columns to be self-contained — for example, a packing-list batch "
                "row must include its container_no; a BOL container row must include container_no and "
                "seal_no. Do NOT leave row-level data only in ``tables``. "
                "For EVERY cell value in items, use {\"value\": <cell_value>, \"confidence\": <0.0-1.0>} "
                "the same way as header fields. For redacted cells use {\"value\": null, \"redacted\": true}.\n\n"
                "- ``tables``: array of table objects (``headers`` + ``rows``) ONLY for tabular data "
                "that does NOT fit as flat row objects in ``items`` — e.g. tax calculation tables, "
                "freight rate tables, summary totals tables. "
                "For redacted cells in tables, use {\"value\": null, \"redacted\": true}.\n\n"
                "- ``raw_text``: full plain-text content of the document.\n\n"
                "Return ONLY valid JSON — no markdown fences, no commentary."
            )

        # Focused mode — build explicit field list
        lines = [
            "Extract the following fields from the document and return a JSON object.\n",
            "=== HEADER FIELDS ===",
        ]

        for fname, fdef in claude_schema.get("fields", {}).items():
            req_tag = "[REQUIRED]" if fdef.get("required") else "[optional]"
            desc = fdef.get("description", "")
            type_tag = fdef.get("type", "string")
            line = f"  - {fname} ({type_tag}) {req_tag}"
            if desc:
                line += f": {desc}"
            lines.append(line)

        items_def = claude_schema.get("items")
        if items_def:
            field_name = items_def.get("field_name", "items")
            lines.append(f"\n=== LINE ITEMS (field: '{field_name}') ===")
            lines.append(
                f"  Return as a JSON array under the key '{field_name}'. "
                "For EVERY cell value in each row, use {\"value\": <cell_value>, \"confidence\": <0.0-1.0>} "
                "(same confidence scale as header fields). Missing cells use null; redacted cells use "
                "{\"value\": null, \"redacted\": true}."
            )
            for fname, fdef in items_def.get("fields", {}).items():
                req_tag = "[REQUIRED]" if fdef.get("required") else "[optional]"
                desc = fdef.get("description", "")
                type_tag = fdef.get("type", "string")
                line = f"  - {fname} ({type_tag}) {req_tag}"
                if desc:
                    line += f": {desc}"
                lines.append(line)

        lines.append(
            "\nCONFIDENCE RULE: For every field in ``fields``, return "
            "{\"value\": <extracted_value>, \"confidence\": <0.0-1.0>} instead of a raw value. "
            "Confidence reflects extraction certainty: 1.0=clear print, 0.9=minor obscuring, "
            "0.7=handwritten/faded, 0.5=uncertain/inferred, 0.3=barely visible. "
            "For absent/missing fields still return null (not a confidence object).\n"
            "\nREDACTION RULE: If a field's label is visible but its value is redacted "
            "(black bar, [REDACTED] stamp, white-out, or any obscured region), "
            "return {\"value\": null, \"redacted\": true} for that field instead of null. "
            "The same applies to individual cells inside ``items``.\n"
            "\nReturn the JSON with top-level keys:\n"
            f"  - ``fields``: object containing all header fields above\n"
            f"  - ``items``: array of line-item objects (use field name above for the key)\n"
            "  - ``raw_text``: plain-text content of the document\n\n"
            "Return ONLY valid JSON — no markdown, no explanation."
        )

        return "\n".join(lines)

    def _parse_json_response(self, raw: str) -> Dict[str, Any]:
        """
        Parse a JSON string returned by Claude.

        Strips markdown code fences if present before parsing.

        Args:
            raw: Raw text response from Claude.

        Returns:
            Parsed dictionary.

        Raises:
            ParserException: If JSON cannot be decoded.
        """
        text = raw.strip()

        # Strip markdown fences (```json ... ``` or ``` ... ```)
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1:]
            if text.endswith("```"):
                text = text[:-3].rstrip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            # Attempt recovery if the response was truncated (hit max_tokens).
            # Strategy: find the last complete JSON object entry, close all
            # open braces, and retry — preserving whatever fields were extracted.
            recovered = self._recover_truncated_json(text)
            if recovered is not None:
                logger.warning(
                    f"Claude response was truncated (max_tokens?); recovered "
                    f"{len(recovered.get('fields', {}))} fields from partial JSON. "
                    f"Consider increasing max_tokens in config/providers.yaml."
                )
                return recovered

            logger.error(f"Failed to parse Claude JSON response: {exc}")
            logger.debug(f"Raw response (first 500 chars): {raw[:500]}")
            raise ParserException(
                f"Claude returned invalid JSON: {exc}. "
                f"Response preview: {raw[:200]}"
            ) from exc

    @staticmethod
    def _recover_truncated_json(text: str) -> Optional[Dict[str, Any]]:
        """
        Attempt to recover a JSON object truncated mid-stream (e.g. hit max_tokens).

        Finds the last fully-closed field entry (`},`), trims there, and closes
        all open brace/bracket pairs so the result is valid JSON.
        """
        # Find the last position that ends a complete object value: `},` or `}`
        # followed only by whitespace/newlines up to the truncation point.
        last_complete = -1
        for marker in ('},\n', '},', '}'):
            pos = text.rfind(marker)
            if pos > last_complete:
                last_complete = pos + len(marker.rstrip(','))  # keep the closing `}`

        if last_complete <= 0:
            return None

        truncated = text[:last_complete]

        # Count and close open braces/brackets
        opens = truncated.count('{') - truncated.count('}')
        closes = truncated.count('[') - truncated.count(']')
        truncated += (']' * max(closes, 0)) + ('}' * max(opens, 0))

        try:
            return json.loads(truncated)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _normalize_key(key: str) -> str:
        """
        Normalise a field key to snake_case.

        Args:
            key: Raw key string.

        Returns:
            Normalised snake_case key (empty string if input is empty/None).
        """
        if not key:
            return ""
        import re
        # Replace spaces, hyphens, slashes with underscores
        normalised = re.sub(r"[\s\-/\\]+", "_", key.strip().lower())
        # Remove characters that are not alphanumeric or underscore
        normalised = re.sub(r"[^\w]", "", normalised)
        # Collapse multiple underscores
        normalised = re.sub(r"_+", "_", normalised).strip("_")
        return normalised


# ==============================================================================
# Provider factory registration
# ==============================================================================

def _create_claude_provider(provider_config: dict) -> ClaudeProvider:
    """
    Factory function registered with ProviderFactory.

    Reads configuration from ``config/providers.yaml`` (claude section)
    and instantiates a ClaudeProvider.

    Args:
        provider_config: Provider-specific config dict from providers.yaml.

    Returns:
        Configured ClaudeProvider instance.
    """
    api_key = os.getenv(provider_config.get("api_key_env", "ANTHROPIC_API_KEY"))

    bedrock_cfg = provider_config.get("bedrock", {})
    bedrock_enabled = bedrock_cfg.get("enabled", False)
    aws_region = bedrock_cfg.get("region", os.getenv("AWS_REGION", "us-east-1"))
    bedrock_model_id = bedrock_cfg.get("model_id")

    model = provider_config.get("model", "claude-sonnet-4-6")
    max_tokens = provider_config.get("max_tokens", 32768)
    timeout = provider_config.get("timeout", 300)

    logger.debug(
        f"Creating ClaudeProvider: model={model}, bedrock={bedrock_enabled}, "
        f"region={aws_region}"
    )

    return ClaudeProvider(
        api_key=api_key,
        model=model,
        max_tokens=max_tokens,
        timeout=timeout,
        bedrock_enabled=bedrock_enabled,
        aws_region=aws_region,
        bedrock_model_id=bedrock_model_id,
    )


# Self-register when this module is imported
try:
    from .provider_factory import ProviderFactory
    ProviderFactory.register_provider("claude", _create_claude_provider)
    logger.info("Claude provider registered successfully")
except Exception as _reg_exc:
    logger.warning(f"Failed to register Claude provider: {_reg_exc}")
