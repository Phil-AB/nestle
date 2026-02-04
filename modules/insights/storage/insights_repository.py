"""
Insights Repository.

Provides storage operations for insights data using dynamic tables.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine

from shared.database.schema_manager import SchemaManager
from shared.database.universal_repository import UniversalRepository
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class InsightsRepository:
    """
    Repository for insights data storage.

    Automatically creates and manages use-case-specific tables.
    Uses dynamic schema from config.

    Example:
        >>> repo = InsightsRepository(engine, session, "forms-capital-loan")
        >>> await repo.initialize()
        >>> await repo.save_insights("doc_123", insights_data)
        >>> insights = await repo.get_by_document_id("doc_123")
    """

    def __init__(
        self,
        engine: AsyncEngine,
        session: AsyncSession,
        use_case_id: str
    ):
        """
        Initialize insights repository.

        Args:
            engine: Async SQLAlchemy engine
            session: Async SQLAlchemy session
            use_case_id: Use case identifier
        """
        self.engine = engine
        self.session = session
        self.use_case_id = use_case_id
        self.schema_manager = SchemaManager(engine)
        self.table = None
        self.repository = None

    async def initialize(self):
        """
        Initialize repository by ensuring table exists.

        Must be called before using repository operations.
        """
        logger.info(f"Initializing insights repository for use case: {self.use_case_id}")

        # Ensure table exists (creates if necessary)
        self.table = await self.schema_manager.ensure_table_exists(
            "insights",
            self.use_case_id
        )

        # Create universal repository for this table
        self.repository = UniversalRepository(self.session, self.table)

        logger.info(f"Insights repository initialized with table: {self.table.name}")

    async def save_insights(
        self,
        document_id: str,
        insights_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Save insights for a document.

        Args:
            document_id: Document identifier
            insights_data: Insights data dictionary

        Returns:
            Saved insights record
        """
        # Check if insights already exist
        existing = await self.get_by_document_id(document_id)

        if existing:
            # Update existing
            logger.info(f"Updating insights for document: {document_id}")
            return await self.repository.update_one(
                {"document_id": document_id},
                insights_data
            )
        else:
            # Create new
            logger.info(f"Creating insights for document: {document_id}")
            insights_data["document_id"] = document_id
            insights_data["use_case_id"] = self.use_case_id
            return await self.repository.create(insights_data)

    async def get_by_document_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get insights by document ID."""
        return await self.repository.find_one({"document_id": document_id})

    async def get_by_id(self, insights_id: str) -> Optional[Dict[str, Any]]:
        """Get insights by ID."""
        return await self.repository.find_by_id(insights_id)

    async def find_by_risk_level(
        self,
        risk_level: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Find insights by risk level."""
        return await self.repository.find_many(
            {"risk_level": risk_level},
            order_by="-created_at",
            limit=limit
        )

    async def find_by_risk_score_range(
        self,
        min_score: int,
        max_score: int,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Find insights by risk score range."""
        return await self.repository.find_many(
            {"risk_score": {"gte": min_score, "lte": max_score}},
            order_by="-created_at",
            limit=limit
        )

    async def find_auto_approved(
        self,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Find auto-approved applications."""
        return await self.repository.find_many(
            {"auto_approval_status": "approved"},
            order_by="-created_at",
            limit=limit
        )

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get aggregate statistics.

        Returns:
            Dictionary with various statistics
        """
        # Count by risk level
        risk_level_stats = await self.repository.aggregate(
            {"count": "count(*)"},
            group_by=["risk_level"]
        )

        # Average risk score
        avg_stats = await self.repository.aggregate(
            {
                "avg_risk_score": "avg(risk_score)",
                "min_risk_score": "min(risk_score)",
                "max_risk_score": "max(risk_score)"
            }
        )

        # Auto-approval stats
        approval_stats = await self.repository.aggregate(
            {"count": "count(*)"},
            group_by=["auto_approval_status"]
        )

        return {
            "total_insights": await self.repository.count(),
            "risk_level_distribution": {
                item["risk_level"]: item["count"]
                for item in risk_level_stats
            },
            "risk_score_stats": avg_stats[0] if avg_stats else {},
            "approval_distribution": {
                item["auto_approval_status"]: item["count"]
                for item in approval_stats
                if item.get("auto_approval_status")
            }
        }

    async def delete_by_document_id(self, document_id: str) -> bool:
        """Delete insights by document ID."""
        return await self.repository.delete_one({"document_id": document_id})

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count insights with optional filters."""
        return await self.repository.count(filters)
