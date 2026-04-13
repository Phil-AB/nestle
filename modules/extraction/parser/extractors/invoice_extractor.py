"""
Specialised extractor for Commercial Invoice documents.

Invoice layout conventions (Nestlé Ghana import context, European supplier):
- Header section: Exporter/Shipper block (name + address), Consignee/Invoice To block,
  Invoice Number, Invoice Date, Shipping Condition (= Incoterm), Currency
- Reference row: Our Order Number (= supplier's order), Your Order Number (= buyer's PO),
  Contract No, Customer Reference
- Line items table: article code, description, qty, unit price, total value, VAT%
- Totals section at bottom: Total Excl. VAT, VAT Amount, Total Incl. VAT, Net Weight,
  Gross Weight, Total Units

Key extraction problems this extractor solves:
1. "Shipping Condition: FCA ROTTERDAM PORT" must map to incoterm, not shipping_condition
2. "Our Order Number" = supplier's internal order → order_number
   "Your Order Number" = buyer's PO reference → po_number
3. "Total Excl. VAT" = total_fob_value when incoterm is FCA/FOB and VAT = 0
4. product_description is in the line items table, not in a header field
   → promote first item description to top-level product_description
5. Net/gross weights appear in the totals row of the line items table, not as header fields
"""

import logging
import re
from typing import Any, Dict, List

from .base import BaseDocumentExtractor

logger = logging.getLogger(__name__)


