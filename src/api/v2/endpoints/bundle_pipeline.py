"""
Bundle pipeline endpoint — accepts a single multi-document PDF and runs the
full vendor document validation workflow against it.

This is an additive alternative to validate_vendor_docs: the existing
separate-file upload flow is unchanged.  Use this endpoint when the clearing
agent has bundled all documents (Invoice, BOL, Packing List, COO, etc.) into
one PDF file.

Flow:
    1. Save the uploaded bundle to disk.
    2. BundleSegmentationService detects document boundaries via Claude.
    3. Each segment is written to its own PDF file.
    4. DocumentProcessingService extracts fields from each segment.
    5. DocumentMerger aggregates duplicate types (e.g. two invoices).
    6. Existing validation workflow runs on the merged extracted_docs.
    7. Same response shape as validate_vendor_docs, plus bundle_segments.
"""

import asyncio
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from modules.validation_engine.normalization.normalizers.synonym_mapper import SynonymMapper
from shared.utils.logger import get_logger

router = APIRouter(prefix="/validation", tags=["bundle"])
logger = get_logger(__name__)

# Document types that the validation workflow can act on.
# Types outside this set (sanitary_certificate, coa, etc.) are extracted and
# stored but are not passed as primary/supporting docs to the workflow — the
# workflow doesn't yet have rules for them.
_WORKFLOW_DOC_TYPES = frozenset({
    "invoice",
    "packing_list",
    "bill_of_lading",
    "freight_manifest",
    "certificate_of_origin",
})


