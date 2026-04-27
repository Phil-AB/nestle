"""
Specialised extractor for Certificate of Origin (COO) documents.

COO layout conventions:
- Exporter/Producer name and address
- Consignee name and address
- Country of origin (the key field — this is what Step 2 validates)
- Description of goods, HS code, quantity, weight
- Certifying body (chamber of commerce, government body)
- Issue date, certificate number
"""

import logging
from typing import Any, Dict, List

from .base import BaseDocumentExtractor

logger = logging.getLogger(__name__)


class CertificateOfOriginExtractor(BaseDocumentExtractor):
    """Specialised extractor for Certificate of Origin documents."""

    async def extract(
        self,
        fields: Dict[str, Any],
        items: List[Dict],
        blocks: List[Dict],
        document_type: str,
    ) -> Dict[str, Any]:
        """Single unified LLM pass over full COO content."""
        try:
            table_text = self._serialize_items(items, max_rows=40)
            block_text = self._serialize_blocks(blocks, max_blocks=80)
            existing_summary = self._fields_summary(fields, max_fields=20)

            prompt = self._build_coo_prompt(
                table_text=table_text,
                block_text=block_text,
                existing_summary=existing_summary,
            )

            result = await self.llm_extraction.ainvoke(prompt)
            extracted = {k: v for k, v in result.model_dump().items() if v is not None}

            logger.info(
                f"CertificateOfOriginExtractor: extracted {len(extracted)} fields "
                f"(items={len(items)}, blocks={len(blocks)})"
            )
            return extracted

        except Exception as e:
            logger.error(f"CertificateOfOriginExtractor.extract failed: {e}", exc_info=True)
            return {}

    def _build_coo_prompt(
        self,
        table_text: str,
        block_text: str,
        existing_summary: str,
    ) -> str:
        return f"""You are a customs document expert specialised in Certificates of Origin.

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
EXTRACTION RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CRITICAL FIELD — country_of_origin:
This is the primary purpose of this document.  Look for:
  - "Country of Origin", "Origin", "Country of Manufacture", "Produced in", "Made in"
  - The certifying statement (e.g. "We hereby certify that the goods described below
    originate in the NETHERLANDS")
  - Extract the COUNTRY NAME or ISO code (e.g. "Netherlands", "NL", "Germany")

PARTIES:
- shipper_name    = COMPANY NAME ONLY of the exporter/producer.
                    Labels: "Exporter", "Producer", "Manufacturer", "Shipper".
- shipper_address = full address of the exporter/producer.
- consignee_name  = COMPANY NAME ONLY of the consignee/importer.
                    Labels: "Consignee", "Importer", "Shipped To".
- consignee_address = full address of the consignee.

REFERENCE NUMBERS:
- invoice_number  = invoice number referenced on the certificate
- bl_number       = BL number if referenced
- order_number    = order number if referenced

GOODS:
- product_description = full description of the goods
- hs_code             = HS tariff code if shown
- country_of_origin   = THE COUNTRY OF ORIGIN (most important field on this document)
- net_weight          = net weight if stated
- gross_weight        = gross weight if stated
- quantity            = quantity if stated

Populate only the fields you find with confidence. Leave everything else as null."""