class InvoiceExtractor(BaseDocumentExtractor):
    """Specialised extractor for Commercial Invoice documents."""

    # Raw field keys that directly name the shipper/exporter.
    # Checked after the LLM call — if Claude extracted it cleanly under one of these
    # keys, use that value instead of the LLM-enhanced result.
    # Order matters: trade name is preferred over legal name; legal name beats generic keys.
    _SHIPPER_KEYS = (
        "seller_trade_name",          # "Vreugdenhil Dairy Foods" (preferred — commercial name)
        "shipper_name", "exporter_name", "shipper", "exporter",
        "supplier", "seller_name", "seller", "from", "sold_by",
    )
    _SHIPPER_ADDR_KEYS = (
        "seller_address",             # Claude OPEN-mode key for supplier address
        "shipper_address", "exporter_address", "supplier_address",
    )

    # Matches European trade-name disclosures in invoice footers:
    # "Vreugdenhil Dairy Foods is a trade name of ..."
    # Captures the commercial name (group 1) before the phrase.
    _TRADE_NAME_RE = re.compile(
        r'([A-Z][A-Za-z0-9\s&\-\.]{2,60}?)\s+is\s+a\s+trade\s+name\s+of\b',
        re.IGNORECASE,
    )

    async def extract(
        self,
        fields: Dict[str, Any],
        items: List[Dict],
        blocks: List[Dict],
        document_type: str,
    ) -> Dict[str, Any]:
        """Single unified LLM pass over full invoice content."""
        try:
            table_text = self._serialize_items(items, max_rows=60)
            block_text = self._serialize_blocks(blocks, max_blocks=80)
            all_fields_text = self._all_fields_text(fields)

            prompt = self._build_invoice_prompt(
                table_text=table_text,
                block_text=block_text,
                all_fields_text=all_fields_text,
            )

            # Temporary diagnostic — remove after debugging
            import pathlib, json as _json
            _dbg = pathlib.Path(__file__).parent / "invoice_debug.json"
            _dbg.write_text(_json.dumps({
                "fields": {k: str(v)[:200] for k, v in fields.items()},
                "blocks": [
                    {"type": b.get("type","?") if isinstance(b,dict) else "?",
                     "text": str(b.get("content") or b.get("text") or b.get("value","") if isinstance(b,dict) else b)[:400]}
                    for b in blocks
                ]
            }, indent=2, ensure_ascii=False))
            result = await self.llm_extraction.ainvoke(prompt)
            extracted = {k: v for k, v in result.model_dump().items() if v is not None}

            # Deterministic override: if Claude extracted a shipper name directly
            # from a field key we recognise, prefer it over the LLM-enhanced value.
            # This prevents the LLM from drifting to footer text (e.g. subsidiary
            # legal disclaimers or trade-name disclosures) when the main company name
            # is already in a clean raw field.
            for key in self._SHIPPER_KEYS:
                raw = self._val(fields.get(key))
                if raw and not self._is_empty(raw):
                    # Take only the last line if the value contains newlines
                    # (guards against "... Chamber of Commerce\nActual Name" leakage)
                    name = str(raw).strip()
                    if "\n" in name:
                        name = name.split("\n")[-1].strip()
                    extracted["shipper_name"] = name
                    logger.info(f"InvoiceExtractor: shipper_name ← raw field '{key}' ({name!r})")
                    break

            # Sanitize shipper_name from LLM result if it still has garbage prefix
            # (e.g. "d Chamber of Commerce number 09040933\nVreugdenhil Dairy Foods")
            if "shipper_name" in extracted and "\n" in str(extracted["shipper_name"]):
                lines = [ln.strip() for ln in str(extracted["shipper_name"]).splitlines() if ln.strip()]
                if lines:
                    extracted["shipper_name"] = lines[-1]
                    logger.info(f"InvoiceExtractor: shipper_name sanitized to last line: {extracted['shipper_name']!r}")

            for key in self._SHIPPER_ADDR_KEYS:
                raw = self._val(fields.get(key))
                if raw and not self._is_empty(raw):
                    extracted["shipper_address"] = str(raw).strip()
                    logger.info(f"InvoiceExtractor: shipper_address ← raw field '{key}'")
                    break

            # Deterministic trade-name scan: search ALL block text for the pattern
            # "X is a trade name of Y".  This handles European invoices where the
            # letterhead shows only an address but the footer discloses the trade name.
            # Only applied if the raw-field override above did NOT find a shipper key.
            if not any(fields.get(k) and not self._is_empty(self._val(fields.get(k)))
                       for k in self._SHIPPER_KEYS):
                for blk in blocks:
                    text = (
                        blk.get("content") or blk.get("text") or blk.get("value", "")
                        if isinstance(blk, dict) else str(blk)
                    )
                    m = self._TRADE_NAME_RE.search(str(text))
                    if m:
                        trade_name = m.group(1).strip()
                        extracted["shipper_name"] = trade_name
                        logger.info(
                            f"InvoiceExtractor: shipper_name ← trade-name pattern: {trade_name!r}"
                        )
                        break

            logger.info(
                f"InvoiceExtractor: extracted {len(extracted)} fields "
                f"(items={len(items)}, blocks={len(blocks)})"
            )
            logger.debug(f"InvoiceExtractor raw fields keys: {list(fields.keys())}")
            logger.debug(f"InvoiceExtractor shipper_name result: {extracted.get('shipper_name')!r}")
            return extracted

        except Exception as e:
            logger.error(f"InvoiceExtractor.extract failed: {e}", exc_info=True)
            return {}

    def _build_invoice_prompt(
        self,
        table_text: str,
        block_text: str,
        all_fields_text: str,
    ) -> str:
        return f"""You are a customs document expert specialised in Commercial Invoices.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RAW REDUCTO FIELDS (every field extracted by OCR — use these as your primary source):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{all_fields_text or "(none)"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TABLE ROWS (line items + header key-value pairs as extracted by OCR):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{table_text or "(no table rows)"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DOCUMENT TEXT BLOCKS (free-text sections):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{block_text or "(no blocks)"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXTRACTION RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PARTIES:
- shipper_name    = COMPANY NAME ONLY of the exporter/seller. Do NOT include address.
                    Labels to look for: "Exporter", "Shipper", "Seller", "Sold By", "From".
                    TRADE NAME RULE: Some invoices have no company name in the header — only
                    an address block. In that case look for a footer sentence of the form:
                      "[Company Name] is a trade name of [Legal Entity]"
                    The text BEFORE "is a trade name of" is the shipper's commercial name — use it.
                    EXCLUSION RULE: Company names listed after "are part of" (e.g. subsidiaries
                    or affiliates listed as "A, B and C are part of [parent]") are NOT the shipper.
                    NEVER use a company name that appears only in a list of subsidiaries or
                    affiliates (e.g. "Nemelco B.V., NutriPro B.V. are part of...").
                    Copy the name VERBATIM. Do NOT paraphrase or invent. Return null if unsure.
- shipper_address = full postal address of the shipper (street, PO Box, postcode, city, country).
                    Typically the FIRST address block at the top of the document.
                    CRITICAL: Capture ALL address components verbatim — street, P.O. Box,
                    postal code, city, country. Do not truncate or summarise.
- consignee_name  = COMPANY NAME ONLY of the consignee/buyer (labels: "Consignee",
                    "Invoice To", "Bill To", "Sold To", "Importer"). No address.
                    Copy verbatim from the document.
- consignee_address = full postal address of the consignee.

REFERENCE NUMBERS — CRITICAL disambiguation:
On a supplier invoice there are two perspectives:
  "Our Order Number" / "Our Ref" = the SUPPLIER's internal order number → order_number
  "Your Order Number" / "Customer Reference" / "Customer Ref" = the BUYER's PO → po_number
  "Contract No" / "Contract Number" = supply contract reference → contract_number
  "Invoice No" / "Invoice Number" = this document's identifier → invoice_number

COMMERCIAL TERMS:
- incoterm = delivery/trade term including place (e.g. "FCA ROTTERDAM PORT", "FOB TEMA").
             Look for labels: "Shipping Condition", "Delivery Terms", "Trade Term", "Incoterm".
             Extract the FULL value including the place name.
- currency  = 3-letter currency code (EUR, USD, GBP, GHS, …)

FINANCIAL VALUES:
- total_fob_value    = FOB/FCA value. Logic:
                       • If a field explicitly labelled "FOB Value" or "FCA Value" exists → use it.
                       • Else if incoterm is FCA/FOB AND VAT = 0 → use "Total Excl. VAT".
                       • Else use "Net Amount" or "Subtotal".
- total_invoice_value = total amount billed (including all charges). Usually "Total Incl. VAT"
                        or the final "Total" line at the bottom.
- vat_amount          = VAT/tax amount if shown separately.

WEIGHTS & GOODS:
The invoice line items table typically has:
  - description columns: article code, product description, batch
  - quantity, unit, unit price, total price columns
  - A TOTALS ROW at the bottom: total qty, total net weight, total gross weight

- product_description = description of the goods. Look in:
                        1. "Description" or "Article Description" column of line items
                        2. A "Description of Goods" header field
                        Use the most complete description found.
- net_weight   = TOTAL shipment net weight. Look for a "Total Net Weight" or "Net Weight"
                 TOTALS ROW at the bottom of the line items table, or a header field.
                 Include the unit (e.g. "189000.00 KG" or "189,000 KG").
- gross_weight = TOTAL shipment gross weight. Same approach as net_weight.
                 Include the unit.
- quantity     = TOTAL shipment quantity/units. From the totals row or header.
- unit_of_measure = unit (BAG, KG, PCS, MT, etc.)
- hs_code      = HS/HSN tariff code if present (usually in line items table).
                 If not shown anywhere on the document, return null.
- country_of_origin = country where goods were manufactured, if stated.

Populate only the fields you find with confidence. Leave everything else as null."""
