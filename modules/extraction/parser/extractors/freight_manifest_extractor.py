"""
Specialised extractor for Freight Manifest documents.

A freight manifest is a carrier-issued document listing ALL cargo on a vessel,
aircraft, or truck — it is not a transport contract (like a BOL/AWB) but a
consolidated cargo list.  It is filed with customs authorities at the port of
entry.

Freight manifest layout conventions:
- Header: Vessel/flight/truck details, voyage/flight number, port of loading,
  port of discharge, carrier name, manifest date
- Line items: one row per consignment/BL/AWB, showing:
    BL/AWB number, shipper, consignee, description of goods,
    number of packages, gross weight, marks & numbers
- Manifest number / customs filing reference
- May span multiple pages for large vessels

Key differences from BOL/AWB:
- Covers MULTIPLE consignments (many BLs / AWBs on one manifest)
- The extraction target is typically ONE specific consignment row matching
  the shipment being processed, not all rows
- Vessel/flight info is in the header (not per-row)
- No container-level details — aggregated at BL level
"""

import logging
from typing import Any, Dict, List

from .base import BaseDocumentExtractor

logger = logging.getLogger(__name__)


class FreightManifestExtractor(BaseDocumentExtractor):
    """Specialised extractor for Freight Manifest documents."""

    async def extract(
        self,
        fields: Dict[str, Any],
        items: List[Dict],
        blocks: List[Dict],
        document_type: str,
    ) -> Dict[str, Any]:
        """Single unified LLM pass over full freight manifest content."""
        try:
            table_text = self._serialize_items(items, max_rows=80)
            block_text = self._serialize_blocks(blocks, max_blocks=100)
            existing_summary = self._fields_summary(fields, max_fields=25)

            prompt = self._build_manifest_prompt(
                table_text=table_text,
                block_text=block_text,
                existing_summary=existing_summary,
            )

            result = await self.llm_extraction.ainvoke(prompt)
            extracted = {k: v for k, v in result.model_dump().items() if v is not None}

            logger.info(
                f"FreightManifestExtractor: extracted {len(extracted)} fields "
                f"(items={len(items)}, blocks={len(blocks)})"
            )
            return extracted

        except Exception as e:
            logger.error(f"FreightManifestExtractor.extract failed: {e}", exc_info=True)
            return {}

    def _build_manifest_prompt(
        self,
        table_text: str,
        block_text: str,
        existing_summary: str,
    ) -> str:
        return f"""You are a customs document expert specialised in Freight Manifests.

A freight manifest lists ALL cargo on a single vessel/flight.  Each row is one
consignment.  Extract fields from the HEADER (vessel/carrier info) and from the
consignment rows.  If multiple consignments appear, extract the fields that are
consistent across rows (e.g. vessel name, ports) plus the fields from any
highlighted or single consignment row.

ALREADY EXTRACTED FIELDS (do not re-extract unless you can improve them):
{existing_summary or "none"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TABLE ROWS (consignment entries):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{table_text or "(no table rows)"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DOCUMENT TEXT BLOCKS (header, vessel info, manifest reference):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{block_text or "(no blocks)"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXTRACTION RULES — Freight Manifest
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

VESSEL / CARRIER (from document header):
- vessel_name        = name of the vessel or aircraft
- carrier_name       = shipping line or airline operating the vessel
- port_of_loading    = port/airport where cargo was loaded
- port_of_discharge  = destination port/airport
- bl_number          = master BL or AWB number for the specific consignment
                       (if only one consignment, this is the transport reference)

PARTIES (per consignment row or from header):
- shipper_name    = COMPANY NAME ONLY of the shipper/exporter for this consignment
- shipper_address = address of the shipper
- consignee_name  = COMPANY NAME ONLY of the consignee/importer
- consignee_address = address of the consignee
- notify_party    = notify party if stated

REFERENCE NUMBERS:
- invoice_number  = invoice number if referenced
- order_number    = order number if referenced
- po_number       = customer PO reference if stated
- contract_number = contract number if referenced

GOODS & WEIGHTS (per consignment or totals):
- product_description = description of goods for this consignment
- gross_weight    = gross weight for this consignment. Include unit.
- net_weight      = net weight if stated. Include unit.
- quantity        = number of packages / pieces for this consignment
- unit_of_measure = unit (BAGS, PKGS, PCS, etc.)
- hs_code         = HS/commodity code if stated
- country_of_origin = country of origin if stated

COMMERCIAL:
- incoterm  = delivery terms if stated
- currency  = currency code

Populate only the fields you find with confidence. Leave everything else as null."""
