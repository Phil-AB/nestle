"""
Analytics Repository.

Provides storage operations for pre-computed analytics aggregations.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine

from shared.database.schema_manager import SchemaManager
from shared.database.universal_repository import UniversalRepository
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


class AnalyticsRepository:
    """
    Repository for analytics aggregation storage.

    Stores pre-computed metrics, dimensional breakdowns, and trends.
    Automatically creates and manages use-case-specific tables.

    Example:
        >>> repo = AnalyticsRepository(engine, session, "forms-capital-loan")
        >>> await repo.initialize()
        >>> await repo.save_metric("average_risk_score", "monthly", "2026-02", 72.5)
        >>> metrics = await repo.get_metrics_for_period("monthly", "2026-02")
    """

    def __init__(
        self,
        engine: AsyncEngine,
        session: AsyncSession,
        use_case_id: str
    ):
        """
        Initialize analytics repository.

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
        """Initialize repository by ensuring table exists."""
        logger.info(f"Initializing analytics repository for use case: {self.use_case_id}")

        # Ensure table exists
        self.table = await self.schema_manager.ensure_table_exists(
            "analytics",
            self.use_case_id
        )

        # Create universal repository
        self.repository = UniversalRepository(self.session, self.table)

        logger.info(f"Analytics repository initialized with table: {self.table.name}")

    async def save_metric(
        self,
        metric_id: str,
        period_type: str,
        period_start: datetime,
        period_end: datetime,
        value: float,
        metric_name: Optional[str] = None,
        dimension_id: Optional[str] = None,
        dimension_value: Optional[str] = None,
        product_id: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Save/update a metric aggregation.

        Args:
            metric_id: Metric identifier
            period_type: Period granularity (daily, monthly, etc.)
            period_start: Period start timestamp
            period_end: Period end timestamp
            value: Metric value (stored in 'average' column)
            metric_name: Human-readable metric name
            dimension_id: Optional dimension identifier
            dimension_value: Optional dimension value
            product_id: Optional product identifier
            additional_data: Additional metric values

        Returns:
            Saved metric record
        """
        # Check if metric already exists
        filters = {
            "use_case_id": self.use_case_id,
            "metric_id": metric_id,
            "period_type": period_type,
            "period_start": period_start,
        }

        if dimension_id:
            filters["dimension_id"] = dimension_id
            filters["dimension_value"] = dimension_value

        if product_id:
            filters["product_id"] = product_id

        existing = await self.repository.find_one(filters)

        data = {
            "use_case_id": self.use_case_id,
            "metric_id": metric_id,
            "metric_name": metric_name,
            "period_type": period_type,
            "period_start": period_start,
            "period_end": period_end,
            "period_label": self._format_period_label(period_type, period_start),
            "average": value,
            "dimension_id": dimension_id,
            "dimension_value": dimension_value,
            "product_id": product_id,
            "last_computed_at": datetime.utcnow()
        }

        if additional_data:
            data.update(additional_data)

        if existing:
            # Update existing
            return await self.repository.update_one(filters, data)
        else:
            # Create new
            return await self.repository.create(data)

    async def save_aggregation(
        self,
        aggregation_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Save a complete aggregation record.

        Args:
            aggregation_data: Complete aggregation data

        Returns:
            Saved aggregation record
        """
        # Ensure use_case_id is set
        aggregation_data["use_case_id"] = self.use_case_id
        aggregation_data["last_computed_at"] = datetime.utcnow()

        # Check if exists
        filters = {
            "use_case_id": aggregation_data["use_case_id"],
            "metric_id": aggregation_data["metric_id"],
            "period_type": aggregation_data["period_type"],
            "period_start": aggregation_data["period_start"],
        }

        if "dimension_id" in aggregation_data:
            filters["dimension_id"] = aggregation_data["dimension_id"]
            filters["dimension_value"] = aggregation_data.get("dimension_value")

        if "product_id" in aggregation_data:
            filters["product_id"] = aggregation_data["product_id"]

        existing = await self.repository.find_one(filters)

        if existing:
            return await self.repository.update_one(filters, aggregation_data)
        else:
            return await self.repository.create(aggregation_data)

    async def get_metrics_for_period(
        self,
        period_type: str,
        period_start: datetime,
        metric_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Get all metrics for a specific period."""
        filters = {
            "use_case_id": self.use_case_id,
            "period_type": period_type,
            "period_start": period_start
        }

        results = await self.repository.find_many(filters)

        if metric_ids:
            results = [r for r in results if r["metric_id"] in metric_ids]

        return results

    async def get_metric_trend(
        self,
        metric_id: str,
        period_type: str,
        periods: int = 12
    ) -> List[Dict[str, Any]]:
        """
        Get trend data for a metric over time.

        Args:
            metric_id: Metric identifier
            period_type: Period granularity
            periods: Number of periods to retrieve

        Returns:
            List of metric values over time
        """
        return await self.repository.find_many(
            {
                "use_case_id": self.use_case_id,
                "metric_id": metric_id,
                "period_type": period_type
            },
            order_by="-period_start",
            limit=periods
        )

    async def get_dimension_breakdown(
        self,
        dimension_id: str,
        period_type: str,
        period_start: datetime
    ) -> List[Dict[str, Any]]:
        """Get breakdown for a dimension in a specific period."""
        return await self.repository.find_many({
            "use_case_id": self.use_case_id,
            "dimension_id": dimension_id,
            "period_type": period_type,
            "period_start": period_start
        })

    async def get_product_metrics(
        self,
        period_type: str,
        period_start: datetime
    ) -> List[Dict[str, Any]]:
        """Get product-specific metrics for a period."""
        results = await self.repository.find_many({
            "use_case_id": self.use_case_id,
            "period_type": period_type,
            "period_start": period_start
        })

        return [r for r in results if r.get("product_id")]

    async def delete_old_aggregations(self, days_old: int) -> int:
        """
        Delete aggregations older than specified days.

        Args:
            days_old: Number of days

        Returns:
            Number of records deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        return await self.repository.delete_many({
            "created_at": {"lt": cutoff_date}
        })

    async def refresh_period(
        self,
        period_type: str,
        period_start: datetime
    ) -> int:
        """
        Delete all aggregations for a period (to trigger recomputation).

        Args:
            period_type: Period granularity
            period_start: Period start timestamp

        Returns:
            Number of records deleted
        """
        return await self.repository.delete_many({
            "use_case_id": self.use_case_id,
            "period_type": period_type,
            "period_start": period_start
        })

    async def get_latest_computation_time(self) -> Optional[datetime]:
        """Get the timestamp of the most recent computation."""
        result = await self.repository.aggregate(
            {"max_time": "max(last_computed_at)"},
            filters={"use_case_id": self.use_case_id}
        )

        if result and result[0].get("max_time"):
            return result[0]["max_time"]

        return None

    async def count_aggregations(
        self,
        period_type: Optional[str] = None
    ) -> int:
        """Count stored aggregations."""
        filters = {"use_case_id": self.use_case_id}

        if period_type:
            filters["period_type"] = period_type

        return await self.repository.count(filters)

    def _format_period_label(self, period_type: str, period_start: datetime) -> str:
        """Format a human-readable period label."""
        if period_type == "monthly":
            return period_start.strftime("%Y-%m")
        elif period_type == "daily":
            return period_start.strftime("%Y-%m-%d")
        elif period_type == "yearly":
            return period_start.strftime("%Y")
        elif period_type == "quarterly":
            quarter = (period_start.month - 1) // 3 + 1
            return f"{period_start.year}-Q{quarter}"
        else:
            return period_start.strftime("%Y-%m-%d")
