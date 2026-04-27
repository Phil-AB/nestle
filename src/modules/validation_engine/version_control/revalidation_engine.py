"""Revalidation engine for creating new validation versions"""

from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4

from .version_models import (
    RevalidationRequest, RevalidationResult, VersionComparison
)
from .version_manager import get_version_manager
from .delta_analyzer import get_delta_analyzer
from ..core.base import ValidationContext
from ..core.session_manager import get_session_manager
from ..orchestration.workflows.validation_workflow import get_validation_workflow
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class RevalidationEngine:
    """
    Orchestrates validation revalidation

    Workflow:
    1. Load original session (V1)
    2. Create new session with updated documents (V2)
    3. Run validation workflow
    4. Compare V1 vs V2 using DeltaAnalyzer
    5. Generate revalidation report
    """

    def __init__(self):
        """Initialize revalidation engine"""
        self.version_manager = get_version_manager()
        self.delta_analyzer = get_delta_analyzer()
        self.session_manager = get_session_manager()

        logger.info("RevalidationEngine initialized")

    async def create_revalidation(
        self, request: RevalidationRequest
    ) -> RevalidationResult:
        """
        Create a new validation version (revalidation)

        Args:
            request: Revalidation request

        Returns:
            Revalidation result with comparison

        Raises:
            ValueError: If original session not found
        """
        logger.info(
            f"Creating revalidation for session {request.original_session_id}"
        )

        # Load original session (V1)
        original_context = self.session_manager.get_session(
            request.original_session_id
        )

        if original_context is None:
            raise ValueError(
                f"Original session not found: {request.original_session_id}"
            )

        original_version = original_context.version

        # Prepare documents for new validation
        documents = request.updated_documents or original_context.documents

        # Create new session (V2)
        new_session_id = uuid4()
        new_version = original_version + 1

        # Create new context with revalidation metadata
        new_context = ValidationContext(
            session_id=new_session_id,
            use_case=original_context.use_case,
            version=new_version,
            documents=documents,
            primary_document=original_context.primary_document,
            supporting_documents=original_context.supporting_documents,
            config=original_context.config,
            tolerance_overrides=(
                request.tolerance_overrides or
                original_context.tolerance_overrides
            ),
            is_revalidation=True,
            previous_version_id=request.original_session_id
        )

        # Store new session
        self.session_manager.create_session(new_context)

        logger.info(
            f"Created new session {new_session_id} as V{new_version} "
            f"(revalidation of {request.original_session_id})"
        )

        # Run validation workflow
        workflow = get_validation_workflow()

        try:
            final_state = await workflow.run(
                session_id=new_session_id,
                documents=documents,
                config=new_context.config,
                primary_document=new_context.primary_document,
                supporting_documents=new_context.supporting_documents,
                tolerance_overrides=new_context.tolerance_overrides,
                skip_steps=request.skip_steps
            )

            workflow_status = final_state.get("workflow_status", "completed")
            final_status = final_state.get("final_status")
            messages = final_state.get("messages", [])

        except Exception as e:
            logger.error(f"Revalidation workflow failed: {str(e)}")
            workflow_status = "failed"
            final_status = "error"
            messages = [f"Workflow error: {str(e)}"]

        # Get updated context after validation
        updated_context = self.session_manager.get_session(new_session_id)

        # Compare V1 vs V2
        comparison = None
        if updated_context:
            comparison = await self.delta_analyzer.compare(
                original_context, updated_context
            )

            # Create version metadata for new version
            await self.version_manager.create_version_metadata(
                updated_context,
                created_by=request.created_by,
                notes=(
                    request.notes or
                    f"Revalidation: {request.revalidation_reason}"
                ),
                tags=request.tags + ["revalidation"]
            )

            # Mark original version as superseded
            await self.version_manager.supersede_version(
                request.original_session_id, original_version
            )

        # Build result
        result = RevalidationResult(
            new_session_id=new_session_id,
            new_version=new_version,
            original_session_id=request.original_session_id,
            original_version=original_version,
            status="completed" if updated_context else "failed",
            workflow_status=workflow_status,
            final_status=final_status,
            comparison=comparison,
            total_discrepancies=(
                len(updated_context.discrepancies) if updated_context else 0
            ),
            fixed_count=comparison.fixed_count if comparison else 0,
            new_count=comparison.new_count if comparison else 0,
            persistent_count=comparison.persistent_count if comparison else 0,
            messages=messages
        )

        logger.info(
            f"Revalidation complete: V{new_version} created, "
            f"{result.fixed_count} fixed, {result.new_count} new, "
            f"{result.persistent_count} persistent"
        )

        return result

    async def compare_versions(
        self,
        v1_session_id: UUID,
        v2_session_id: UUID
    ) -> VersionComparison:
        """
        Compare two validation versions

        Args:
            v1_session_id: First version session ID
            v2_session_id: Second version session ID

        Returns:
            Version comparison

        Raises:
            ValueError: If sessions not found
        """
        # Load sessions
        v1_context = self.session_manager.get_session(v1_session_id)
        v2_context = self.session_manager.get_session(v2_session_id)

        if v1_context is None:
            raise ValueError(f"Session not found: {v1_session_id}")
        if v2_context is None:
            raise ValueError(f"Session not found: {v2_session_id}")

        # Compare
        comparison = await self.delta_analyzer.compare(v1_context, v2_context)

        return comparison

    async def get_revalidation_history(
        self, original_session_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Get revalidation history for a session

        Args:
            original_session_id: Original session UUID

        Returns:
            List of revalidations with summaries
        """
        # Get version history
        versions = await self.version_manager.get_version_history(
            original_session_id
        )

        history = []
        for i, version_meta in enumerate(versions):
            # Get comparison with previous version if available
            comparison_summary = None
            if i > 0:
                prev_meta = versions[i - 1]
                try:
                    comparison = await self.compare_versions(
                        prev_meta.session_id, version_meta.session_id
                    )
                    comparison_summary = {
                        "fixed": comparison.fixed_count,
                        "new": comparison.new_count,
                        "persistent": comparison.persistent_count,
                        "improvement_rate": comparison.improvement_rate
                    }
                except:
                    pass

            history.append({
                "session_id": str(version_meta.session_id),
                "version": version_meta.version,
                "status": version_meta.status,
                "final_status": version_meta.final_status,
                "accuracy_score": version_meta.accuracy_score,
                "total_discrepancies": version_meta.total_discrepancies,
                "comparison": comparison_summary,
                "created_at": version_meta.created_at.isoformat(),
                "notes": version_meta.notes
            })

        return history

    async def suggest_revalidation(
        self, session_id: UUID
    ) -> Dict[str, Any]:
        """
        Suggest whether revalidation is needed

        Args:
            session_id: Session UUID

        Returns:
            Suggestion with reasoning
        """
        context = self.session_manager.get_session(session_id)

        if context is None:
            return {
                "recommended": False,
                "reason": "Session not found"
            }

        # Get version metadata
        version_meta = await self.version_manager.get_version_metadata(
            session_id, context.version
        )

        if version_meta is None:
            return {
                "recommended": False,
                "reason": "Version metadata not found"
            }

        # Decision factors
        critical_count = version_meta.critical_count
        major_count = version_meta.major_count
        accuracy = version_meta.accuracy_score or 0

        reasons = []
        recommended = False

        # Critical discrepancies always require revalidation
        if critical_count > 0:
            recommended = True
            reasons.append(
                f"{critical_count} critical discrepancies require resolution"
            )

        # Multiple major discrepancies
        if major_count >= 3:
            recommended = True
            reasons.append(
                f"{major_count} major discrepancies should be addressed"
            )

        # Low accuracy
        if accuracy < 70:
            recommended = True
            reasons.append(
                f"Low accuracy ({accuracy}%) indicates significant issues"
            )

        # Auto-fixes that should be verified
        if version_meta.auto_fixed_count > 0:
            reasons.append(
                f"{version_meta.auto_fixed_count} auto-fixes "
                "should be verified"
            )

        # No issues - no need for revalidation
        if not recommended:
            if accuracy >= 95:
                reasons.append("High accuracy - no revalidation needed")
            elif version_meta.total_discrepancies == 0:
                reasons.append("No discrepancies detected")
            else:
                reasons.append("Issues are minor - revalidation optional")

        return {
            "recommended": recommended,
            "confidence": "high" if critical_count > 0 else "medium",
            "reasons": reasons,
            "metrics": {
                "accuracy": accuracy,
                "critical_discrepancies": critical_count,
                "major_discrepancies": major_count,
                "total_discrepancies": version_meta.total_discrepancies
            }
        }

    async def batch_revalidate(
        self, session_ids: List[UUID], reason: str
    ) -> List[RevalidationResult]:
        """
        Revalidate multiple sessions in batch

        Args:
            session_ids: List of session UUIDs
            reason: Revalidation reason

        Returns:
            List of revalidation results
        """
        results = []

        for session_id in session_ids:
            try:
                request = RevalidationRequest(
                    original_session_id=session_id,
                    revalidation_reason=reason,
                    tags=["batch_revalidation"]
                )

                result = await self.create_revalidation(request)
                results.append(result)

            except Exception as e:
                logger.error(
                    f"Batch revalidation failed for {session_id}: {str(e)}"
                )
                results.append(RevalidationResult(
                    new_session_id=uuid4(),
                    new_version=0,
                    original_session_id=session_id,
                    original_version=0,
                    status="failed",
                    workflow_status="error",
                    final_status="error",
                    messages=[f"Error: {str(e)}"]
                ))

        return results


# Singleton instance
_revalidation_engine_instance: Optional[RevalidationEngine] = None


def get_revalidation_engine() -> RevalidationEngine:
    """
    Get singleton revalidation engine instance

    Returns:
        RevalidationEngine instance
    """
    global _revalidation_engine_instance
    if _revalidation_engine_instance is None:
        _revalidation_engine_instance = RevalidationEngine()
    return _revalidation_engine_instance
