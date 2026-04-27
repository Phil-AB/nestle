"""LangGraph validation workflow builder"""

import os
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import UUID

from langgraph.graph import StateGraph, END
from ..state_definitions import (
    ValidationWorkflowState,
    WorkflowNode,
    WorkflowStatus,
    EdgeCondition
)
from ..nodes.validation_nodes import (
    initialize_node,
    normalize_node,
    validate_node,
    analyze_discrepancies_node,
    require_user_confirmation_node,
    generate_report_node
)
from ...core.session_manager import get_session_manager
from ...utils.constants import Severity
from shared.utils.logger import get_logger

logger = get_logger(__name__)


def _build_checkpointer():
    """
    Return an appropriate LangGraph checkpointer.

    Uses AsyncPostgresSaver when DATABASE_URL is configured so that workflow
    checkpoints survive server restarts and HITL resume works correctly.
    Falls back to MemorySaver for local development and tests.
    """
    db_url = os.getenv("DATABASE_URL") or os.getenv("DB_HOST")
    if db_url:
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            # Convert postgresql:// → postgresql+asyncpg:// for asyncpg driver
            conn_string = db_url
            if conn_string.startswith("postgresql://"):
                conn_string = conn_string.replace("postgresql://", "postgresql+asyncpg://", 1)
            checkpointer = AsyncPostgresSaver.from_conn_string(conn_string)
            logger.info("LangGraph checkpointer: AsyncPostgresSaver")
            return checkpointer
        except Exception as e:
            logger.warning(
                f"AsyncPostgresSaver unavailable ({e}), falling back to MemorySaver"
            )

    from langgraph.checkpoint.memory import MemorySaver
    logger.info("LangGraph checkpointer: MemorySaver (in-memory)")
    return MemorySaver()


