"""
Specialised extractor for Bill of Lading (BOL / Airway Bill) documents.

BOL layout conventions (ocean freight, Ghana import context):
- Page 1: Header block (shipper, consignee, notify party, carrier, ports),
          followed by a CONTAINER TABLE with per-container rows:
          Container No | Seal No | Description | Qty (bags) | Net Wt (kg) | Gross Wt (kg)
- Page 2: Continuation of container table, then a FREE-TEXT SUMMARY BLOCK:
          "NETT WEIGHT KG  189000.00"
          "GROSS WEIGHT KG 192780.00"
          "TOTALS  7560 BAGS"
          Also: Booking No, BL No, Order No, Customer Ref, Contract No

Key extraction problems this extractor solves:
1. Generic enhancer parses the container table first and picks up per-container
   weights/quantities (e.g. 27,540 kg per container instead of 192,780 kg total).
2. The page 2 summary block that holds the true totals is passed as blocks[]
   and may be beyond the 30-block cap of the generic enhancer.
3. The BOL carries the shipping-line's own reference (e.g. Grimaldi Ref No.)
   alongside the supplier's order number — these must not be confused.

Strategy: single unified LLM pass over ALL content (items + blocks) with
explicit BOL-specific instructions.  The LLM can see both the per-container
table rows AND the summary block in one call and is explicitly told to prefer
the summary section totals.
"""

import logging
from typing import Any, Dict, List

from .base import BaseDocumentExtractor

logger = logging.getLogger(__name__)


class BOLExtractor(BaseDocumentExtractor):
    """Specialised extractor for Bill of Lading documents."""

    async def extract(
        self,
        fields: Dict[str, Any],
        items: List[Dict],
        blocks: List[Dict],
        document_type: str,
    ) -> Dict[str, Any]:
        """
        Run a single unified LLM pass over the full BOL content.

        Instead of splitting into table-parse → block-parse (the generic
        enhancer's approach), this extractor assembles ALL content — both
        the container table rows and the text blocks — into one prompt and
        asks a single question with BOL-specific domain knowledge.
        """
        try:
            # Build a combined document representation
            table_text = self._serialize_items(items, max_rows=80)
            block_text = self._serialize_blocks(blocks, max_blocks=100)
            existing_summary = self._fields_summary(fields, max_fields=25)

            prompt = self._build_bol_prompt(
                table_text=table_text,
                block_text=block_text,
                existing_summary=existing_summary,
            )

            result = await self.llm_extraction.ainvoke(prompt)

            # model_to_fields: drop None values
            extracted = {
                k: v
                for k, v in result.model_dump().items()
                if v is not None
            }

            logger.info(
                f"BOLExtractor: extracted {len(extracted)} fields "
                f"(items={len(items)}, blocks={len(blocks)})"
            )
            return extracted

        except Exception as e:
            logger.error(f"BOLExtractor.extract failed: {e}", exc_info=True)
            return {}

    # ──────────────────────────────────────────────────────────────────────────

    def _build_bol_prompt(
        self,
        table_text: str,
        block_text: str,
        existing_summary: str,
    ) -> str:
        return f"""You are a customs document expert specialised in Bills of Lading (BOL).

ALREADY EXTRACTED FIELDS (do not re-extract unless you can improve them):
{existing_summary or "none"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CONTAINER TABLE ROWS (per-container data):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{table_text or "(no table rows)"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DOCUMENT TEXT BLOCKS (free-text sections, including page 2 summary):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{block_text or "(no blocks)"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXTRACTION RULES — read carefully before answering
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PARTIES:
- shipper_name     = company name of the shipper/exporter ONLY (label: "Shipper", "Exporter").
                     Copy verbatim from the document.
                     Return null ONLY if the company NAME itself is redacted or illegible
                     (e.g. replaced with "XXXXXXXXXX" or blank). If the name is visible but
                     the address is redacted/omitted, still extract the name.
                     Do NOT use the carrier/shipping line as shipper_name.
- shipper_address  = full postal address of the shipper. Separate from name.
                     Return null if the address is redacted — the name may still be extracted.
- consignee_name   = company name of the consignee ONLY (label: "Consignee"). No address.
                     Copy verbatim from the document.
- consignee_address = full postal address of the consignee.
- notify_party     = notify party name and address.
- carrier_name     = ocean carrier / shipping line (label: "Carrier", "Shipping Line").

REFERENCE NUMBERS — CRITICAL disambiguation:
This BOL carries TWO types of reference numbers that must NOT be confused:
  a) SHIPPING-LINE references: Booking No, Bl. No., B/L No, Carrier Ref → map to bl_number / booking_number
  b) SUPPLIER/TRADE references: Order No, Contract No, Customer Ref, PO No → map to order_number / contract_number / po_number

- bl_number      = Bill of Lading number (labels: "B/L No", "BL No", "Bl. No.", "Bill of Lading No").
                   If absent but Booking No is present, use Booking No as bl_number.
- booking_number = Booking reference (labels: "Booking No", "Booking Ref", "Booking Number").
- order_number   = SUPPLIER's internal order (labels: "Order No", "Our Order No", "Supplier Order").
                   This is the vendor's order reference, NOT a booking or carrier reference.
- contract_number = Contract or agreement number (labels: "Contract No", "Contract Number").
- po_number      = Buyer's PO / Customer Reference (labels: "Customer Ref", "PO No", "Your Order No").

TRANSPORT:
- vessel_name        = name of the vessel/ship
- port_of_loading    = port where goods are loaded
- port_of_discharge  = destination port
- container_numbers  = comma-separated list of all container IDs (pattern: 4 uppercase letters + 7 digits)
- container_count    = total number of containers (integer)
- seal_numbers       = comma-separated seal numbers
- incoterm           = delivery terms if stated

GOODS & WEIGHTS — THE MOST CRITICAL RULES:
This BOL has TWO representations of weight and quantity:
  1. CONTAINER TABLE (above): per-container rows — each row shows ONE container's weight/qty.
  2. SUMMARY BLOCK (in text blocks): the SHIPMENT TOTALS for the entire consignment.

ALWAYS use the SHIPMENT TOTALS from the summary block, not per-container values.
Look for patterns like:
  "NETT WEIGHT KG 189000.00"  → net_weight = "189000.00 KG"
  "GROSS WEIGHT KG 192780.00" → gross_weight = "192780.00 KG"
  "TOTALS 7560 BAGS"          → quantity = "7560"
  "TOTAL GROSS WEIGHT: 192,780.00 KG" → gross_weight = "192780.00 KG"
  A row labelled "TOTALS" or "TOTAL" in the container table → use those values

If NO explicit summary totals exist anywhere (neither in the table nor in the blocks),
return null for net_weight, gross_weight, and quantity. Do NOT use per-container values.

- product_description = description of the goods (label: "Kind of packages; description of goods",
                        "Description of Goods", or from the "Description" column of the container table).
                        Use the most complete description. If all containers have the same description, use it.
- net_weight    = TOTAL shipment net weight (from summary totals section ONLY)
- gross_weight  = TOTAL shipment gross weight (from summary totals section ONLY)
- quantity      = TOTAL shipment quantity/bags (from summary totals section ONLY)
- unit_of_measure = unit of measure (e.g. "BAGS", "KG", "MT")

Populate only the fields you find with confidence. Leave everything else as null."""
