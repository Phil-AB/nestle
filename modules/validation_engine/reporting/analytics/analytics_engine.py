"""Analytics engine for validation metrics"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from uuid import UUID
from collections import defaultdict

from ...core.session_manager import get_session_manager
from ...version_control import get_version_manager
from ..report_models import AnalyticsDashboardData
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class AnalyticsEngine:
    """
    Analytics engine for validation metrics and trends

    Provides:
    - Aggregated statistics across sessions
    - Trend analysis
    - Performance metrics
    - Discrepancy patterns
    - Use case analytics
    """

    def __init__(self):
        """Initialize analytics engine"""
        self.session_manager = get_session_manager()
        self.version_manager = get_version_manager()

        logger.info("AnalyticsEngine initialized")

    async def get_dashboard_data(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        use_case: Optional[str] = None
    ) -> AnalyticsDashboardData:
        """
        Get analytics dashboard data

        Args:
            start_date: Start of period (default: 30 days ago)
            end_date: End of period (default: now)
            use_case: Filter by use case

        Returns:
            Dashboard data with metrics and trends
        """
        if end_date is None:
            end_date = datetime.utcnow()
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        logger.info(
            f"Generating analytics dashboard for period: "
            f"{start_date.date()} to {end_date.date()}"
        )

        # Get all sessions in period
        sessions = self._get_sessions_in_period(start_date, end_date, use_case)

        # Calculate metrics
        metrics = await self._calculate_metrics(sessions)

        # Build dashboard data
        dashboard = AnalyticsDashboardData(
            period_start=start_date,
            period_end=end_date,
            generated_at=datetime.utcnow(),
            **metrics
        )

        return dashboard

    def _get_sessions_in_period(
        self,
        start_date: datetime,
        end_date: datetime,
        use_case: Optional[str] = None
    ) -> List:
        """Get all sessions within date range"""
        # In production, this would query database
        # For now, return empty list (placeholder)
        return []

    async def _calculate_metrics(
        self, sessions: List
    ) -> Dict[str, Any]:
        """
        Calculate analytics metrics from sessions

        Args:
            sessions: List of validation sessions

        Returns:
            Dictionary of metrics
        """
        if not sessions:
            return self._empty_metrics()

        # Overall metrics
        total_sessions = len(sessions)
        total_validations = 0
        accuracy_scores = []
        processing_times = []

        # Status distribution
        status_counts = defaultdict(int)

        # Discrepancy metrics
        severity_counts = defaultdict(int)
        category_counts = defaultdict(int)
        discrepancy_patterns = defaultdict(int)

        # Use case breakdown
        use_case_counts = defaultdict(int)
        use_case_accuracy = defaultdict(list)

        # Time series data
        daily_sessions = defaultdict(int)
        daily_accuracy = defaultdict(list)

        # Process each session
        for session in sessions:
            # Overall metrics
            total_validations += len(session.validation_results)

            # Accuracy
            if session.validation_results:
                passed = sum(1 for r in session.validation_results if r.passed)
                accuracy = (passed / len(session.validation_results)) * 100
                accuracy_scores.append(accuracy)

            # Status
            final_status = self._determine_final_status(session)
            status_counts[final_status] += 1

            # Discrepancies
            for disc in session.discrepancies:
                severity_counts[disc.severity.lower()] += 1
                category_counts[disc.category] += 1
                discrepancy_patterns[disc.field_name] += 1

            # Use case
            use_case_counts[session.use_case] += 1
            if accuracy_scores:
                use_case_accuracy[session.use_case].append(accuracy_scores[-1])

            # Time series
            date_key = session.created_at.date().isoformat()
            daily_sessions[date_key] += 1
            if accuracy_scores:
                daily_accuracy[date_key].append(accuracy_scores[-1])

        # Calculate averages
        avg_accuracy = sum(accuracy_scores) / len(accuracy_scores) if accuracy_scores else 0.0
        avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0.0

        # Get most common discrepancies
        most_common = sorted(
            discrepancy_patterns.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        # Calculate use case accuracies
        use_case_avg_accuracy = {
            uc: sum(scores) / len(scores)
            for uc, scores in use_case_accuracy.items()
            if scores
        }

        # Format time series data
        daily_sessions_list = [
            {"date": date, "count": count}
            for date, count in sorted(daily_sessions.items())
        ]

        daily_accuracy_list = [
            {
                "date": date,
                "avg_accuracy": sum(scores) / len(scores) if scores else 0
            }
            for date, scores in sorted(daily_accuracy.items())
        ]

        # Calculate revalidation rate
        revalidation_count = sum(1 for s in sessions if s.is_revalidation)
        revalidation_rate = (revalidation_count / total_sessions * 100) if total_sessions > 0 else 0.0

        return {
            "total_sessions": total_sessions,
            "total_validations": total_validations,
            "avg_accuracy": round(avg_accuracy, 2),
            "avg_processing_time_ms": round(avg_processing_time, 2),
            "status_distribution": dict(status_counts),
            "discrepancy_trends": dict(severity_counts),
            "discrepancy_by_category": dict(category_counts),
            "most_common_discrepancies": [
                {"field": field, "count": count}
                for field, count in most_common
            ],
            "recurring_issues": self._identify_recurring_issues(discrepancy_patterns),
            "sessions_by_use_case": dict(use_case_counts),
            "accuracy_by_use_case": use_case_avg_accuracy,
            "revalidation_rate": round(revalidation_rate, 2),
            "avg_improvement_rate": 0.0,  # Would calculate from version comparisons
            "daily_sessions": daily_sessions_list,
            "daily_accuracy": daily_accuracy_list
        }

    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure"""
        return {
            "total_sessions": 0,
            "total_validations": 0,
            "avg_accuracy": 0.0,
            "avg_processing_time_ms": 0.0,
            "status_distribution": {},
            "discrepancy_trends": {},
            "discrepancy_by_category": {},
            "most_common_discrepancies": [],
            "recurring_issues": [],
            "sessions_by_use_case": {},
            "accuracy_by_use_case": {},
            "revalidation_rate": 0.0,
            "avg_improvement_rate": 0.0,
            "daily_sessions": [],
            "daily_accuracy": []
        }

    def _determine_final_status(self, session) -> str:
        """Determine final status from session"""
        severity_counts = {"critical": 0, "major": 0, "minor": 0}
        for disc in session.discrepancies:
            severity = disc.severity.lower()
            if severity in severity_counts:
                severity_counts[severity] += 1

        if severity_counts["critical"] > 0:
            return "failed"
        elif severity_counts["major"] > 0:
            return "partial"
        elif severity_counts["minor"] > 0:
            return "warning"
        else:
            return "passed"

    def _identify_recurring_issues(
        self, discrepancy_patterns: Dict[str, int]
    ) -> List[Dict[str, Any]]:
        """Identify recurring issues (appearing multiple times)"""
        recurring = [
            {"field": field, "occurrences": count, "severity": "high"}
            for field, count in discrepancy_patterns.items()
            if count >= 3  # Appears 3+ times
        ]
        return sorted(recurring, key=lambda x: x["occurrences"], reverse=True)[:10]

    async def get_use_case_analytics(
        self, use_case: str
    ) -> Dict[str, Any]:
        """
        Get analytics for a specific use case

        Args:
            use_case: Use case name

        Returns:
            Use case analytics
        """
        # Get sessions for this use case
        sessions = self._get_sessions_by_use_case(use_case)

        if not sessions:
            return {
                "use_case": use_case,
                "total_sessions": 0,
                "message": "No sessions found for this use case"
            }

        metrics = await self._calculate_metrics(sessions)

        return {
            "use_case": use_case,
            "total_sessions": metrics["total_sessions"],
            "avg_accuracy": metrics["avg_accuracy"],
            "status_distribution": metrics["status_distribution"],
            "common_discrepancies": metrics["most_common_discrepancies"],
            "trends": {
                "daily_sessions": metrics["daily_sessions"],
                "daily_accuracy": metrics["daily_accuracy"]
            }
        }

    def _get_sessions_by_use_case(self, use_case: str) -> List:
        """Get sessions for specific use case"""
        # Placeholder - would query database in production
        return []

    async def get_discrepancy_trends(
        self,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get discrepancy trends over time

        Args:
            days: Number of days to analyze

        Returns:
            Discrepancy trends
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        sessions = self._get_sessions_in_period(start_date, end_date)

        # Track daily discrepancy counts by severity
        daily_trends = defaultdict(lambda: defaultdict(int))

        for session in sessions:
            date_key = session.created_at.date().isoformat()
            for disc in session.discrepancies:
                severity = disc.severity.lower()
                daily_trends[date_key][severity] += 1

        # Format for charts
        trend_data = []
        for date_str in sorted(daily_trends.keys()):
            trend_data.append({
                "date": date_str,
                "critical": daily_trends[date_str]["critical"],
                "major": daily_trends[date_str]["major"],
                "minor": daily_trends[date_str]["minor"],
                "info": daily_trends[date_str]["info"],
                "total": sum(daily_trends[date_str].values())
            })

        return {
            "period_days": days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "trends": trend_data
        }


# Singleton instance
_analytics_engine_instance: Optional[AnalyticsEngine] = None


def get_analytics_engine() -> AnalyticsEngine:
    """
    Get singleton analytics engine instance

    Returns:
        AnalyticsEngine instance
    """
    global _analytics_engine_instance
    if _analytics_engine_instance is None:
        _analytics_engine_instance = AnalyticsEngine()
    return _analytics_engine_instance
