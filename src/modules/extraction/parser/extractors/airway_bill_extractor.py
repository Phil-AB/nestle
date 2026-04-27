"""
Specialised extractor for Airway Bill (AWB) documents — IATA standard format.

AWB layout conventions:
- Top section: Shipper name/address, Consignee name/address, Issuing carrier
- Middle section: Airport of departure, Airport of destination, flight info,
  routing details, declared value for carriage, declared value for customs
- Goods section: Number of pieces, gross weight, kg/lb indicator,
  rate class, commodity item number, chargeable weight, rate/charge,
  total, nature and quantity of goods (description)
- Charges section: weight charge, valuation charge, tax, other charges,
  total collect/prepaid
- AWB number (format: XXX-XXXXXXXX, 3-digit carrier code + 8 digits)

Key field differences from ocean BOL:
- No container numbers / seal numbers
- AWB number (not BL number) is the transport reference
- Airport of departure / Airport of destination (not port of loading/discharge)
- Pieces count (not container count)
- Chargeable weight vs gross weight (different concepts)
- IATA commodity codes (not HS codes on the AWB itself)
"""

import logging
from typing import Any, Dict, List

from .base import BaseDocumentExtractor

logger = logging.getLogger(__name__)


class AirwayBillExtractor(BaseDocumentExtractor):
    """Specialised extractor for Airway Bill (AWB) documents."""

    async def extract(
        self,
        fields: Dict[str, Any],
        items: List[Dict],
        blocks: List[Dict],
        document_type: str,
    ) -> Dict[str, Any]:
        """Single unified LLM pass over full AWB content."""
        try:
            table_text = self._serialize_items(items, max_rows=60)
            block_text = self._serialize_blocks(blocks, max_blocks=100)
            existing_summary = self._fields_summary(fields, max_fields=25)

            prompt = self._build_awb_prompt(
                table_text=table_text,
                block_text=block_text,
                existing_summary=existing_summary,
            )

            result = await self.llm_extraction.ainvoke(prompt)
            extracted = {k: v for k, v in result.model_dump().items() if v is not None}

            logger.info(
                f"AirwayBillExtractor: extracted {len(extracted)} fields "
                f"(items={len(items)}, blocks={len(blocks)})"
            )
            return extracted

        except Exception as e:
            logger.error(f"AirwayBillExtractor.extract failed: {e}", exc_info=True)
            return {}

    def _build_awb_prompt(
        self,
        table_text: str,
        block_text: str,
        existing_summary: str,
    ) -> str:
        return f"""You are a customs document expert specialised in Air Waybills (AWB).

ALREADY EXTRACTED FIELDS (do not re-extract unless you can improve them):
{existing_summary or "none"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TABLE ROWS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{table_text or "(no table rows)"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DOCUMENT TEXT BLOCKS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{block_text or "(no blocks)"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXTRACTION RULES — Air Waybill (AWB)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TRANSPORT REFERENCE:
- bl_number      = AWB number (format: 3-digit carrier code + hyphen + 8 digits,
                   e.g. "074-12345678"). Labels: "Air Waybill No", "AWB No", "MAWB".
                   This is the AWB's equivalent of the ocean BL number.
- booking_number = House AWB or booking reference if separate from the master AWB.
- vessel_name    = Flight number (e.g. "LH 592"). Labels: "Flight No", "Flight Number".
- port_of_loading    = Airport of departure (IATA code or full name).
                       Labels: "Airport of Departure", "From", "Origin Airport".
- port_of_discharge  = Airport of destination (IATA code or full name).
                       Labels: "Airport of Destination", "To", "Destination Airport".
- carrier_name   = Issuing carrier / airline name.

PARTIES:
- shipper_name    = COMPANY NAME ONLY of the shipper/consignor.
                    Labels: "Shipper", "Consignor", "Shipper's Name and Address" (name part only).
- shipper_address = full postal address of the shipper.
- consignee_name  = COMPANY NAME ONLY of the consignee.
                    Labels: "Consignee", "Consignee's Name and Address" (name part only).
- consignee_address = full postal address of the consignee.
- notify_party    = notify party if stated.

REFERENCE NUMBERS:
- order_number    = supplier's order number if referenced
- po_number       = buyer's PO / customer reference if stated
- contract_number = contract number if referenced
- invoice_number  = invoice number referenced on the AWB

COMMERCIAL TERMS:
- incoterm  = delivery/trade term if stated
- currency  = currency code used

GOODS & WEIGHTS:
- product_description = nature and quantity of goods / description of goods
- gross_weight    = total ACTUAL gross weight. Include unit (KG or LB).
                    Labels: "Gross Weight", "Actual Gross Weight".
                    Note: "Chargeable Weight" is a billing concept — do NOT use it as gross_weight.
- net_weight      = net weight if stated separately
- quantity        = number of pieces / units. Labels: "No. of Pieces", "Pieces", "Quantity".
- unit_of_measure = unit (PCS, PKG, BAGS, etc.)
- hs_code         = HS/commodity code if stated on the AWB

Populate only the fields you find with confidence. Leave everything else as null."""
