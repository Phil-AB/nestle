"""Pipeline endpoints — shipment-linked Step 2 and Step 6 workflows."""

import asyncio
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4, UUID

from fastapi import APIRouter, HTTPException, UploadFile, File
from sqlalchemy import select as sa_select, func as sa_func, distinct, desc

from modules.validation_engine.normalization.normalizers.synonym_mapper import SynonymMapper
from shared.utils.logger import get_logger

from .validation_models import (
    CreateShipmentRequest,
    DiscrepancyConfirmation,
    ResumeSessionRequest,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/validation", tags=["validation"])


def _tracked_task(coro, *, label: str) -> asyncio.Task:
    """Fire-and-forget task that logs an error if it fails instead of silently swallowing it."""
    task = asyncio.create_task(coro)

    def _on_done(t: asyncio.Task) -> None:
        if not t.cancelled() and t.exception() is not None:
            logger.error("Background task '%s' failed: %s", label, t.exception(), exc_info=t.exception())

    task.add_done_callback(_on_done)
    return task


async def _send_validation_alert(
    shipment_id: str,
    step: str,
    final_status: str,
    discrepancies: List[Dict[str, Any]],
    summary: Optional[Dict[str, Any]],
    shipment_number: Optional[str] = None,
) -> None:
    """Fire-and-forget wrapper so email errors never surface to the caller."""
    try:
        from modules.notification import get_email_service
        svc = get_email_service()
        await svc.send_validation_alert(
            shipment_id=shipment_id,
            step=step,
            final_status=final_status,
            discrepancies=discrepancies,
            summary=summary,
            shipment_number=shipment_number,
        )
    except Exception as exc:
        logger.warning(f"Email notification failed (non-critical): {exc}")


# ---------------------------------------------------------------------------
# Pipeline Dashboard Stats
# ---------------------------------------------------------------------------

@router.get("/pipeline/stats", tags=["pipeline"])
async def get_pipeline_stats():
    """
    Return aggregate statistics for the validation pipeline dashboard.

    Reads from the dedicated shipment_token_usage table:
    - Step 2 (vendor_validation): one row per vendor-doc validation run
    - Step 6 (boe_validation):    one row per BOE cross-verification run

    Each shipment can appear in the table twice — once per validation type —
    allowing the dashboard to show both step tokens individually and in total.
    """
    from src.database.connection import get_session as get_db_session
    from src.database.schema import ShipmentTokenUsage as ShipmentTokenUsageModel

    async with get_db_session() as db:
        step2_q = await db.execute(
            sa_select(sa_func.count(distinct(ShipmentTokenUsageModel.shipment_id))).where(
                ShipmentTokenUsageModel.validation_type == "vendor_validation",
                ShipmentTokenUsageModel.shipment_id.isnot(None),
            )
        )
        step2_count = step2_q.scalar() or 0

        step6_q = await db.execute(
            sa_select(sa_func.count(distinct(ShipmentTokenUsageModel.shipment_id))).where(
                ShipmentTokenUsageModel.validation_type == "boe_validation",
                ShipmentTokenUsageModel.shipment_id.isnot(None),
            )
        )
        step6_count = step6_q.scalar() or 0

        all_rows_q = await db.execute(
            sa_select(ShipmentTokenUsageModel).order_by(
                ShipmentTokenUsageModel.created_at.desc()
            )
        )
        all_rows = all_rows_q.scalars().all()

    shipments: list = []
    total_tokens = total_input_tokens = total_output_tokens = 0
    total_cost = 0.0
    total_calls = 0

    for row in all_rows:
        t_in = row.total_input_tokens or 0
        t_out = row.total_output_tokens or 0
        t_tot = row.total_tokens or 0
        t_cost = float(row.estimated_cost_usd or 0.0)
        t_calls = row.call_count or 0

        total_tokens += t_tot
        total_input_tokens += t_in
        total_output_tokens += t_out
        total_cost += t_cost
        total_calls += t_calls

        step = "step2" if row.validation_type == "vendor_validation" else "step6"
        shipments.append({
            "shipment_id": row.shipment_id or "unknown",
            "step": step,
            "validation_type": row.validation_type,
            "document_type": "invoice" if step == "step2" else "bill_of_entry",
            "documents_processed": row.documents_processed or 1,
            "total_tokens": t_tot,
            "input_tokens": t_in,
            "output_tokens": t_out,
            "estimated_cost_usd": round(t_cost, 6),
            "call_count": t_calls,
            "by_model": row.by_model or [],
            "created_at": row.created_at.isoformat() if row.created_at else None,
        })

    model_totals: dict = {}
    for s in shipments:
        for m in s.get("by_model", []):
            key = f"{m.get('provider','?')}/{m.get('model','?')}"
            if key not in model_totals:
                model_totals[key] = {
                    "provider": m.get("provider"),
                    "model": m.get("model"),
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "cost_usd": 0.0,
                    "calls": 0,
                }
            model_totals[key]["input_tokens"] += m.get("input_tokens", 0)
            model_totals[key]["output_tokens"] += m.get("output_tokens", 0)
            model_totals[key]["total_tokens"] += m.get("total_tokens", 0)
            model_totals[key]["cost_usd"] += m.get("cost_usd", 0.0)
            model_totals[key]["calls"] += m.get("calls", 0)

    return {
        "step2_shipments": step2_count,
        "step6_shipments": step6_count,
        "total_shipments_processed": step2_count + step6_count,
        "total_tokens": total_tokens,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_estimated_cost_usd": round(total_cost, 4),
        "total_llm_calls": total_calls,
        "by_model": list(model_totals.values()),
        "shipments": shipments,
    }


# ---------------------------------------------------------------------------
# Dashboard Overview Stats
# ---------------------------------------------------------------------------

@router.get("/dashboard/stats", tags=["dashboard"])
async def get_dashboard_stats():
    """
    Return aggregate statistics for the main dashboard overview.

    Draws from shipments, api_documents, validation_results and
    shipment_token_usage tables to provide a high-level processing summary.
    """
    from src.database.connection import get_session as get_db_session
    from src.database.schema import (
        Shipment as ShipmentModel,
        ShipmentTokenUsage as ShipmentTokenUsageModel,
    )
    from src.database.models.api_document import APIDocument as APIDocumentModel

    async with get_db_session() as db:
        ship_total_q = await db.execute(
            sa_select(sa_func.count(ShipmentModel.id))
        )
        total_shipments = ship_total_q.scalar() or 0

        ship_by_status_q = await db.execute(
            sa_select(ShipmentModel.status, sa_func.count(ShipmentModel.id))
            .group_by(ShipmentModel.status)
        )
        shipments_by_status = {row[0]: row[1] for row in ship_by_status_q}

        doc_total_q = await db.execute(
            sa_select(sa_func.count(APIDocumentModel.document_id))
        )
        total_documents = doc_total_q.scalar() or 0

        doc_by_type_q = await db.execute(
            sa_select(
                APIDocumentModel.document_type,
                sa_func.count(APIDocumentModel.document_id),
            ).group_by(APIDocumentModel.document_type)
        )
        documents_by_type = {}
        for row in doc_by_type_q:
            key = row[0] or "unknown"
            documents_by_type[key] = documents_by_type.get(key, 0) + row[1]

        doc_by_status_q = await db.execute(
            sa_select(
                APIDocumentModel.extraction_status,
                sa_func.count(APIDocumentModel.document_id),
            ).group_by(APIDocumentModel.extraction_status)
        )
        documents_by_status = {}
        for row in doc_by_status_q:
            key = row[0] or "unknown"
            documents_by_status[key] = documents_by_status.get(key, 0) + row[1]

        step2_q = await db.execute(
            sa_select(sa_func.count(distinct(ShipmentTokenUsageModel.shipment_id))).where(
                ShipmentTokenUsageModel.validation_type == "vendor_validation",
                ShipmentTokenUsageModel.shipment_id.isnot(None),
            )
        )
        step2_count = step2_q.scalar() or 0

        step6_q = await db.execute(
            sa_select(sa_func.count(distinct(ShipmentTokenUsageModel.shipment_id))).where(
                ShipmentTokenUsageModel.validation_type == "boe_validation",
                ShipmentTokenUsageModel.shipment_id.isnot(None),
            )
        )
        step6_count = step6_q.scalar() or 0

        recent_q = await db.execute(
            sa_select(ShipmentModel).order_by(desc(ShipmentModel.created_at)).limit(10)
        )
        recent_shipments = [
            {
                "id": str(s.id),
                "shipment_number": s.shipment_number,
                "status": s.status,
                "supplier_name": s.supplier_name,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in recent_q.scalars().all()
        ]

    return {
        "total_shipments": total_shipments,
        "shipments_by_status": shipments_by_status,
        "total_documents": total_documents,
        "documents_by_type": documents_by_type,
        "documents_by_status": documents_by_status,
        "pipeline": {
            "step2_validated": step2_count,
            "step6_validated": step6_count,
        },
        "recent_shipments": recent_shipments,
    }


# ---------------------------------------------------------------------------
# Shipment creation
# ---------------------------------------------------------------------------

@router.post("/shipments", tags=["pipeline"])
async def create_shipment(request: CreateShipmentRequest):
    """
    Create a Shipment record.

    Must be called before uploading vendor documents or a BOE.
    Returns a ``shipment_id`` that ties all documents and validation
    sessions together.
    """
    try:
        from src.database.connection import get_session as get_db_session
        from src.database.schema import Shipment
        from src.database.repositories.shipment_repository import ShipmentRepository

        resolved_number = request.shipment_number or f"PENDING-{uuid4()}"

        async with get_db_session() as db:
            repo = ShipmentRepository(db)
            existing = await repo.get_by_number(resolved_number)
            if existing:
                return {
                    "shipment_id": existing.id,
                    "shipment_number": existing.shipment_number,
                    "status": existing.status,
                    "message": "Shipment already exists",
                }

            shipment = Shipment(
                shipment_number=resolved_number,
                supplier_name=request.supplier_name,
                consignee_name=request.consignee_name,
                incoterm=request.incoterm,
                transport_mode=request.transport_mode,
                status="pending",
            )
            db.add(shipment)
            await db.commit()
            await db.refresh(shipment)

        logger.info(f"Created shipment {shipment.id} ({shipment.shipment_number})")
        return {
            "shipment_id": shipment.id,
            "shipment_number": shipment.shipment_number,
            "status": shipment.status,
            "message": "Shipment created",
        }

    except Exception as e:
        logger.error(f"Failed to create shipment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# List shipments
# ---------------------------------------------------------------------------

@router.get("/shipments", tags=["pipeline"])
async def list_shipments(limit: int = 50, offset: int = 0):
    """Return a list of shipments from the database, newest first."""
    try:
        from src.database.connection import get_session as get_db_session
        from src.database.schema import Shipment
        from src.database.models.api_document import APIDocument
        from sqlalchemy import select, func

        async with get_db_session() as db:
            result = await db.execute(
                select(Shipment)
                .order_by(desc(Shipment.created_at))
                .limit(limit)
                .offset(offset)
            )
            shipments = result.scalars().all()

            shipment_ids = [s.id for s in shipments]
            doc_counts: dict = {}
            if shipment_ids:
                count_result = await db.execute(
                    select(
                        APIDocument.shipment_id,
                        func.count(APIDocument.id).label("doc_count"),
                    )
                    .where(APIDocument.shipment_id.in_(shipment_ids))
                    .where(APIDocument.extraction_status == "complete")
                    .group_by(APIDocument.shipment_id)
                )
                for row in count_result:
                    doc_counts[row.shipment_id] = row.doc_count

        return {
            "shipments": [
                {
                    "shipment_id": s.id,
                    "shipment_number": s.shipment_number,
                    "supplier_name": s.supplier_name,
                    "consignee_name": s.consignee_name,
                    "incoterm": s.incoterm,
                    "transport_mode": s.transport_mode,
                    "status": s.status,
                    "vendor_docs_count": doc_counts.get(s.id, 0),
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in shipments
            ],
            "total": len(shipments),
        }

    except Exception as e:
        logger.error(f"Failed to list shipments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Shipment detail
# ---------------------------------------------------------------------------

@router.get("/shipments/{shipment_id}", tags=["pipeline"])
async def get_shipment(shipment_id: str):
    """Return full detail for a single shipment: metadata, documents, and token usage."""
    try:
        from src.database.connection import get_session as get_db_session
        from src.database.schema import Shipment, ShipmentTokenUsage as ShipmentTokenUsageModel
        from src.database.models.api_document import APIDocument
        from sqlalchemy import select

        async with get_db_session() as db:
            ship_q = await db.execute(select(Shipment).where(Shipment.id == shipment_id))
            shipment = ship_q.scalar_one_or_none()
            if not shipment:
                raise HTTPException(status_code=404, detail=f"Shipment {shipment_id} not found")

            docs_q = await db.execute(
                select(APIDocument)
                .where(APIDocument.shipment_id == shipment_id)
                .order_by(APIDocument.created_at)
            )
            docs = docs_q.scalars().all()

            token_q = await db.execute(
                select(ShipmentTokenUsageModel)
                .where(ShipmentTokenUsageModel.shipment_id == shipment_id)
                .order_by(ShipmentTokenUsageModel.created_at)
            )
            token_rows = token_q.scalars().all()

        documents = [
            {
                "document_id": d.document_id,
                "document_type": d.document_type,
                "document_name": d.document_name,
                "extraction_status": d.extraction_status,
                "extraction_confidence": d.extraction_confidence,
                "fields_count": d.fields_count or len(d.fields or {}),
                "items_count": d.items_count or len(d.items or []),
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ]

        token_usage = [
            {
                "validation_type": t.validation_type,
                "documents_processed": t.documents_processed,
                "total_tokens": t.total_tokens,
                "input_tokens": t.total_input_tokens,
                "output_tokens": t.total_output_tokens,
                "estimated_cost_usd": float(t.estimated_cost_usd or 0),
                "call_count": t.call_count,
                "by_model": t.by_model or [],
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in token_rows
        ]

        return {
            "shipment_id": shipment.id,
            "shipment_number": shipment.shipment_number,
            "boe_number": shipment.boe_number,
            "supplier_name": shipment.supplier_name,
            "consignee_name": shipment.consignee_name,
            "incoterm": shipment.incoterm,
            "transport_mode": shipment.transport_mode,
            "status": shipment.status,
            "created_at": shipment.created_at.isoformat() if shipment.created_at else None,
            "updated_at": shipment.updated_at.isoformat() if shipment.updated_at else None,
            "documents": documents,
            "token_usage": token_usage,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get shipment {shipment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Step 2: Vendor document validation
# ---------------------------------------------------------------------------

@router.post("/shipments/{shipment_id}/validate-vendor-docs", tags=["pipeline"])
async def validate_vendor_docs(
    shipment_id: str,
    invoice_file: UploadFile = File(...),
    packing_list_file: UploadFile = File(...),
    bill_of_lading_file: Optional[UploadFile] = File(None),
    freight_manifest_file: Optional[UploadFile] = File(None),
    certificate_of_origin_file: Optional[UploadFile] = File(None),
):
    """
    Step 2 — Vendor Document Pre-Validation.

    Accepts the invoice and packing list (required) plus optional freight
    manifest and certificate of origin.  Extracts all files, stores the
    resulting ``APIDocument`` records linked to the shipment, then runs the
    ``vendor_document_validation`` workflow.

    If critical or major discrepancies are found the response includes the
    discrepancies and a ``session_id`` for HITL review via the resume
    endpoint.  When everything passes, returns the final status directly.
    """
    from src.api.services.document_processing_service import DocumentProcessingService
    from src.database.connection import get_session as get_db_session
    from src.database.models.api_document import APIDocument

    try:
        processing_service = DocumentProcessingService(use_database=False, use_ai_enhancement=False)

        file_map: Dict[str, UploadFile] = {
            "invoice": invoice_file,
            "packing_list": packing_list_file,
        }
        if bill_of_lading_file:
            file_map["bill_of_lading"] = bill_of_lading_file
        if freight_manifest_file:
            file_map["freight_manifest"] = freight_manifest_file
        if certificate_of_origin_file:
            file_map["certificate_of_origin"] = certificate_of_origin_file

        from src.api.config import get_api_settings
        settings = get_api_settings()

        async def _extract_one(
            doc_id: str, doc_type: str, upload: UploadFile
        ) -> Tuple[str, Any, Path, str, str]:
            content = await upload.read()
            original_filename = upload.filename or f"{doc_type}.bin"
            suffix = Path(original_filename).suffix or ".bin"
            mime_type = upload.content_type or mimetypes.guess_type(original_filename)[0] or "application/octet-stream"

            upload_dir = Path(settings.UPLOAD_DIRECTORY) / doc_id
            upload_dir.mkdir(parents=True, exist_ok=True)
            permanent_path = upload_dir / f"{doc_id}{suffix}"
            permanent_path.write_bytes(content)

            result = await processing_service.process_document(
                file_path=permanent_path, document_type=doc_type
            )
            return doc_type, result, permanent_path, original_filename, mime_type

        extraction_results = await asyncio.gather(
            *[_extract_one(str(uuid4()), dt, f) for dt, f in file_map.items()]
        )

        from shared.utils.token_tracker import create_tracker, set_step, aggregate_token_usages
        extraction_token_usages = [r.get("token_usage") for _, r, *_ in extraction_results]

        synonym_mapper = SynonymMapper()

        extracted_docs: Dict[str, Dict[str, Any]] = {}
        extracted_documents_meta: Dict[str, Dict[str, Any]] = {}
        invoice_doc_id: Optional[str] = None

        async with get_db_session() as db:
            for doc_type, result, file_path, orig_filename, mime_type in extraction_results:
                if result.get("status") != "complete":
                    raise HTTPException(
                        status_code=422,
                        detail=f"Extraction failed for {doc_type}: "
                               f"{result.get('metadata', {}).get('error', 'unknown error')}",
                    )
                doc_id = file_path.parent.name  # reuse the uuid we generated
                raw_fields = result.get("fields", {})
                items = result.get("items", [])
                tables = result.get("raw_provider_response", {}).get("tables", [])

                normalized_fields = synonym_mapper.map_document_fields(
                    raw_fields, document_type=doc_type
                )

                extracted_docs[doc_type] = {**normalized_fields, "items": items}
                extracted_documents_meta[doc_type] = {
                    "document_id": doc_id,
                    "fields": normalized_fields,
                    "items": items,
                    "tables": tables,
                }
                if doc_type == "invoice":
                    invoice_doc_id = doc_id

                doc_meta = result.get("metadata", {}) or {}
                doc_token_usage = result.get("token_usage")
                if doc_token_usage:
                    doc_meta["extraction_token_usage"] = doc_token_usage
                api_doc = APIDocument(
                    document_id=doc_id,
                    document_type=doc_type,
                    shipment_id=shipment_id,
                    file_path=str(file_path),
                    filename=orig_filename,
                    mime_type=mime_type,
                    fields=normalized_fields,
                    items=items,
                    blocks=result.get("blocks", []),
                    extraction_status="complete",
                    doc_metadata=doc_meta,
                )
                db.add(api_doc)
            await db.commit()

        # Auto-derive shipment_number from BL number
        if "bill_of_lading" in extracted_docs:
            bol_fields = extracted_docs["bill_of_lading"]
            bl_number = bol_fields.get("bl_number") or bol_fields.get("bill_of_lading_number")
            if isinstance(bl_number, dict):
                bl_number = bl_number.get("value")
            if bl_number:
                from sqlalchemy.exc import IntegrityError
                from src.database.schema import Shipment
                async with get_db_session() as db:
                    stmt = sa_select(Shipment).where(Shipment.id == shipment_id)
                    row = await db.execute(stmt)
                    shipment = row.scalar_one_or_none()
                    if shipment and not shipment.boe_number:
                        shipment.shipment_number = str(bl_number)
                        try:
                            await db.commit()
                            logger.info(f"Updated shipment {shipment_id} number to BL: {bl_number}")
                        except IntegrityError:
                            await db.rollback()
                            logger.warning(
                                f"BL number {bl_number} already on another shipment — "
                                f"reassigning to shipment {shipment_id}"
                            )
                            old = await db.execute(
                                sa_select(Shipment).where(
                                    Shipment.shipment_number == str(bl_number),
                                    Shipment.id != shipment_id,
                                )
                            )
                            for prev in old.scalars().all():
                                prev.shipment_number = f"REASSIGNED-{prev.id}"
                            await db.commit()
                            stmt2 = sa_select(Shipment).where(Shipment.id == shipment_id)
                            shipment = (await db.execute(stmt2)).scalar_one()
                            shipment.shipment_number = str(bl_number)
                            await db.commit()

        # Run validation workflow
        from modules.validation_engine.core.session_manager import get_session_manager
        from modules.validation_engine.orchestration import get_validation_workflow

        validation_tracker = create_tracker()
        set_step("validation_workflow")

        session_manager = get_session_manager()
        workflow = get_validation_workflow()

        context = await session_manager.create_session(
            use_case="vendor_document_validation",
            documents=extracted_docs,
            primary_document="invoice",
            supporting_documents=[dt for dt in extracted_docs if dt != "invoice"],
            shipment_id=shipment_id,
        )

        final_state = await workflow.run(
            session_id=context.session_id,
            documents=extracted_docs,
            config=context.config,
            primary_document="invoice",
            supporting_documents=context.supporting_documents,
        )

        shipment_token_usage = aggregate_token_usages(
            extraction_token_usages + [validation_tracker.get_summary()]
        )

        # Persist token usage
        if invoice_doc_id and shipment_token_usage:
            from src.database.schema import ShipmentTokenUsage as ShipmentTokenUsageModel
            async with get_db_session() as db:
                result_row = await db.execute(
                    sa_select(APIDocument).where(APIDocument.document_id == invoice_doc_id)
                )
                inv_doc = result_row.scalar_one_or_none()
                if inv_doc:
                    merged = dict(inv_doc.doc_metadata or {})
                    merged["shipment_token_usage"] = shipment_token_usage
                    inv_doc.doc_metadata = merged

                token_row = ShipmentTokenUsageModel(
                    shipment_id=shipment_id,
                    validation_type="vendor_validation",
                    total_input_tokens=shipment_token_usage.get("total_input_tokens", 0),
                    total_output_tokens=shipment_token_usage.get("total_output_tokens", 0),
                    total_tokens=shipment_token_usage.get("total_tokens", 0),
                    estimated_cost_usd=shipment_token_usage.get("estimated_cost_usd", 0.0),
                    call_count=shipment_token_usage.get("call_count", 0),
                    documents_processed=len(file_map),
                    by_model=shipment_token_usage.get("by_model", []),
                    breakdown=shipment_token_usage.get("breakdown", []),
                )
                db.add(token_row)
                await db.commit()

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
            "documents_processed": list(extracted_docs.keys()),
            "messages": final_state.get("messages", []),
        }

        _tracked_task(
            _send_validation_alert(
                shipment_id=shipment_id,
                step="vendor_validation",
                final_status=final_status,
                discrepancies=discrepancies,
                summary=summary,
            ),
            label="send_validation_alert:vendor_validation",
        )

        if str(workflow_status) in ("awaiting_user", "WorkflowStatus.AWAITING_USER"):
            return {
                "session_id": str(context.session_id),
                "shipment_id": shipment_id,
                "workflow_status": "awaiting_user",
                "final_status": final_status,
                "summary": summary,
                "discrepancies": discrepancies,
                "validation_results": validation_results,
                "extracted_documents": extracted_documents_meta,
                "token_usage": shipment_token_usage,
            }

        return {
            "session_id": str(context.session_id),
            "shipment_id": shipment_id,
            "workflow_status": "completed",
            "final_status": final_status,
            "summary": summary,
            "discrepancies": discrepancies,
            "validation_results": validation_results,
            "extracted_documents": extracted_documents_meta,
            "token_usage": shipment_token_usage,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vendor doc validation failed for shipment {shipment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Step 6: BOE cross-verification
# ---------------------------------------------------------------------------

@router.post("/shipments/{shipment_id}/validate-boe", tags=["pipeline"])
async def validate_boe(
    shipment_id: str,
    boe_file: UploadFile = File(...),
):
    """
    Step 6 — BOE Cross-Verification.

    Accepts only the BOE file.  Retrieves the vendor documents that were
    stored during Step 2 from the database (no re-upload required).

    Validates the BOE against the stored invoice, packing list, and any
    other vendor documents that were uploaded at Step 2.
    """
    from src.api.services.document_processing_service import DocumentProcessingService
    from src.database.connection import get_session as get_db_session
    from src.database.repositories.api_document_repository import APIDocumentRepository
    from src.database.models.api_document import APIDocument

    try:
        processing_service = DocumentProcessingService(use_database=False, use_ai_enhancement=False)

        async with get_db_session() as db:
            repo = APIDocumentRepository(db)
            vendor_doc_types = ("invoice", "packing_list", "bill_of_lading", "freight_manifest", "certificate_of_origin")
            vendor_docs_raw, _ = await repo.list_documents(
                shipment_id=shipment_id,
                extraction_status="complete",
                limit=20,
            )

        vendor_docs = {
            d.document_type: {**d.fields, "items": d.items or []}
            for d in vendor_docs_raw
            if d.document_type in vendor_doc_types
        }

        if "invoice" not in vendor_docs:
            raise HTTPException(
                status_code=422,
                detail=f"Invoice not found for shipment {shipment_id}. Run Step 2 first.",
            )
        if "packing_list" not in vendor_docs:
            raise HTTPException(
                status_code=422,
                detail=f"Packing list not found for shipment {shipment_id}. Run Step 2 first.",
            )

        from shared.utils.token_tracker import create_tracker, set_step, aggregate_token_usages
        from src.api.config import get_api_settings
        settings = get_api_settings()

        boe_content = await boe_file.read()
        boe_doc_id = str(uuid4())
        boe_orig_filename = boe_file.filename or "bill_of_entry.pdf"
        boe_suffix = Path(boe_orig_filename).suffix or ".pdf"
        boe_mime = boe_file.content_type or mimetypes.guess_type(boe_orig_filename)[0] or "application/octet-stream"
        boe_upload_dir = Path(settings.UPLOAD_DIRECTORY) / boe_doc_id
        boe_upload_dir.mkdir(parents=True, exist_ok=True)
        boe_file_path = boe_upload_dir / f"{boe_doc_id}{boe_suffix}"
        boe_file_path.write_bytes(boe_content)

        boe_result = await processing_service.process_document(
            file_path=boe_file_path, document_type="bill_of_entry"
        )

        if boe_result.get("status") != "complete":
            raise HTTPException(
                status_code=422,
                detail=f"BOE extraction failed: "
                       f"{boe_result.get('metadata', {}).get('error', 'unknown error')}",
            )

        boe_extraction_token_usage = boe_result.get("token_usage")

        synonym_mapper = SynonymMapper()
        boe_raw_fields = boe_result.get("fields", {})
        boe_normalized_fields = synonym_mapper.map_document_fields(
            boe_raw_fields, document_type="bill_of_entry"
        )

        # Persist BOE document to DB
        boe_doc_meta = boe_result.get("metadata", {}) or {}
        if boe_extraction_token_usage:
            boe_doc_meta["extraction_token_usage"] = boe_extraction_token_usage
        async with get_db_session() as db:
            boe_api_doc = APIDocument(
                document_id=boe_doc_id,
                document_type="bill_of_entry",
                shipment_id=shipment_id,
                file_path=str(boe_file_path),
                filename=boe_orig_filename,
                mime_type=boe_mime,
                fields=boe_normalized_fields,
                items=boe_result.get("items", []),
                blocks=boe_result.get("blocks", []),
                extraction_status="complete",
                doc_metadata=boe_doc_meta,
            )
            db.add(boe_api_doc)
            await db.commit()

        # Store BOE declaration number — overwrite mode: reassign from any prior shipment
        decl_number = boe_normalized_fields.get("declaration_number")
        if isinstance(decl_number, dict):
            decl_number = decl_number.get("value")
        if decl_number:
            from src.database.schema import Shipment
            async with get_db_session() as db:
                decl_str = str(decl_number)

                # Release boe_number from any shipment that already holds it
                conflict_stmt = sa_select(Shipment).where(
                    Shipment.boe_number == decl_str,
                    Shipment.id != shipment_id,
                )
                for prev in (await db.execute(conflict_stmt)).scalars().all():
                    logger.warning(
                        f"Reassigning BOE {decl_str} from shipment {prev.id} to {shipment_id}"
                    )
                    if prev.shipment_number == decl_str:
                        prev.shipment_number = f"REASSIGNED-{prev.id}"
                    prev.boe_number = None

                # Release shipment_number if held elsewhere
                sn_conflict_stmt = sa_select(Shipment).where(
                    Shipment.shipment_number == decl_str,
                    Shipment.id != shipment_id,
                )
                for prev in (await db.execute(sn_conflict_stmt)).scalars().all():
                    prev.shipment_number = f"REASSIGNED-{prev.id}"

                # Flush the clears to DB first — PostgreSQL checks unique
                # constraints per-statement, so the nulls must land before
                # the new assignment or the constraint fires.
                await db.flush()

                # Now assign to current shipment
                stmt = sa_select(Shipment).where(Shipment.id == shipment_id)
                shipment = (await db.execute(stmt)).scalar_one_or_none()
                if shipment:
                    shipment.boe_number = decl_str
                    if not shipment.shipment_number or shipment.shipment_number.startswith("PENDING-"):
                        shipment.shipment_number = decl_str
                    await db.commit()
                    logger.info(f"Stored BOE declaration number {decl_str} for shipment {shipment_id}")

        documents = {
            **vendor_docs,
            "bill_of_entry": {
                **boe_normalized_fields,
                "items": boe_result.get("items", []),
            },
        }

        from modules.validation_engine.core.session_manager import get_session_manager
        from modules.validation_engine.orchestration import get_validation_workflow

        boe_validation_tracker = create_tracker()
        set_step("boe_validation_workflow")

        session_manager = get_session_manager()
        workflow = get_validation_workflow()

        context = await session_manager.create_session(
            use_case="boe_validation",
            documents=documents,
            primary_document="bill_of_entry",
            supporting_documents=[dt for dt in documents if dt != "bill_of_entry"],
            shipment_id=shipment_id,
        )

        final_state = await workflow.run(
            session_id=context.session_id,
            documents=documents,
            config=context.config,
            primary_document="bill_of_entry",
            supporting_documents=context.supporting_documents,
        )

        boe_token_usage = aggregate_token_usages(
            [boe_extraction_token_usage, boe_validation_tracker.get_summary()]
        )

        # Persist token usage
        if boe_token_usage:
            from src.database.schema import ShipmentTokenUsage as ShipmentTokenUsageModel
            async with get_db_session() as db:
                result_row = await db.execute(
                    sa_select(APIDocument).where(APIDocument.document_id == boe_doc_id)
                )
                boe_doc = result_row.scalar_one_or_none()
                if boe_doc:
                    merged = dict(boe_doc.doc_metadata or {})
                    merged["shipment_token_usage"] = boe_token_usage
                    boe_doc.doc_metadata = merged

                token_row = ShipmentTokenUsageModel(
                    shipment_id=shipment_id,
                    validation_type="boe_validation",
                    total_input_tokens=boe_token_usage.get("total_input_tokens", 0),
                    total_output_tokens=boe_token_usage.get("total_output_tokens", 0),
                    total_tokens=boe_token_usage.get("total_tokens", 0),
                    estimated_cost_usd=boe_token_usage.get("estimated_cost_usd", 0.0),
                    call_count=boe_token_usage.get("call_count", 0),
                    documents_processed=1,
                    by_model=boe_token_usage.get("by_model", []),
                    breakdown=boe_token_usage.get("breakdown", []),
                )
                db.add(token_row)
                await db.commit()

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
            "documents_processed": list(documents.keys()),
            "messages": final_state.get("messages", []),
        }

        needs_review = str(workflow_status) in (
            "awaiting_user", "WorkflowStatus.AWAITING_USER",
            "analyzing", "WorkflowStatus.ANALYZING",
        ) or bool(discrepancies)

        extracted_boe = {
            "document_id": boe_result.get("document_id", ""),
            "fields": boe_result.get("fields", {}),
            "items": boe_result.get("items", []),
            "blocks": boe_result.get("blocks", []),
        }

        _tracked_task(
            _send_validation_alert(
                shipment_id=shipment_id,
                step="boe_validation",
                final_status=final_status,
                discrepancies=discrepancies,
                summary=summary,
            ),
            label="send_validation_alert:boe_validation",
        )

        if needs_review and discrepancies:
            return {
                "session_id": str(context.session_id),
                "shipment_id": shipment_id,
                "workflow_status": "awaiting_user",
                "final_status": final_status,
                "summary": summary,
                "discrepancies": discrepancies,
                "validation_results": validation_results,
                "extracted_boe": extracted_boe,
                "token_usage": boe_token_usage,
            }

        return {
            "session_id": str(context.session_id),
            "shipment_id": shipment_id,
            "workflow_status": "completed",
            "final_status": final_status,
            "summary": summary,
            "discrepancies": discrepancies,
            "validation_results": validation_results,
            "extracted_boe": extracted_boe,
            "token_usage": boe_token_usage,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"BOE validation failed for shipment {shipment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# HITL Resume
# ---------------------------------------------------------------------------

@router.post("/sessions/{session_id}/resume", tags=["pipeline"])
async def resume_validation_session(
    session_id: UUID,
    request: ResumeSessionRequest,
):
    """
    Resume a validation session that is waiting for human input.

    Accepts the user's discrepancy confirmations and any missing field
    values, then continues the LangGraph workflow from the saved
    checkpoint.

    Works for both Step 2 (vendor_document_validation) and Step 6
    (boe_validation) sessions.
    """
    try:
        from modules.validation_engine.orchestration import get_validation_workflow

        workflow = get_validation_workflow()

        user_confirmations = {
            c.discrepancy_id: {"confirmed": c.confirmed, "comment": c.comment}
            for c in request.confirmations
        }

        final_state = await workflow.resume(
            session_id=session_id,
            user_confirmations=user_confirmations,
            user_input=request.user_input,
        )

        final_status = final_state.get("final_status")

        # Update Shipment.status to reflect the resolution:
        # - All discrepancies accepted → "validated" (shipment may proceed)
        # - Any discrepancy rejected  → "errors" (shipment is blocked)
        if request.shipment_id:
            try:
                from src.database.connection import get_session as get_db_session
                from src.database.schema import Shipment

                async with get_db_session() as db:
                    ship_row = await db.execute(
                        sa_select(Shipment).where(Shipment.id == request.shipment_id)
                    )
                    shipment = ship_row.scalar_one_or_none()
                    if shipment:
                        if final_status in ("passed", "requires_attention"):
                            shipment.status = "validated"
                        elif final_status == "failed":
                            shipment.status = "errors"
                        await db.commit()
            except Exception as e:
                logger.warning(f"Could not update shipment status after resume: {e}")

        return {
            "session_id": str(session_id),
            "workflow_status": str(final_state.get("workflow_status")),
            "final_status": final_status,
            "message": "Session resumed.",
            "messages": final_state.get("messages", []),
        }

    except Exception as e:
        logger.error(f"Session resume failed for {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
