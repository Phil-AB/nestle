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

NOTE: When using Claude as the extraction provider, AI enhancement is skipped
entirely (Claude performs semantic extraction in a single pass).  This extractor
only runs for non-Claude providers (e.g. Reducto).  It follows the same
"no renaming" principle as the vendor validation pipeline: Claude sees the EXACT
field labels from the document and the structured output schema maps them to
canonical names — no LLM-based semantic renaming.
"""

import logging
import re
from typing import Any, Dict, List

from .base import BaseDocumentExtractor

logger = logging.getLogger(__name__)


class BOEExtractor(BaseDocumentExtractor):
    """Specialised extractor for Bill of Entry documents (Ghana GRA format)."""

    # Raw field keys (from non-Claude OCR) that directly name the consignee/importer.
    # Checked after the LLM call — if the OCR provider already extracted it cleanly,
    # use the raw value instead of the LLM-enhanced result (prevents drift).
    _CONSIGNEE_KEYS = (
        "consignee_name", "consignee",
        "importer_name", "importer",
        "buyer_name", "buyer",
        "invoice_to", "bill_to",
    )
    _CONSIGNEE_ADDR_KEYS = (
        "consignee_address", "importer_address",
        "bill_to_address", "delivery_address",
    )

    # Raw field keys that directly name the shipper/exporter.
    _SHIPPER_KEYS = (
        "shipper_name", "shipper",
        "exporter_name", "exporter",
        "supplier_name", "supplier",
        "seller_name", "seller",
    )
    _SHIPPER_ADDR_KEYS = (
        "shipper_address", "exporter_address",
        "supplier_address", "seller_address",
    )

    # Declarant (clearing agent) keys.
    # GRA BOE raw field is "declarant_representative" (Field 9 label).
    _DECLARANT_KEYS = (
        "declarant_name", "declarant",
        "declarant_representative_name",     # Claude split-field variant
        "declarant_representative",          # GRA BOE Field 9 raw label (combined)
        "representative_name", "representative",
        "clearing_agent", "customs_agent",
    )
    _DECLARANT_REG_KEYS = (
        "declarant_reg_number", "declarant_reg_no",
        "declarant_no",                      # GRA BOE Field 9 registration sub-field
        "agent_reg_number", "license_number",
        "ch_number",
    )

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
            # Pass ALL raw fields to the LLM — same as InvoiceExtractor.
            # Truncating to 30 fields (as the old code did) causes missed extractions
            # when GRA BOE key-name encoded fields push real party fields beyond the limit.
            all_fields_text = self._all_fields_text(fields)

            prompt = self._build_boe_prompt(
                table_text=table_text,
                block_text=block_text,
                all_fields_text=all_fields_text,
            )

            result = await self.llm_extraction.ainvoke(prompt)
            extracted = {k: v for k, v in result.model_dump().items() if v is not None}

            # ── Deterministic overrides ───────────────────────────────────────
            # If the OCR provider already extracted a clean value under a
            # recognised raw key, prefer it over the LLM-enhanced result.
            # This mirrors InvoiceExtractor's approach and prevents the LLM
            # from drifting to wrong values when the raw extraction is correct.

            for key in self._CONSIGNEE_KEYS:
                raw = self._val(fields.get(key))
                if raw and not self._is_empty(raw):
                    name = str(raw).strip()
                    # Take only the first line — BOE consignee blocks often have
                    # "Company Name\nStreet\nCity" merged into one field.
                    if "\n" in name:
                        name = name.split("\n")[0].strip()
                    extracted["consignee_name"] = name
                    logger.info(f"BOEExtractor: consignee_name ← raw field '{key}' ({name!r})")
                    break

            for key in self._CONSIGNEE_ADDR_KEYS:
                raw = self._val(fields.get(key))
                if raw and not self._is_empty(raw):
                    extracted["consignee_address"] = str(raw).strip()
                    logger.info(f"BOEExtractor: consignee_address ← raw field '{key}'")
                    break

            for key in self._SHIPPER_KEYS:
                raw = self._val(fields.get(key))
                if raw and not self._is_empty(raw):
                    name = str(raw).strip()
                    if "\n" in name:
                        name = name.split("\n")[0].strip()
                    extracted["shipper_name"] = name
                    logger.info(f"BOEExtractor: shipper_name ← raw field '{key}' ({name!r})")
                    break

            for key in self._SHIPPER_ADDR_KEYS:
                raw = self._val(fields.get(key))
                if raw and not self._is_empty(raw):
                    extracted["shipper_address"] = str(raw).strip()
                    logger.info(f"BOEExtractor: shipper_address ← raw field '{key}'")
                    break

            for key in self._DECLARANT_KEYS:
                raw = self._val(fields.get(key))
                if raw and not self._is_empty(raw):
                    name = str(raw).strip()
                    if "\n" in name:
                        name = name.split("\n")[0].strip()
                    extracted["declarant_name"] = name
                    logger.info(f"BOEExtractor: declarant_name ← raw field '{key}' ({name!r})")
                    break

            for key in self._DECLARANT_REG_KEYS:
                raw = self._val(fields.get(key))
                if raw and not self._is_empty(raw):
                    extracted["declarant_reg_number"] = str(raw).strip()
                    logger.info(f"BOEExtractor: declarant_reg_number ← raw field '{key}'")
                    break

            logger.info(
                f"BOEExtractor: extracted {len(extracted)} fields "
                f"(items={len(items)}, blocks={len(blocks)})"
            )
            logger.debug(f"BOEExtractor raw fields keys: {list(fields.keys())[:20]}")
            return extracted

        except Exception as e:
            logger.error(f"BOEExtractor.extract failed: {e}", exc_info=True)
            return {}

    def _build_boe_prompt(
        self,
        table_text: str,
        block_text: str,
        all_fields_text: str,
    ) -> str:
        return f"""You are a customs document expert specialised in Bills of Entry (BOE / customs declaration).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RAW EXTRACTED FIELDS (every field extracted by OCR — use these as your primary source):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{all_fields_text or "(none)"}

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

