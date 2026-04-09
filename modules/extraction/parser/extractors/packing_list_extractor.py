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
- shipper_name    = COMPANY NAME ONLY of the exporter/shipper. No address.
                    Labels: "Exporter", "Shipper", "Seller", "From".
- shipper_address = full postal address of the shipper.
- consignee_name  = COMPANY NAME ONLY of the consignee/delivered-to party.
                    Labels: "Consignee", "Delivered To", "Invoice To".
- consignee_address = full postal address of the consignee.

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
ALWAYS use the TOTALS ROW values, never per-container values.
Look for:
  - A row where the first/label column says "TOTAL", "TOTALS", "Total sent Net weight", etc.
  - "Total Net Weight: 189,000.00 KG" anywhere in the document
  - "Total Gross Weight: 192,780.00 KG"
  - "Total Units: 7,560 BAGS" or similar

- net_weight   = TOTAL shipment net weight (from TOTALS row or summary). Include unit.
- gross_weight = TOTAL shipment gross weight (from TOTALS row or summary). Include unit.
- quantity     = TOTAL shipment quantity (from TOTALS row). Do not use per-container qty.
- unit_of_measure = unit (BAG, KG, MT, etc.)
- container_count   = total number of containers (integer). Count the data rows or look for
                      "No. of Containers: 7" in a header field.
- container_numbers = comma-separated container IDs (pattern: 4 uppercase letters + 7 digits).
                      Collect ALL container IDs from the table.

GOODS:
- product_description = description of the goods from the "Description" column of the container
                        table. Use the most complete description. If all containers have the same
                        description, use it.
- hs_code             = HS tariff code if shown anywhere on the document.
- country_of_origin   = country of manufacture if stated.

Populate only the fields you find with confidence. Leave everything else as null."""
