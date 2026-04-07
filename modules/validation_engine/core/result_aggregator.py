"""Result aggregator for validation engine"""

from typing import List, Dict, Any, Optional
from uuid import UUID

from .base import (
    ValidationResult, Discrepancy, ValidationContext,
    ValidationResultSummary
)
from ..utils.constants import Severity, FinalStatus
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class ResultAggregator:
    """
    Aggregate and analyze validation results

    Provides:
    - Result summarization
    - Discrepancy grouping
    - Status determination
    - Metrics calculation
    """

    @staticmethod
    def aggregate_results(
        results: List[ValidationResult]
    ) -> Dict[str, Any]:
        """
        Aggregate validation results

        Args:
            results: List of validation results

        Returns:
            Dictionary with aggregated results
        """
        if not results:
            return {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "by_validator": {},
                "by_severity": {},
                "average_confidence": 0.0
            }

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed

        # Group by validator
        by_validator: Dict[str, Dict[str, int]] = {}
        for result in results:
            if result.validator_name not in by_validator:
                by_validator[result.validator_name] = {
                    "total": 0,
                    "passed": 0,
                    "failed": 0
                }

            by_validator[result.validator_name]["total"] += 1
            if result.passed:
                by_validator[result.validator_name]["passed"] += 1
            else:
                by_validator[result.validator_name]["failed"] += 1

        # Group by severity
        by_severity = {
            Severity.CRITICAL: 0,
            Severity.MAJOR: 0,
            Severity.MINOR: 0,
            Severity.INFO: 0
        }
        for result in results:
            if not result.passed:
                by_severity[result.severity] = by_severity.get(result.severity, 0) + 1

        # Calculate average confidence
        avg_confidence = sum(r.confidence for r in results) / total

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / total if total > 0 else 0.0,
            "by_validator": by_validator,
            "by_severity": by_severity,
            "average_confidence": avg_confidence
        }

    @staticmethod
    def aggregate_discrepancies(
        discrepancies: List[Discrepancy]
    ) -> Dict[str, Any]:
        """
        Aggregate discrepancies

        Args:
            discrepancies: List of discrepancies

        Returns:
            Dictionary with aggregated discrepancies
        """
        if not discrepancies:
            return {
                "total": 0,
                "by_severity": {},
                "by_category": {},
                "by_type": {},
                "auto_fixable": 0,
                "auto_fixed": 0,
                "user_confirmed": 0,
                "user_rejected": 0,
                "pending_confirmation": 0
            }

        total = len(discrepancies)

        # Group by severity
        by_severity = {
            Severity.CRITICAL: 0,
            Severity.MAJOR: 0,
            Severity.MINOR: 0,
            Severity.INFO: 0
        }
        for d in discrepancies:
            by_severity[d.severity] = by_severity.get(d.severity, 0) + 1

        # Group by category
        by_category: Dict[str, int] = {}
        for d in discrepancies:
            by_category[d.category] = by_category.get(d.category, 0) + 1

        # Group by type
        by_type: Dict[str, int] = {}
        for d in discrepancies:
            by_type[d.discrepancy_type] = by_type.get(d.discrepancy_type, 0) + 1

        # Count auto-fix stats
        auto_fixable = sum(1 for d in discrepancies if d.auto_fixable)
        auto_fixed = sum(1 for d in discrepancies if d.auto_fixed)

        # Count user confirmations
        user_confirmed = sum(
            1 for d in discrepancies if d.user_confirmed is True
        )
        user_rejected = sum(
            1 for d in discrepancies if d.user_confirmed is False
        )
        pending = sum(
            1 for d in discrepancies if d.user_confirmed is None
        )

        return {
            "total": total,
            "by_severity": by_severity,
            "by_category": by_category,
            "by_type": by_type,
            "auto_fixable": auto_fixable,
            "auto_fixed": auto_fixed,
            "auto_fix_rate": auto_fixed / auto_fixable if auto_fixable > 0 else 0.0,
            "user_confirmed": user_confirmed,
            "user_rejected": user_rejected,
            "pending_confirmation": pending
        }

    @staticmethod
    def determine_final_status(
        context: ValidationContext,
        summary: ValidationResultSummary
    ) -> str:
        """
        Determine final validation status

        Args:
            context: Validation context
            summary: Validation result summary

        Returns:
            Final status (passed, failed, requires_attention, false_positive)
        """
        # If all validations passed and no critical/major discrepancies
        if (summary.all_validations_passed and
            summary.critical_discrepancies == 0 and
            summary.major_discrepancies == 0):
            return FinalStatus.PASSED

        # If has critical discrepancies
        if summary.critical_discrepancies > 0:
            # Check if user rejected all critical discrepancies as false positives
            critical_discrepancies = [
                d for d in context.discrepancies
                if d.severity == Severity.CRITICAL
            ]
            all_rejected = all(
                d.user_confirmed is False
                for d in critical_discrepancies
            )
            if all_rejected:
                return FinalStatus.FALSE_POSITIVE

            return FinalStatus.FAILED

        # If requires user confirmation
        if summary.requires_user_confirmation:
            return FinalStatus.REQUIRES_ATTENTION

        # If has major discrepancies but some auto-fixed
        if summary.major_discrepancies > 0:
            return FinalStatus.REQUIRES_ATTENTION

        # If only minor or info discrepancies
        if summary.minor_discrepancies > 0 or summary.info_discrepancies > 0:
            return FinalStatus.REQUIRES_ATTENTION

        # Default to failed if something went wrong
        return FinalStatus.FAILED

    @staticmethod
    def group_discrepancies_by_field(
        discrepancies: List[Discrepancy]
    ) -> Dict[str, List[Discrepancy]]:
        """
        Group discrepancies by field name

        Args:
            discrepancies: List of discrepancies

        Returns:
            Dictionary mapping field names to discrepancies
        """
        grouped: Dict[str, List[Discrepancy]] = {}

        for discrepancy in discrepancies:
            field = discrepancy.field_name
            if field not in grouped:
                grouped[field] = []
            grouped[field].append(discrepancy)

        return grouped

    @staticmethod
    def group_discrepancies_by_severity(
        discrepancies: List[Discrepancy]
    ) -> Dict[str, List[Discrepancy]]:
        """
        Group discrepancies by severity

        Args:
            discrepancies: List of discrepancies

        Returns:
            Dictionary mapping severity to discrepancies
        """
        grouped = {
            Severity.CRITICAL: [],
            Severity.MAJOR: [],
            Severity.MINOR: [],
            Severity.INFO: []
        }

        for discrepancy in discrepancies:
            severity = discrepancy.severity
            if severity in grouped:
                grouped[severity].append(discrepancy)

        return grouped

    @staticmethod
    def get_top_discrepancies(
        discrepancies: List[Discrepancy],
        limit: int = 10,
        by_severity: bool = True
    ) -> List[Discrepancy]:
        """
        Get top N discrepancies

        Args:
            discrepancies: List of discrepancies
            limit: Maximum number to return
            by_severity: Sort by severity (True) or confidence (False)

        Returns:
            List of top discrepancies
        """
        if by_severity:
            # Sort by severity priority: critical > major > minor > info
            severity_order = {
                Severity.CRITICAL: 0,
                Severity.MAJOR: 1,
                Severity.MINOR: 2,
                Severity.INFO: 3
            }
            sorted_discrepancies = sorted(
                discrepancies,
                key=lambda d: (severity_order.get(d.severity, 4), -d.confidence)
            )
        else:
            # Sort by confidence (lowest first = least certain)
            sorted_discrepancies = sorted(
                discrepancies,
                key=lambda d: d.confidence
            )

        return sorted_discrepancies[:limit]

    @staticmethod
    def calculate_accuracy_metrics(
        context: ValidationContext
    ) -> Dict[str, float]:
        """
        Calculate accuracy metrics

        Args:
            context: Validation context

        Returns:
            Dictionary with accuracy metrics
        """
        results = context.validation_results

        if not results:
            return {
                "overall_accuracy": 0.0,
                "average_confidence": 0.0,
                "precision": 0.0,
                "recall": 0.0
            }

        # Overall accuracy (pass rate)
        passed = sum(1 for r in results if r.passed)
        overall_accuracy = passed / len(results)

        # Average confidence
        avg_confidence = sum(r.confidence for r in results) / len(results)

        # Precision and recall (if ground truth available)
        # For now, use confidence as proxy
        precision = avg_confidence
        recall = avg_confidence

        return {
            "overall_accuracy": overall_accuracy,
            "average_confidence": avg_confidence,
            "precision": precision,
            "recall": recall
        }

    @staticmethod
    def generate_validation_report(
        context: ValidationContext,
        summary: ValidationResultSummary
    ) -> Dict[str, Any]:
        """
        Generate comprehensive validation report

        Args:
            context: Validation context
            summary: Validation result summary

        Returns:
            Dictionary with complete validation report
        """
        final_status = ResultAggregator.determine_final_status(context, summary)

        results_agg = ResultAggregator.aggregate_results(
            context.validation_results
        )

        discrepancies_agg = ResultAggregator.aggregate_discrepancies(
            context.discrepancies
        )

        accuracy = ResultAggregator.calculate_accuracy_metrics(context)

        # Group discrepancies
        discrepancies_by_severity = ResultAggregator.group_discrepancies_by_severity(
            context.discrepancies
        )
        discrepancies_by_field = ResultAggregator.group_discrepancies_by_field(
            context.discrepancies
        )

        # Get top discrepancies
        top_discrepancies = ResultAggregator.get_top_discrepancies(
            context.discrepancies,
            limit=10
        )

        return {
            "session_id": str(context.session_id),
            "use_case": context.use_case,
            "version": context.version,
            "is_revalidation": context.is_revalidation,
            "final_status": final_status,
            "summary": summary.dict(),
            "results": results_agg,
            "discrepancies": discrepancies_agg,
            "accuracy": accuracy,
            "grouped_discrepancies": {
                "by_severity": {
                    k: [d.dict() for d in v]
                    for k, v in discrepancies_by_severity.items()
                },
                "by_field": {
                    k: [d.dict() for d in v]
                    for k, v in discrepancies_by_field.items()
                }
            },
            "top_discrepancies": [d.dict() for d in top_discrepancies],
            "documents": {
                "primary": context.primary_document,
                "supporting": context.supporting_documents
            },
            "user_provided_data": context.user_provided_data,
            "timestamps": {
                "created_at": context.created_at.isoformat(),
                "updated_at": context.updated_at.isoformat()
            }
        }
