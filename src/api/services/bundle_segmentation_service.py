"""
Bundle segmentation: detect document boundaries in a multi-document PDF using
Claude, split the PDF into per-type segment files, and merge duplicate document
types (e.g. two invoices) into a single aggregated document for the validation
workflow.
"""

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel
from pypdf import PdfReader, PdfWriter

logger = logging.getLogger(__name__)

KNOWN_DOCUMENT_TYPES = frozenset({
    "invoice",
    "packing_list",
    "bill_of_lading",
    "delivery_note",
})


class SegmentResult(BaseModel):
    document_type: str
    file_path: Path
    pages: List[int]  # 1-based page numbers
    confidence: float
    source_filename: str

    model_config = {"arbitrary_types_allowed": True}


class BundleSegmentationService:
    """
    Detects document boundaries in a bundled PDF using Claude, then writes
    each detected segment to its own PDF file.
    """

    def __init__(self, upload_dir: Path):
        self._upload_dir = upload_dir

    async def segment(self, bundle_path: Path) -> List[SegmentResult]:
        """Analyse bundle_path and return one SegmentResult per detected document."""
        raw_segments = await self._detect_boundaries(bundle_path)
        return self._split_pdf(bundle_path, raw_segments)

    # ── private helpers ────────────────────────────────────────────────────────

    async def _detect_boundaries(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """
        Send the full PDF to Claude via Bedrock and ask it to identify document
        boundaries by page number.  Works for both text-based and scanned PDFs
        because Claude reads the document visually.
        """
        pdf_bytes = pdf_path.read_bytes()
        total_pages = len(PdfReader(str(pdf_path)).pages)

        prompt = (
            f"This PDF has {total_pages} page(s). "
            "It is a bundled file containing multiple shipping documents combined into one.\n\n"
            "Identify the document boundaries — which pages belong to which document type — "
            "and return a structured JSON response.\n\n"
            "RECOGNISED DOCUMENT TYPES (use these exact string keys):\n"
            "- invoice         (commercial invoice or fiscal invoice / CFDI)\n"
            "- packing_list    (packing list)\n"
            "- bill_of_lading  (bill of lading or sea waybill)\n"
            "- delivery_note   (SAP delivery note, despatch note, or outbound delivery document)\n\n"
            "RULES:\n"
            "1. Each contiguous group of pages belonging to the SAME SINGLE document instance is ONE segment.\n"
            "2. If the same document type appears more than once, create a SEPARATE segment for EACH instance.\n"
            "   This includes adjacent pages: two invoices on consecutive pages are TWO segments, not one.\n"
            "   Key signals that a new document instance starts: a new Invoice Number / FOLIO FISCAL, "
            "   a new Delivery Note number, or a fresh header/letterhead.\n"
            "3. Assign confidence >= 0.85 for pages you are certain about.\n"
            "4. If a page is not one of the four recognised types above (e.g. certificate of origin, "
            "   sanitary certificate, certificate of analysis, customs declaration), "
            "   assign document_type \"unknown\" — do NOT force it into a recognised type.\n"
            "5. Page numbers are 1-indexed.\n"
            "6. Every page must appear in exactly one segment — do not skip pages.\n\n"
            "Return ONLY valid JSON — no markdown fences, no explanation:\n"
            '{"segments": [{"document_type": "bill_of_lading", "pages": [1, 2], "confidence": 0.97}]}'
        )

        raw = await asyncio.to_thread(
            self._call_bedrock, pdf_bytes, prompt
        )

        raw = raw.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            data = json.loads(raw)
            segments = data.get("segments", [])
            logger.info("BundleSegmentationService: detected %d segments in %d pages", len(segments), total_pages)
            return segments
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"BundleSegmentationService: Claude returned non-JSON: {raw[:300]}"
            ) from exc

    @staticmethod
    def _call_bedrock(pdf_bytes: bytes, prompt: str) -> str:
        """Synchronous Bedrock converse call (run via asyncio.to_thread)."""
        import boto3
        from botocore import UNSIGNED
        from botocore.config import Config as BotocoreConfig

        bearer_token = os.getenv("AWS_BEARER_TOKEN_BEDROCK", "")
        aws_region = os.getenv("AWS_REGION", "us-east-1")
        model = os.getenv("LLM_MODEL_ID", "global.anthropic.claude-sonnet-4-6")

        client = boto3.client(
            "bedrock-runtime",
            region_name=aws_region,
            aws_access_key_id="bedrock-api-key",
            aws_secret_access_key="not-used",
            config=BotocoreConfig(
                signature_version=UNSIGNED,
                read_timeout=120,
                connect_timeout=30,
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )

        if bearer_token:
            def _inject(request, **kwargs):
                request.headers["Authorization"] = f"Bearer {bearer_token}"
            client.meta.events.register("before-send.bedrock-runtime.*", _inject)

        response = client.converse(
            modelId=model,
            system=[{"text": "You are a customs document expert who identifies document types within bundled PDFs."}],
            messages=[{
                "role": "user",
                "content": [
                    {"document": {"format": "pdf", "name": "bundle", "source": {"bytes": pdf_bytes}}},
                    {"text": prompt},
                ],
            }],
            inferenceConfig={"maxTokens": 2048, "temperature": 0.0},
        )

        content = response.get("output", {}).get("message", {}).get("content", [{}])
        return content[0].get("text", "")

    @staticmethod
    def _split_pdf(
        bundle_path: Path,
        raw_segments: List[Dict[str, Any]],
    ) -> List[SegmentResult]:
        reader = PdfReader(str(bundle_path))
        total_pages = len(reader.pages)
        bundle_id = bundle_path.stem
        results: List[SegmentResult] = []
        type_counts: Dict[str, int] = {}

        for seg in raw_segments:
            doc_type: str = seg.get("document_type", "unknown")
            if doc_type == "delivery_note":
                doc_type = "packing_list"
            pages: List[int] = seg.get("pages", [])
            confidence: float = float(seg.get("confidence", 0.0))

            if not pages:
                continue

            type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
            idx = type_counts[doc_type]
            suffix = f"_{idx}" if idx > 1 else ""
            seg_path = bundle_path.parent / f"{bundle_id}_{doc_type}{suffix}.pdf"

            writer = PdfWriter()
            valid_pages: List[int] = []
            for p in pages:
                zero_idx = p - 1
                if 0 <= zero_idx < total_pages:
                    writer.add_page(reader.pages[zero_idx])
                    valid_pages.append(p)

            if not valid_pages:
                logger.warning("Bundle segment %s has no valid pages — skipping", doc_type)
                continue

            with open(seg_path, "wb") as f:
                writer.write(f)

            results.append(SegmentResult(
                document_type=doc_type,
                file_path=seg_path,
                pages=valid_pages,
                confidence=confidence,
                source_filename=bundle_path.name,
            ))
            logger.info(
                "Bundle segment: type=%s confidence=%.2f",
                doc_type, confidence,
            )

        return results


class MergeIssue(BaseModel):
    """A conflict or inconsistency detected while merging same-type document segments."""
    field: str
    issue_type: str   # "identity_conflict" | "currency_mismatch"
    values: List[str]
    severity: str     # "warning" | "error"
    message: str


class DocumentMerger:
    """
    Merges multiple same-type extracted document segments into one document for
    the validation workflow, with pre-merge consistency checking.

    Field categories (per document type)
    ─────────────────────────────────────
    SUMMABLE  — numeric totals (weights, values, quantities).
                Summed only when all docs share the same currency.
                A currency mismatch emits a MergeIssue(error) and skips summation.
    IDENTITY  — header fields that must be equal across all docs
                (shipper, consignee, port, BL number, container_count …).
                If they differ a MergeIssue(warning) is emitted and the field
                is LEFT UNSET in the merged doc so downstream validators surface
                the conflict rather than silently validating a guessed value.
    UNION     — identifier fields collected as a deduplicated comma-joined list
                (invoice_number, order_number, container_numbers …).
    FIRST_WINS — every other field; first non-empty value wins.
    items     — concatenated from all docs in the set.

    Returns (merged_doc, issues).
    """

    _IDENTITY_FIELDS: Dict[str, frozenset] = {
        "invoice": frozenset({
            "currency", "shipper_name", "consignee_name",
            "port_of_loading", "port_of_discharge", "bl_number",
            "vessel_name", "voyage_number", "incoterm", "container_count",
        }),
        "packing_list": frozenset({
            "currency", "shipper_name", "consignee_name",
            "port_of_loading", "port_of_discharge", "bl_number",
            # container_count is SUMMABLE for packing_list: each delivery note covers
            # its own containers, so totals must be summed, not asserted equal.
        }),
        "bill_of_lading": frozenset({
            "shipper_name", "consignee_name", "port_of_loading",
            "port_of_discharge", "bl_number", "container_count",
            "vessel_name", "voyage_number",
        }),
    }

    _SUMMABLE_FIELDS: Dict[str, frozenset] = {
        "invoice": frozenset({
            "total_amount", "invoice_value", "fob_value", "cif_value",
            "total_invoice_value", "total_fob_value",
            "gross_weight", "net_weight", "quantity", "number_of_packages",
            "total_packages", "total_quantity", "total_weight",
        }),
        "packing_list": frozenset({
            "gross_weight", "net_weight", "quantity",
            "number_of_packages", "total_packages", "total_quantity",
            "container_count",
        }),
        "bill_of_lading": frozenset({
            "gross_weight", "net_weight", "quantity",
        }),
    }

    _UNION_FIELDS: Dict[str, frozenset] = {
        "invoice": frozenset({"invoice_number", "order_number", "po_number", "document_number", "product_description"}),
        "packing_list": frozenset({"reference_number", "document_number", "container_numbers", "po_number", "order_number"}),
        "bill_of_lading": frozenset({"container_numbers"}),
    }

    def merge(
        self,
        doc_type: str,
        extracted_list: List[Dict[str, Any]],
    ) -> "tuple[Dict[str, Any], List[MergeIssue]]":
        """
        Merge a list of same-type extracted dicts into one.

        Returns:
            (merged_doc, issues) — merged_doc is ready for the validation workflow;
            issues lists any identity conflicts or currency mismatches detected.
        """
        if len(extracted_list) == 1:
            return extracted_list[0], []

        identity_fields = self._IDENTITY_FIELDS.get(doc_type, frozenset())
        summable_fields = self._SUMMABLE_FIELDS.get(doc_type, frozenset())
        union_fields = self._UNION_FIELDS.get(doc_type, frozenset())

        # Pre-merge checks
        issues: List[MergeIssue] = []
        conflicted_fields = self._check_identity_fields(identity_fields, extracted_list, issues)
        currency_ok = self._check_currency(doc_type, extracted_list, issues)

        merged: Dict[str, Any] = {}
        all_items: List[Any] = []
        merged_from: List[str] = []
        union_buckets: Dict[str, List[str]] = {f: [] for f in union_fields}

        for doc in extracted_list:
            # Provenance: record the primary reference number of each source doc
            for ref_key in ("invoice_number", "reference_number", "document_number"):
                val = doc.get(ref_key)
                if val is not None:
                    raw = val.get("value") if isinstance(val, dict) else val
                    if raw and str(raw).strip() not in ("", "-"):
                        merged_from.append(str(raw).strip())
                        break

            all_items.extend(doc.get("items", []))

            for key, value in doc.items():
                if key == "items":
                    continue

                if key in union_fields:
                    token = self._scalar_str(value)
                    if token:
                        union_buckets[key].append(token)
                elif key in conflicted_fields:
                    # Identity conflict: leave unset so validators surface the gap
                    pass
                elif key in identity_fields:
                    # Identity field with consensus: first non-empty wins
                    if key not in merged or self._is_empty(merged.get(key)):
                        merged[key] = value
                elif key in summable_fields and currency_ok:
                    merged[key] = self._sum_field(merged.get(key), value)
                else:
                    # FIRST_WINS for everything else (and summable fields when
                    # currency mismatch blocks summation)
                    if key not in merged or self._is_empty(merged.get(key)):
                        merged[key] = value

        merged["items"] = all_items
        merged["merged_from"] = merged_from
        merged["merge_count"] = len(extracted_list)

        # Write union fields as deduplicated comma-joined strings
        for field, tokens in union_buckets.items():
            seen: List[str] = []
            for t in tokens:
                if t not in seen:
                    seen.append(t)
            if seen:
                merged[field] = ", ".join(seen)

        # Derive product_description from line items when absent from header.
        # Invoices and packing lists often carry description only at the item level.
        # Building a header-level summary enables cross-document fuzzy matching.
        if not merged.get("product_description"):
            item_descs: List[str] = []
            for item in all_items:
                token = self._scalar_str(item.get("product_description"))
                if token and token not in item_descs:
                    item_descs.append(token)
            if item_descs:
                merged["product_description"] = "; ".join(item_descs)

        logger.info(
            "DocumentMerger: merged %d %s docs (from=%s items=%d issues=%d)",
            len(extracted_list), doc_type, merged_from, len(all_items), len(issues),
        )
        return merged, issues

    # ── pre-merge checks ───────────────────────────────────────────────────────

    @staticmethod
    def _check_identity_fields(
        identity_fields: frozenset,
        docs: List[Dict[str, Any]],
        issues: List[MergeIssue],
    ) -> frozenset:
        """
        Detect identity fields where docs disagree.
        Appends MergeIssue entries to `issues` and returns the set of
        conflicted field names so the merger can leave them unset.
        """
        conflicted: List[str] = []
        for field in identity_fields:
            values = [
                DocumentMerger._scalar_str(doc.get(field))
                for doc in docs
                if not DocumentMerger._is_empty(doc.get(field))
            ]
            unique = list(dict.fromkeys(values))  # ordered dedup
            if len(unique) > 1:
                conflicted.append(field)
                issues.append(MergeIssue(
                    field=field,
                    issue_type="identity_conflict",
                    values=unique,
                    severity="warning",
                    message=(
                        f"Documents disagree on '{field}' ("
                        + " vs ".join(f'"{v}"' for v in unique)
                        + "). Field left unset — downstream validators will flag the gap."
                    ),
                ))
        return frozenset(conflicted)

    @staticmethod
    def _check_currency(
        doc_type: str,
        docs: List[Dict[str, Any]],
        issues: List[MergeIssue],
    ) -> bool:
        """
        Check that all docs share the same currency before summing value fields.
        Returns True if summation is safe, False otherwise.
        """
        currencies = [
            DocumentMerger._scalar_str(doc.get("currency")).upper()
            for doc in docs
            if not DocumentMerger._is_empty(doc.get("currency"))
        ]
        unique = list(dict.fromkeys(currencies))
        if len(unique) > 1:
            issues.append(MergeIssue(
                field="currency",
                issue_type="currency_mismatch",
                values=unique,
                severity="error",
                message=(
                    f"Cannot sum {doc_type} values: documents use different currencies "
                    f"({', '.join(unique)}). Numeric totals will not be summed."
                ),
            ))
            return False
        return True

    # ── field helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _is_empty(v: Any) -> bool:
        if v is None:
            return True
        raw = v.get("value") if isinstance(v, dict) else v
        return raw is None or str(raw).strip() in ("", "<empty>", "-", "—", "N/A")

    @staticmethod
    def _scalar_str(v: Any) -> str:
        raw = v.get("value") if isinstance(v, dict) else v
        return str(raw).strip() if raw is not None else ""

    @staticmethod
    def _sum_field(existing: Any, new_val: Any) -> Any:
        def _to_float(v: Any) -> float:
            raw = v.get("value") if isinstance(v, dict) else v
            if isinstance(raw, (int, float)):
                return float(raw)
            try:
                cleaned = str(raw).replace(",", "").strip()
                m = re.match(r"^-?[\d]+\.?[\d]*", cleaned)
                return float(m.group()) if m else 0.0
            except (ValueError, TypeError, AttributeError):
                return 0.0

        if existing is None:
            return new_val
        total = _to_float(existing) + _to_float(new_val)
        if isinstance(existing, dict):
            return {**existing, "value": total}
        return total
