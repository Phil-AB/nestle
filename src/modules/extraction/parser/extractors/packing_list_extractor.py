"""
Specialised extractor for Packing List documents.

Packing list layout conventions (Nestlé Ghana import context):
- Header section: shipper/exporter block, consignee/delivered-to block,
  packing list number, date, order/contract/PO references, incoterm
- Container table: per-container rows with container ID, seal, description,
  qty (bags), net weight (kg), gross weight (kg)
- TOTALS ROW at the bottom of the container table OR a "Total sent X" summary row
  — this is the SHIPMENT TOTAL and must be used for net_weight, gross_weight, quantity
- Possibly a separate key-value section for order references and consignee address

Key extraction problems this extractor solves:
1. net_weight / gross_weight / quantity: must come from TOTALS row, not per-container
2. product_description: in the "Description" column of the container table
3. container_count / container_numbers: from the container table
4. Shipper block may appear as a text block (section header pattern) rather than
   a standard key-value pair
"""

import logging
from typing import Any, Dict, List

from .base import BaseDocumentExtractor

logger = logging.getLogger(__name__)


class PackingListExtractor(BaseDocumentExtractor):
    """Specialised extractor for Packing List documents."""

    async def extract(
        self,
        fields: Dict[str, Any],
        items: List[Dict],
        blocks: List[Dict],
        document_type: str,
    ) -> Dict[str, Any]:
        """Single unified LLM pass over full packing list content."""
        try:
            table_text = self._serialize_items(items, max_rows=80)
            block_text = self._serialize_blocks(blocks, max_blocks=80)
            existing_summary = self._fields_summary(fields, max_fields=25)

            prompt = self._build_packing_list_prompt(
                table_text=table_text,
                block_text=block_text,
                existing_summary=existing_summary,
            )

            result = await self.llm_extraction.ainvoke(prompt)
            extracted = {k: v for k, v in result.model_dump().items() if v is not None}

            logger.info(
                f"PackingListExtractor: extracted {len(extracted)} fields "
                f"(items={len(items)}, blocks={len(blocks)})"
            )
            return extracted

        except Exception as e:
            logger.error(f"PackingListExtractor.extract failed: {e}", exc_info=True)
            return {}

    def _build_packing_list_prompt(
        self,
        table_text: str,
        block_text: str,
        existing_summary: str,
    ) -> str:
        return f"""You are a customs document expert specialised in Packing Lists.

ALREADY EXTRACTED FIELDS (do not re-extract unless you can improve them):
{existing_summary or "none"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TABLE ROWS (container rows + any totals rows):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{table_text or "(no table rows)"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DOCUMENT TEXT BLOCKS (free-text sections, header info):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{block_text or "(no blocks)"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXTRACTION RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PARTIES:
- shipper_name    = COMPANY NAME ONLY of the EXPORTER / SUPPLIER who ISSUED this packing list.
                    This is the company whose letterhead or name appears at the TOP of the document
                    as the document author/sender — NOT the buyer or consignee.
                    Labels to look for: "Exporter", "Shipper", "Seller", "From", "Issued by",
                    or simply the company name in the document letterhead.
                    CRITICAL: "Bill To", "Invoice To", "Consignee", "Delivered To" are the BUYER,
                    NOT the shipper. Never use the "Bill To" party as shipper_name.
                    If no explicit "Shipper" label exists, use the company name shown as the
                    document issuer (e.g. the company whose address is at the top, NOT the Bill-To address).
- shipper_address = full postal address of the shipper (same company as shipper_name above).
                    CRITICAL: Do NOT use the "Bill To" address here — that belongs in consignee_address.
- consignee_name  = COMPANY NAME ONLY of the consignee / buyer / delivered-to party.
                    Labels: "Consignee", "Delivered To", "Invoice To", "Bill To", "Ship To".
- consignee_address = full postal address of the consignee (the "Bill To" or "Delivery" address).

REFERENCE NUMBERS:
- order_number    = supplier's internal order (labels: "Our Order No", "Order No", "Order Number")
- po_number       = buyer's PO / customer reference (labels: "Your Order No", "Customer Ref",
                    "Customer Reference", "PO No")
- contract_number = contract reference (labels: "Contract No", "Contract Number")
- incoterm        = delivery terms (labels: "Shipping Condition", "Delivery Terms", "Incoterm")

CONTAINER TABLE — TWO TYPES OF ROWS:
The container table has:
  a) PER-CONTAINER rows: one row per container, showing that container's qty and weight
  b) TOTALS ROW(S): labelled "TOTALS", "TOTAL", "Total sent Net weight", "Total sent Gross weight",
                    "Grand Total" — these show the ENTIRE SHIPMENT totals

WEIGHTS & QUANTITIES — CRITICAL RULES:

⚠️  SAP DELIVERY NOTE WARNING: Some packing lists are SAP Delivery Notes, not traditional
packing lists. In SAP Delivery Notes the line-items table has columns like:
  Line | Material Description | Quantity | UOM | Batch | EAN/SSCC | Net/Weight

The "Net/Weight" column in SAP Delivery Notes contains the LINE ITEM MONETARY VALUE IN USD
(e.g. 52,143.84), NOT a weight in KG. DO NOT use this column for gross_weight or net_weight.

For SAP Delivery Notes, the ACTUAL WEIGHTS are in the document summary/footer, e.g.:
  "Gross Weight: 15,123 TNE"   ← this is KG (TNE is a SAP unit code equivalent to KG here)
  "Net Weight: 9.677"          ← this may be in tonnes; prefer the value labeled KG elsewhere
  "PESO BRUTO: 12,897.024 KG"

⚠️  NUMBER FORMAT: Commas in weight values are THOUSANDS SEPARATORS, not decimal points.
  "15,123" means FIFTEEN THOUSAND ONE HUNDRED AND TWENTY-THREE (15123), not 15.123.
  "12,897" means TWELVE THOUSAND EIGHT HUNDRED AND NINETY-SEVEN (12897), not 12.897.
  Always output the numeric value WITHOUT the comma: "15,123 TNE" → gross_weight = 15123.

The ACTUAL QUANTITY for SAP Delivery Notes is the sum of the "Quantity" column in the
line-items table (integer cases/packages), NOT from the Net/Weight column.

For TRADITIONAL packing lists:
ALWAYS use the TOTALS ROW values, never per-container values.
Look for:
  - A row where the first/label column says "TOTAL", "TOTALS", "Total sent Net weight", etc.
  - "Total Net Weight: 189,000.00 KG" anywhere in the document
  - "Total Gross Weight: 192,780.00 KG"
  - "Total Units: 7,560 BAGS" or similar

- net_weight   = TOTAL shipment net weight in KG. From TOTALS row, footer label, or "PESO NETO".
                 If the only net weight found is in tonnes (clearly a small decimal when the
                 gross weight is thousands of KG), convert: multiply by 1000.
                 NEVER use a monetary USD value as net_weight.
- gross_weight = TOTAL shipment gross weight in KG. From TOTALS row, footer "Gross Weight: X KG/TNE",
                 or "PESO BRUTO". TNE in SAP context = KG — use the raw number.
                 NEVER use a monetary USD value as gross_weight.
- quantity     = TOTAL shipment quantity (integer packages/cases). From TOTALS row or sum of
                 the Quantity column in the line-items table. Do NOT use per-container qty only.
- unit_of_measure = unit (BAG, KG, CS, MT, etc.)
- container_count   = total number of containers (integer). Count the data rows or look for
                      "No. of Containers: 7" in a header field, or count "Container Num:" entries.
- container_numbers = comma-separated container IDs (pattern: 4 uppercase letters + 7 digits).
                      Collect ALL container IDs from the table AND from "Container Num:" header
                      fields in SAP Delivery Notes.

GOODS:
- product_description = description of the goods from the "Description" column of the container
                        table. Use the most complete description. If all containers have the same
                        description, use it.
                        FORMATTING RULES for product codes:
                        • Alphanumeric model/batch codes (e.g. "MQAV004F-1") must keep the hyphen
                          attached to the adjacent characters — no spaces around the hyphen.
                        • Commas separating the model code from the bag size belong AFTER the code,
                          not inside it: correct → "MQAV004F-1, 25kg bag"; wrong → "MQAV004F - 1,25 kg bag".
                        • Copy the description faithfully; do not reformat or reorder the words.
- hs_code             = HS tariff code if shown anywhere on the document.
- country_of_origin   = country of manufacture if stated.

Populate only the fields you find with confidence. Leave everything else as null."""
