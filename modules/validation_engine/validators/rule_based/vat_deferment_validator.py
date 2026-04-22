"""
VAT Deferment Validator

Validates that BOE line items claiming VAT deferment under CPC code 40V02
have HS codes that appear on Nestle Ghana's approved VAT deferment list (URV 0014).

Checks:
1. Each line item HS code appears in the VAT deferment list
2. Flags any HS codes not eligible for VAT deferment
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from ...core.base import IValidator, ValidationResult, ValidationContext
from ...validators.validator_registry import ValidatorRegistry
from ...utils.constants import ValidatorType, Severity
from shared.utils.logger import get_logger

logger = get_logger(__name__)

_VAT_CACHE: Dict[str, Any] = {}


def _load_vat_data(path: str) -> Dict[str, Any]:
    if path in _VAT_CACHE:
        return _VAT_CACHE[path]
    full_path = Path(path)
    if not full_path.exists():
        full_path = Path(__file__).parents[4] / path
    with open(full_path, "r") as f:
        data = yaml.safe_load(f)
    _VAT_CACHE[path] = data
    return data


def _build_hs_index(items: List[Dict]) -> Dict[str, str]:
    """Return {normalised_hs: description} for fast lookup."""
    index: Dict[str, str] = {}
    for item in items:
        code = re.sub(r"[.\s]", "", str(item.get("hs_code", ""))).strip()
        desc = str(item.get("description", "")).strip()
        if code:
            index[code] = desc
    return index


def _normalize_hs(code: str) -> str:
    return re.sub(r"[.\s]", "", str(code)).strip()


@ValidatorRegistry.register("vat_deferment_validator")
class VATDefermentValidator(IValidator):
    """
    Validates BOE line items against the GRA VAT Deferment list (URV 0014).

    Triggered only when CPC code is 40V02 (VAT deferred imports).
    Checks that each line item HS code is on the approved deferment list.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.validator_type = ValidatorType.RULE_BASED
        self.validator_name = "vat_deferment_validator"

        self.data_path = config.get("vat_data_path", "config/data/vat_deferment_list.yaml")
        self.applicable_cpc_codes = config.get("applicable_cpc_codes", ["40V02"])
        self.customs_code_field = config.get("customs_code_field", "bill_of_entry.customs_code")
        self.line_items_field = config.get("line_items_field", "bill_of_entry.items")
        self.item_hs_field = config.get("item_hs_code_field", "hs_code")
        self.item_desc_field = config.get("item_description_field", "product_description")
        self.validations = config.get("validations", {})
        self.failure_severities = config.get("failure_severities", {})

    def supports_field_type(self, field_type: str) -> bool:
        return True

    async def validate(
        self,
        source_data: Dict[str, Any],
        target_data: Optional[Dict[str, Any]],
        context: ValidationContext,
    ) -> List[ValidationResult]:
        results: List[ValidationResult] = []

        # Load VAT deferment reference data
        try:
            vat_data = _load_vat_data(self.data_path)
        except Exception as exc:
            results.append(self._create_result(
                field_name="vat_deferment_data",
                passed=False,
                message=f"Could not load VAT deferment data from {self.data_path}: {exc}",
                severity=Severity.CRITICAL,
                source_value=None,
                target_value=None,
            ))
            return results

        hs_index = _build_hs_index(vat_data.get("items", []))
        urv_ref = vat_data.get("urv_reference", "URV 0014")

        # Skip entire validator if CPC code is not 40V02
        cpc_code = self._get_field_from_documents(self.customs_code_field, context)
        if cpc_code not in self.applicable_cpc_codes:
            return results

        # ── Check each line item HS code ──────────────────────────────────────
        if self.validations.get("check_item_eligibility", True):
            items = self._get_field_from_documents(self.line_items_field, context) or []
            eligible_count = 0
            for idx, item in enumerate(items):
                raw_hs = item.get(self.item_hs_field) if isinstance(item, dict) else None
                if not raw_hs:
                    continue
                normalized = _normalize_hs(str(raw_hs))
                desc = item.get(self.item_desc_field, "") if isinstance(item, dict) else ""
                if normalized in hs_index:
                    eligible_count += 1
                    results.append(self._create_result(
                        field_name=f"items[{idx}].hs_code",
                        passed=True,
                        message=(
                            f"HS code '{raw_hs}' is on the VAT deferment list ({urv_ref}). "
                            f"VAT deferment under CPC {cpc_code} confirmed."
                        ),
                        severity=Severity.INFO,
                        source_value=raw_hs,
                        target_value=hs_index[normalized],
                    ))
                else:
                    results.append(self._create_result(
                        field_name=f"items[{idx}].hs_code",
                        passed=False,
                        message=(
                            f"HS code '{raw_hs}' ({desc}) is NOT on the VAT deferment list "
                            f"({urv_ref}). VAT deferment under CPC {cpc_code} cannot be applied."
                        ),
                        severity=self._sev("item_not_on_deferment_list", Severity.MAJOR),
                        source_value=raw_hs,
                        target_value=f"approved HS code from VAT deferment list ({urv_ref})",
                    ))

        return results

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _sev(self, key: str, default: str) -> str:
        raw = self.failure_severities.get(key)
        if raw and hasattr(Severity, raw.upper()):
            return getattr(Severity, raw.upper())
        return default

    def _get_field_from_documents(self, field_path: str, context: ValidationContext) -> Any:
        if not field_path:
            return None
        parts = field_path.split(".")
        if len(parts) < 2:
            return None
        doc_type = parts[0]
        field_name = ".".join(parts[1:])
        if doc_type in context.normalized_data:
            return self._get_nested_value(context.normalized_data[doc_type], field_name)
        if doc_type in context.documents:
            return self._get_nested_value(context.documents[doc_type], field_name)
        return None

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        try:
            value = data
            for key in path.split("."):
                if isinstance(value, dict):
                    value = value.get(key)
                else:
                    return None
                if value is None:
                    return None
            return value
        except (KeyError, TypeError, AttributeError):
            return None

    def _create_result(
        self,
        field_name: str,
        passed: bool,
        message: str,
        severity: str,
        source_value: Any,
        target_value: Any,
        confidence: float = 1.0,
        metadata: Optional[Dict] = None,
    ) -> ValidationResult:
        return ValidationResult(
            validator_name=self.validator_name,
            validator_type=self.validator_type,
            field_name=field_name,
            source_value=source_value,
            target_value=target_value,
            passed=passed,
            confidence=confidence,
            severity=severity,
            message=message,
            metadata=metadata or {},
        )