class ValidationWorkflow:
    """
    LangGraph-based validation workflow

    Workflow:
    START → INITIALIZE → NORMALIZE → VALIDATE → ANALYZE → [conditional routing] → REPORT → END

    HITL: the graph interrupts *before* REQUIRE_USER_CONFIRMATION, surfaces the
    discrepancies to the caller, and waits for ``resume()`` to be called with the
    user's decisions before continuing.
    """

    def __init__(self):
        """Initialize validation workflow"""
        self.graph = self._build_graph()
        self._checkpointer = _build_checkpointer()
        self.app = self.graph.compile(
            checkpointer=self._checkpointer,
            interrupt_before=[WorkflowNode.REQUIRE_USER_CONFIRMATION],
        )

        logger.info("ValidationWorkflow initialized")

    def _build_graph(self) -> StateGraph:
        """
        Build LangGraph state graph

        Returns:
            Configured StateGraph
        """
        # Create graph
        graph = StateGraph(ValidationWorkflowState)

        # Add nodes
        graph.add_node(WorkflowNode.INITIALIZE, initialize_node)
        graph.add_node(WorkflowNode.NORMALIZE, normalize_node)
        graph.add_node(WorkflowNode.VALIDATE, validate_node)
        graph.add_node(WorkflowNode.ANALYZE_DISCREPANCIES, analyze_discrepancies_node)
        graph.add_node(WorkflowNode.REQUIRE_USER_CONFIRMATION, require_user_confirmation_node)
        graph.add_node(WorkflowNode.GENERATE_REPORT, generate_report_node)

        # Set entry point
        graph.set_entry_point(WorkflowNode.INITIALIZE)

        # Add edges (workflow flow)
        # INITIALIZE → NORMALIZE
        graph.add_edge(WorkflowNode.INITIALIZE, WorkflowNode.NORMALIZE)

        # NORMALIZE → VALIDATE
        graph.add_edge(WorkflowNode.NORMALIZE, WorkflowNode.VALIDATE)

        # VALIDATE → ANALYZE_DISCREPANCIES
        graph.add_edge(WorkflowNode.VALIDATE, WorkflowNode.ANALYZE_DISCREPANCIES)

        # ANALYZE_DISCREPANCIES → [conditional routing]
        graph.add_conditional_edges(
            WorkflowNode.ANALYZE_DISCREPANCIES,
            self._route_after_analysis,
            {
                EdgeCondition.NO_DISCREPANCIES: WorkflowNode.GENERATE_REPORT,
                EdgeCondition.REQUIRES_USER: WorkflowNode.REQUIRE_USER_CONFIRMATION,
                EdgeCondition.VALIDATION_PASSED: WorkflowNode.GENERATE_REPORT,
            }
        )

        # REQUIRE_USER_CONFIRMATION → GENERATE_REPORT (will pause here)
        graph.add_edge(WorkflowNode.REQUIRE_USER_CONFIRMATION, WorkflowNode.GENERATE_REPORT)

        # GENERATE_REPORT → END
        graph.add_edge(WorkflowNode.GENERATE_REPORT, END)

        logger.info("Workflow graph built with 6 nodes")

        return graph

    def _route_after_analysis(self, state: ValidationWorkflowState) -> str:
        """
        Conditional routing after discrepancy analysis

        Args:
            state: Current workflow state

        Returns:
            Next node name
        """
        discrepancies = state.get("discrepancies", [])

        # No discrepancies - go straight to report
        if not discrepancies:
            logger.info("No discrepancies found, proceeding to report")
            return EdgeCondition.NO_DISCREPANCIES

        # Any discrepancy requires review — all failures carry equal weight
        logger.info(f"Found {len(discrepancies)} discrepancies, routing to review")
        return EdgeCondition.REQUIRES_USER

    async def run(
        self,
        session_id: UUID,
        documents: Dict[str, Dict[str, Any]],
        config: Dict[str, Any],
        **kwargs
    ) -> ValidationWorkflowState:
        """
        Run validation workflow

        Args:
            session_id: Validation session ID
            documents: Documents to validate
            config: Use case configuration
            **kwargs: Additional state parameters

        Returns:
            Final workflow state
        """
        logger.info(f"Starting validation workflow for session {session_id}")

        # Build initial state
        initial_state: ValidationWorkflowState = {
            "session_id": str(session_id),
            "use_case": config.get("use_case", {}).get("name", "unknown"),
            "version": kwargs.get("version", 1),
            "documents": documents,
            "primary_document": kwargs.get("primary_document", ""),
            "supporting_documents": kwargs.get("supporting_documents", []),
            "config": config,
            "tolerance_overrides": kwargs.get("tolerance_overrides", {}),
            "current_step": "start",
            "completed_steps": [],
            "failed_steps": [],
            "normalized": False,
            "normalized_documents": {},
            "normalization_errors": [],
            "validation_results": [],
            "all_validations_passed": False,
            "discrepancies": [],
            "critical_discrepancies": [],
            "auto_fixed_count": 0,
            "requires_user_confirmation": False,
            "user_confirmed": False,
            "user_confirmations": {},
            "user_input": {},
            "awaiting_user": False,
            "is_revalidation": kwargs.get("is_revalidation", False),
            "previous_version_id": kwargs.get("previous_version_id"),
            "changes_detected": [],
            "workflow_status": WorkflowStatus.INITIALIZING,
            "final_status": "",
            "error": None,
            "retry_count": 0,
            "max_retries": 3,
            "messages": [],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        # Thread config links this invocation to its LangGraph checkpoint.
        thread_config = {"configurable": {"thread_id": str(session_id)}}

        try:
            # Run workflow — will pause *before* REQUIRE_USER_CONFIRMATION if needed
            final_state = await self.app.ainvoke(initial_state, config=thread_config)

            logger.info(
                f"Workflow completed for session {session_id}. "
                f"Status: {final_state.get('workflow_status')}"
            )

            return final_state

        except Exception as e:
            logger.error(f"Workflow execution failed: {str(e)}")
            initial_state["workflow_status"] = WorkflowStatus.FAILED
            initial_state["error"] = str(e)
            initial_state["final_status"] = "failed"
            return initial_state

    async def resume(
        self,
        session_id: UUID,
        user_confirmations: Optional[Dict[str, Any]] = None,
        user_input: Optional[Dict[str, Any]] = None,
    ) -> ValidationWorkflowState:
        """
        Resume a paused workflow after human review.

        Records user decisions in the session manager, updates the LangGraph
        checkpoint with the resolved state, then continues from the saved
        checkpoint (no re-processing of earlier nodes).

        Args:
            session_id: Validation session ID
            user_confirmations: Mapping of discrepancy_id → {confirmed: bool, ...}
            user_input: Optional user-supplied field values for missing data

        Returns:
            Final workflow state
        """
        logger.info(f"Resuming workflow for session {session_id}")

        thread_config = {"configurable": {"thread_id": str(session_id)}}
        session_manager = get_session_manager()

        # Persist confirmations in the session store
        if user_confirmations:
            for disc_id, conf in user_confirmations.items():
                confirmed = conf if isinstance(conf, bool) else conf.get("confirmed", False)
                comment = conf.get("comment") if isinstance(conf, dict) else None
                await session_manager.add_user_confirmation(
                    session_id=session_id,
                    discrepancy_id=disc_id,
                    confirmed=confirmed,
                    comment=comment,
                )

        if user_input:
            for field_name, value in user_input.items():
                await session_manager.add_user_data(
                    session_id=session_id,
                    field_name=field_name,
                    value=value,
                )

        # Push updated confirmation data into the LangGraph checkpoint so that
        # generate_report_node can compute the correct final_status.
        confirmation_payload: Dict[str, Any] = {}
        if user_confirmations:
            confirmation_payload["user_confirmations"] = {
                disc_id: (
                    {"confirmed": conf, "comment": None}
                    if isinstance(conf, bool)
                    else conf
                )
                for disc_id, conf in user_confirmations.items()
            }
            confirmation_payload["user_confirmed"] = True
            confirmation_payload["awaiting_user"] = False

        if confirmation_payload:
            try:
                await self.app.aupdate_state(thread_config, values=confirmation_payload)
            except Exception as e:
                logger.warning(f"aupdate_state failed (continuing anyway): {e}")

        try:
            # Continue from checkpoint — pass None as input so LangGraph uses
            # the saved state rather than starting a new invocation.
            final_state = await self.app.ainvoke(None, config=thread_config)

            logger.info(
                f"Workflow resumed and completed for session {session_id}. "
                f"Status: {final_state.get('workflow_status')}"
            )

            return final_state

        except Exception as e:
            logger.error(f"Workflow resume failed for session {session_id}: {e}")
            return {
                "session_id": str(session_id),
                "workflow_status": WorkflowStatus.FAILED,
                "error": str(e),
                "messages": [f"Resume failed: {e}"],
                "updated_at": datetime.utcnow().isoformat(),
            }


# Singleton instance
_validation_workflow_instance: Optional[ValidationWorkflow] = None


def get_validation_workflow() -> ValidationWorkflow:
    """
    Get singleton validation workflow instance

    Returns:
        ValidationWorkflow instance
    """
    global _validation_workflow_instance
    if _validation_workflow_instance is None:
        _validation_workflow_instance = ValidationWorkflow()
    return _validation_workflow_instance
