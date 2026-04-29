"""
Specialised extractor for Sanitary Certificate documents.

Sanitary certificates are issued by government health/agriculture authorities
and certify that exported goods meet the health standards of the destination
country. Key fields: issuing authority, certificate number, product description,
importer/exporter, issue date, and any lot/batch references.
"""

import logging
from typing import Any, Dict, List

from .base import BaseDocumentExtractor

logger = logging.getLogger(__name__)


class SanitaryCertExtractor(BaseDocumentExtractor):
    """Specialised extractor for Sanitary Certificate documents."""

    async def extract(
        self,
        fields: Dict[str, Any],
        items: List[Dict],
        blocks: List[Dict],
        document_type: str,
    ) -> Dict[str, Any]:
        """Single unified LLM pass over full sanitary certificate content."""
        try:
            table_text = self._serialize_items(items, max_rows=40)
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
                "SanitaryCertExtractor: extracted %d fields (items=%d, blocks=%d)",
                len(extracted), len(items), len(blocks),
            )
            return extracted

        except Exception as e:
            logger.error("SanitaryCertExtractor.extract failed: %s", e, exc_info=True)
            return {}

    def _build_prompt(
        self,
        table_text: str,
        block_text: str,
        existing_summary: str,
    ) -> str:
        return f"""You are a customs document expert specialised in Sanitary Certificates.

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

DOCUMENT IDENTITY:
- reference_number   = the certificate number / folio / document ID.
                       Labels: "Certificate No", "Folio", "No.", "Número", "Oficio".
- issue_date         = date the certificate was issued. Normalise to YYYY-MM-DD.
- expiry_date        = expiry / valid-until date if stated. Normalise to YYYY-MM-DD.

ISSUING AUTHORITY:
- issuer             = name of the government body or authority that issued it.
                       Labels: "Issued by", "Authority", "Autoridad", "SENASICA", "SAGARPA",
                       "Ministry of Agriculture", "Servicio Nacional".
- issuer_country     = country of the issuing authority.
- issuer_signature   = name of the signing official if present.

PARTIES:
- shipper_name       = COMPANY NAME ONLY of the exporter/producer.
                       Labels: "Exporter", "Producer", "Exporter/Producer", "Exportador".
- shipper_address    = full address of the exporter.
- consignee_name     = COMPANY NAME ONLY of the consignee/importer.
                       Labels: "Consignee", "Importer", "Importador", "Consignatario".
- consignee_address  = full address of the consignee.

GOODS:
- product_description = full description of the goods as stated on this certificate.
- hs_code             = HS / tariff code if shown.
- quantity            = total quantity if stated.
- net_weight          = net weight if stated.
- gross_weight        = gross weight if stated.
- lot_number          = production lot / batch number if stated.
                        Labels: "Lot", "Lote", "Batch", "Production Lot".

REFERENCES:
- invoice_number      = commercial invoice number referenced on this certificate.
- bl_number           = BL / AWB number if referenced.

Populate only the fields you find with confidence. Leave everything else as null."""
