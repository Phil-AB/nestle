"""
Specialised extractor for Certificate of Analysis (COA) documents.

A COA is issued by the manufacturer or an accredited lab and certifies that
a product batch meets specified quality/safety parameters. Key fields:
product name, lot/batch number, test results, issuing lab, and validity.
"""

import logging
from typing import Any, Dict, List

from .base import BaseDocumentExtractor

logger = logging.getLogger(__name__)


class COAExtractor(BaseDocumentExtractor):
    """Specialised extractor for Certificate of Analysis documents."""

    async def extract(
        self,
        fields: Dict[str, Any],
        items: List[Dict],
        blocks: List[Dict],
        document_type: str,
    ) -> Dict[str, Any]:
        """Single unified LLM pass over full COA content."""
        try:
            table_text = self._serialize_items(items, max_rows=60)
            block_text = self._serialize_blocks(blocks, max_blocks=80)
            existing_summary = self._fields_summary(fields, max_fields=20)

            prompt = self._build_prompt(
                table_text=table_text,
                block_text=block_text,
                existing_summary=existing_summary,
            )

            result = await self.llm_extraction.ainvoke(prompt)
            extracted = {k: v for k, v in result.model_dump().items() if v is not None}

            logger.info(
                "COAExtractor: extracted %d fields (items=%d, blocks=%d)",
                len(extracted), len(items), len(blocks),
            )
            return extracted

        except Exception as e:
            logger.error("COAExtractor.extract failed: %s", e, exc_info=True)
            return {}

    def _build_prompt(
        self,
        table_text: str,
        block_text: str,
        existing_summary: str,
    ) -> str:
        return f"""You are a customs and quality-assurance document expert specialised in Certificates of Analysis (COA).

ALREADY EXTRACTED FIELDS (do not re-extract unless you can improve them):
{existing_summary or "none"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TABLE ROWS (test parameters and results):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{table_text or "(no table rows)"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DOCUMENT TEXT BLOCKS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{block_text or "(no blocks)"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EXTRACTION RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DOCUMENT IDENTITY:
- reference_number    = the COA document number / certificate ID.
                        Labels: "Certificate No", "COA No", "Análisis No", "Document No".
- issue_date          = date the COA was issued. Normalise to YYYY-MM-DD.

PRODUCT:
- product_description = full product name and description as stated on the COA.
                        Labels: "Product", "Material", "Article", "Producto".
- product_code        = internal product / article code if present.
- lot_number          = production lot / batch number this COA covers.
                        Labels: "Lot No", "Batch No", "Lote", "Lot Number", "Production Lot".
- manufacture_date    = date of manufacture if stated. Normalise to YYYY-MM-DD.
- expiry_date         = best-before / expiry date if stated. Normalise to YYYY-MM-DD.
- quantity            = quantity of product covered by this COA.
- net_weight          = net weight if stated.

ISSUING ENTITY:
- issuer              = name of the manufacturer, laboratory, or authority issuing the COA.
                        Labels: "Issued by", "Manufacturer", "Laboratory", "Laboratorio".
- issuer_country      = country of the issuing entity.

PARTIES:
- shipper_name        = COMPANY NAME ONLY of the exporter/manufacturer.
                        Labels: "Manufacturer", "Supplier", "Exporter", "Producer".
- consignee_name      = COMPANY NAME ONLY of the consignee/buyer if stated.

REFERENCES:
- invoice_number      = commercial invoice number referenced on this COA if present.
- hs_code             = HS / tariff code if shown.

Populate only the fields you find with confidence. Leave everything else as null."""
