"""
BOE Section-Specific Extractor for Ghana GRA BOE Forms.

The Ghana Revenue Authority (GRA) BOE form has a very dense, multi-column
table layout.  Two extraction paths are supported:

  Reducto path:
    Reducto often embeds numeric values inside field *key names* rather than
    field values because adjacent label and value cells get merged.
    Strategies: key-name scanning + value parsing.

  Claude path:
    Claude preserves the EXACT field labels from the GRA BOE form (verbatim
    snake_case conversion).  Canonical mapping handles these verbatim names
    and also extracts from the structured items and blocks.

The result is a flat dict of normalised field names + values that is merged
back into result["fields"] by document_processing_service.
"""

from typing import Dict, Any, List, Optional
from decimal import Decimal
import re

from shared.contracts.boe_section_schemas import (
    BOESection16, BOESection21, BOESection25Item,
    BOESection31Item, BOESection40Item, BOEStructuredData,
)
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class BOESectionExtractor:
    """Extracts key fields from Ghana GRA BOE forms."""

    # ─── Public API ──────────────────────────────────────────────────────────

    def extract_sections(self, raw_fields: Dict[str, Any]) -> BOEStructuredData:
        """
        Legacy structured output — kept for compatibility.
        Internally delegates to extract_flat_fields and wraps the result.
        """
        flat = self.extract_flat_fields(raw_fields)

        section_16 = None
        if flat.get("exchange_rate") or flat.get("currency_code"):
            section_16 = BOESection16(
                currency_code=flat.get("currency_code"),
                exchange_rate=self._to_decimal(flat.get("exchange_rate")),
            )

        section_21 = None
        if flat.get("entry_exit_code") or flat.get("mode_of_transport"):
            section_21 = BOESection21(
                entry_exit_code=flat.get("entry_exit_code"),
                port_of_entry=flat.get("port_of_entry"),
            )
            if section_21.entry_exit_code:
                section_21.mode_of_transport = section_21.get_transport_mode()

        section_25: List[BOESection25Item] = []
        if flat.get("description"):
            section_25.append(BOESection25Item(line_number=1, description=flat["description"]))

        section_31: List[BOESection31Item] = []
        if flat.get("hs_code") or flat.get("net_weight"):
            section_31.append(BOESection31Item(
                line_number=1,
                hs_code=flat.get("hs_code"),
                country_of_origin=flat.get("country_of_origin"),
                quantity=self._to_decimal(flat.get("quantity")),
                net_weight=self._to_decimal(flat.get("net_weight")),
                unit_value=self._to_decimal(flat.get("unit_price")),
                total_value=self._to_decimal(flat.get("total_fob_value")),
            ))

        section_40: List[BOESection40Item] = []
        if flat.get("duty_amount") or flat.get("duty_rate"):
            section_40.append(BOESection40Item(
                line_number=1,
                duty_rate_percent=self._to_decimal(flat.get("duty_rate")),
                duty_amount=self._to_decimal(flat.get("duty_amount")),
                vat_rate_percent=self._to_decimal(flat.get("vat_rate")),
                vat_amount=self._to_decimal(flat.get("vat_amount")),
                total_amount=self._to_decimal(flat.get("customs_value")),
            ))

        boe = BOEStructuredData(
            declaration_number=flat.get("boe_number"),
            section_16=section_16,
            section_21=section_21,
            section_25=section_25,
            section_31=section_31,
            section_40=section_40,
        )
        logger.info(
            f"BOE sections: s16={section_16 is not None}, s21={section_21 is not None}, "
            f"s25={len(section_25)}, s31={len(section_31)}, s40={len(section_40)}, "
            f"flat_fields={list(flat.keys())}"
        )
        return boe

    def extract_flat_fields(
        self,
        raw_fields: Dict[str, Any],
        items: Optional[List[Dict[str, Any]]] = None,
        blocks: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Main extraction entry point.  Returns a flat dict of canonical field
        names → normalised values extracted from the GRA BOE raw fields.

        Args:
            raw_fields: Flat field dict from the AI provider (may contain
                        dict-wrapped values with 'value'/'confidence' keys).
            items: Optional list of goods line-item rows.
            blocks: Optional list of structured blocks (tables, text) from
                    the provider response — used to extract tax table data
                    and attached document references.
        """
        extracted: Dict[str, Any] = {}

        for key, raw_val in raw_fields.items():
            # Unwrap dict-wrapped values (Reducto / Claude confidence envelopes)
            if isinstance(raw_val, dict) and "value" in raw_val:
                raw_val = raw_val["value"]
            val_str = str(raw_val).strip() if raw_val is not None else ""

            # Skip clearly empty cells
            if val_str in ("", "<empty>", "-", "—"):
                val_str = ""

            # Claude verbatim GRA label → canonical mapping (runs first — authoritative)
            self._parse_canonical_from_gra_fields(key, val_str, extracted)
            # Reducto key-name encoding (numeric values embedded in key names)
            self._parse_key_name(key, val_str, extracted)
            # Reducto / generic field value parsing (fills gaps only)
            self._parse_field_value(key, val_str, extracted)

        # Extract from structured goods item rows
        if items:
            self._parse_goods_items(items, extracted)
            # Reducto tax table (items contain tax rows for Reducto path)
            self._parse_tax_table(items, extracted)

        # Extract from structured blocks (Claude path: tax table + attached docs)
        if blocks:
            self._parse_tax_blocks(blocks, extracted)
            self._parse_attached_docs_blocks(blocks, extracted)

        self._post_process(extracted)
        return extracted

    def filter_goods_items(
        self, items: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Remove non-goods rows from the items array.

        Claude sometimes dumps attached-document reference rows, tax summary
        rows, or other non-goods data into the items array.  A genuine BOE
        goods line-item always has at least a commodity_code / item_no.
        Document-reference rows only have document_description + reference_number.

        Returns a cleaned list containing only genuine goods line items.
        """
        if not items:
            return []

        # Keys that indicate a goods line item (GRA BOE Section 31)
        GOODS_KEYS = {
            "item_no", "commodity_code", "hs_code", "gross_wt_kg",
            "net_wt_kg", "quantity_unit", "customs_value", "description_of_goods",
            "fob_fcy_cc", "fob_ncy", "freight_ncy", "insurance_ncy",
            "cty_org_dest", "cpc", "marks_numbers",
        }

        # Keys that indicate a document reference row
        DOC_REF_KEYS = {"document_description", "reference_number"}

        cleaned = []
        for row in items:
            # Unwrap confidence envelopes to check actual values
            unwrapped = {
                k: (v["value"] if isinstance(v, dict) and "value" in v else v)
                for k, v in row.items()
                if not k.startswith("_")
            }

            # Count how many goods-specific keys have non-empty values
            goods_count = sum(
                1 for k in GOODS_KEYS
                if unwrapped.get(k) is not None
                and str(unwrapped.get(k, "")).strip() not in ("", "—", "-", "None")
            )

            # Count how many doc-reference keys have values
            doc_count = sum(
                1 for k in DOC_REF_KEYS
                if unwrapped.get(k) is not None
                and str(unwrapped.get(k, "")).strip() not in ("", "—", "-", "None")
            )

            # If it has document reference columns but no goods columns, skip it
            if doc_count > 0 and goods_count == 0:
                logger.debug(f"Skipping non-goods item row: {unwrapped.get('document_description', '?')}")
                continue

            # If it has no goods keys at all and very few populated fields, skip
            populated = sum(
                1 for v in unwrapped.values()
                if v is not None and str(v).strip() not in ("", "—", "-", "None")
            )
            if goods_count == 0 and populated <= 3:
                logger.debug(f"Skipping sparse non-goods item row ({populated} fields)")
                continue

            cleaned.append(row)

        if len(cleaned) != len(items):
            logger.info(
                f"Filtered items: {len(items)} raw → {len(cleaned)} goods items "
                f"({len(items) - len(cleaned)} document/tax rows removed)"
            )

        return cleaned

    # ─── Claude GRA canonical field mapping ─────────────────────────────────

    def _parse_canonical_from_gra_fields(
        self, key: str, val_str: str, out: Dict[str, Any]
    ) -> None:
        """
        Map Claude's verbatim GRA BOE field names to canonical names.

        When Claude is the extraction provider it preserves the exact field
        labels from the GRA BOE form (snake_case converted), e.g.:
          curr_code, bl_awb, delivery_terms_place, gross_mass_kg, …

        This method maps those verbatim keys to the canonical names the
        validation engine expects.
        """
        if not val_str:
            return

        # ── BL / AWB number ──────────────────────────────────────────────────
        # Key: "bl_awb", Value: "S328717359"
        if key in ("bl_awb", "bl_awb_no", "bl_no") and "bl_number" not in out:
            out["bl_number"] = val_str

        # ── Currency code ────────────────────────────────────────────────────
        # Key: "curr_code", Value: "EUR"
        if key in ("curr_code", "currency_code") and "currency" not in out:
            m = re.search(r'\b([A-Z]{3})\b', val_str)
            if m:
                out["currency"] = m.group(1)

        # ── Delivery terms / Incoterm ────────────────────────────────────────
        # Key: "delivery_terms_place", Value: "FCA TEMA"
        if key == "delivery_terms_place" and "incoterm" not in out:
            out["incoterm"] = val_str

        # ── Total FOB value (FCY) ────────────────────────────────────────────
        # Key: "total_fob_fcy_imp_ncy_exp", Value: "467,775.00 EUR" → 467775.0
        if key == "total_fob_fcy_imp_ncy_exp" and "total_fob_value" not in out:
            m = re.search(r'([\d,]+\.?\d*)', val_str)
            if m:
                try:
                    out["total_fob_value"] = float(m.group(1).replace(",", ""))
                except ValueError:
                    pass

        # ── FOB value in national currency (Field 19 / Field 34 FOB Ncy) ─────
        # Key: "fob_ncy_import_export" or "fob_import_ncy", Value: "5,991,028.31"
        # Used for insurance rate calculation (all GHS: FOB Ncy + Freight Ncy = C&F)
        if key in ("fob_ncy_import_export", "fob_import_ncy", "fob_ncy") and "fob_ncy" not in out:
            m = re.search(r'([\d,]+\.?\d*)', val_str)
            if m:
                try:
                    out["fob_ncy"] = float(m.group(1).replace(",", ""))
                except ValueError:
                    pass

        # ── Total Invoice / CIF value ────────────────────────────────────────
        # Key: "total_invoice_fcy_cc", Value: "482,410.48 EUR" → 482410.48
        if key == "total_invoice_fcy_cc" and "total_invoice_value" not in out:
            m = re.search(r'([\d,]+\.?\d*)', val_str)
            if m:
                try:
                    out["total_invoice_value"] = float(m.group(1).replace(",", ""))
                except ValueError:
                    pass

        # ── Gross weight (header-level field) ────────────────────────────────
        # Key: "gross_mass_kg", Value: "192,780.0000" → 192780.0
        if key == "gross_mass_kg" and "gross_weight" not in out:
            m = re.search(r'([\d,]+\.?\d*)', val_str)
            if m:
                try:
                    out["gross_weight"] = float(m.group(1).replace(",", ""))
                except ValueError:
                    pass

        # ── Port of loading ──────────────────────────────────────────────────
        # Key: "port_of_loading_unloading", Value: "BEANR Antwerpen"
        if key == "port_of_loading_unloading" and "port_of_loading" not in out:
            out["port_of_loading"] = val_str

        # ── Port of discharge ────────────────────────────────────────────────
        # Key: "place_ship_land_ct_lnd", Value: "WTTMA1MPS3" (Tema port code)
        if key == "place_ship_land_ct_lnd" and "port_of_discharge" not in out:
            out["port_of_discharge"] = val_str

        # ── Exporter / Shipper ───────────────────────────────────────────────
        # Claude may split the exporter block into two separate fields:
        #   "exporter_name"    = "VREUGDENHIL DAIRY FOODS"
        #   "exporter_address" = "ARKERPOORT 5, 3861 PS, P.O. BOX 64 3860 AB"
        # Or combine them into one field:
        #   "exporter_address" = "VREUGDENHIL DAIRY FOODS, ARKERPOORT 5, …"
        #
        # Dedicated name field — always wins (overrides any address-derived value)
        # so iteration order does not matter.
        if key == "exporter_name":
            name = val_str.strip()
            if name and re.search(r'[A-Za-z]', name):
                out["shipper_name"] = name

        if key == "exporter_address":
            # Only derive name from address when no dedicated name field was seen yet.
            # When the value starts with "NAME, STREET, …" the first comma-part is the name.
            if "shipper_name" not in out and "," in val_str:
                parts = val_str.split(",", 1)
                name = parts[0].strip()
                if name and re.search(r'[A-Za-z]', name):
                    out["shipper_name"] = name
            if "shipper_address" not in out:
                out["shipper_address"] = val_str

        # ── Importer / Consignee ─────────────────────────────────────────────
        # Same split-field pattern as exporter above.
        if key == "importer_name":
            name = val_str.strip()
            if name and re.search(r'[A-Za-z]', name):
                out["consignee_name"] = name

        if key in ("importer_address", "consignee_actual_exporter"):
            if "consignee_name" not in out and "," in val_str:
                parts = val_str.split(",", 1)
                name = parts[0].strip()
                if name and re.search(r'[A-Za-z]', name):
                    out["consignee_name"] = name
            if "consignee_address" not in out:
                out["consignee_address"] = val_str

        # ── Declarant / Representative ───────────────────────────────────────
        # Claude may split this into:
        #   "declarant_representative_name"    = "CARGO CENTER GHANA LIMITED"
        #   "declarant_representative_address" = "UNN OFFICE NEAR TEMA HARBOUR, …"
        # Or combine them in "declarant_representative".
        # Dedicated name field — always wins over combined-field extraction.
        if key == "declarant_representative_name":
            name = val_str.strip()
            if name and re.search(r'[A-Za-z]', name):
                out["declarant_name"] = name

        if key == "declarant_representative" and "declarant_name" not in out:
            # Strip leading CH-number prefix if present
            clean = re.sub(r'^CH\d{4,8}\s*', '', val_str, flags=re.IGNORECASE).strip()
            name = clean.split(",", 1)[0].strip()
            if name and re.search(r'[A-Za-z]', name):
                out["declarant_name"] = name

        # ── Declarant registration number ────────────────────────────────────
        # Key: "declarant_representative_no", Value: "CH000258"
        if key == "declarant_representative_no" and "declarant_reg_number" not in out:
            m = re.search(r'\b(CH\d{4,8})\b', val_str, re.IGNORECASE)
            if m:
                out["declarant_reg_number"] = m.group(1).upper()

        # ── BOE number ───────────────────────────────────────────────────────
        # Key: "bill_of_entry_boe_no", Value: "40126075519 / 00"
        if key == "bill_of_entry_boe_no" and "boe_number" not in out:
            clean = re.split(r'\s*/\s*\d+', val_str)[0].strip()
            if re.fullmatch(r'\d{8,14}', clean):
                out["boe_number"] = clean

        # ── BOE date ────────────────────────────────────────────────────────
        # Key: "date" or "boe_date" or "declaration_date"
        # Value: "28/01/2026"
        if key in ("date", "boe_date", "declaration_date") and "boe_date" not in out:
            if re.search(r'\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}', val_str):
                out["boe_date"] = val_str

        # ── Regime ──────────────────────────────────────────────────────────
        # Key: "regime", Value: "40"
        if key == "regime" and "regime" not in out:
            m = re.search(r'\d{2}', val_str)
            if m:
                out["regime"] = m.group()

        # ── Reference number ────────────────────────────────────────────────
        # Key: "reference_number", Value: "2601270102GCH000258"
        if key in ("reference_number", "reference_no") and "reference_number" not in out:
            if len(val_str) >= 8:
                out["reference_number"] = val_str

        # ── Mode of transport ───────────────────────────────────────────────
        # Key: "m_trans" or "mode_of_transport", Value: "10"
        if key in ("m_trans", "mode_of_transport", "m_trans_ship_aircraft_id") \
                and "mode_of_transport" not in out:
            out["mode_of_transport"] = val_str

        # ── Consignee exporter number ──────────────────────────────────────
        # Claude sometimes extracts this under the generic label "no"
        # Value: "C0003137171"
        if key == "no" and re.fullmatch(r'C\d{7,12}', val_str, re.IGNORECASE) \
                and "consignee_exporter_no" not in out:
            out["consignee_exporter_no"] = val_str

        # ── Entry/Exit office (may be split across two fields) ──────────────
        # Claude sometimes splits "TMA1 CEPS TEMA" into:
        #   entry_exit_office = "TMA1" and identification_warehouse = "CEPS TEMA"
        # Reconstruct if we detect the split.
        if key == "entry_exit_office" and "entry_exit_office" not in out:
            out["entry_exit_office"] = val_str

        if key == "identification_warehouse" and "identification_warehouse" not in out:
            # Check if this looks like a continuation of entry/exit office
            # rather than an actual warehouse ID (warehouse IDs are typically
            # alphanumeric codes, not city names with spaces)
            if re.match(r'^(CEPS|CUSTOMS)', val_str, re.IGNORECASE):
                # Merge with entry_exit_office
                existing = out.get("entry_exit_office", "")
                if existing:
                    out["entry_exit_office"] = f"{existing} {val_str}"
                else:
                    out["entry_exit_office"] = val_str
                # Don't set identification_warehouse — it's blank on this form
            else:
                out["identification_warehouse"] = val_str

        # ── Country of consignment destination name (supplementary) ────────
        # Key: "country_of_consig_destinat_name", Value: "Belgium"
        # Keep as a display-friendly companion to the country code
        if key == "country_of_consig_destinat_name" and "country_name" not in out:
            out["country_name"] = val_str

    # ─── Goods items extraction (Claude path) ────────────────────────────────

    def _parse_goods_items(
        self, items: List[Dict[str, Any]], out: Dict[str, Any]
    ) -> None:
        """
        Extract canonical fields from BOE goods line-item rows.

        Claude extracts BOE item rows with GRA-specific column keys:
          commodity_code, gross_wt_kg, net_wt_kg, quantity_unit,
          customs_value, freight_ncy, insurance_ncy, cpc,
          cty_org_dest, fob_fcy_cc, description_of_goods
        """
        for item in items:
            # Unwrap confidence envelopes
            item = {
                k: (v["value"] if isinstance(v, dict) and "value" in v else v)
                for k, v in item.items()
            }

            def _raw(field: str) -> str:
                v = item.get(field)
                return str(v).strip() if v is not None else ""

            def _num(field: str) -> Optional[float]:
                raw = _raw(field).replace(",", "")
                if not raw:
                    return None
                # Strip trailing non-numeric suffix (e.g. " EUR")
                m = re.match(r'[\d.]+', raw)
                if m:
                    try:
                        return float(m.group())
                    except ValueError:
                        pass
                return None

            # ── HS Code ──────────────────────────────────────────────────────
            if "hs_code" not in out:
                raw_hs = _raw("commodity_code").replace(",", "")
                if raw_hs and re.fullmatch(r'\d{6,10}', raw_hs):
                    out["hs_code"] = raw_hs

            # ── Gross weight ─────────────────────────────────────────────────
            if "gross_weight" not in out:
                v = _num("gross_wt_kg")
                if v is not None:
                    out["gross_weight"] = v

            # ── Net weight ───────────────────────────────────────────────────
            if "net_weight" not in out:
                v = _num("net_wt_kg")
                if v is not None:
                    out["net_weight"] = v

            # ── Quantity (numeric) ───────────────────────────────────────────
            # Value: "7,560 BG" → 7560.0
            if "quantity" not in out:
                raw_qty = _raw("quantity_unit")
                m = re.match(r'^([\d,\.]+)', raw_qty)
                if m:
                    try:
                        out["quantity"] = float(m.group(1).replace(",", ""))
                    except ValueError:
                        pass

            # ── Customs value ────────────────────────────────────────────────
            if "customs_value" not in out:
                v = _num("customs_value")
                if v is not None:
                    out["customs_value"] = v

            # ── Freight value ────────────────────────────────────────────────
            if "freight_value" not in out:
                v = _num("freight_ncy")
                if v is not None:
                    out["freight_value"] = v

            # ── Insurance value ──────────────────────────────────────────────
            if "insurance_value" not in out:
                v = _num("insurance_ncy")
                if v is not None:
                    out["insurance_value"] = v

            # ── CPC / Customs procedure code ─────────────────────────────────
            if "customs_code" not in out:
                raw = _raw("cpc")
                if raw and re.match(r'40[A-Z]\d{2,3}', raw):
                    out["customs_code"] = raw

            # ── Country of origin ────────────────────────────────────────────
            if "country_of_origin" not in out:
                raw = _raw("cty_org_dest")
                if raw and re.fullmatch(r'[A-Z]{2,3}', raw):
                    out["country_of_origin"] = raw

            # ── FOB value from item FCY field ────────────────────────────────
            # Value: "467,775.00 EUR" → 467775.0
            if "total_fob_value" not in out:
                raw = _raw("fob_fcy_cc")
                m = re.search(r'([\d,]+\.?\d*)', raw)
                if m:
                    try:
                        out["total_fob_value"] = float(m.group(1).replace(",", ""))
                    except ValueError:
                        pass

            # ── FOB Ncy from item FOB Ncy field (Field 34) ───────────────────
            # FOB in national currency (GHS) — used for insurance rate calculation
            # together with Freight Ncy so all values are in the same currency.
            if "fob_ncy" not in out:
                raw = _raw("fob_ncy")
                m = re.search(r'([\d,]+\.?\d*)', raw)
                if m:
                    try:
                        out["fob_ncy"] = float(m.group(1).replace(",", ""))
                    except ValueError:
                        pass

            # ── Product description ──────────────────────────────────────────
            if "product_description" not in out:
                raw = _raw("description_of_goods")
                if raw:
                    out["product_description"] = raw

    # ─── Tax table extraction from blocks (Claude path) ──────────────────────

    def _parse_tax_blocks(
        self, blocks: List[Dict[str, Any]], out: Dict[str, Any]
    ) -> None:
        """
        Extract tax duty/VAT data from the GRA BOE Section 40 tax table.

        Claude stores table blocks with structure:
          {"type": "Table", "content": {"headers": [...], "rows": [...]}}

        Tax table (Block 1 in typical GRA BOE output):
          Headers: Tax Code | Tax base Amt | TBC | Rate | Exempted/Suspended | Amount Payable
          Row:     ["01", "6,178,472.22", "24", "5.00", "0.00", "308,923.61"]

        Tax code → canonical field mapping:
          01 = Import Duty    → duty_rate, duty_amount
          02 = Import VAT     → vat_rate, vat_amount
          47 = Import NHIL    → nhil_amount
        """
        TAX_CODE_MAP = {
            "01": ("duty_rate",  "duty_amount"),
            "02": ("vat_rate",   "vat_amount"),
            "47": (None,         "nhil_amount"),
        }

        for block in blocks:
            if block.get("type") != "Table":
                continue

            content = block.get("content", {})
            headers = [str(h).lower() for h in content.get("headers", [])]
            rows = content.get("rows", [])
            if not rows:
                continue

            # Identify the numeric tax computation table:
            # first column must be a 2-digit tax code (e.g. "01", "02")
            first_row_vals = [str(v).strip() for v in rows[0]] if rows else []
            if not first_row_vals or not re.fullmatch(r'\d{2}', first_row_vals[0]):
                continue

            # Determine column positions
            # Expected order: Tax Code | Tax Base Amt | TBC | Rate | Exempted | Amount Payable
            # We detect by header name where possible, fall back to positional.
            code_col = 0
            rate_col = 3
            amount_col = 5

            for i, h in enumerate(headers):
                if "rate" in h and "amount" not in h:
                    rate_col = i
                if "payable" in h or ("amount" in h and i > 2):
                    amount_col = i

            for row in rows:
                row_vals = [str(v).strip() for v in row]
                if len(row_vals) <= max(code_col, rate_col, amount_col):
                    continue

                tax_code = row_vals[code_col]
                if tax_code not in TAX_CODE_MAP:
                    continue

                rate_field, amount_field = TAX_CODE_MAP[tax_code]

                # Extract rate (as decimal fraction, e.g. 5.00% → 0.05)
                if rate_field and rate_field not in out:
                    raw_rate = row_vals[rate_col].replace(",", "")
                    m = re.search(r'([\d]+\.[\d]+)', raw_rate)
                    if m:
                        try:
                            rate_pct = float(m.group(1))
                            if 0 < rate_pct <= 100:
                                out[rate_field] = rate_pct / 100.0
                        except ValueError:
                            pass

                # Extract amount payable
                if amount_field and amount_field not in out:
                    raw_amt = row_vals[amount_col].replace(",", "")
                    m = re.search(r'([\d]+\.[\d]+)', raw_amt)
                    if m:
                        try:
                            out[amount_field] = float(m.group(1))
                        except ValueError:
                            pass

            logger.debug(
                f"Tax blocks: duty_rate={out.get('duty_rate')}, "
                f"duty_amount={out.get('duty_amount')}, "
                f"vat_amount={out.get('vat_amount')}, "
                f"nhil_amount={out.get('nhil_amount')}"
            )
            # Only process the first matching tax table block
            return

    # ─── Attached documents table extraction from blocks ─────────────────────

    def _parse_attached_docs_blocks(
        self, blocks: List[Dict[str, Any]], out: Dict[str, Any]
    ) -> None:
        """
        Extract invoice number and BL number from the 'Attached Documents' table.

        Claude stores this as a Table block with rows:
          ["INVOICE", "9400080882"]
          ["BILL OF LADING / AIRWAYBILL", "S328717359"]
        """
        for block in blocks:
            if block.get("type") != "Table":
                continue

            content = block.get("content", {})
            headers = [str(h).lower() for h in content.get("headers", [])]
            rows = content.get("rows", [])

            # Identify the attached documents table: headers contain
            # "document" and "reference" columns
            if not any("document" in h for h in headers):
                continue
            if not any("reference" in h for h in headers):
                continue

            for row in rows:
                row_vals = [str(v).strip() for v in row]
                if len(row_vals) < 2:
                    continue

                doc_type = row_vals[0].upper()
                ref_val  = row_vals[1].strip()

                if not ref_val or ref_val.upper() in ("N/A", "NA", "", "-"):
                    continue

                if "INVOICE" in doc_type and "invoice_number" not in out:
                    if re.search(r'\d{6,}', ref_val):
                        out["invoice_number"] = ref_val

                if ("BILL OF LADING" in doc_type or "AIRWAYBILL" in doc_type
                        or "AWB" in doc_type) and "bl_number" not in out:
                    out["bl_number"] = ref_val

    # ─── Key-name scanning (Reducto path) ───────────────────────────────────

    def _parse_key_name(self, key: str, val_str: str, out: Dict[str, Any]) -> None:
        """Extract values that Reducto encoded inside the field key name."""

        # ── BOE number from key like "bill_of_entryboe_no" ───────────────────
        # Value: "40126075519 / 00"
        if ("bill_of_entry" in key and "no" in key) or "boe_no" in key:
            if "boe_number" not in out and val_str:
                # Strip trailing " / 00" revision suffix
                clean = re.split(r'\s*/\s*\d+', val_str)[0].strip()
                if re.fullmatch(r'\d{8,14}', clean):
                    out["boe_number"] = clean

        # ── Section 3: Gross Mass Kg ─────────────────────────────────────────
        # Key: "3_gross_mass_kg_1927800000_bill_of_date"
        # The 10-digit integer = gross_weight × 10000 (GRA prints 4 decimal places)
        m = re.search(r'gross_mass_kg_(\d{6,12})(?:_|$)', key)
        if m and "gross_weight" not in out:
            raw = int(m.group(1))
            out["gross_weight"] = raw / 10000.0 if raw > 9_999_999 else float(raw)

        # ── Section 15: Total FOB ────────────────────────────────────────────
        # Key: "15_total_fob_fcy_imp_ncy_exp_46777500"
        # Trailing digits = FOB value × 100 (2 decimal places)
        m = re.search(r'15_total_fob_fcy_imp_ncy_exp_(\d+)', key)
        if m and "total_fob_value" not in out:
            raw = int(m.group(1))
            out["total_fob_value"] = raw / 100.0

        # ── Section 12: Delivery Terms / Incoterm ───────────────────────────
        # Key: "12_delivery_terms_&_place_fca_tema"
        m = re.search(r'12_delivery_terms_&_place_([a-z]{3})', key, re.IGNORECASE)
        if m and "incoterm" not in out:
            out["incoterm"] = m.group(1).upper()

        # ── Section 7: Importer / Consignee ─────────────────────────────────
        if key.startswith("7_importer") and "consignee_name" not in out:
            m = re.search(
                r'liect_((?:[A-Za-z\u00C0-\u017E]+_)+limited)(?:_|$)', key, re.IGNORECASE
            )
            if m:
                company = m.group(1).replace("_", " ").strip()
                out["consignee_name"] = company.title()

        # ── Freight + Insurance embedded in long compound key ────────────────
        if "35_freight_ncy" in key and "freight_value" not in out:
            nums = re.findall(r'\b(\d{1,3}_\d{3}_\d{3}_\d{2})\b', key)
            if len(nums) >= 3:
                try:
                    out["freight_value_local"] = float(nums[1].replace("_", "")) / 100
                    out["insurance_value_local"] = float(nums[2].replace("_", "")) / 100
                except Exception:
                    pass
            elif len(nums) >= 2:
                try:
                    out["freight_value_local"] = float(nums[0].replace("_", "")) / 100
                    out["insurance_value_local"] = float(nums[1].replace("_", "")) / 100
                except Exception:
                    pass

    # ─── Value parsing (Reducto + fallback) ─────────────────────────────────

    def _parse_field_value(self, key: str, val_str: str, out: Dict[str, Any]) -> None:
        """Extract values embedded inside a field's value string."""
        if not val_str:
            return

        # ── Field 9: Declarant / Representative ─────────────────────────────
        # Matches both the combined field and the split name variant.
        # "declarant_representative_name" always wins (no guard); combined field
        # only fills in when not already set.
        # Explicit exclusion of "_no" and "_address" suffix variants.
        is_declarant_name_field = key == "declarant_representative_name"
        is_declarant_combined = (
            key == "declarant_representative" or key.startswith("9_declarant")
        ) and not key.endswith(("_no", "_address"))
        if is_declarant_name_field or (is_declarant_combined and "declarant_name" not in out):
            first_line = val_str.split("\n")[0].strip()
            if first_line and re.search(r'[A-Za-z]', first_line):
                out["declarant_name"] = first_line

        # ── Field 9: Declarant registration number ──────────────────────────
        # Raw field "declarant_no" or "declarant_representative_no" holds the
        # CH-number (e.g. "CH000258").
        if key in ("declarant_no", "declarant_representative_no") \
                and "declarant_reg_number" not in out:
            m = re.search(r'\b(CH\d{4,8})\b', val_str, re.IGNORECASE)
            if m:
                out["declarant_reg_number"] = m.group(1).upper()

        # ── Section 7: Consignee from field VALUE ────────────────────────────
        if key.startswith("7_importer") and "consignee_name" not in out:
            first_line = val_str.split("\n")[0].strip()
            if first_line and re.search(r'[A-Za-z\u00C0-\u017E]', first_line):
                out["consignee_name"] = first_line

        # ── HS Code from Section 26/27 value ────────────────────────────────
        if ("25_marks" in key or "27_commodity" in key or "commodity_code" in key
                or "item_no" in key):
            m = re.search(r'\b(\d{8,10})\b', val_str)
            if m and "hs_code" not in out:
                out["hs_code"] = m.group(1)

        # ── Customs Code from container / CPC field ──────────────────────────
        if "container_nos" in key or "cpc" in key or "chassis" in key:
            m = re.search(r'\b(40[A-Z]\d{2,3})\b', val_str)
            if m and "customs_code" not in out:
                out["customs_code"] = m.group(1)

        # ── Customs Value ────────────────────────────────────────────────────
        m = re.search(r'customs\s+value\s+([\d,]+\.?\d*)', val_str, re.IGNORECASE)
        if m and "customs_value" not in out:
            try:
                out["customs_value"] = float(m.group(1).replace(",", ""))
            except Exception:
                pass

        # ── Quantity from quantity_unit ──────────────────────────────────────
        if "quantity_unit" in key or "quantity_&_unit" in key:
            m = re.match(r'^([\d,\.]+)', val_str)
            if m and "quantity" not in out:
                try:
                    out["quantity"] = float(m.group(1).replace(",", ""))
                except Exception:
                    pass

        # ── BOE number from field VALUE ──────────────────────────────────────
        if ("bill_of_entry" in key and "no" in key) or "boe_no" in key:
            if "boe_number" not in out and val_str:
                clean = re.split(r'\s*/\s*\d+', val_str)[0].strip()
                if re.fullmatch(r'\d{8,14}', clean):
                    out["boe_number"] = clean

        # ── Invoice number from attached documents table ─────────────────────
        m = re.search(r'invoice\s*[|\s]+(\d{8,12})', val_str, re.IGNORECASE)
        if m and "invoice_number" not in out:
            out["invoice_number"] = m.group(1)

        # ── Exchange rate ────────────────────────────────────────────────────
        if "rate_of_xchange" in key or "exchange_rate" in key:
            m = re.search(r'([\d]+\.[\d]+)', val_str)
            if m and "exchange_rate" not in out:
                try:
                    out["exchange_rate"] = float(m.group(1))
                except Exception:
                    pass

        # ── Duty rate from tax/levy lines ────────────────────────────────────
        if ("duty" in key or "import_duty" in key or "31_" in key) and "duty_rate" not in out:
            m = re.search(r'\b(\d{1,2}\.\d{1,4})\b', val_str)
            if m:
                try:
                    rate = float(m.group(1))
                    if 0 < rate <= 100:
                        out["duty_rate"] = rate / 100.0
                except Exception:
                    pass

    # ─── Tax table parsing from items (Reducto path) ─────────────────────────

    def _parse_tax_table(self, items: List[Dict[str, Any]], out: Dict[str, Any]) -> None:
        """
        Parse the BOE Section 40 tax computation table from extracted items.

        Used by the Reducto extraction path where tax rows appear as items.
        For the Claude path, use _parse_tax_blocks instead.
        """
        TAX_CODE_MAP = {
            "01": ("duty_rate", "duty_amount"),
            "02": (None, "vat_amount"),
            "47": (None, "nhil_amount"),
        }

        for item in items:
            item = {k: (v["value"] if isinstance(v, dict) and "value" in v else v)
                    for k, v in item.items()}

            tax_code = None
            for tc_key in ("tax_code", "code", "tc", "tax"):
                raw = str(item.get(tc_key, "")).strip()
                if re.fullmatch(r'\d{2}', raw):
                    tax_code = raw
                    break

            if tax_code not in TAX_CODE_MAP:
                continue

            rate_field, amount_field = TAX_CODE_MAP[tax_code]

            if rate_field and rate_field not in out:
                for rk in ("rate", "rate_pct", "rate_%", "duty_rate", "pct"):
                    raw_rate = str(item.get(rk, "")).strip()
                    m = re.search(r'([\d]+\.[\d]+)', raw_rate)
                    if m:
                        try:
                            rate_pct = float(m.group(1))
                            if 0 < rate_pct <= 100:
                                out[rate_field] = rate_pct / 100.0
                                break
                        except ValueError:
                            pass

            if amount_field and amount_field not in out:
                for ak in ("amount_payable", "payable", "amount", "tax_amount"):
                    raw_amt = str(item.get(ak, "")).strip().replace(",", "")
                    m = re.search(r'([\d]+\.[\d]+)', raw_amt)
                    if m:
                        try:
                            out[amount_field] = float(m.group(1))
                            break
                        except ValueError:
                            pass

    # ─── Post-processing ─────────────────────────────────────────────────────

    def _post_process(self, out: Dict[str, Any]) -> None:
        """Derive or clean up fields after the main scan."""

        # HS code is stored as the full numeric code (e.g. "1901902000").
        # Strip any dots that may have been introduced by upstream parsing so
        # the value always matches the 10-digit format used in the reference data.
        if "hs_code" in out:
            hs = str(out["hs_code"]).replace(".", "")
            if re.fullmatch(r'\d{6,10}', hs):
                out["hs_code"] = hs

        # Ensure quantity is float
        if "quantity" in out and not isinstance(out["quantity"], float):
            try:
                out["quantity"] = float(out["quantity"])
            except Exception:
                pass

        # Remove garbage/noise fields that Claude sometimes extracts from
        # stray letters or labels on the dense GRA BOE form layout.
        noise_keys = {
            "f",  # stray single letter
            "page_no",  # page number, not a data field
            "items_count",  # item count, redundant with items array
        }
        for k in noise_keys:
            out.pop(k, None)

    # ─── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _to_decimal(value: Any) -> Optional[Decimal]:
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except Exception:
            return None


def extract_boe_sections(parsed_data: Dict[str, Any]) -> BOEStructuredData:
    return BOESectionExtractor().extract_sections(parsed_data)
