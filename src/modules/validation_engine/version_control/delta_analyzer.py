"""Delta analyzer for comparing validation versions"""

from typing import Dict, Any, List, Optional
from uuid import UUID

from ..core.base import IVersionComparator, ValidationContext, Discrepancy
from .version_models import (
    VersionComparison, DiscrepancyChange, ChangeType
)
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class DeltaAnalyzer(IVersionComparator):
    """
    Analyzes differences between validation versions

    Compares V1 vs V2 to identify:
    - Fixed discrepancies (in V1, not in V2)
    - New discrepancies (not in V1, in V2)
    - Persistent discrepancies (in both versions)
    - Improved/worsened severity
    - Value changes
    """

    def __init__(self):
        """Initialize delta analyzer"""
        logger.info("DeltaAnalyzer initialized")

    async def compare(
        self,
        previous_context: ValidationContext,
        current_context: ValidationContext
    ) -> VersionComparison:
        """
        Compare two validation versions

        Args:
            previous_context: Previous version (V1)
            current_context: Current version (V2)

        Returns:
            Detailed version comparison
        """
        logger.info(
            f"Comparing V{previous_context.version} "
            f"(session {previous_context.session_id}) vs "
            f"V{current_context.version} "
            f"(session {current_context.session_id})"
        )

        # Index discrepancies by field_name for quick lookup
        v1_discs = {d.field_name: d for d in previous_context.discrepancies}
        v2_discs = {d.field_name: d for d in current_context.discrepancies}

        # Analyze changes
        changes = []
        fixed_count = 0
        new_count = 0
        persistent_count = 0
        improved_count = 0
        worsened_count = 0

        # Find fixed discrepancies (in V1, not in V2)
        for field_name, v1_disc in v1_discs.items():
            if field_name not in v2_discs:
                change = self._create_fixed_change(field_name, v1_disc)
                changes.append(change)
                fixed_count += 1

        # Find new and persistent discrepancies
        for field_name, v2_disc in v2_discs.items():
            if field_name not in v1_discs:
                # New discrepancy (not in V1, in V2)
                change = self._create_new_change(field_name, v2_disc)
                changes.append(change)
                new_count += 1
            else:
                # Persistent discrepancy (in both versions)
                v1_disc = v1_discs[field_name]
                change = self._create_persistent_change(
                    field_name, v1_disc, v2_disc
                )
                changes.append(change)
                persistent_count += 1

                # Check for severity changes
                if v1_disc.severity != v2_disc.severity:
                    if self._is_improved(v1_disc.severity, v2_disc.severity):
                        improved_count += 1
                    else:
                        worsened_count += 1

        # Calculate metrics
        improvement_rate = (
            (fixed_count / len(v1_discs) * 100)
            if len(v1_discs) > 0 else 0.0
        )
        regression_rate = (
            (new_count / len(v1_discs) * 100)
            if len(v1_discs) > 0 else 0.0
        )

        # Get summary data
        v1_summary = self._get_summary(previous_context)
        v2_summary = self._get_summary(current_context)

        # Status comparison
        status_improved = self._is_status_improved(
            v1_summary.get("final_status"),
            v2_summary.get("final_status")
        )

        # Accuracy delta
        v1_accuracy = v1_summary.get("accuracy_score")
        v2_accuracy = v2_summary.get("accuracy_score")
        accuracy_delta = None
        if v1_accuracy is not None and v2_accuracy is not None:
            accuracy_delta = v2_accuracy - v1_accuracy

        comparison = VersionComparison(
            v1_session_id=previous_context.session_id,
            v1_version=previous_context.version,
            v2_session_id=current_context.session_id,
            v2_version=current_context.version,
            total_changes=len(changes),
            fixed_count=fixed_count,
            new_count=new_count,
            persistent_count=persistent_count,
            improved_count=improved_count,
            worsened_count=worsened_count,
            changes=changes,
            v1_discrepancy_count=len(previous_context.discrepancies),
            v2_discrepancy_count=len(current_context.discrepancies),
            improvement_rate=round(improvement_rate, 2),
            regression_rate=round(regression_rate, 2),
            v1_final_status=v1_summary.get("final_status"),
            v2_final_status=v2_summary.get("final_status"),
            status_improved=status_improved,
            v1_accuracy=v1_accuracy,
            v2_accuracy=v2_accuracy,
            accuracy_delta=accuracy_delta
        )

        logger.info(
            f"Comparison complete: {fixed_count} fixed, {new_count} new, "
            f"{persistent_count} persistent, improvement rate: {improvement_rate:.1f}%"
        )

        return comparison

    def _create_fixed_change(
        self, field_name: str, v1_disc: Discrepancy
    ) -> DiscrepancyChange:
        """Create change record for fixed discrepancy"""
        return DiscrepancyChange(
            field_name=field_name,
            change_type=ChangeType.FIXED,
            v1_present=True,
            v1_severity=v1_disc.severity,
            v1_source_value=v1_disc.source_value,
            v1_target_value=v1_disc.target_value,
            v1_confidence=v1_disc.confidence,
            v2_present=False,
            auto_fixed=v1_disc.auto_fix_applied or False
        )

    def _create_new_change(
        self, field_name: str, v2_disc: Discrepancy
    ) -> DiscrepancyChange:
        """Create change record for new discrepancy"""
        return DiscrepancyChange(
            field_name=field_name,
            change_type=ChangeType.NEW,
            v1_present=False,
            v2_present=True,
            v2_severity=v2_disc.severity,
            v2_source_value=v2_disc.source_value,
            v2_target_value=v2_disc.target_value,
            v2_confidence=v2_disc.confidence
        )

    def _create_persistent_change(
        self, field_name: str, v1_disc: Discrepancy, v2_disc: Discrepancy
    ) -> DiscrepancyChange:
        """Create change record for persistent discrepancy"""
        # Determine specific change type
        change_type = ChangeType.PERSISTENT

        severity_changed = v1_disc.severity != v2_disc.severity
        values_changed = (
            v1_disc.source_value != v2_disc.source_value or
            v1_disc.target_value != v2_disc.target_value
        )

        if severity_changed:
            if self._is_improved(v1_disc.severity, v2_disc.severity):
                change_type = ChangeType.IMPROVED
            else:
                change_type = ChangeType.WORSENED
        elif values_changed:
            change_type = ChangeType.VALUE_CHANGED

        return DiscrepancyChange(
            field_name=field_name,
            change_type=change_type,
            v1_present=True,
            v1_severity=v1_disc.severity,
            v1_source_value=v1_disc.source_value,
            v1_target_value=v1_disc.target_value,
            v1_confidence=v1_disc.confidence,
            v2_present=True,
            v2_severity=v2_disc.severity,
            v2_source_value=v2_disc.source_value,
            v2_target_value=v2_disc.target_value,
            v2_confidence=v2_disc.confidence,
            severity_changed=severity_changed,
            values_changed=values_changed,
            auto_fixed=v2_disc.auto_fix_applied or False
        )

    def _is_improved(self, v1_severity: str, v2_severity: str) -> bool:
        """Check if severity improved (decreased)"""
        severity_order = {"critical": 4, "major": 3, "minor": 2, "info": 1}
        v1_level = severity_order.get(v1_severity.lower(), 0)
        v2_level = severity_order.get(v2_severity.lower(), 0)
        return v2_level < v1_level

    def _is_status_improved(
        self, v1_status: Optional[str], v2_status: Optional[str]
    ) -> bool:
        """Check if final status improved"""
        if v1_status is None or v2_status is None:
            return False

        status_order = {
            "failed": 0,
            "partial": 1,
            "warning": 2,
            "passed": 3
        }

        v1_level = status_order.get(v1_status.lower(), 0)
        v2_level = status_order.get(v2_status.lower(), 0)

        return v2_level > v1_level

    def _get_summary(self, context: ValidationContext) -> Dict[str, Any]:
        """Get validation summary from context"""
        # Group discrepancies by severity
        severity_counts = {"critical": 0, "major": 0, "minor": 0, "info": 0}
        for disc in context.discrepancies:
            severity = disc.severity.lower()
            if severity in severity_counts:
                severity_counts[severity] += 1

        # Calculate accuracy
        total = len(context.validation_results)
        passed = sum(1 for r in context.validation_results if r.passed)
        accuracy = (passed / total * 100) if total > 0 else 0.0

        # Determine final status
        if severity_counts["critical"] > 0:
            final_status = "failed"
        elif severity_counts["major"] > 0:
            final_status = "partial"
        elif severity_counts["minor"] > 0:
            final_status = "warning"
        else:
            final_status = "passed"

        return {
            "total_validations": total,
            "passed_validations": passed,
            "total_discrepancies": len(context.discrepancies),
            "severity_counts": severity_counts,
            "accuracy_score": round(accuracy, 2),
            "final_status": final_status
        }

    async def get_change_summary(
        self, comparison: VersionComparison
    ) -> Dict[str, Any]:
        """
        Generate human-readable change summary

        Args:
            comparison: Version comparison result

        Returns:
            Summary with key insights
        """
        summary = {
            "overall_assessment": self._assess_changes(comparison),
            "key_metrics": {
                "fixed_discrepancies": comparison.fixed_count,
                "new_discrepancies": comparison.new_count,
                "persistent_discrepancies": comparison.persistent_count,
                "improvement_rate": f"{comparison.improvement_rate}%",
                "regression_rate": f"{comparison.regression_rate}%"
            },
            "status_change": {
                "from": comparison.v1_final_status,
                "to": comparison.v2_final_status,
                "improved": comparison.status_improved
            },
            "accuracy_change": {
                "v1": comparison.v1_accuracy,
                "v2": comparison.v2_accuracy,
                "delta": comparison.accuracy_delta
            },
            "critical_changes": self._get_critical_changes(comparison),
            "recommendations": self._generate_recommendations(comparison)
        }

        return summary

    def _assess_changes(self, comparison: VersionComparison) -> str:
        """Assess overall change quality"""
        if comparison.improvement_rate >= 80:
            return "Excellent: Most discrepancies resolved"
        elif comparison.improvement_rate >= 50:
            return "Good: Significant progress made"
        elif comparison.improvement_rate >= 25:
            return "Fair: Some improvements"
        elif comparison.regression_rate > comparison.improvement_rate:
            return "Concerning: More new issues than fixes"
        else:
            return "Minimal: Few changes detected"

    def _get_critical_changes(
        self, comparison: VersionComparison
    ) -> List[Dict[str, Any]]:
        """Extract critical changes requiring attention"""
        critical = []

        for change in comparison.changes:
            # New critical discrepancies
            if (change.change_type == ChangeType.NEW and
                    change.v2_severity == "critical"):
                critical.append({
                    "type": "new_critical",
                    "field": change.field_name,
                    "message": f"New critical issue detected in {change.field_name}"
                })

            # Worsened severity
            elif change.change_type == ChangeType.WORSENED:
                critical.append({
                    "type": "worsened",
                    "field": change.field_name,
                    "message": (
                        f"{change.field_name} severity worsened: "
                        f"{change.v1_severity} → {change.v2_severity}"
                    )
                })

            # Persistent critical issues
            elif (change.change_type == ChangeType.PERSISTENT and
                    change.v2_severity == "critical"):
                critical.append({
                    "type": "persistent_critical",
                    "field": change.field_name,
                    "message": f"Critical issue persists in {change.field_name}"
                })

        return critical[:10]  # Limit to top 10

    def _generate_recommendations(
        self, comparison: VersionComparison
    ) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []

        # Check for regression
        if comparison.regression_rate > 10:
            recommendations.append(
                "Review newly introduced discrepancies - "
                f"{comparison.new_count} new issues detected"
            )

        # Check for persistent critical issues
        persistent_critical = sum(
            1 for c in comparison.changes
            if c.change_type == ChangeType.PERSISTENT and
            c.v2_severity == "critical"
        )
        if persistent_critical > 0:
            recommendations.append(
                f"Address {persistent_critical} persistent critical issues "
                "requiring immediate attention"
            )

        # Check for worsened issues
        if comparison.worsened_count > 0:
            recommendations.append(
                f"Investigate {comparison.worsened_count} issues with "
                "increased severity"
            )

        # Positive progress
        if comparison.fixed_count > 0:
            recommendations.append(
                f"Good progress: {comparison.fixed_count} issues resolved"
            )

        # Accuracy improvement
        if comparison.accuracy_delta and comparison.accuracy_delta > 5:
            recommendations.append(
                f"Validation accuracy improved by {comparison.accuracy_delta:.1f}%"
            )

        return recommendations


# Singleton instance
_delta_analyzer_instance: Optional[DeltaAnalyzer] = None


def get_delta_analyzer() -> DeltaAnalyzer:
    """
    Get singleton delta analyzer instance

    Returns:
        DeltaAnalyzer instance
    """
    global _delta_analyzer_instance
    if _delta_analyzer_instance is None:
        _delta_analyzer_instance = DeltaAnalyzer()
    return _delta_analyzer_instance
