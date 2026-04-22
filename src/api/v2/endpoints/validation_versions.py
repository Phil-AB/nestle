"""Version control and revalidation endpoints."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException

from modules.validation_engine.version_control import (
    get_version_manager,
    get_revalidation_engine,
    get_delta_analyzer,
    RevalidationRequest,
)
from shared.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/validation", tags=["validation"])


@router.post("/sessions/{session_id}/revalidate")
async def create_revalidation(
    session_id: UUID,
    reason: str,
    updated_documents: Optional[Dict[str, Dict[str, Any]]] = None,
    tolerance_overrides: Optional[Dict[str, float]] = None,
    notes: Optional[str] = None,
    tags: Optional[List[str]] = None,
):
    """
    Create a new validation version (revalidation).

    Creates a new validation version based on an existing session,
    optionally with updated documents. Compares V1 vs V2 and provides
    delta analysis.
    """
    try:
        logger.info(f"Creating revalidation for session {session_id}")

        revalidation_engine = get_revalidation_engine()

        request = RevalidationRequest(
            original_session_id=session_id,
            revalidation_reason=reason,
            updated_documents=updated_documents,
            tolerance_overrides=tolerance_overrides,
            notes=notes,
            tags=tags or [],
        )

        result = await revalidation_engine.create_revalidation(request)

        return {
            "new_session_id": str(result.new_session_id),
            "new_version": result.new_version,
            "original_session_id": str(result.original_session_id),
            "original_version": result.original_version,
            "status": result.status,
            "workflow_status": result.workflow_status,
            "final_status": result.final_status,
            "comparison": result.comparison.dict() if result.comparison else None,
            "summary": {
                "total_discrepancies": result.total_discrepancies,
                "fixed": result.fixed_count,
                "new": result.new_count,
                "persistent": result.persistent_count,
            },
            "messages": result.messages,
        }

    except ValueError as e:
        logger.error(f"Revalidation failed: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Revalidation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/versions")
async def get_version_history(session_id: UUID):
    """Get version history for a session."""
    try:
        version_manager = get_version_manager()
        versions = await version_manager.get_version_history(session_id)
        return {
            "session_id": str(session_id),
            "total_versions": len(versions),
            "versions": [v.dict() for v in versions],
        }
    except Exception as e:
        logger.error(f"Failed to get version history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/versions/{version}")
async def get_version_summary(session_id: UUID, version: int):
    """Get detailed version summary."""
    try:
        version_manager = get_version_manager()
        summary = await version_manager.get_version_summary(session_id, version)
        if not summary:
            raise HTTPException(
                status_code=404,
                detail=f"Version {version} not found for session {session_id}",
            )
        return summary
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get version summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/versions/compare")
async def compare_versions(
    v1_session_id: UUID,
    v2_session_id: UUID,
):
    """
    Compare two validation versions.

    Performs delta analysis between two validation versions,
    identifying fixed, new, and persistent discrepancies.
    """
    try:
        logger.info(f"Comparing versions: {v1_session_id} vs {v2_session_id}")

        revalidation_engine = get_revalidation_engine()
        delta_analyzer = get_delta_analyzer()

        comparison = await revalidation_engine.compare_versions(
            v1_session_id, v2_session_id
        )
        summary = await delta_analyzer.get_change_summary(comparison)

        return {
            "comparison": comparison.dict(),
            "summary": summary,
        }

    except ValueError as e:
        logger.error(f"Version comparison failed: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Version comparison failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/revalidation-history")
async def get_revalidation_history(session_id: UUID):
    """Get revalidation history."""
    try:
        revalidation_engine = get_revalidation_engine()
        history = await revalidation_engine.get_revalidation_history(session_id)
        return {
            "session_id": str(session_id),
            "total_revalidations": len(history) - 1,
            "history": history,
        }
    except Exception as e:
        logger.error(f"Failed to get revalidation history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/revalidation-suggestion")
async def get_revalidation_suggestion(session_id: UUID):
    """
    Get revalidation suggestion.

    Analyzes session and suggests whether revalidation is recommended
    based on discrepancy severity and accuracy.
    """
    try:
        revalidation_engine = get_revalidation_engine()
        suggestion = await revalidation_engine.suggest_revalidation(session_id)
        return {
            "session_id": str(session_id),
            **suggestion,
        }
    except Exception as e:
        logger.error(f"Failed to get revalidation suggestion: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/lineage")
async def get_version_lineage(session_id: UUID, version: int):
    """Get version lineage (ancestry chain)."""
    try:
        version_manager = get_version_manager()
        lineage = await version_manager.get_lineage(session_id, version)
        return {
            "session_id": str(session_id),
            "version": version,
            "lineage_depth": len(lineage),
            "lineage": lineage,
        }
    except Exception as e:
        logger.error(f"Failed to get version lineage: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
