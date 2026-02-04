"""
Integration helper for Analytics storage.

Simplifies integration of dynamic database storage with existing AnalyticsService.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from modules.analytics.storage.analytics_repository import AnalyticsRepository
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class AnalyticsStorage:
    """
    High-level storage interface for analytics aggregations.

    Handles repository initialization and provides simplified API.

    Example:
        >>> storage = AnalyticsStorage(engine, session, "forms-capital-loan")
        >>> await storage.initialize()
        >>>
        >>> # Save monthly metric
        >>> await storage.save_monthly_metric(
        ...     "average_risk_score",
        ...     datetime(2026, 2, 1),
        ...     72.5
        ... )
        >>>
        >>> # Get trend
        >>> trend = await storage.get_trend("average_risk_score", "monthly", 12)
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
        self.repository: Optional[AnalyticsRepository] = None
        self._initialized = False

    async def initialize(self):
        """Initialize storage (creates table if needed)."""
        if self._initialized:
            return

        self.repository = AnalyticsRepository(
            self.engine,
            self.session,
            self.use_case_id
        )
        await self.repository.initialize()
        self._initialized = True

        logger.info(f"Analytics storage initialized for: {self.use_case_id}")

    async def save_monthly_metric(
        self,
        metric_id: str,
        period_start: datetime,
        value: float,
        **kwargs
    ) -> Dict[str, Any]:
        """Save a monthly metric."""
        if not self._initialized:
            await self.initialize()

        period_end = period_start + relativedelta(months=1) - timedelta(seconds=1)

        return await self.repository.save_metric(
            metric_id=metric_id,
            period_type="monthly",
            period_start=period_start,
            period_end=period_end,
            value=value,
            **kwargs
        )

    async def save_daily_metric(
        self,
        metric_id: str,
        period_start: datetime,
        value: float,
        **kwargs
    ) -> Dict[str, Any]:
        """Save a daily metric."""
        if not self._initialized:
            await self.initialize()

        period_end = period_start + timedelta(days=1) - timedelta(seconds=1)

        return await self.repository.save_metric(
            metric_id=metric_id,
            period_type="daily",
            period_start=period_start,
            period_end=period_end,
            value=value,
            **kwargs
        )

    async def save_dimension_breakdown(
        self,
        dimension_id: str,
        dimension_value: str,
        period_type: str,
        period_start: datetime,
        count: int,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Save a dimensional breakdown.

        Args:
            dimension_id: Dimension identifier (e.g., 'risk_level')
            dimension_value: Dimension value (e.g., 'high')
            period_type: Period granularity
            period_start: Period start
            count: Count for this dimension value
            **kwargs: Additional metric values

        Returns:
            Saved record
        """
        if not self._initialized:
            await self.initialize()

        period_end = self._calculate_period_end(period_type, period_start)

        return await self.repository.save_aggregation({
            "metric_id": f"dimension_{dimension_id}",
            "period_type": period_type,
            "period_start": period_start,
            "period_end": period_end,
            "dimension_id": dimension_id,
            "dimension_value": dimension_value,
            "count": count,
            **kwargs
        })

    async def save_product_metric(
        self,
        product_id: str,
        period_type: str,
        period_start: datetime,
        eligible_count: int,
        total_count: int,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Save product eligibility metrics.

        Args:
            product_id: Product identifier
            period_type: Period granularity
            period_start: Period start
            eligible_count: Number of eligible applications
            total_count: Total applications
            **kwargs: Additional metrics

        Returns:
            Saved record
        """
        if not self._initialized:
            await self.initialize()

        period_end = self._calculate_period_end(period_type, period_start)
        approval_rate = (eligible_count / total_count * 100) if total_count > 0 else 0

        return await self.repository.save_aggregation({
            "metric_id": f"product_{product_id}",
            "period_type": period_type,
            "period_start": period_start,
            "period_end": period_end,
            "product_id": product_id,
            "eligible_count": eligible_count,
            "count": total_count,
            "approval_rate": approval_rate,
            **kwargs
        })

    async def get_trend(
        self,
        metric_id: str,
        period_type: str,
        periods: int = 12
    ) -> List[Dict[str, Any]]:
        """Get trend data for a metric."""
        if not self._initialized:
            await self.initialize()

        return await self.repository.get_metric_trend(
            metric_id,
            period_type,
            periods
        )

    async def get_dimension_breakdown(
        self,
        dimension_id: str,
        period_type: str,
        period_start: datetime
    ) -> List[Dict[str, Any]]:
        """Get breakdown for a dimension."""
        if not self._initialized:
            await self.initialize()

        return await self.repository.get_dimension_breakdown(
            dimension_id,
            period_type,
            period_start
        )

    async def get_product_metrics(
        self,
        period_type: str,
        period_start: datetime
    ) -> List[Dict[str, Any]]:
        """Get product metrics for a period."""
        if not self._initialized:
            await self.initialize()

        return await self.repository.get_product_metrics(
            period_type,
            period_start
        )

    async def cleanup_old_data(self, days: int = 365) -> int:
        """
        Clean up old aggregations.

        Args:
            days: Delete aggregations older than this many days

        Returns:
            Number of records deleted
        """
        if not self._initialized:
            await self.initialize()

        return await self.repository.delete_old_aggregations(days)

    def _calculate_period_end(
        self,
        period_type: str,
        period_start: datetime
    ) -> datetime:
        """Calculate period end based on type."""
        if period_type == "daily":
            return period_start + timedelta(days=1) - timedelta(seconds=1)
        elif period_type == "monthly":
            return period_start + relativedelta(months=1) - timedelta(seconds=1)
        elif period_type == "yearly":
            return period_start + relativedelta(years=1) - timedelta(seconds=1)
        elif period_type == "quarterly":
            return period_start + relativedelta(months=3) - timedelta(seconds=1)
        else:
            return period_start + timedelta(days=1) - timedelta(seconds=1)


# Factory function
async def create_analytics_storage(
    engine: AsyncEngine,
    session: AsyncSession,
    use_case_id: str
) -> AnalyticsStorage:
    """
    Create and initialize analytics storage.

    Args:
        engine: Async SQLAlchemy engine
        session: Async SQLAlchemy session
        use_case_id: Use case identifier

    Returns:
        Initialized AnalyticsStorage instance
    """
    storage = AnalyticsStorage(engine, session, use_case_id)
    await storage.initialize()
    return storage