@router.post("/shipments/{shipment_id}/validate-bundle", tags=["bundle"])
async def validate_bundle(
    shipment_id: str,
    bundle_file: UploadFile = File(...),
):
    """
    Bundle PDF validation — Step 2 variant for multi-document bundles.

    Accepts a single PDF containing multiple document types (Invoice, BOL,
    Packing List, COO, Sanitary Certificate, COA, etc.) and runs the vendor
    document validation workflow.

    Multiple instances of the same document type (e.g. two invoices covering
    different product lines) are merged into a single aggregated document
    before the workflow runs, ensuring all line items are validated.
    """
    from src.api.config import get_api_settings
    from src.api.services.bundle_segmentation_service import (
        BundleSegmentationService,
        DocumentMerger,
        MergeIssue,
    )
    from src.api.services.document_processing_service import DocumentProcessingService
    from src.database.connection import get_session as get_db_session
    from src.database.models.api_document import APIDocument

    settings = get_api_settings()

    try:
        # ── 1. Save bundle to disk ────────────────────────────────────────────
        bundle_id = str(uuid4())
        bundle_content = await bundle_file.read()
        original_filename = bundle_file.filename or "bundle.pdf"

        upload_dir = Path(settings.UPLOAD_DIRECTORY) / bundle_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = upload_dir / f"{bundle_id}.pdf"
        bundle_path.write_bytes(bundle_content)

        logger.info(
            "Bundle upload saved: shipment=%s bundle_id=%s size=%d bytes",
            shipment_id, bundle_id, len(bundle_content),
        )

        # ── 2. Detect document boundaries ────────────────────────────────────
        segmentation_service = BundleSegmentationService(upload_dir=upload_dir)
        segments = await segmentation_service.segment(bundle_path)

        if not segments:
            raise HTTPException(
                status_code=422,
                detail="Bundle segmentation produced no segments — could not identify any document types in the uploaded PDF.",
            )

        # Drop segments Claude couldn't identify — no extractor is registered for "unknown"
        known_segments = [s for s in segments if s.document_type != "unknown"]
        unknown_count = len(segments) - len(known_segments)
        if unknown_count:
            logger.info(
                "Bundle: skipping %d unknown segment(s) for shipment %s",
                unknown_count, shipment_id,
            )
        segments = known_segments

        if not segments:
            raise HTTPException(
                status_code=422,
                detail="Bundle segmentation could not identify any known document types in the uploaded PDF.",
            )

        logger.info(
            "Bundle segmentation complete: %d segments detected for shipment %s",
            len(segments), shipment_id,
        )

        # ── 3. Extract each segment ───────────────────────────────────────────
        processing_service = DocumentProcessingService(use_database=False, use_ai_enhancement=False)

        async def _extract_segment(seg) -> Tuple[str, Any, Path]:
            result = await processing_service.process_document(
                file_path=seg.file_path,
                document_type=seg.document_type,
            )
            return seg.document_type, result, seg.file_path

        extraction_results = await asyncio.gather(
            *[_extract_segment(seg) for seg in segments]
        )

        from shared.utils.token_tracker import create_tracker, set_step, aggregate_token_usages
        extraction_token_usages = [r.get("token_usage") for _, r, _ in extraction_results]

        # ── 4. Normalise and group by document type ───────────────────────────
        synonym_mapper = SynonymMapper()

        # group: {doc_type: [extracted_dict, ...]}
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        raw_segment_meta: List[Dict[str, Any]] = []
        # first document_id saved per type — used as the field-review handle
        first_doc_id: Dict[str, str] = {}

        async with get_db_session() as db:
            for (doc_type, result, file_path), seg in zip(extraction_results, segments):
                if result.get("status") != "complete":
                    logger.warning(
                        "Extraction incomplete for segment %s: %s",
                        doc_type, result.get("metadata", {}).get("error", "unknown"),
                    )

                new_doc_id = str(uuid4())
                if doc_type not in first_doc_id:
                    first_doc_id[doc_type] = new_doc_id

                raw_fields = result.get("fields", {})
                items = result.get("items", [])

                normalized_fields = synonym_mapper.map_document_fields(
                    raw_fields, document_type=doc_type
                )
                extracted = {**normalized_fields, "items": items}

                grouped.setdefault(doc_type, []).append(extracted)

                raw_segment_meta.append({
                    "document_type": doc_type,
                    "pages": seg.pages,
                    "confidence": seg.confidence,
                    "source_filename": seg.source_filename,
                    "extraction_status": result.get("status", "unknown"),
                })

                doc_token_usage = result.get("token_usage")
                doc_meta = result.get("metadata", {}) or {}
                if doc_token_usage:
                    doc_meta["extraction_token_usage"] = doc_token_usage
                doc_meta["bundle_id"] = bundle_id
                doc_meta["bundle_pages"] = seg.pages
                doc_meta["bundle_confidence"] = seg.confidence

                api_doc = APIDocument(
                    document_id=new_doc_id,
                    document_type=doc_type,
                    shipment_id=shipment_id,
                    file_path=str(file_path),
                    filename=f"{original_filename}[{doc_type}:p{seg.pages[0]}-{seg.pages[-1]}]",
                    mime_type="application/pdf",
                    fields=normalized_fields,
                    items=items,
                    blocks=result.get("blocks", []),
                    extraction_status=result.get("status", "unknown"),
                    doc_metadata=doc_meta,
                )
                db.add(api_doc)

            await db.commit()

        # ── 5. Merge duplicate document types ─────────────────────────────────
        merger = DocumentMerger()
        extracted_docs: Dict[str, Dict[str, Any]] = {}
        merge_info: Dict[str, Any] = {}
        all_merge_issues: List[Any] = []

        # {doc_type: {document_id, fields, items}} — for the field review step
        extracted_documents_meta: Dict[str, Dict[str, Any]] = {}

        for doc_type, doc_list in grouped.items():
            merged, issues = merger.merge(doc_type, doc_list)
            extracted_docs[doc_type] = merged
            if issues:
                all_merge_issues.extend([i.model_dump() for i in issues])
                for issue in issues:
                    logger.warning(
                        "Bundle merge issue [%s] %s: %s",
                        issue.severity, doc_type, issue.message,
                    )
            if len(doc_list) > 1:
                merge_info[doc_type] = {
                    "merged_count": len(doc_list),
                    "merged_from": merged.get("merged_from", []),
                    "issues": [i.model_dump() for i in issues],
                }
            # Build field-review meta from the merged result
            merged_fields = {
                k: v for k, v in merged.items()
                if k not in ("items", "merged_from", "merge_count")
            }
            extracted_documents_meta[doc_type] = {
                "document_id": first_doc_id.get(doc_type, str(uuid4())),
                "fields": merged_fields,
                "items": merged.get("items", []),
            }

        # Guard: invoice is required
        if "invoice" not in extracted_docs:
            raise HTTPException(
                status_code=422,
                detail=(
                    "No invoice was detected in the bundle. "
                    "An invoice is required to run the validation workflow. "
                    f"Detected document types: {list(extracted_docs.keys())}"
                ),
            )

        # Separate workflow docs from ancillary docs (COA, sanitary cert, etc.)
        workflow_docs = {k: v for k, v in extracted_docs.items() if k in _WORKFLOW_DOC_TYPES}
        ancillary_docs = {k: v for k, v in extracted_docs.items() if k not in _WORKFLOW_DOC_TYPES}

        if ancillary_docs:
            logger.info(
                "Bundle ancillary docs (not passed to workflow): %s",
                list(ancillary_docs.keys()),
            )

        # ── 6. Run validation workflow ────────────────────────────────────────
        from modules.validation_engine.core.session_manager import get_session_manager
        from modules.validation_engine.orchestration import get_validation_workflow

        validation_tracker = create_tracker()
        set_step("validation_workflow")

        session_manager = get_session_manager()
        workflow = get_validation_workflow()

        context = await session_manager.create_session(
            use_case="vendor_document_validation",
            documents=workflow_docs,
            primary_document="invoice",
            supporting_documents=[dt for dt in workflow_docs if dt != "invoice"],
            shipment_id=shipment_id,
        )

        final_state = await workflow.run(
            session_id=context.session_id,
            documents=workflow_docs,
            config=context.config,
            primary_document="invoice",
            supporting_documents=context.supporting_documents,
        )

        shipment_token_usage = aggregate_token_usages(
            extraction_token_usages + [validation_tracker.get_summary()]
        )

        # ── 7. Persist token usage ────────────────────────────────────────────
        if shipment_token_usage:
            from sqlalchemy import select as sa_select
            from src.database.schema import ShipmentTokenUsage as ShipmentTokenUsageModel

            async with get_db_session() as db:
                token_row = ShipmentTokenUsageModel(
                    shipment_id=shipment_id,
                    validation_type="bundle_validation",
                    total_input_tokens=shipment_token_usage.get("total_input_tokens", 0),
                    total_output_tokens=shipment_token_usage.get("total_output_tokens", 0),
                    total_tokens=shipment_token_usage.get("total_tokens", 0),
                    estimated_cost_usd=shipment_token_usage.get("estimated_cost_usd", 0.0),
                    call_count=shipment_token_usage.get("call_count", 0),
                    documents_processed=len(segments),
                    by_model=shipment_token_usage.get("by_model", []),
                    breakdown=shipment_token_usage.get("breakdown", []),
                )
                db.add(token_row)
                await db.commit()

        # ── 8. Build response ─────────────────────────────────────────────────
        workflow_status = final_state.get("workflow_status")
        discrepancies = final_state.get("discrepancies", []) or []
        validation_results = final_state.get("validation_results", []) or []

        final_status = final_state.get("final_status") or ""
        if not final_status:
            if final_state.get("all_validations_passed"):
                final_status = "passed"
            elif discrepancies:
                final_status = "requires_attention"
            else:
                final_status = "passed"

        total = len(validation_results)
        passed = sum(1 for r in validation_results if r.get("passed"))
        summary = {
            "total_checks": total,
            "passed_checks": passed,
            "failed_checks": total - passed,
            "total_discrepancies": len(discrepancies),
            "documents_processed": list(workflow_docs.keys()),
            "ancillary_documents": list(ancillary_docs.keys()),
            "messages": final_state.get("messages", []),
        }

        base_response = {
            "session_id": str(context.session_id),
            "shipment_id": shipment_id,
            "final_status": final_status,
            "summary": summary,
            "discrepancies": discrepancies,
            "validation_results": validation_results,
            "token_usage": shipment_token_usage,
            "bundle_segments": raw_segment_meta,
            "merged_documents": merge_info,
            "merge_issues": all_merge_issues,
            "extracted_documents": extracted_documents_meta,
        }

        if str(workflow_status) in ("awaiting_user", "WorkflowStatus.AWAITING_USER"):
            return {**base_response, "workflow_status": "awaiting_user"}

        return {**base_response, "workflow_status": "completed"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Bundle validation failed for shipment %s: %s", shipment_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
