"""Session manager for validation engine"""

import os
from collections import OrderedDict
from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4
from datetime import datetime

from .base import ValidationContext, ValidationResult, Discrepancy, ValidationResultSummary
from .config_loader import get_config_loader
from ..utils.constants import (
    ValidationStatus, SessionType, FinalStatus, Severity, ResolutionStatus
)
from ..utils.exceptions import SessionNotFoundException
from shared.utils.logger import get_logger

logger = get_logger(__name__)

# Maximum number of sessions held in the in-process LRU cache.
_LRU_MAX_SIZE = 100


class SessionManager:
    """
    Manage validation session lifecycle with LRU cache + DB write-through.

    The in-memory OrderedDict acts as an LRU cache (max 100 entries).
    Every mutation is also written to the ``validation_sessions`` table so
    that sessions survive server restarts.  On a cache miss, ``get_session``
    falls back to the database.

    DB integration is opt-in: if the database is not configured the manager
    works in-memory-only mode (backward-compatible with tests / local dev).
    """

    def __init__(self):
        """Initialize session manager"""
        self.config_loader = get_config_loader()
        # Ordered dict used as an LRU cache; most-recently-used at the end.
        self._sessions: OrderedDict[UUID, ValidationContext] = OrderedDict()
        self._db_enabled = bool(os.getenv("DATABASE_URL") or os.getenv("DB_HOST"))
        logger.info(
            f"SessionManager initialized (db_persistence={'enabled' if self._db_enabled else 'disabled'})"
        )

    # ------------------------------------------------------------------
    # Internal LRU helpers
    # ------------------------------------------------------------------

    def _cache_put(self, session_id: UUID, context: ValidationContext) -> None:
        """Insert / update cache entry and evict LRU entry if over capacity."""
        if session_id in self._sessions:
            self._sessions.move_to_end(session_id)
        self._sessions[session_id] = context
        while len(self._sessions) > _LRU_MAX_SIZE:
            self._sessions.popitem(last=False)  # evict least-recently used

    def _cache_get(self, session_id: UUID) -> Optional[ValidationContext]:
        """Return cached context (promoting to MRU), or None if absent."""
        if session_id not in self._sessions:
            return None
        self._sessions.move_to_end(session_id)
        return self._sessions[session_id]

    # ------------------------------------------------------------------
    # DB helpers (no-ops when db is unavailable)
    # ------------------------------------------------------------------

    async def _db_create(
        self,
        context: ValidationContext,
        shipment_id: Optional[str] = None,
        workflow_status: str = "created",
    ) -> None:
        if not self._db_enabled:
            return
        try:
            from src.database.connection import get_session as get_db_session
            from src.database.repositories.validation_session_repository import (
                ValidationSessionRepository,
            )
            async with get_db_session() as db:
                repo = ValidationSessionRepository(db)
                await repo.create(
                    session_id=str(context.session_id),
                    use_case=context.use_case,
                    version=context.version,
                    context_data=context.dict(),
                    shipment_id=shipment_id,
                    workflow_status=workflow_status,
                )
        except Exception as e:
            logger.warning(f"DB create for session {context.session_id} failed (in-memory only): {e}")

    async def _db_update(
        self,
        context: ValidationContext,
        workflow_status: str = "running",
    ) -> None:
        if not self._db_enabled:
            return
        try:
            from src.database.connection import get_session as get_db_session
            from src.database.repositories.validation_session_repository import (
                ValidationSessionRepository,
            )
            async with get_db_session() as db:
                repo = ValidationSessionRepository(db)
                await repo.update_context(
                    session_id=str(context.session_id),
                    context_data=context.dict(),
                    workflow_status=workflow_status,
                )
        except Exception as e:
            logger.warning(f"DB update for session {context.session_id} failed (in-memory only): {e}")

    async def _db_load(self, session_id: UUID) -> Optional[ValidationContext]:
        """Load a session from the database on cache miss."""
        if not self._db_enabled:
            return None
        try:
            from src.database.connection import get_session as get_db_session
            from src.database.repositories.validation_session_repository import (
                ValidationSessionRepository,
            )
            async with get_db_session() as db:
                repo = ValidationSessionRepository(db)
                record = await repo.get_by_id(str(session_id))
                if record is None:
                    return None
                context = ValidationContext(**record.context_data)
                self._cache_put(session_id, context)
                logger.info(f"Loaded session {session_id} from DB (cache miss)")
                return context
        except Exception as e:
            logger.warning(f"DB load for session {session_id} failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_session(
        self,
        use_case: str,
        documents: Dict[str, Dict[str, Any]],
        primary_document: str,
        supporting_documents: List[str],
        tolerance_overrides: Optional[Dict[str, float]] = None,
        is_revalidation: bool = False,
        previous_version_id: Optional[UUID] = None,
        user_provided_data: Optional[Dict[str, Any]] = None,
        shipment_id: Optional[str] = None,
    ) -> ValidationContext:
        """
        Create a new validation session.

        Args:
            use_case: Use case name (e.g., "boe_validation")
            documents: Extracted document data {doc_type: data}
            primary_document: Primary document type
            supporting_documents: List of supporting document types
            tolerance_overrides: Per-session tolerance overrides
            is_revalidation: Whether this is a revalidation
            previous_version_id: Previous version ID (for revalidation)
            user_provided_data: User-provided data for missing fields
            shipment_id: Optional shipment UUID to link this session

        Returns:
            ValidationContext for the session

        Raises:
            UseCaseNotFoundException: If use case not found
            ValidationConfigException: If config is invalid
        """
        # Load use case config
        config = self.config_loader.load_use_case(use_case)

        # Generate session ID
        session_id = uuid4()

        # Determine version number
        version = 1
        if is_revalidation and previous_version_id:
            previous_context = await self.get_session(previous_version_id)
            version = previous_context.version + 1

        # Create context
        context = ValidationContext(
            session_id=session_id,
            use_case=use_case,
            version=version,
            documents=documents,
            primary_document=primary_document,
            supporting_documents=supporting_documents,
            config=config,
            tolerance_overrides=tolerance_overrides or {},
            current_step="initialize",
            is_revalidation=is_revalidation,
            previous_version_id=previous_version_id,
            user_provided_data=user_provided_data or {},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self._cache_put(session_id, context)
        await self._db_create(context, shipment_id=shipment_id, workflow_status="created")

        logger.info(
            f"Created validation session {session_id} for use case '{use_case}' "
            f"(version {version}, revalidation: {is_revalidation})"
        )

        return context

    async def get_session(self, session_id: UUID) -> ValidationContext:
        """
        Get validation session by ID (cache → DB fallback).

        Args:
            session_id: Session UUID

        Returns:
            ValidationContext

        Raises:
            SessionNotFoundException: If session not found in cache or DB
        """
        context = self._cache_get(session_id)
        if context is not None:
            return context

        # Cache miss — try database
        context = await self._db_load(session_id)
        if context is not None:
            return context

        raise SessionNotFoundException(f"Session {session_id} not found")

    async def update_session(
        self,
        context: ValidationContext,
        workflow_status: str = "running",
    ) -> None:
        """
        Persist updated session state to cache and database.

        Args:
            context: Updated validation context
            workflow_status: Current workflow status for DB index
        """
        context.updated_at = datetime.utcnow()
        self._cache_put(context.session_id, context)
        await self._db_update(context, workflow_status=workflow_status)
        logger.debug(f"Updated session {context.session_id}")

    async def update_step(self, session_id: UUID, step: str) -> None:
        """Update current workflow step."""
        context = await self.get_session(session_id)
        context.current_step = step
        await self.update_session(context)
        logger.info(f"Session {session_id} moved to step: {step}")

    async def add_validation_results(
        self,
        session_id: UUID,
        results: List[ValidationResult],
    ) -> None:
        """Add validation results to session."""
        context = await self.get_session(session_id)
        context.validation_results.extend(results)
        await self.update_session(context)
        logger.debug(f"Added {len(results)} validation results to session {session_id}")

    async def add_discrepancies(
        self,
        session_id: UUID,
        discrepancies: List[Discrepancy],
    ) -> None:
        """Add discrepancies to session."""
        context = await self.get_session(session_id)
        context.discrepancies.extend(discrepancies)
        await self.update_session(context)
        logger.info(f"Added {len(discrepancies)} discrepancies to session {session_id}")

    async def add_user_confirmation(
        self,
        session_id: UUID,
        discrepancy_id: str,
        confirmed: bool,
        comment: Optional[str] = None,
    ) -> None:
        """Record a user confirmation for a discrepancy."""
        context = await self.get_session(session_id)

        for discrepancy in context.discrepancies:
            if str(discrepancy.id) == discrepancy_id:
                discrepancy.user_confirmed = confirmed
                discrepancy.user_comment = comment
                discrepancy.resolution_status = (
                    ResolutionStatus.ACCEPTED if confirmed else ResolutionStatus.REJECTED
                )
                break

        context.user_confirmations[discrepancy_id] = {
            "confirmed": confirmed,
            "comment": comment,
        }

        await self.update_session(context, workflow_status="running")
        logger.info(
            f"User {'confirmed' if confirmed else 'rejected'} "
            f"discrepancy {discrepancy_id} in session {session_id}"
        )

    async def add_user_data(
        self,
        session_id: UUID,
        field_name: str,
        value: Any,
    ) -> None:
        """Add user-provided data for a missing field."""
        context = await self.get_session(session_id)
        context.user_provided_data[field_name] = value
        await self.update_session(context)
        logger.info(f"Added user data for field '{field_name}' in session {session_id}")

    async def get_summary(self, session_id: UUID) -> ValidationResultSummary:
        """Return a ValidationResultSummary for the session."""
        context = await self.get_session(session_id)

        total_validations = len(context.validation_results)
        passed_validations = sum(1 for r in context.validation_results if r.passed)
        failed_validations = total_validations - passed_validations

        total_discrepancies = len(context.discrepancies)
        error_count = sum(1 for d in context.discrepancies if d.severity == Severity.ERROR)
        info_count = sum(1 for d in context.discrepancies if d.severity == Severity.INFO)

        auto_fixed = sum(1 for d in context.discrepancies if d.auto_fixed)

        avg_confidence = 0.0
        if context.validation_results:
            avg_confidence = (
                sum(r.confidence for r in context.validation_results)
                / len(context.validation_results)
            )

        return ValidationResultSummary(
            total_validations=total_validations,
            passed_validations=passed_validations,
            failed_validations=failed_validations,
            total_discrepancies=total_discrepancies,
            error_discrepancies=error_count,
            info_discrepancies=info_count,
            auto_fixed_count=auto_fixed,
            all_validations_passed=failed_validations == 0,
            average_confidence=avg_confidence,
        )

    async def list_sessions(
        self,
        use_case: Optional[str] = None,
        is_revalidation: Optional[bool] = None,
    ) -> List[UUID]:
        """List cached session IDs with optional filtering."""
        sessions = []
        for session_id, context in self._sessions.items():
            if use_case and context.use_case != use_case:
                continue
            if is_revalidation is not None and context.is_revalidation != is_revalidation:
                continue
            sessions.append(session_id)
        return sessions

    async def get_version_chain(self, session_id: UUID) -> List[UUID]:
        """Return the version chain for a session (V1 → V2 → V3 …)."""
        context = await self.get_session(session_id)
        chain = [session_id]
        current_id = context.previous_version_id

        while current_id:
            chain.insert(0, current_id)
            try:
                prev_context = await self.get_session(current_id)
                current_id = prev_context.previous_version_id
            except SessionNotFoundException:
                break

        return chain

    async def delete_session(self, session_id: UUID) -> None:
        """Remove session from the cache (DB record is kept for audit)."""
        if session_id not in self._sessions:
            raise SessionNotFoundException(f"Session {session_id} not found")
        del self._sessions[session_id]
        logger.info(f"Evicted session {session_id} from cache")

    def clear_all_sessions(self) -> None:
        """Clear all sessions from the cache (useful for testing)."""
        self._sessions.clear()
        logger.info("Cleared all sessions from cache")


# Singleton instance
_session_manager_instance: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get singleton session manager instance."""
    global _session_manager_instance
    if _session_manager_instance is None:
        _session_manager_instance = SessionManager()
    return _session_manager_instance
