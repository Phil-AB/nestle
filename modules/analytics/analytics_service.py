"""
Universal Analytics Service.

100% config-driven analytics for any use case.
No hardcoded field names, thresholds, or product names.

Queries insights table for risk scores and analytics data using raw SQL.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from shared.utils.logger import setup_logger
from modules.analytics.config_loader import AnalyticsConfigLoader

logger = setup_logger(__name__)


def _convert_decimal_to_native(value: Any) -> Any:
    """Convert Decimal types to native Python types for JSON serialization."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [_convert_decimal_to_native(item) for item in value]
    if isinstance(value, dict):
        return {k: _convert_decimal_to_native(v) for k, v in value.items()}
    return value


class AnalyticsService:
    """
    Universal config-driven analytics service.

    Features:
    - 100% config-driven (no hardcoding)
    - Dynamic field mapping
    - Configurable metrics and dimensions
    - Universal aggregations
    - Queries insights table for analytics data

    Example:
        >>> service = AnalyticsService("forms-capital-loan", session)
        >>> dashboard = await service.get_dashboard()
        >>> dashboard["overview"]["total_documents"]
        150
    """

    def _get_insights_table_name(self) -> str:
        """Get the insights table name for this use case."""
        return f"insights_{self.use_case_id.replace('-', '_')}"

    def __init__(self, use_case_id: str, session: AsyncSession):
        """
        Initialize analytics service.

        Args:
            use_case_id: Use case identifier
            session: Async SQLAlchemy session
        """
        self.use_case_id = use_case_id
        self.session = session
        self.table_name = self._get_insights_table_name()

        logger.info(f"Initializing analytics service for use case: {use_case_id}")
        logger.info(f"Using insights table: {self.table_name}")
        self.config_loader = AnalyticsConfigLoader(use_case_id)

        try:
            configs = self.config_loader.load_all()
            self.metrics_config = configs.get("metrics", {})
            self.dimensions_config = configs.get("dimensions", {})
            logger.info(f"Loaded analytics config for: {use_case_id}")
        except FileNotFoundError as e:
            logger.warning(f"Analytics config not found: {e}, using defaults")
            self.metrics_config = {}
            self.dimensions_config = {}

    def _build_date_filter_sql(self, date_range: Optional[str]) -> str:
        """Build SQL date filter clause."""
        if not date_range or date_range == "all":
            return ""

        now = datetime.utcnow()
        if date_range == "30d":
            date_threshold = (now - timedelta(days=30)).isoformat()
            return f"AND created_at >= '{date_threshold}'"
        elif date_range == "90d":
            date_threshold = (now - timedelta(days=90)).isoformat()
            return f"AND created_at >= '{date_threshold}'"
        elif date_range == "12m":
            date_threshold = (now - relativedelta(months=12)).isoformat()
            return f"AND created_at >= '{date_threshold}'"
        return ""

    async def get_dashboard(
        self,
        date_range: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get complete dashboard data."""
        logger.info(f"Generating dashboard for use case: {self.use_case_id}")
        start_time = datetime.utcnow()

        date_filter_sql = self._build_date_filter_sql(date_range)

        # Get overview metrics
        overview = await self._calculate_overview_metrics(date_filter_sql)

        # Get dimension breakdowns
        dimensions = await self._calculate_dimension_breakdowns(date_filter_sql)

        # Get trends
        trends = await self._calculate_trends(date_filter_sql)

        # Get product metrics
        products = await self._calculate_product_metrics(date_filter_sql)

        processing_time = (datetime.utcnow() - start_time).total_seconds()

        # Convert all Decimal values to native Python types for JSON serialization
        result = {
            "use_case_id": self.use_case_id,
            "overview": _convert_decimal_to_native(overview),
            "dimensions": _convert_decimal_to_native(dimensions),
            "trends": _convert_decimal_to_native(trends),
            "products": _convert_decimal_to_native(products),
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "processing_time_seconds": round(processing_time, 3),
                "date_range": date_range or "all",
                "filters_applied": filters or {}
            }
        }

        return result

    async def _calculate_overview_metrics(self, date_filter_sql: str) -> Dict[str, Any]:
        """Calculate overview metrics."""
        metrics = {}
        overview_config = self.metrics_config.get("overview_metrics", {})

        # Get total count first
        total_query = text(f"SELECT COUNT(*) FROM {self.table_name} WHERE 1=1 {date_filter_sql}")
        total_result = await self.session.execute(total_query)
        total_count = total_result.scalar() or 0
        metrics["total_documents"] = total_count

        for metric_id, metric_config in overview_config.items():
            try:
                value = await self._calculate_metric_sql(metric_config, date_filter_sql, total_count)
                metrics[metric_id] = value
            except Exception as e:
                logger.error(f"Error calculating metric {metric_id}: {e}")
                metrics[metric_id] = None

        return metrics

    async def _calculate_metric_sql(self, metric_config: Dict[str, Any], date_filter_sql: str, total_count: int) -> Any:
        """Calculate a single metric using SQL."""
        aggregation = metric_config.get("aggregation", "count")
        source = metric_config.get("source", {})
        field_path = source.get("field")
        decimals = metric_config.get("decimals", 1)

        if aggregation == "count":
            query = text(f"SELECT COUNT(*) FROM {self.table_name} WHERE 1=1 {date_filter_sql}")
            result = await self.session.execute(query)
            return int(result.scalar() or 0)

        elif aggregation == "average":
            # Get raw average without SQL rounding to avoid string conversion
            query = text(f"SELECT AVG({field_path}) FROM {self.table_name} WHERE 1=1 {date_filter_sql}")
            result = await self.session.execute(query)
            avg_value = result.scalar()
            if avg_value is not None:
                # Explicitly convert to float before rounding
                return round(float(avg_value), decimals)
            return float(metric_config.get("default", 0))

        elif aggregation == "sum":
            query = text(f"SELECT COALESCE(SUM({field_path}), 0) FROM {self.table_name} WHERE 1=1 {date_filter_sql}")
            result = await self.session.execute(query)
            return float(result.scalar() or 0)

        elif aggregation == "count_where":
            condition = metric_config.get("condition", {})
            condition_sql = self._build_condition_sql(condition)
            query = text(f"SELECT COUNT(*) FROM {self.table_name} WHERE {condition_sql} {date_filter_sql}")
            result = await self.session.execute(query)
            return int(result.scalar() or 0)

        elif aggregation == "percentage":
            condition = metric_config.get("condition", {})
            condition_sql = self._build_condition_sql(condition)

            # Get numerator
            numerator_query = text(f"SELECT COUNT(*) FROM {self.table_name} WHERE {condition_sql} {date_filter_sql}")
            numerator_result = await self.session.execute(numerator_query)
            numerator = numerator_result.scalar() or 0

            # Use passed total_count as denominator
            denominator = total_count if total_count > 0 else 1

            return round(numerator / denominator * 100, 1) if denominator > 0 else 0

        return metric_config.get("default", 0)

    def _build_condition_sql(self, condition: Dict[str, Any]) -> str:
        """Build SQL condition clause."""
        field_path = condition.get("source", {}).get("field", "")
        operator = condition.get("operator", "equals")
        value = condition.get("value")

        # Sanitize field path (only allow alphanumeric and underscore)
        field_path = ''.join(c for c in field_path if c.isalnum() or c == '_')

        if operator == "equals":
            return f"{field_path} = '{value}'"
        elif operator == "not_equals":
            return f"{field_path} != '{value}'"
        elif operator == "gte":
            return f"{field_path} >= {value}"
        elif operator == "gt":
            return f"{field_path} > {value}"
        elif operator == "lte":
            return f"{field_path} <= {value}"
        elif operator == "lt":
            return f"{field_path} < {value}"
        elif operator == "in":
            values = "', '".join(str(v) for v in value)
            return f"{field_path} IN ('{values}')"
        elif operator == "contains":
            return f"{field_path} LIKE '%{value}%'"

        return "1=1"

    async def _calculate_dimension_breakdowns(self, date_filter_sql: str) -> Dict[str, Any]:
        """Calculate dimension breakdowns."""
        breakdowns = {}
        dimensions = self.dimensions_config.get("dimensions", {})

        for dim_id, dim_config in dimensions.items():
            try:
                breakdowns[dim_id] = await self._aggregate_dimension_sql(dim_config, date_filter_sql)
            except Exception as e:
                logger.error(f"Error calculating dimension {dim_id}: {e}")
                breakdowns[dim_id] = {}

        return breakdowns

    async def _aggregate_dimension_sql(self, dim_config: Dict[str, Any], date_filter_sql: str) -> Dict[str, Any]:
        """Aggregate dimension using SQL."""
        field_path = dim_config.get("source", {}).get("field", "")
        aggregation_type = dim_config.get("aggregation", "count_by_value")

        # Sanitize field path
        field_path_sanitized = ''.join(c for c in field_path if c.isalnum() or c == '_')

        if aggregation_type == "count_by_value":
            query = text(f"""
                SELECT {field_path_sanitized} as value, COUNT(*) as count
                FROM {self.table_name}
                WHERE 1=1 {date_filter_sql}
                GROUP BY {field_path_sanitized}
            """)
            result = await self.session.execute(query)
            return {row.value or "Unknown": row.count for row in result}

        elif aggregation_type == "distribution":
            ranges = dim_config.get("ranges", [])
            distribution = []

            for range_config in ranges:
                label = range_config.get("label", "")
                min_val = range_config.get("min")
                max_val = range_config.get("max")

                conditions = []
                if min_val is not None:
                    conditions.append(f"{field_path_sanitized} >= {min_val}")
                if max_val is not None:
                    conditions.append(f"{field_path_sanitized} < {max_val}")

                where_sql = f"WHERE {' AND '.join(conditions)} {date_filter_sql}" if conditions else f"WHERE 1=1 {date_filter_sql}"

                query = text(f"SELECT COUNT(*) FROM {self.table_name} {where_sql}")
                result = await self.session.execute(query)
                count = result.scalar() or 0

                distribution.append({
                    "label": label,
                    "min": min_val,
                    "max": max_val,
                    "count": count,
                    "percentage": 0
                })

            return distribution

        elif aggregation_type == "value_mapping":
            value_map = dim_config.get("value_map", {})
            result_map = {}

            for category, values in value_map.items():
                if isinstance(values, list):
                    count = 0
                    for val in values:
                        query = text(f"SELECT COUNT(*) FROM {self.table_name} WHERE {field_path_sanitized} = :val {date_filter_sql}")
                        result = await self.session.execute(query, {"val": val})
                        count += result.scalar() or 0
                    result_map[category] = count
                else:
                    query = text(f"SELECT COUNT(*) FROM {self.table_name} WHERE {field_path_sanitized} = :val {date_filter_sql}")
                    result = await self.session.execute(query, {"val": values})
                    result_map[category] = result.scalar() or 0

            return result_map

        return {}

    async def _calculate_trends(self, date_filter_sql: str) -> List[Dict[str, Any]]:
        """Calculate trends."""
        # Since we have date_filter_sql, we need to add it to the trends query too
        # For now, return empty list - trends need more complex SQL
        query = text(f"""
            SELECT DATE_TRUNC('month', created_at)::date as period,
                   COUNT(*) as count
            FROM {self.table_name}
            WHERE 1=1 {date_filter_sql}
            GROUP BY DATE_TRUNC('month', created_at)
            ORDER BY period DESC
            LIMIT 12
        """)
        result = await self.session.execute(query)
        trends = [{"period": str(row.period), "count": row.count} for row in result]
        trends.reverse()
        return trends

    async def _calculate_product_metrics(self, date_filter_sql: str) -> Dict[str, Any]:
        """Calculate product metrics."""
        products_config = self.metrics_config.get("products", {})
        results = {}

        # Get total count
        total_query = text(f"SELECT COUNT(*) FROM {self.table_name} WHERE 1=1 {date_filter_sql}")
        total_result = await self.session.execute(total_query)
        total_count = total_result.scalar() or 1

        for product_id, product_config in products_config.items():
            eligibility_conditions = product_config.get("eligibility_conditions", [])

            conditions = []
            for cond in eligibility_conditions:
                conditions.append(self._build_condition_sql(cond))

            if conditions:
                condition_sql = " AND ".join(conditions)
                query = text(f"SELECT COUNT(*) FROM {self.table_name} WHERE {condition_sql} {date_filter_sql}")
                result = await self.session.execute(query)
                eligible_count = result.scalar() or 0
            else:
                eligible_count = 0

            results[product_id] = {
                "product_name": product_config.get("name", product_id),
                "eligible": eligible_count,
                "total": total_count,
                "percentage": round(eligible_count / total_count * 100, 1) if total_count > 0 else 0
            }

        return results

    # Other public methods
    async def get_overview_metrics(self, date_range: Optional[str] = None, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get overview metrics only."""
        date_filter_sql = self._build_date_filter_sql(date_range)
        return await self._calculate_overview_metrics(date_filter_sql)

    async def get_dimension_breakdown(self, dimension_id: str, date_range: Optional[str] = None, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get breakdown for a specific dimension."""
        date_filter_sql = self._build_date_filter_sql(date_range)
        dim_config = self.dimensions_config.get("dimensions", {}).get(dimension_id)
        if not dim_config:
            return {"error": f"Dimension not found: {dimension_id}"}
        return await self._aggregate_dimension_sql(dim_config, date_filter_sql)

    async def get_trends(self, period: str = "monthly", count: int = 12, date_range: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get trend data."""
        date_filter_sql = self._build_date_filter_sql(date_range)
        return await self._calculate_trends(date_filter_sql)

    async def get_percentile(self, document_id: str, metric_id: str) -> Optional[float]:
        """Get percentile rank - not implemented for SQL version."""
        return None
