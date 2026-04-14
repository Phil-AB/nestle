"""Discrepancy classifier - classifies severity, category, and type"""

from typing import Dict, Any, List, Optional
from decimal import Decimal
from ...core.base import Discrepancy, ValidationContext
from ...core.config_loader import get_config_loader
from ...utils.constants import (
    Severity, DiscrepancyType, DiscrepancyCategory, LikelyCause
)
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class DiscrepancyClassifier:
    """
    Classify discrepancies by severity, category, and likely cause

    Uses config-driven rules to determine:
    - Severity: critical, major, minor, info
    - Category: hs_code, weight, duty, currency, etc.
    - Type: value_mismatch, missing_field, calculation_error, etc.
    - Likely cause: OCR error, calculation error, format difference, etc.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize discrepancy classifier

        Args:
            config: Classification configuration
        """
        self.config = config or {}

        # Load config
        config_loader = get_config_loader()

        # Get classification rules from use case config
        self.classification_rules = {}

        logger.info("DiscrepancyClassifier initialized")

    async def classify(
        self,
        discrepancy: Discrepancy,
        context: ValidationContext
    ) -> Discrepancy:
        """
        Classify a discrepancy

        Args:
            discrepancy: Discrepancy to classify
            context: Validation context

        Returns:
            Classified discrepancy
        """
        # Get classification rules from use case config
        use_case_config = context.config.get("use_case", {})
        disc_handling = use_case_config.get("discrepancy_handling", {})
        classification_config = disc_handling.get("classification", {})

        if not classification_config.get("enabled", False):
            return discrepancy

        # Type must be classified BEFORE severity — severity rules check discrepancy_type
        # and the default type (VALUE_MISMATCH) would cause incorrect matches otherwise.
        discrepancy = self._classify_type(discrepancy, context)

        # Classify severity (now has correct type to match against rules)
        discrepancy = self._classify_severity(
            discrepancy,
            classification_config,
            context
        )

        # Classify category and likely cause
        discrepancy = self._classify_category(discrepancy, context)
        discrepancy = self._determine_likely_cause(discrepancy, context)

        logger.debug(
            f"Classified discrepancy '{discrepancy.field_name}': "
            f"{discrepancy.severity} {discrepancy.category}"
        )

        return discrepancy

    def _classify_severity(
        self,
        discrepancy: Discrepancy,
        classification_config: Dict[str, Any],
        context: ValidationContext
    ) -> Discrepancy:
        """
        Classify discrepancy severity based on rules

        Args:
            discrepancy: Discrepancy to classify
            classification_config: Classification configuration
            context: Validation context

        Returns:
            Discrepancy with severity set
        """
        severity_rules = classification_config.get("severity_rules", {})

        field_name = discrepancy.field_name.lower()

        # Check critical rules
        for pattern in severity_rules.get("critical", []):
            if self._matches_pattern(pattern, field_name, discrepancy):
                discrepancy.severity = Severity.CRITICAL
                return discrepancy

        # Check major rules
        for pattern in severity_rules.get("major", []):
            if self._matches_pattern(pattern, field_name, discrepancy):
                discrepancy.severity = Severity.MAJOR
                return discrepancy

        # Check minor rules
        for pattern in severity_rules.get("minor", []):
            if self._matches_pattern(pattern, field_name, discrepancy):
                discrepancy.severity = Severity.MINOR
                return discrepancy

        # Check info rules
        for pattern in severity_rules.get("info", []):
            if self._matches_pattern(pattern, field_name, discrepancy):
                discrepancy.severity = Severity.INFO
                return discrepancy

        # Default severity
        return discrepancy

    def _matches_pattern(
        self,
        pattern: str,
        field_name: str,
        discrepancy: Discrepancy
    ) -> bool:
        """
        Check if discrepancy matches a severity pattern

        Args:
            pattern: Pattern to match (e.g., "hs_code mismatch")
            field_name: Field name
            discrepancy: Discrepancy

        Returns:
            True if matches
        """
        pattern_lower = pattern.lower()

        # Check field name
        if field_name in pattern_lower:
            return True

        # Check for specific patterns
        if "mismatch" in pattern_lower and discrepancy.discrepancy_type == DiscrepancyType.VALUE_MISMATCH:
            return True

        if "missing" in pattern_lower and discrepancy.discrepancy_type == DiscrepancyType.MISSING_FIELD:
            return True

        # Check percentage differences
        if ">" in pattern_lower or "<" in pattern_lower:
            try:
                # Extract percentage from pattern (e.g., "error > 5%")
                import re
                match = re.search(r'(>|<)\s*(\d+(?:\.\d+)?)%', pattern_lower)
                if match:
                    operator = match.group(1)
                    threshold = float(match.group(2))

                    # Calculate percentage difference
                    if discrepancy.source_value and discrepancy.target_value:
                        try:
                            source = float(discrepancy.source_value)
                            target = float(discrepancy.target_value)

                            if target != 0:
                                pct_diff = abs((source - target) / target * 100)

                                if operator == ">" and pct_diff > threshold:
                                    return True
                                elif operator == "<" and pct_diff < threshold:
                                    return True
                        except:
                            pass
            except:
                pass

        return False

    def _classify_category(
        self,
        discrepancy: Discrepancy,
        context: ValidationContext
    ) -> Discrepancy:
        """
        Classify discrepancy category

        Args:
            discrepancy: Discrepancy to classify
            context: Validation context

        Returns:
            Discrepancy with category set
        """
        field_name = discrepancy.field_name.lower()

        # HS Code
        if any(term in field_name for term in ["hs_code", "hsn_code", "tariff_code"]):
            discrepancy.category = DiscrepancyCategory.HS_CODE

        # Weight
        elif any(term in field_name for term in ["weight", "poids"]):
            discrepancy.category = DiscrepancyCategory.WEIGHT

        # Duty
        elif any(term in field_name for term in ["duty", "tax", "tarif", "droits"]):
            discrepancy.category = DiscrepancyCategory.DUTY

        # Currency/Price
        elif any(term in field_name for term in ["price", "amount", "value", "currency", "montant", "valeur"]):
            discrepancy.category = DiscrepancyCategory.CURRENCY

        # Quantity
        elif any(term in field_name for term in ["quantity", "qty", "quantité"]):
            discrepancy.category = DiscrepancyCategory.QUANTITY

        # Date
        elif any(term in field_name for term in ["date", "datetime"]):
            discrepancy.category = DiscrepancyCategory.DATE

        # Calculation
        elif "calculation" in discrepancy.metadata.get("source", "").lower():
            discrepancy.category = DiscrepancyCategory.CALCULATION

        # Other
        else:
            discrepancy.category = DiscrepancyCategory.OTHER

        return discrepancy

    def _classify_type(
        self,
        discrepancy: Discrepancy,
        context: ValidationContext
    ) -> Discrepancy:
        """
        Classify discrepancy type

        Args:
            discrepancy: Discrepancy to classify
            context: Validation context

        Returns:
            Discrepancy with type set
        """
        # Check if values are missing
        if discrepancy.source_value is None or discrepancy.target_value is None:
            discrepancy.discrepancy_type = DiscrepancyType.MISSING_FIELD

        # Check if it's a calculation error
        elif "calculation" in discrepancy.metadata.get("source", "").lower():
            discrepancy.discrepancy_type = DiscrepancyType.CALCULATION_ERROR

        # Check if values are different types
        elif type(discrepancy.source_value) != type(discrepancy.target_value):
            discrepancy.discrepancy_type = DiscrepancyType.TYPE_MISMATCH

        # Check if it's a format difference
        elif self._is_format_difference(discrepancy):
            discrepancy.discrepancy_type = DiscrepancyType.FORMAT_DIFFERENCE

        # Default: value mismatch
        else:
            discrepancy.discrepancy_type = DiscrepancyType.VALUE_MISMATCH

        return discrepancy

    def _determine_likely_cause(
        self,
        discrepancy: Discrepancy,
        context: ValidationContext
    ) -> Discrepancy:
        """
        Determine likely cause of discrepancy

        Args:
            discrepancy: Discrepancy to analyze
            context: Validation context

        Returns:
            Discrepancy with likely_cause set
        """
        # Format differences
        if discrepancy.discrepancy_type == DiscrepancyType.FORMAT_DIFFERENCE:
            discrepancy.likely_cause = LikelyCause.FORMAT_DIFFERENCE

        # Missing data
        elif discrepancy.discrepancy_type == DiscrepancyType.MISSING_FIELD:
            discrepancy.likely_cause = LikelyCause.MISSING_DATA

        # Calculation errors
        elif discrepancy.discrepancy_type == DiscrepancyType.CALCULATION_ERROR:
            discrepancy.likely_cause = LikelyCause.CALCULATION_ERROR

        # Small differences (likely rounding or measurement)
        elif self._is_small_difference(discrepancy):
            if discrepancy.category == DiscrepancyCategory.WEIGHT:
                discrepancy.likely_cause = "measurement variation"
            else:
                discrepancy.likely_cause = LikelyCause.ROUNDING_DIFFERENCE

        # Unit differences
        elif self._is_unit_difference(discrepancy):
            discrepancy.likely_cause = LikelyCause.UNIT_DIFFERENCE

        # Large differences (likely OCR or typo)
        elif self._is_large_difference(discrepancy):
            discrepancy.likely_cause = LikelyCause.OCR_ERROR

        # Unknown
        else:
            discrepancy.likely_cause = LikelyCause.UNKNOWN

        return discrepancy

    def _is_format_difference(self, discrepancy: Discrepancy) -> bool:
        """Check if discrepancy is a format difference"""
        if not isinstance(discrepancy.source_value, str):
            return False
        if not isinstance(discrepancy.target_value, str):
            return False

        # Remove formatting and compare
        source_clean = discrepancy.source_value.replace(" ", "").replace(",", "").lower()
        target_clean = discrepancy.target_value.replace(" ", "").replace(",", "").lower()

        return source_clean == target_clean

    def _is_small_difference(self, discrepancy: Discrepancy) -> bool:
        """Check if discrepancy is a small numeric difference (< 2%)"""
        try:
            source = float(discrepancy.source_value)
            target = float(discrepancy.target_value)

            if target != 0:
                pct_diff = abs((source - target) / target * 100)
                return pct_diff < 2.0
        except:
            pass

        return False

    def _is_large_difference(self, discrepancy: Discrepancy) -> bool:
        """Check if discrepancy is a large numeric difference (> 10%)"""
        try:
            source = float(discrepancy.source_value)
            target = float(discrepancy.target_value)

            if target != 0:
                pct_diff = abs((source - target) / target * 100)
                return pct_diff > 10.0
        except:
            pass

        return False

    def _is_unit_difference(self, discrepancy: Discrepancy) -> bool:
        """Check if discrepancy might be due to unit differences"""
        # Common unit conversion factors
        factors = [0.453592, 1000, 0.001, 2.20462]  # LBS/KG, MT/KG, etc.

        try:
            source = float(discrepancy.source_value)
            target = float(discrepancy.target_value)

            if target != 0:
                ratio = source / target

                # Check if ratio matches a known conversion factor
                for factor in factors:
                    if abs(ratio - factor) < 0.01 or abs(ratio - (1/factor)) < 0.01:
                        return True
        except:
            pass

        return False


# Singleton instance
_discrepancy_classifier_instance: Optional[DiscrepancyClassifier] = None


def get_discrepancy_classifier() -> DiscrepancyClassifier:
    """
    Get singleton discrepancy classifier instance

    Returns:
        DiscrepancyClassifier instance
    """
    global _discrepancy_classifier_instance
    if _discrepancy_classifier_instance is None:
        _discrepancy_classifier_instance = DiscrepancyClassifier()
    return _discrepancy_classifier_instance
