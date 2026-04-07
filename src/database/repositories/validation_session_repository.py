"""
Repository for ValidationSession CRUD operations.

Provides database persistence for validation engine sessions so that
in-progress workflows survive server restarts.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from src.database.schema import ValidationSession
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class ValidationSessionRepository:
    """
    Repository for ValidationSession model operations.

    All mutations commit immediately so that the in-memory LRU cache and
    the database stay in sync after every state change.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session
        """
        self.session = session

    async def create(
        self,
        session_id: str,
        use_case: str,
        version: int,
        context_data: Dict[str, Any],
        shipment_id: Optional[str] = None,
        workflow_status: str = "created",
    ) -> ValidationSession:
        """
        Create a new validation session record.

        Args:
            session_id: UUID string for the session (matches ValidationContext.session_id)
            use_case: Use case name (e.g. "vendor_document_validation")
            version: Use case version
            context_data: Serialised ValidationContext dict
            shipment_id: Optional shipment UUID to link this session
            workflow_status: Initial workflow status

        Returns:
            Created ValidationSession instance
        """
        record = ValidationSession(
            id=session_id,
            use_case=use_case,
            version=version,
            workflow_status=workflow_status,
            context_data=context_data,
            shipment_id=shipment_id,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        logger.info(f"Created validation session: {session_id} (use_case={use_case})")
        return record

    async def get_by_id(self, session_id: str) -> Optional[ValidationSession]:
        """
        Get validation session by primary key.

        Args:
            session_id: UUID string

        Returns:
            ValidationSession if found, None otherwise
        """
        return await self.session.get(ValidationSession, session_id)

    async def update_context(
        self,
        session_id: str,
        context_data: Dict[str, Any],
        workflow_status: str,
    ) -> Optional[ValidationSession]:
        """
        Update context data and workflow status for an existing session.

        Args:
            session_id: UUID string
            context_data: Updated serialised ValidationContext dict
            workflow_status: New workflow status

        Returns:
            Updated ValidationSession, or None if not found
        """
        record = await self.session.get(ValidationSession, session_id)
        if record is None:
            logger.warning(f"Session {session_id} not found for update")
            return None

        record.context_data = context_data
        record.workflow_status = workflow_status
        record.updated_at = datetime.utcnow()
        await self.session.commit()
        await self.session.refresh(record)
        logger.debug(f"Updated session {session_id} → status={workflow_status}")
        return record

    async def get_pending_user_confirmation(
        self, limit: int = 50
    ) -> List[ValidationSession]:
        """
        Return sessions that are currently waiting for human review.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of sessions with workflow_status = "awaiting_user"
        """
        query = (
            select(ValidationSession)
            .where(ValidationSession.workflow_status == "awaiting_user")
            .order_by(ValidationSession.updated_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_shipment(self, shipment_id: str) -> List[ValidationSession]:
        """
        Return all sessions linked to a shipment, newest first.

        Args:
            shipment_id: Shipment UUID string

        Returns:
            List of ValidationSession records
        """
        query = (
            select(ValidationSession)
            .where(ValidationSession.shipment_id == shipment_id)
            .order_by(ValidationSession.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
