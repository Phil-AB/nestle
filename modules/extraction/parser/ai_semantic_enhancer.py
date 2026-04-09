"""
AI Semantic Enhancer for intelligent document extraction post-processing.

Adds AI-powered semantic understanding to raw extraction results from
providers like Reducto. Solves problems like:
- Text sections treated as single-column tables
- Section headers (EXPORTER:, CONSIGNEE:) not recognized as labels
- Multi-line addresses split into separate rows
- Context-dependent field extraction (e.g. Total Excl. VAT = FOB when FCA + 0% VAT)
- Container numbers embedded in description text
- PO number disambiguation (Our Order Number vs Your Order Number)
- Incoterm extracted from Shipping Condition / Delivery Terms field labels

Uses structured outputs (Pydantic schemas) for all LLM calls to eliminate
field-naming non-determinism.
"""

import logging
from typing import Dict, Any, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Structured output schemas
#
# These Pydantic models are bound to every LLM call via
# `llm.with_structured_output(...)`.  The model is forced to either fill a
# field or return null — it cannot invent field names or merge distinct
# concepts (e.g. shipper_name + shipper_address) into a single value.
# ─────────────────────────────────────────────────────────────────────────────

class DocumentExtractionFields(BaseModel):
    """
    Canonical structured output for a single LLM extraction pass.
    All fields are optional — only include what is present in the source.
    """

    # ── Parties ──────────────────────────────────────────────────────────────
    shipper_name: Optional[str] = Field(
        None,
        description=(
            "EXPORTER / SHIPPER company name ONLY — the company that manufactured "
            "or dispatched the goods (labelled 'Exporter', 'Shipper', 'Seller', 'From', 'Sold By'). "
            "Do NOT include street/city/postal address here. "
            "Do NOT use the ocean carrier or shipping line as the shipper. "
            "Example: 'utriPro B.V.' or 'Vreugdenhil Dairy Foods B.V.'"
        )
    )
    shipper_address: Optional[str] = Field(
        None,
        description=(
            "Full postal address of the shipper/exporter — street, city, postcode, country. "
            "This is the address block that follows the company name. "
            "May be multi-line (use \\n as separator). "
            "Do NOT put the company name here; that belongs in shipper_name."
        )
    )
    shipper_country: Optional[str] = Field(
        None,
        description="Country of the shipper/exporter (e.g. 'Netherlands', 'NL')"
    )
    consignee_name: Optional[str] = Field(
        None,
        description=(
            "CONSIGNEE / IMPORTER company name ONLY "
            "(labelled 'Consignee', 'Invoice To', 'Bill To', 'Importer', 'Sold To', 'To'). "
            "Do NOT include address here."
        )
    )
    consignee_address: Optional[str] = Field(
        None,
        description="Full postal address of the consignee/importer. May be multi-line."
    )
    consignee_country: Optional[str] = Field(
        None,
        description="Country of the consignee/importer"
    )
    notify_party: Optional[str] = Field(
        None,
        description="Notify party name and address (bill of lading field)"
    )
    carrier_name: Optional[str] = Field(
        None,
        description=(
            "Ocean carrier or shipping line name "
            "(labelled 'Carrier', 'Ocean Carrier', 'Shipping Line', 'Vessel Operator'). "
            "This is NOT the shipper."
        )
    )

    # ── Reference numbers ────────────────────────────────────────────────────
    invoice_number: Optional[str] = Field(
        None,
        description="Invoice identifier / invoice number"
    )
    order_number: Optional[str] = Field(
        None,
        description=(
            "Supplier's internal order number (labelled 'Our Order Number', 'Order No', "
            "'Supplier Order'). NOT a shipping booking reference."
        )
    )
    po_number: Optional[str] = Field(
        None,
        description=(
            "Buyer's purchase order number (labelled 'Your Order Number', 'PO Number', "
            "'Customer Reference', 'Purchase Order'). On a supplier invoice, "
            "'Your Order Number' = the buyer's PO."
        )
    )
    contract_number: Optional[str] = Field(
        None,
        description="Contract or agreement number"
    )
    bl_number: Optional[str] = Field(
        None,
        description=(
            "Bill of lading number (labelled 'B/L No', 'BL No', 'Bl. No.', "
            "'Bill of Lading No', 'BL Number'). "
            "On a bill_of_lading document, if absent but booking_number is present, "
            "use booking_number as bl_number."
        )
    )
    booking_number: Optional[str] = Field(
        None,
        description=(
            "Shipping booking reference (labelled 'Booking No', 'Booking Ref'). "
            "NOT the same as order_number."
        )
    )
    etls_approval_number: Optional[str] = Field(
        None,
        description="ETLS (ECOWAS Trade Liberalisation Scheme) approval number"
    )

    # ── Commercial terms ─────────────────────────────────────────────────────
    incoterm: Optional[str] = Field(
        None,
        description=(
            "Delivery / trade term including place (e.g. 'FCA ROTTERDAM PORT', 'FOB TEMA'). "
            "Look for labels: 'Shipping Condition', 'Delivery Terms', 'Trade Term', 'Incoterm'."
        )
    )
    currency: Optional[str] = Field(
        None,
        description="Currency code (EUR, USD, GBP, GHS, etc.)"
    )

    # ── Financial ────────────────────────────────────────────────────────────
    total_fob_value: Optional[str] = Field(
        None,
        description=(
            "FOB / FCA value of the shipment. "
            "Look for 'FOB Value', 'Total Excl. VAT' (when incoterm is FCA/FOB and VAT=0), "
            "'Net Amount'. Include currency symbol if shown."
        )
    )
    total_invoice_value: Optional[str] = Field(
        None,
        description="Total amount on the invoice including all charges"
    )
    vat_amount: Optional[str] = Field(
        None,
        description="VAT amount shown on the invoice"
    )

    # ── Transport ────────────────────────────────────────────────────────────
    vessel_name: Optional[str] = Field(
        None,
        description="Vessel or ship name"
    )
    port_of_loading: Optional[str] = Field(
        None,
        description="Port where goods are loaded / place of departure"
    )
    port_of_discharge: Optional[str] = Field(
        None,
        description="Destination port / port of delivery"
    )
    container_numbers: Optional[str] = Field(
        None,
        description=(
            "Comma-separated list of container IDs. "
            "Container ID format: 4 uppercase letters + 7 digits (e.g. GCNU4823653, CAAU8000243)."
        )
    )
    container_count: Optional[int] = Field(
        None,
        description="Total number of containers (integer)"
    )
    seal_numbers: Optional[str] = Field(
        None,
        description="Comma-separated list of seal numbers"
    )

    # ── Goods ────────────────────────────────────────────────────────────────
    product_description: Optional[str] = Field(
        None,
        description="Description of the goods"
    )
    hs_code: Optional[str] = Field(
        None,
        description="Harmonized tariff code (e.g. '1901.90', '19019020')"
    )
    country_of_origin: Optional[str] = Field(
        None,
        description="Country where goods were manufactured/produced"
    )
    net_weight: Optional[str] = Field(
        None,
        description=(
            "TOTAL shipment net weight (include unit, e.g. '12500.00 KG'). "
            "If the document lists per-container weights AND a grand total, extract the GRAND TOTAL only. "
            "Never extract a per-container or per-item subtotal as this field."
        )
    )
    gross_weight: Optional[str] = Field(
        None,
        description=(
            "TOTAL shipment gross weight (include unit, e.g. '13200.00 KG'). "
            "If the document lists per-container weights AND a grand total, extract the GRAND TOTAL only. "
            "Never extract a per-container or per-item subtotal as this field."
        )
    )
    quantity: Optional[str] = Field(
        None,
        description="Number of units / quantity"
    )
    unit_of_measure: Optional[str] = Field(
        None,
        description="Unit of measure (BAG, KG, PCS, MT, etc.)"
    )