CRITICAL: Use the value EXACTLY as found in the raw fields above. Do NOT rename,
re-label, or infer values not present. Copy verbatim. Return null if not found.

PARTIES:
- consignee_name    = COMPANY NAME ONLY of the importer/consignee. No address.
                      Labels to look for (in raw fields or text blocks):
                      "Consignee", "Importer", "7 Importer & Address",
                      "7_importer_&_address_...", "Importer Name".
                      Take the company name only — NOT the street/city/postal address.
                      If the value contains newlines, use only the first line.
- consignee_address = full postal address of the consignee/importer.
- shipper_name      = COMPANY NAME ONLY of the exporter/shipper. No address.
                      Labels: "Exporter", "Shipper", "Supplier",
                      "8 Exporter & Address", "8_exporter_&_address_...".
                      Take the company name only.
- shipper_address   = full postal address of the shipper/exporter.

DECLARANT (clearing agent):
- declarant_name       = Name of the clearing agent / declarant company.
                         Labels: "Declarant/Representative", "Declarant",
                         "Representative", "Clearing Agent", "Customs Agent".
                         Often preceded by a registration code like "CH000258".
- declarant_reg_number = Registration/license number of the declarant.
                         Format: "CH" followed by digits (e.g. "CH000258").
                         Look for it immediately before the company name in the
                         Declarant/Representative section.

REFERENCE NUMBERS:
- invoice_number  = commercial invoice number referenced on this BOE.
                    Labels: "Invoice No", "Invoice Number", "Inv No".
- bl_number       = bill of lading number.
                    Labels: "B/L No", "BL No", "Bill of Lading No".
- order_number    = supplier's order number if referenced.
- po_number       = buyer's PO / customer reference if stated.
- contract_number = contract number if referenced.

COMMERCIAL TERMS:
- incoterm  = delivery/trade term (e.g. "FCA", "FOB", "CIF").
              Labels: "Delivery Terms", "12 Delivery Terms & Place",
              "Incoterm", "Trade Term". Extract the FULL value including place name.
- currency  = 3-letter currency code used for valuation.
              Labels: "Currency Code", "16 Currency Code", "Currency".

FINANCIAL (extract ONLY if clearly stated as plain text — section-encoded values
are decoded by the BOE section extractor separately):
- total_fob_value     = FOB value (NUMERIC ONLY, no currency prefix, e.g. "467775.00").
- total_invoice_value = Invoice/CIF value (NUMERIC ONLY, no currency prefix).
- customs_value       = CIF customs value, field 42 on GRA BOE (NUMERIC ONLY).
- freight_value       = Freight amount in local currency (NUMERIC ONLY).
- insurance_value     = Insurance amount in local currency (NUMERIC ONLY).
NOTE: Use the separate `currency` field for the currency code, NOT embedded in the numeric value.

TAX COMPUTATION (Section 40 / Tax Table):
IMPORTANT: Scan every row of the tax computation table. The table has columns:
  Tax Code | Tax Base Amt | TBC | Rate % | Exempted/Suspended | Amount Payable
You MUST extract ALL of the following if the rows are present:
- duty_rate    = Rate % column for Tax Code "01" (Import Duty), converted to DECIMAL
                 (e.g. table shows "5.00" → duty_rate = 0.05)
- duty_amount  = Amount Payable column for Tax Code "01" (Import Duty)
- vat_rate     = Rate % column for Tax Code "02" (Import VAT), as a decimal fraction
                 (e.g. table shows "15.00" → vat_rate = 0.15)
- vat_amount   = Amount Payable column for Tax Code "02" (Import VAT)
- nhil_amount  = Amount Payable column for Tax Code "47" (Import NHIL)

TRANSPORT:
- vessel_name        = vessel or ship name.
                       Labels: "Vessel Name", "Ship", "21 Vessel/Flight".
- port_of_loading    = port of loading / place of dispatch.
- port_of_discharge  = port of discharge / destination.
- container_numbers  = comma-separated container IDs (4 letters + 7 digits).
- container_count    = number of containers (integer).

GOODS:
- product_description = description of the goods.
- hs_code             = HS tariff code (if shown as plain labelled text, not section-encoded).
- country_of_origin   = country of origin of the goods.
                        Labels: "Country of Origin", "31 Country of Origin".
- net_weight          = total net weight (include unit, e.g. "189000 KG").
- gross_weight        = total gross weight (include unit, e.g. "192780 KG").
- quantity            = total quantity (include unit).

Populate only the fields you find with confidence. Leave everything else as null."""
