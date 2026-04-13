"""
BOE Section-Specific Extractor for Ghana GRA BOE Forms.

The Ghana Revenue Authority (GRA) BOE form has a very dense, multi-column
table layout.  Reducto often embeds numeric values inside field *key names*
rather than field values because adjacent label and value cells get merged.

This extractor uses two complementary strategies:
  1. Direct field lookup — for fields where Reducto did produce a clean KV pair.
  2. Key-name scanning — for values that ended up encoded inside the key name
     (e.g. "3_gross_mass_kg_1927800000_bill_of_date" → gross_weight=192780.0).
  3. Value parsing — for multi-value strings embedded in a single field value
     (e.g. "26 Item No 27 Commodity Code DGD Ref. No.\\n0001 1901902000").

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
    ) -> Dict[str, Any]:
        """
        Main extraction entry point.  Returns a flat dict of canonical field
        names → normalised values extracted from the GRA BOE raw fields.

        Args:
            raw_fields: Flat field dict from the AI provider (may contain
                        Reducto dict-wrapped values).
            items: Optional list of line-item / table rows.  Used to parse
                   the tax computation table (Section 40) for duty_rate and
                   duty_amount.
        """
        extracted: Dict[str, Any] = {}

        for key, raw_val in raw_fields.items():
            # Unwrap Reducto dict-wrapped values
            if isinstance(raw_val, dict) and "value" in raw_val:
                raw_val = raw_val["value"]
            val_str = str(raw_val).strip() if raw_val is not None else ""

            # Skip clearly empty cells
            if val_str in ("", "<empty>", "-", "—"):
                val_str = ""

            self._parse_key_name(key, val_str, extracted)
            self._parse_field_value(key, val_str, extracted)

        # Parse Section 40 (tax table) from items if provided
        if items:
            self._parse_tax_table(items, extracted)

        self._post_process(extracted)
        return extracted

    # ─── Key-name scanning ───────────────────────────────────────────────────

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
        # Note: no \b word boundaries — underscores are \w so boundaries would fail
        m = re.search(r'gross_mass_kg_(\d{6,12})(?:_|$)', key)
        if m and "gross_weight" not in out:
            raw = int(m.group(1))
            # Values like 1927800000 need ÷10000 → 192780.0
            # Values like 192780 need no division
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
        # Key: "7_importer_&_address_a_customis_liect_nestle_ghana_limited_no33..."
        # Use `liect_` as the specific anchor (not the greedy `address_[a-z_]+_`
        # alternative, which over-matches and leaves only "ghana_limited").
        # Use [A-Za-zÀ-ÿ]+ (no underscore) for word chars so the group stops
        # cleanly at digit-only tokens like _no33_.
        if key.startswith("7_importer") and "consignee_name" not in out:
            m = re.search(
                r'liect_((?:[A-Za-z\u00C0-\u017E]+_)+limited)(?:_|$)', key, re.IGNORECASE
            )
            if m:
                company = m.group(1).replace("_", " ").strip()
                out["consignee_name"] = company.title()

        # ── Freight + Insurance embedded in long compound key ────────────────
        # Key contains sub-patterns like: "_133_851_18_" or "_53_592_73_"
        # after markers "35_freight_ncy" and "36_insurance_ncy"
        if "35_freight_ncy" in key and "freight_value" not in out:
            # Extract first 3-part number sequence after "freight_ncy_"
            # Typical: "...35_freight_ncy_36_insurance_ncy_5_991_028_31_133_851_18_53_592_73..."
            # FOB NCY = 5_991_028_31 = 5,991,028.31
            # Freight = 133_851_18 = 133,851.18
            # Insurance = 53_592_73 = 53,592.73
            nums = re.findall(r'\b(\d{1,3}_\d{3}_\d{3}_\d{2})\b', key)
            if len(nums) >= 3:
                # nums[0] = FOB NCY, [1] = Freight NCY, [2] = Insurance NCY
                try:
                    out["freight_value_local"] = float(nums[1].replace("_", "").replace("_", "")) / 100
                    out["insurance_value_local"] = float(nums[2].replace("_", "").replace("_", "")) / 100
                except Exception:
                    pass
            elif len(nums) >= 2:
                try:
                    out["freight_value_local"] = float(nums[0].replace("_", "")) / 100
                    out["insurance_value_local"] = float(nums[1].replace("_", "")) / 100
                except Exception:
                    pass

    # ─── Value parsing ───────────────────────────────────────────────────────

    def _parse_field_value(self, key: str, val_str: str, out: Dict[str, Any]) -> None:
        """Extract values embedded inside a field's value string."""
        if not val_str:
            return

        # ── Section 7: Consignee from field VALUE ────────────────────────────
        # Fallback: if key-name regex failed (e.g. accented char stopped the match),
        # use the first non-empty line of the value — Reducto often puts the full
        # company name there (e.g. "Nestlé Ghana Limited\nNo. 33, Airport...").
        if key.startswith("7_importer") and "consignee_name" not in out:
            first_line = val_str.split("\n")[0].strip()
            # Accept only if it looks like a company name (has letters, not just digits)
            if first_line and re.search(r'[A-Za-z\u00C0-\u017E]', first_line):
                out["consignee_name"] = first_line

        # ── HS Code from Section 26/27 value ────────────────────────────────
        # Value: "26 Item No 27 Commodity Code DGD Ref. No.\n0001 1901902000"
        if ("25_marks" in key or "27_commodity" in key or "commodity_code" in key
                or "item_no" in key):
            m = re.search(r'\b(\d{8,10})\b', val_str)
            if m and "hs_code" not in out:
                raw_hs = m.group(1)
                # Normalise to international 6-digit format XXXX.XX
                out["hs_code"] = f"{raw_hs[:4]}.{raw_hs[4:6]}"
                out["hs_code_full"] = raw_hs  # keep full national code

        # ── Customs Code from container / CPC field ──────────────────────────
        # Value: "BE GEN 40V02"
        if "container_nos" in key or "cpc" in key or "chassis" in key:
            m = re.search(r'\b(40[A-Z]\d{2,3})\b', val_str)
            if m and "customs_code" not in out:
                out["customs_code"] = m.group(1)

        # ── Customs Value ────────────────────────────────────────────────────
        # Value: "42 Customs Value 6,178,472.22"
        m = re.search(r'customs\s+value\s+([\d,]+\.?\d*)', val_str, re.IGNORECASE)
        if m and "customs_value" not in out:
            try:
                out["customs_value"] = float(m.group(1).replace(",", ""))
            except Exception:
                pass

        # ── Quantity from quantity_unit ──────────────────────────────────────
        # Value: "7,560 BG"
        if "quantity_unit" in key or "quantity_&_unit" in key:
            m = re.match(r'^([\d,\.]+)', val_str)
            if m and "quantity" not in out:
                try:
                    out["quantity"] = float(m.group(1).replace(",", ""))
                except Exception:
                    pass

        # ── BOE number from field VALUE ──────────────────────────────────────
        # Field: "bill_of_entry_no" / "bill_of_entryboe_no"
        # Value: "40126075519 / 00"
        if ("bill_of_entry" in key and "no" in key) or "boe_no" in key:
            if "boe_number" not in out and val_str:
                clean = re.split(r'\s*/\s*\d+', val_str)[0].strip()
                if re.fullmatch(r'\d{8,14}', clean):
                    out["boe_number"] = clean

        # ── Invoice number from attached documents table ─────────────────────
        # Value may contain "| INVOICE | 9400080882 |"
        m = re.search(r'invoice\s*[|\s]+(\d{8,12})', val_str, re.IGNORECASE)
        if m and "invoice_number" not in out:
            out["invoice_number"] = m.group(1)

        # ── Exchange rate ────────────────────────────────────────────────────
        # Value like "13.5620" in a rate_of_xchange field
        if "rate_of_xchange" in key or "exchange_rate" in key:
            m = re.search(r'([\d]+\.[\d]+)', val_str)
            if m and "exchange_rate" not in out:
                try:
                    out["exchange_rate"] = float(m.group(1))
                except Exception:
                    pass

        # ── Duty rate from tax/levy lines ────────────────────────────────────
        # Value like "52 2.50" or just "2.50"
        if ("duty" in key or "import_duty" in key or "31_" in key) and "duty_rate" not in out:
            m = re.search(r'\b(\d{1,2}\.\d{1,4})\b', val_str)
            if m:
                try:
                    rate = float(m.group(1))
                    if 0 < rate <= 100:
                        out["duty_rate"] = rate / 100.0  # store as decimal fraction
                except Exception:
                    pass

    # ─── Tax table parsing (Section 40) ──────────────────────────────────────

    def _parse_tax_table(self, items: List[Dict[str, Any]], out: Dict[str, Any]) -> None:
        """
        Parse the BOE Section 40 tax computation table from extracted items.

        Ghana GRA BOE tax table structure (each row = one tax line):
          tax_code | tax_base_amount | tbc | rate_pct | exempted | amount_payable

        Tax code 01 = Import Duty (5% on customs value).
        Tax code 02 = Import VAT (15% on customs_value + duty_amount).
        Tax code 47 = NHIL (2.5% of the VAT base).

        We populate:
          duty_rate    — decimal fraction (e.g. 0.05 for 5%)
          duty_amount  — Import Duty amount payable (Tax 01)
          vat_amount   — Import VAT amount payable (Tax 02)
          nhil_amount  — NHIL amount payable (Tax 47)
        """
        # Tax code → canonical output field
        TAX_CODE_MAP = {
            "01": ("duty_rate", "duty_amount"),
            "02": (None, "vat_amount"),
            "47": (None, "nhil_amount"),
        }

        for item in items:
            # Unwrap any Reducto envelopes in item values
            item = {k: (v["value"] if isinstance(v, dict) and "value" in v else v)
                    for k, v in item.items()}

            # Identify the tax code — look for a key like "tax_code" / "code"
            tax_code = None
            for tc_key in ("tax_code", "code", "tc", "tax"):
                raw = str(item.get(tc_key, "")).strip()
                if re.fullmatch(r'\d{2}', raw):
                    tax_code = raw
                    break

            if tax_code not in TAX_CODE_MAP:
                continue

            rate_field, amount_field = TAX_CODE_MAP[tax_code]

            # Extract rate (%) — look for a "rate" or "rate_pct" column
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

            # Extract amount payable — look for "amount_payable" / "payable" / "amount"
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

        if "duty_rate" in out or "duty_amount" in out:
            logger.debug(
                f"Tax table: duty_rate={out.get('duty_rate')}, "
                f"duty_amount={out.get('duty_amount')}, "
                f"vat_amount={out.get('vat_amount')}"
            )

    # ─── Post-processing ─────────────────────────────────────────────────────

    def _post_process(self, out: Dict[str, Any]) -> None:
        """Derive or clean up fields after the main scan."""
        # BOE gross weight is typically the sum of net weight + tare.
        # If we have gross but not net, we can't derive net safely — leave it absent.

        # Normalise HS code format (ensure XXXX.XX not raw digits)
        if "hs_code" in out:
            hs = str(out["hs_code"])
            if re.fullmatch(r'\d{6,10}', hs):
                out["hs_code"] = f"{hs[:4]}.{hs[4:6]}"

        # Ensure quantity is float
        if "quantity" in out and not isinstance(out["quantity"], float):
            try:
                out["quantity"] = float(out["quantity"])
            except Exception:
                pass

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