class SemanticResolutionFields(BaseModel):
    """
    Output of the semantic resolution pass (step 4).

    Only fields that can be INFERRED from existing extracted data — not
    re-extracted from raw text.  Only populate a field when you are confident
    it can be derived from what is already present.
    """
    total_fob_value: Optional[str] = Field(
        None,
        description=(
            "Set ONLY if: incoterm is FCA/FOB AND vat_amount is 0/absent AND "
            "total_fob_value is currently missing. Then set to total_excl_vat or "
            "total_invoice_value."
        )
    )
    incoterm: Optional[str] = Field(
        None,
        description=(
            "Set ONLY if incoterm is missing but shipping_condition or delivery_terms "
            "is present. Use that value."
        )
    )
    po_number: Optional[str] = Field(
        None,
        description=(
            "Set ONLY if po_number is missing but your_order_number is present "
            "(on a supplier invoice, 'Your Order Number' = buyer's PO)."
        )
    )
    order_number: Optional[str] = Field(
        None,
        description=(
            "Set ONLY if order_number is missing but our_order_number is present."
        )
    )
    container_count: Optional[int] = Field(
        None,
        description=(
            "Set ONLY if container_count is missing but can be derived from a "
            "container list or pattern like '7X40FT'."
        )
    )
    container_numbers: Optional[str] = Field(
        None,
        description=(
            "Comma-separated container IDs found in ANY field value "
            "(including text_block_* fields). Pattern: 4 letters + 7 digits."
        )
    )
    country_of_origin: Optional[str] = Field(
        None,
        description=(
            "Set ONLY if missing at header level but all line items share the same origin."
        )
    )
    bl_number: Optional[str] = Field(
        None,
        description=(
            "Set ONLY if bl_number is missing. Look for BL label patterns in text_block_* "
            "fields. On bill_of_lading: if still absent but booking_number present, "
            "set bl_number = booking_number."
        )
    )
    shipper_name: Optional[str] = Field(
        None,
        description=(
            "Set ONLY if shipper_name is missing but can be found in a text_block_* field "
            "near a 'Shipper:' or 'Exporter:' label. Company name only, not address. "
            "Do NOT use the carrier name."
        )
    )
    consignee_name: Optional[str] = Field(
        None,
        description=(
            "Set ONLY if consignee_name is missing but can be found near a 'Consignee:' "
            "or 'Invoice To:' label in any field. Company name only."
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main enhancer class
# ─────────────────────────────────────────────────────────────────────────────

class AISemanticEnhancer:
    """
    Enhances raw extraction with AI-powered semantic understanding.

    This layer adds intelligence on top of computer vision extraction,
    enabling the system to understand document structure and context
    beyond bounding boxes and table grids.

    Dispatch order:
        1. If a specialised extractor is registered for the document type,
           delegate to it.  Specialised extractors use a single unified LLM
           pass with document-type-specific prompts and domain knowledge.
        2. Otherwise fall back to the generic 4-step pipeline:
           a. _parse_sections_with_ai   — section-header blocks
           b. _parse_table_with_ai      — multi-column table rows
           c. _parse_blocks_with_ai     — free-text blocks
           d. _resolve_field_semantics  — contextual field mapping

    All LLM calls use structured outputs (Pydantic schemas) to eliminate
    field-naming non-determinism.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model_variant: Optional[str] = None
    ):
        """
        Initialize AI Semantic Enhancer.

        Uses centralized LLM configuration from config/llm.yaml.
        Module name: "ai_semantic_enhancer"
        """
        from shared.utils.llm_config import get_llm_for_module
        from .extractors.registry import DocumentExtractorRegistry

        self.llm = get_llm_for_module(
            module_name="ai_semantic_enhancer",
            provider=provider,
            model_variant=model_variant
        )

        # Pre-bind structured output variants to avoid rebuilding per call
        self._llm_extraction = self.llm.with_structured_output(DocumentExtractionFields)
        self._llm_resolution = self.llm.with_structured_output(SemanticResolutionFields)

        # Specialised extractor registry — dispatched before generic pipeline
        self._extractor_registry = DocumentExtractorRegistry(
            llm_extraction=self._llm_extraction,
            llm_resolution=self._llm_resolution,
        )

        logger.info("Initialized AI Semantic Enhancer with structured outputs and extractor registry")

    async def enhance_extraction(
        self,
        raw_extraction: Dict[str, Any],
        document_type: str
    ) -> Dict[str, Any]:
        """
        Enhance raw extraction via the registered specialised extractor.

        Every document type must have a specialist registered in
        DocumentExtractorRegistry.  If none exists, MissingExtractorError is
        raised — this is the correct behaviour: create a specialist rather than
        silently degrading to a generic approach.

        After the specialist runs, the semantic resolution step infers any
        fields derivable from context (FOB value, PO aliasing, container count,
        BL number fallback, etc.).
        """
        from .extractors.registry import MissingExtractorError

        try:
            logger.info(f"AI Semantic Enhancement starting for {document_type}")

            fields = raw_extraction.get("fields", {})
            items = raw_extraction.get("items", [])
            blocks = raw_extraction.get("blocks", [])

            logger.info(f"Input: {len(fields)} fields, {len(items)} items, {len(blocks)} blocks")

            # ── Specialised extractor (required) ──────────────────────────────
            extractor = self._extractor_registry.get(document_type)
            logger.info(
                f"Dispatching to {type(extractor).__name__} for '{document_type}'"
            )
            extracted = await extractor.extract(fields, items, blocks, document_type)
            enhanced_fields = self._wrap_fields(extracted, "specialised_extractor")
            logger.info(f"  {type(extractor).__name__}: {len(enhanced_fields)} fields extracted")

            # ── Semantic resolution ────────────────────────────────────────────
            # Infer fields derivable from context: FOB value, PO aliasing,
            # container count, BL number fallback, etc.
            merged = {**fields, **enhanced_fields}
            resolved_fields = await self._resolve_field_semantics(merged, document_type)
            enhanced_fields.update(resolved_fields)
            logger.info(f"  Semantic resolution: {len(resolved_fields)} additional fields")

            result = {
                "fields": enhanced_fields,
                "metadata": {
                    "ai_enhanced": True,
                    "enhancement_method": type(extractor).__name__,
                    "fields_added": len(enhanced_fields),
                }
            }

            logger.info(f"AI Semantic Enhancement complete: {len(enhanced_fields)} enhanced fields")
            return result

        except MissingExtractorError:
            # Re-raise so the caller sees the actionable message
            raise
        except Exception as e:
            logger.error(f"AI Semantic Enhancement failed: {e}", exc_info=True)
            return {
                "fields": {},
                "metadata": {
                    "ai_enhanced": False,
                    "enhancement_error": str(e)
                }
            }

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION DETECTION & PARSING
    # ─────────────────────────────────────────────────────────────────────────

    def _detect_single_column_table(self, items: List[Dict]) -> bool:
        """
        Detect if items array represents a single-column table.

        This is a common Reducto failure mode where structured sections
        are treated as a table with only one column.
        """
        if not items or len(items) < 3:
            return False

        first_item = items[0]
        if not isinstance(first_item, dict):
            return False

        data_keys = [k for k in first_item.keys()
                     if not k.startswith('_') and k not in ['row_index', 'table_bbox']]

        if len(data_keys) != 1:
            return False

        column_name = data_keys[0]
        consistent_count = sum(
            1 for item in items[:10]
            if isinstance(item, dict) and column_name in item
        )

        is_single_column = (consistent_count / min(len(items), 10)) >= 0.8

        if is_single_column:
            logger.info(f"Single-column table detected with column: '{column_name}'")

        return is_single_column

    async def _parse_sections_with_ai(
        self,
        items: List[Dict],
        document_type: str
    ) -> Dict[str, Any]:
        """
        Use AI to parse section-based content from a single-column table.

        Handles patterns like:
            EXPORTER:
            VREUGDENHIL DAIRY FOODS
            ARKERPOORT 5, NIJKERK
            CONSIGNEE:
            NESTLE GHANA LIMITED
            ...
        """
        try:
            text_lines = []
            for item in items:
                if isinstance(item, dict):
                    for key, value in item.items():
                        if not key.startswith('_') and key not in ['row_index', 'table_bbox']:
                            if isinstance(value, dict) and 'value' in value:
                                text_lines.append(value['value'])
                            else:
                                text_lines.append(str(value))
                            break

            if not text_lines:
                return {}

            content = "\n".join(text_lines)
            prompt = self._build_section_parsing_prompt(content, document_type)
            result: DocumentExtractionFields = await self._llm_extraction.ainvoke(prompt)
            parsed_fields = self._model_to_fields(result)

            logger.info(f"LLM parsed {len(parsed_fields)} fields from {len(text_lines)} lines")
            return self._wrap_fields(parsed_fields, "section_parsing")

        except Exception as e:
            logger.error(f"Section parsing with AI failed: {e}")
            return {}

    # ─────────────────────────────────────────────────────────────────────────
    # TABLE PARSING
    # ─────────────────────────────────────────────────────────────────────────

    async def _parse_table_with_ai(
        self,
        items: List[Dict],
        document_type: str,
        existing_fields: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use AI to parse multi-column table data for customs domain fields.

        Extracts fields that Reducto found structurally but that require
        semantic understanding to map correctly, e.g.:
        - 'Shipping Condition' → incoterm
        - 'Our Order Number' / 'Your Order Number' → order_number / po_number
        - 'Total Excl. VAT' → total_fob_value (when combined with incoterm context)
        - Line item HS codes, quantities, unit prices
        """
        try:
            if not items:
                return {}

            table_text = self._serialize_table_items(items)
            if not table_text.strip():
                return {}

            prompt = self._build_table_parsing_prompt(table_text, document_type, existing_fields)
            result: DocumentExtractionFields = await self._llm_extraction.ainvoke(prompt)
            parsed_fields = self._model_to_fields(result)

            logger.info(f"LLM extracted {len(parsed_fields)} fields from table")
            return self._wrap_fields(parsed_fields, "table_parsing")

        except Exception as e:
            logger.error(f"Table parsing with AI failed: {e}")
            return {}

    def _serialize_table_items(self, items: List[Dict]) -> str:
        """Convert table items to a readable text representation for the LLM."""
        lines = []
        for i, item in enumerate(items[:50]):  # cap at 50 rows
            if not isinstance(item, dict):
                continue
            row_parts = []
            for key, value in item.items():
                if key.startswith('_') or key in ['row_index', 'table_bbox']:
                    continue
                if isinstance(value, dict) and 'value' in value:
                    row_parts.append(f"{key}: {value['value']}")
                else:
                    row_parts.append(f"{key}: {value}")
            if row_parts:
                lines.append(" | ".join(row_parts))
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────────
    # BLOCK PARSING
    # ─────────────────────────────────────────────────────────────────────────

    async def _parse_blocks_with_ai(
        self,
        blocks: List[Dict],
        document_type: str
    ) -> Dict[str, Any]:
        """
        Use AI to parse unstructured text blocks.

        Extracts:
        - Container numbers and seal numbers (from packing lists / BOLs)
        - Miscellaneous reference numbers
        - Embedded addresses not picked up by section parsing
        """
        try:
            if not blocks:
                return {}

            block_text = self._serialize_blocks(blocks)
            if not block_text.strip():
                return {}

            prompt = self._build_block_parsing_prompt(block_text, document_type)
            result: DocumentExtractionFields = await self._llm_extraction.ainvoke(prompt)
            parsed_fields = self._model_to_fields(result)

            logger.info(f"LLM extracted {len(parsed_fields)} fields from blocks")
            return self._wrap_fields(parsed_fields, "block_parsing")

        except Exception as e:
            logger.error(f"Block parsing with AI failed: {e}")
            return {}

    def _serialize_blocks(self, blocks: List[Dict]) -> str:
        """Convert blocks to plain text for the LLM."""
        lines = []
        for block in blocks[:30]:  # cap at 30 blocks
            if isinstance(block, dict):
                text = block.get("text") or block.get("content") or block.get("value", "")
                if text:
                    lines.append(str(text))
            elif isinstance(block, str):
                lines.append(block)
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────────
    # SEMANTIC FIELD RESOLUTION
    # ─────────────────────────────────────────────────────────────────────────

    async def _resolve_field_semantics(
        self,
        all_fields: Dict[str, Any],
        document_type: str
    ) -> Dict[str, Any]:
        """
        Post-process all extracted fields to resolve contextual mappings.

        Handles cases that no structural extractor can solve:
        - 'Total Excl. VAT' = FOB value when Incoterm is FCA/FOB and VAT = 0
        - 'Shipping Condition' / 'Delivery Terms' → incoterm
        - Container count embedded in description ('7X40FT CONTAINER')
        - PO number from 'Your Order Number' (supplier's view = buyer's PO)
        - Country of origin at header level from BOE country code
        """
        try:
            if not all_fields:
                return {}

            # Flatten field values for the prompt
            flat_fields = {}
            for key, val in all_fields.items():
                if isinstance(val, dict) and 'value' in val:
                    flat_fields[key] = val['value']
                else:
                    flat_fields[key] = val

            prompt = self._build_semantic_resolution_prompt(flat_fields, document_type)
            result: SemanticResolutionFields = await self._llm_resolution.ainvoke(prompt)
            resolved = self._model_to_fields(result)

            # Only return fields that are genuinely new (don't overwrite existing)
            new_fields = {}
            for field_name, field_value in resolved.items():
                if field_name not in flat_fields and field_value not in (None, "", "null", "unknown"):
                    new_fields[field_name] = {
                        "value": field_value,
                        "source": "ai_enhancement",
                        "enhancement_method": "semantic_resolution"
                    }

            return new_fields

        except Exception as e:
            logger.error(f"Semantic field resolution failed: {e}")
            return {}

    # ─────────────────────────────────────────────────────────────────────────
    # PROMPT BUILDERS
    # ─────────────────────────────────────────────────────────────────────────

    def _build_section_parsing_prompt(self, content: str, document_type: str) -> str:
        """Build LLM prompt for section-header based content."""
        return f"""You are a customs document parsing expert. Extract structured fields from this {document_type} document.

The document contains SECTION HEADERS (ending with ":") followed by their content.
Common sections include EXPORTER:, CONSIGNEE:, DECLARANT:, SHIPPER:, SHIPPING DETAILS:, etc.

DOCUMENT CONTENT:
{content}

EXTRACTION RULES:
1. Identify section headers (lines ending with ":") and extract content under each section.
2. For party sections (EXPORTER, CONSIGNEE, DECLARANT, SHIPPER):
   - shipper_name / consignee_name = COMPANY NAME ONLY (first line after label)
   - shipper_address / consignee_address = full postal address (subsequent lines, joined with \\n)
   - These MUST be two separate fields — never combine name and address into one field.
3. For CARRIER / SHIPPING LINE sections: set carrier_name, NOT shipper_name.
4. If shipper_name and carrier_name would be the same company, set shipper_name to null.
5. For shipping sections: extract vessel_name, port_of_loading, port_of_discharge.
6. For reference sections: extract invoice_number, order_number, po_number, bl_number.

Populate only the fields you find. Leave everything else as null."""

    def _build_table_parsing_prompt(
        self,
        table_text: str,
        document_type: str,
        existing_fields: Dict[str, Any]
    ) -> str:
        """Build LLM prompt for multi-column table parsing with customs domain knowledge."""
        existing_summary = ", ".join(
            f"{k}={v['value'] if isinstance(v, dict) and 'value' in v else v}"
            for k, v in list(existing_fields.items())[:15]
        )

        return f"""You are a customs document parsing expert. Extract structured fields from this {document_type} table data.

ALREADY EXTRACTED FIELDS (do not re-extract these):
{existing_summary or "none"}

TABLE ROWS:
{table_text}

EXTRACTION RULES:
PARTIES:
- shipper_name = COMPANY NAME ONLY of the exporter/shipper (NOT address, NOT carrier).
  Labels: "Exporter", "Shipper", "Sold By", "From", "Seller".
- shipper_address = full postal address of the shipper (separate from shipper_name).
- consignee_name = COMPANY NAME ONLY of the consignee/importer.
  Labels: "Consignee", "Invoice To", "Bill To", "Importer", "Sold To".
- consignee_address = full postal address of the consignee (separate from consignee_name).
- carrier_name = ocean carrier / shipping line (NOT the shipper).

REFERENCE NUMBERS:
- order_number = supplier's internal order ("Our Order Number", "Order No")
- po_number = buyer's PO ("Your Order Number", "Customer Reference", "PO Number")
- invoice_number = invoice identifier
- bl_number = bill of lading number

COMMERCIAL TERMS:
- incoterm = full value including place (e.g. "FCA ROTTERDAM PORT")
  Labels: "Shipping Condition", "Delivery Terms", "Trade Term", "Incoterm"
- currency = currency code

FINANCIAL:
- total_fob_value = FOB/FCA value ("Total Excl. VAT" when incoterm is FCA/FOB and VAT=0)
- total_invoice_value = total amount including all charges
- vat_amount = VAT amount

WEIGHTS / GOODS:
- product_description = the description of the goods (look in line item "Description" columns, article descriptions, or "Description of Goods" fields). Use the most complete description found.
- net_weight = TOTAL shipment net weight. If per-item/per-container weights are shown alongside a grand total, use the GRAND TOTAL only.
- gross_weight = TOTAL shipment gross weight. If per-item/per-container weights are shown alongside a grand total, use the GRAND TOTAL only.
- quantity = TOTAL shipment quantity/units. If per-container quantities are shown alongside a grand total, use the GRAND TOTAL only.
- unit_of_measure, hs_code, country_of_origin

Populate only the fields you find. Leave everything else as null."""

    def _build_block_parsing_prompt(self, block_text: str, document_type: str) -> str:
        """Build LLM prompt for unstructured block content."""
        return f"""You are a customs document parsing expert. Extract structured data from these text blocks from a {document_type}.

TEXT BLOCKS:
{block_text}

EXTRACTION RULES:
TRANSPORT:
- container_numbers = comma-separated container IDs (pattern: 4 uppercase letters + 7 digits, e.g. GCNU4823653)
- container_count = integer count of containers
- seal_numbers = comma-separated seal numbers
- vessel_name, port_of_loading, port_of_discharge

REFERENCES:
- bl_number = bill of lading number (labels: "B/L No", "BL No", "Bl. No.", "Bill of Lading No")
- booking_number = shipping booking reference (labels: "Booking No", "Booking Ref")
  NOTE: booking_number is NOT order_number — do not map a booking ref to order_number.
- order_number = supplier internal order (labels: "Order No", "Our Order")
  ONLY use if the document explicitly refers to a supplier/internal order, not a booking ref.
- etls_approval_number = ETLS approval number if present

PARTIES:
- shipper_name = COMPANY NAME ONLY of exporter/shipper. Labels: "Shipper", "Exporter", "Seller", "From".
  Do NOT use the carrier/shipping line as shipper_name.
- shipper_address = full postal address of shipper (separate from shipper_name).
- consignee_name = COMPANY NAME ONLY of consignee/importer.
- consignee_address = full postal address of consignee.
- notify_party = notify party name and address.
- carrier_name = ocean carrier or shipping line name.

WEIGHTS / GOODS:
- product_description = the description of the goods (look in "Kind of packages; description of goods", "Description of Goods", or any item description column). Use the most complete description found.
- net_weight = TOTAL shipment net weight. If per-container weights are listed alongside a grand total (e.g. "NETT WEIGHT KG 189000.00"), use the GRAND TOTAL only — never a per-container value.
- gross_weight = TOTAL shipment gross weight. If per-container weights are listed alongside a grand total (e.g. "GROSS WEIGHT KG 192780.00"), use the GRAND TOTAL only — never a per-container value.
- quantity = TOTAL shipment quantity. If per-container quantities are listed alongside a grand total (e.g. "TOTALS 7560 BAGS"), use the GRAND TOTAL only.

Populate only the fields you find. Leave everything else as null."""

    def _build_semantic_resolution_prompt(
        self,
        flat_fields: Dict[str, Any],
        document_type: str
    ) -> str:
        """
        Build LLM prompt to resolve contextual field mappings from all extracted data.
        """
        fields_text = "\n".join(f"  {k}: {v}" for k, v in flat_fields.items())

        return f"""You are a customs document expert. Given the extracted fields below from a {document_type},
infer ADDITIONAL fields that can be derived from context. Only output fields NOT already listed.

EXTRACTED FIELDS:
{fields_text}

INFERENCE RULES (only apply when the target field is NOT already extracted):

1. FOB VALUE: If incoterm contains "FCA" or "FOB" AND vat_amount is 0/absent AND total_fob_value is missing
   → total_fob_value = total_excl_vat or total_invoice_value

2. INCOTERM: If incoterm is missing but shipping_condition or delivery_terms is present
   → incoterm = that value

3. PO NUMBER: On a supplier invoice, "Your Order Number" = buyer's PO
   → if po_number missing but your_order_number present: po_number = your_order_number
   → if order_number missing but our_order_number present: order_number = our_order_number

4. CONTAINER COUNT: If container_count missing but a pattern like "7X40FT" or a container list is present
   → derive container_count from it

5. CONTAINER NUMBERS: Scan ALL field values (including text_block_* fields) for 4-letter+7-digit IDs
   → container_numbers = comma-separated list of all found IDs

6. COUNTRY OF ORIGIN: If missing at header level but all line items share the same origin
   → country_of_origin = that value

7. BL NUMBER: Scan text_block_* fields for "Bl. No.", "B/L No", "BL No" patterns
   → bl_number = value following that label
   On bill_of_lading: if bl_number still missing but booking_number present
   → bl_number = booking_number

8. SHIPPER NAME: If shipper_name is missing, look in text_block_* fields near "Shipper:" or "Exporter:" labels
   → shipper_name = company name found (NOT the carrier, NOT an address)

9. CONSIGNEE NAME: If consignee_name is missing, look near "Consignee:" or "Invoice To:" labels
   → consignee_name = company name found

Populate only fields you can confidently derive. Leave everything else as null."""

    # ─────────────────────────────────────────────────────────────────────────
    # UTILITIES
    # ─────────────────────────────────────────────────────────────────────────

    def _model_to_fields(self, model: BaseModel) -> Dict[str, Any]:
        """
        Convert a Pydantic model instance to a plain dict, omitting null values.
        """
        return {
            k: v
            for k, v in model.model_dump().items()
            if v is not None
        }

    def _wrap_fields(
        self,
        fields: Dict[str, Any],
        method: str
    ) -> Dict[str, Any]:
        """
        Wrap extracted field values in the standard source-tracking envelope.
        """
        return {
            field_name: {
                "value": field_value,
                "source": "ai_enhancement",
                "enhancement_method": method
            }
            for field_name, field_value in fields.items()
        }


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────

_enhancer_instance: Optional[AISemanticEnhancer] = None


def get_ai_enhancer() -> AISemanticEnhancer:
    """Get or create AI Semantic Enhancer singleton."""
    global _enhancer_instance

    if _enhancer_instance is None:
        try:
            _enhancer_instance = AISemanticEnhancer()
            logger.info("AI Semantic Enhancer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AI Semantic Enhancer: {e}")
            raise

    return _enhancer_instance
