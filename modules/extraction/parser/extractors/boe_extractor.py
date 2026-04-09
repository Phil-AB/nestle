"""
Specialised extractor for Bill of Entry (BOE) documents — Ghana GRA format.

BOE layout conventions (Ghana Customs GRA format):
- The GRA BOE uses a key-name encoded format where section numbers and field
  labels are embedded in the key names (e.g. "16_Currency_Code", "25_HS_Code").
- Section 16: CIF value, FOB value, freight, insurance, exchange rate, currency
- Section 21: Mode of transport, port info, vessel name
- Section 25: HS code, tariff details, duty rate, quantity, unit value per item
- Section 31: Country of origin, goods description per item
- Section 40: Customs value, duty amounts, VAT, NHIL, levy amounts

The BOE section extractor (boe_section_extractor.py) handles the GRA-specific
key-name decoding and runs AFTER this AI enhancement step.  This extractor's
role is to capture fields that are NOT encoded in section key names:
- Declarant name/address/registration
- Consignee name/address
- Shipper/exporter name
- BL number, container details
- Any free-text fields in the header section

Note: HS codes, duty amounts, VAT, CIF/FOB values are better extracted by the
BOE section extractor (deterministic, no LLM needed for those).  This extractor
focuses on the party and reference fields that require semantic understanding.
"""

import logging
from typing import Any, Dict, List

from .base import BaseDocumentExtractor

logger = logging.getLogger(__name__)


class BOEExtractor(BaseDocumentExtractor):
    """Specialised extractor for Bill of Entry documents (Ghana GRA format)."""

    async def extract(
        self,
        fields: Dict[str, Any],
        items: List[Dict],
        blocks: List[Dict],
        document_type: str,
    ) -> Dict[str, Any]:
        """Single unified LLM pass over full BOE content."""
        try:
            table_text = self._serialize_items(items, max_rows=60)
            block_text = self._serialize_blocks(blocks, max_blocks=100)
            existing_summary = self._fields_summary(fields, max_fields=30)

            prompt = self._build_boe_prompt(
                table_text=table_text,
                block_text=block_text,
                existing_summary=existing_summary,
            )

            result = await self.llm_extraction.ainvoke(prompt)
            extracted = {k: v for k, v in result.model_dump().items() if v is not None}

            logger.info(
                f"BOEExtractor: extracted {len(extracted)} fields "
                f"(items={len(items)}, blocks={len(blocks)})"
            )
            return extracted

        except Exception as e:
            logger.error(f"BOEExtractor.extract failed: {e}", exc_info=True)
            return {}

    def _build_boe_prompt(
        self,
        table_text: str,
        block_text: str,
        existing_summary: str,
    ) -> str:
        return f"""You are a customs document expert specialised in Bills of Entry (BOE / customs declaration).

ALREADY EXTRACTED FIELDS (do not re-extract unless you can improve them):
{existing_summary or "none"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TABLE ROWS (key-value pairs and item rows from the BOE):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{table_text or "(no table rows)"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DOCUMENT TEXT BLOCKS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{block_text or "(no blocks)"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXTRACTION RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PARTIES:
- consignee_name    = COMPANY NAME ONLY of the importer/consignee.
                      Labels: "Consignee", "Importer", "Declarant Name".
- consignee_address = full postal address of the consignee/importer.
- shipper_name      = COMPANY NAME ONLY of the exporter/shipper.
                      Labels: "Exporter", "Shipper", "Supplier".
- shipper_address   = full postal address of the shipper/exporter.

REFERENCE NUMBERS:
- invoice_number  = commercial invoice number referenced on this BOE
- bl_number       = bill of lading number (labels: "B/L No", "BL No", "Bill of Lading No")
- order_number    = supplier's order number if referenced
- po_number       = buyer's PO / customer reference if stated
- contract_number = contract number if referenced

COMMERCIAL TERMS:
- incoterm  = delivery/trade term (e.g. "FCA", "FOB", "CIF")
- currency  = currency code used for valuation

FINANCIAL (extract if clearly stated as plain text — section-encoded values
are handled by the BOE section extractor separately):
- total_fob_value     = FOB value if shown as a labelled field
- total_invoice_value = invoice/CIF value if shown as a labelled field

TRANSPORT:
- vessel_name        = vessel or ship name
- port_of_loading    = port of loading / place of dispatch
- port_of_discharge  = port of discharge / destination
- container_numbers  = comma-separated container IDs (4 letters + 7 digits)
- container_count    = number of containers (integer)

GOODS:
- product_description = description of the goods
- hs_code             = HS tariff code (if shown as plain labelled text, not section-encoded)
- country_of_origin   = country of origin of the goods
- net_weight          = total net weight (include unit)
- gross_weight        = total gross weight (include unit)
- quantity            = total quantity

Populate only the fields you find with confidence. Leave everything else as null."""
