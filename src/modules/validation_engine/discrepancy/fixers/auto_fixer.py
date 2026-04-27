"""Auto-fixer for common discrepancies"""

from typing import Dict, Any, Optional
from ...core.base import Discrepancy, ValidationContext
from ...normalization import get_normalization_engine
from ...utils.constants import (
    DiscrepancyType, DiscrepancyCategory, AutoFixType
)
from shared.utils.logger import get_logger

logger = get_logger(__name__)


class AutoFixer:
    """
    Automatically fix common discrepancies

    Fixes:
    - Format differences (dates, decimals, currencies)
    - Unit conversions (weights, currencies)
    - Synonym resolution (field name variations)
    - Whitespace/case differences
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize auto-fixer

        Args:
            config: Auto-fix configuration
        """
        self.config = config or {}
        self.norm_engine = get_normalization_engine()

        logger.info("AutoFixer initialized")

    async def can_fix(
        self,
        discrepancy: Discrepancy,
        context: ValidationContext
    ) -> bool:
        """
        Determine if discrepancy can be auto-fixed

        Args:
            discrepancy: Discrepancy to check
            context: Validation context

        Returns:
            True if auto-fixable
        """
        # Check if auto-fix enabled in config
        use_case_config = context.config.get("use_case", {})
        disc_handling = use_case_config.get("discrepancy_handling", {})
        auto_fix_config = disc_handling.get("auto_fix", {})

        if not auto_fix_config.get("enabled", False):
            return False

        # Check if this type of issue is auto-fixable
        auto_fix_rules = auto_fix_config.get("rules", [])

        for rule in auto_fix_rules:
            fix_type = rule.get("type")
            fixable_issues = rule.get("issues", [])

            # Format normalization
            if fix_type == AutoFixType.FORMAT_NORMALIZATION:
                if discrepancy.discrepancy_type == DiscrepancyType.FORMAT_DIFFERENCE:
                    return True
                if discrepancy.category == DiscrepancyCategory.DATE:
                    return True

            # Unit conversion
            elif fix_type == AutoFixType.UNIT_CONVERSION:
                if "unit" in discrepancy.likely_cause.lower():
                    return True

            # Synonym resolution
            elif fix_type == AutoFixType.SYNONYM_RESOLUTION:
                if "synonym" in discrepancy.likely_cause.lower():
                    return True

        # Check based on likely cause
        auto_fixable_causes = [
            "format difference",
            "unit difference",
            "synonym variation",
            "rounding difference"
        ]

        return any(cause in discrepancy.likely_cause.lower() for cause in auto_fixable_causes)

    async def fix(
        self,
        discrepancy: Discrepancy,
        context: ValidationContext
    ) -> Optional[Dict[str, Any]]:
        """
        Attempt to auto-fix discrepancy

        Args:
            discrepancy: Discrepancy to fix
            context: Validation context

        Returns:
            Fixed value dict or None if fix failed
        """
        try:
            # Format normalization
            if discrepancy.discrepancy_type == DiscrepancyType.FORMAT_DIFFERENCE:
                return await self._fix_format(discrepancy, context)

            # Unit conversion
            if "unit" in discrepancy.likely_cause.lower():
                return await self._fix_unit(discrepancy, context)

            # Whitespace/case
            if self._is_whitespace_difference(discrepancy):
                return self._fix_whitespace(discrepancy, context)

            return None

        except Exception as e:
            logger.error(f"Auto-fix failed for '{discrepancy.field_name}': {str(e)}")
            return None

    async def _fix_format(
        self,
        discrepancy: Discrepancy,
        context: ValidationContext
    ) -> Optional[Dict[str, Any]]:
        """Fix format differences"""
        # Date normalization
        if discrepancy.category == DiscrepancyCategory.DATE:
            try:
                from ...normalization.normalizers.format_normalizer import FormatNormalizer
                normalizer = FormatNormalizer()

                source_normalized = normalizer.normalize_date(discrepancy.source_value)
                target_normalized = normalizer.normalize_date(discrepancy.target_value)

                if source_normalized == target_normalized:
                    return {
                        "fix_type": AutoFixType.FORMAT_NORMALIZATION,
                        "original_source": discrepancy.source_value,
                        "original_target": discrepancy.target_value,
                        "normalized_source": source_normalized,
                        "normalized_target": target_normalized,
                        "match": True
                    }
            except:
                pass

        # Decimal normalization
        elif discrepancy.category == DiscrepancyCategory.CURRENCY:
            try:
                from ...normalization.normalizers.format_normalizer import FormatNormalizer
                normalizer = FormatNormalizer()

                source_normalized = float(normalizer.normalize_decimal(discrepancy.source_value))
                target_normalized = float(normalizer.normalize_decimal(discrepancy.target_value))

                if abs(source_normalized - target_normalized) < 0.01:
                    return {
                        "fix_type": AutoFixType.FORMAT_NORMALIZATION,
                        "original_source": discrepancy.source_value,
                        "original_target": discrepancy.target_value,
                        "normalized_source": source_normalized,
                        "normalized_target": target_normalized,
                        "match": True
                    }
            except:
                pass

        return None

    async def _fix_unit(
        self,
        discrepancy: Discrepancy,
        context: ValidationContext
    ) -> Optional[Dict[str, Any]]:
        """Fix unit conversion issues"""
        if discrepancy.category != DiscrepancyCategory.WEIGHT:
            return None

        try:
            from ...normalization.normalizers.unit_converter import UnitConverter
            converter = UnitConverter()

            # Try common conversions
            units = ["LBS", "MT", "G", "TON"]

            source_value = float(discrepancy.source_value)

            for unit in units:
                try:
                    converted = await converter.convert_weight(source_value, unit, "KG")
                    target_value = float(discrepancy.target_value)

                    # Check if conversion matches
                    if abs(converted - target_value) < target_value * 0.01:  # Within 1%
                        return {
                            "fix_type": AutoFixType.UNIT_CONVERSION,
                            "original_value": source_value,
                            "original_unit": unit,
                            "converted_value": float(converted),
                            "target_unit": "KG",
                            "match": True
                        }
                except:
                    continue

        except:
            pass

        return None

    def _fix_whitespace(
        self,
        discrepancy: Discrepancy,
        context: ValidationContext
    ) -> Optional[Dict[str, Any]]:
        """Fix whitespace/case differences"""
        try:
            from ...normalization.normalizers.format_normalizer import FormatNormalizer
            normalizer = FormatNormalizer()

            source_normalized = normalizer.normalize_whitespace(str(discrepancy.source_value))
            target_normalized = normalizer.normalize_whitespace(str(discrepancy.target_value))

            if source_normalized.lower() == target_normalized.lower():
                return {
                    "fix_type": "whitespace_normalization",
                    "original_source": discrepancy.source_value,
                    "original_target": discrepancy.target_value,
                    "normalized_source": source_normalized,
                    "normalized_target": target_normalized,
                    "match": True
                }
        except:
            pass

        return None

    def _is_whitespace_difference(self, discrepancy: Discrepancy) -> bool:
        """Check if discrepancy is just whitespace/case"""
        if not isinstance(discrepancy.source_value, str):
            return False
        if not isinstance(discrepancy.target_value, str):
            return False

        source_clean = "".join(discrepancy.source_value.lower().split())
        target_clean = "".join(discrepancy.target_value.lower().split())

        return source_clean == target_clean


# Singleton instance
_auto_fixer_instance: Optional[AutoFixer] = None


def get_auto_fixer() -> AutoFixer:
    """
    Get singleton auto-fixer instance

    Returns:
        AutoFixer instance
    """
    global _auto_fixer_instance
    if _auto_fixer_instance is None:
        _auto_fixer_instance = AutoFixer()
    return _auto_fixer_instance
