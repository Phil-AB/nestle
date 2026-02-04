"""
Integration helper for Insights storage.

Simplifies integration of dynamic database storage with existing InsightsService.
"""

from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from modules.insights.storage.insights_repository import InsightsRepository
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class InsightsStorage:
    """
    High-level storage interface for insights.

    Handles repository initialization and provides simplified API.

    Example:
        >>> from src.database.connection import get_engine, get_session
        >>>
        >>> engine = get_engine()
        >>> async with get_session() as session:
        ...     storage = InsightsStorage(engine, session, "forms-capital-loan")
        ...     await storage.initialize()
        ...
        ...     # Save insights
        ...     await storage.save("doc_123", {
        ...         "risk_score": 75,
        ...         "risk_level": "medium",
        ...         "full_name": "John Doe",
        ...         "monthly_income": 5000,
        ...         "auto_approval_status": "manual_review"
        ...     })
        ...
        ...     # Retrieve insights
        ...     insights = await storage.get("doc_123")
    """

    def __init__(
        self,
        engine: AsyncEngine,
        session: AsyncSession,
        use_case_id: str
    ):
        """
        Initialize storage.

        Args:
            engine: Async SQLAlchemy engine
            session: Async SQLAlchemy session
            use_case_id: Use case identifier
        """
        self.engine = engine
        self.session = session
        self.use_case_id = use_case_id
        self.repository: Optional[InsightsRepository] = None
        self._initialized = False

    async def initialize(self):
        """Initialize storage (creates table if needed)."""
        if self._initialized:
            return

        self.repository = InsightsRepository(
            self.engine,
            self.session,
            self.use_case_id
        )
        await self.repository.initialize()
        self._initialized = True

        logger.info(f"Insights storage initialized for: {self.use_case_id}")

    async def save(
        self,
        document_id: str,
        insights: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Save insights for a document.

        Automatically handles create/update logic.

        Args:
            document_id: Document identifier
            insights: Insights data from InsightsService

        Returns:
            Saved record
        """
        if not self._initialized:
            await self.initialize()

        # Extract relevant fields from insights dictionary
        data = self._prepare_insights_data(insights)

        return await self.repository.save_insights(document_id, data)

    async def get(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get insights by document ID."""
        if not self._initialized:
            await self.initialize()

        return await self.repository.get_by_document_id(document_id)

    async def delete(self, document_id: str) -> bool:
        """Delete insights by document ID."""
        if not self._initialized:
            await self.initialize()

        return await self.repository.delete_by_document_id(document_id)

    async def get_statistics(self) -> Dict[str, Any]:
        """Get aggregate statistics."""
        if not self._initialized:
            await self.initialize()

        return await self.repository.get_statistics()

    def _prepare_insights_data(self, insights: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare insights data for database storage.

        Stores the complete insights in full_insights JSONB column for perfect reconstruction.
        Also extracts individual fields for querying and analytics.

        Args:
            insights: Raw insights dictionary from InsightsService

        Returns:
            Data dictionary ready for database
        """
        import json

        data = {}

        # Store the FULL insights as JSONB - this preserves everything
        data["full_insights"] = insights

        # Extract fields for querying/indexing (keep existing for analytics)
        profile = insights.get("customer_profile", {})
        if profile:
            data["full_name"] = profile.get("full_name")
            data["age"] = profile.get("age")
            data["monthly_income"] = profile.get("monthly_income")
            data["occupation"] = profile.get("occupation")
            data["employment_status"] = profile.get("employment_status")
            data["debt_to_income_ratio"] = profile.get("debt_to_income_ratio")
            data["disposable_income"] = profile.get("disposable_income")

        risk = insights.get("risk_assessment", {})
        if risk:
            data["risk_score"] = risk.get("risk_score")
            # Normalize risk_level for database constraint
            risk_level = risk.get("risk_level", "")
            if risk_level:
                risk_level_normalized = risk_level.lower().replace(" ", "").replace("-", "")
                if "high" in risk_level_normalized:
                    data["risk_level"] = "high"
                elif "medium" in risk_level_normalized:
                    data["risk_level"] = "medium"
                elif "low" in risk_level_normalized:
                    data["risk_level"] = "low"
                elif "critical" in risk_level_normalized:
                    data["risk_level"] = "critical"
                else:
                    data["risk_level"] = "medium"
            data["risk_factors"] = risk.get("scoring_breakdown")  # Store breakdown for analytics

        products = insights.get("product_eligibility", {})
        if products:
            data["eligible_products"] = products

        decisions = insights.get("automated_decisions", {})
        if decisions:
            # Extract common decisions for querying
            loan_approval = decisions.get("loan_approval", {})
            if isinstance(loan_approval, dict):
                data["auto_approval_status"] = loan_approval.get("decision")

            loan_amount = decisions.get("loan_amount_recommendation", {})
            if isinstance(loan_amount, dict):
                data["max_loan_amount"] = loan_amount.get("value")

        # Extract metadata
        metadata = insights.get("metadata", {})
        if metadata:
            data["config_version"] = metadata.get("config_version", {}).get("criteria")
            data["processing_time_ms"] = int(
                metadata.get("processing_time_seconds", 0) * 1000
            )
            data["engine_type"] = metadata.get("engine", "hybrid")

        return data


# Factory function for easy instantiation
async def create_insights_storage(
    engine: AsyncEngine,
    session: AsyncSession,
    use_case_id: str
) -> InsightsStorage:
    """
    Create and initialize insights storage.

    Args:
        engine: Async SQLAlchemy engine
        session: Async SQLAlchemy session
        use_case_id: Use case identifier

    Returns:
        Initialized InsightsStorage instance
    """
    storage = InsightsStorage(engine, session, use_case_id)
    await storage.initialize()
    return storage
