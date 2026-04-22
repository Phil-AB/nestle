"""
Concession Eligibility Validator

Validates that BOE line items claiming zero duty under CPC codes 40U01/40W01
are approved under Nestle Ghana's Master Concession (MD202601CUSTCU030000003304).

Checks:
1. Concession reference number matches what is declared on the BOE
2. Concession has not expired (expiry date from master_concession.yaml)
3. Each line item HS code appears in the approved concession items list
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from ...core.base import IValidator, ValidationResult, ValidationContext
from ...validators.validator_registry import ValidatorRegistry
from ...utils.constants import ValidatorType, Severity
from shared.utils.logger import get_logger

logger = get_logger(__name__)

_CONCESSION_CACHE: Dict[str, Any] = {}


def _load_concession_data(path: str) -> Dict[str, Any]:
    if path in _CONCESSION_CACHE:
        return _CONCESSION_CACHE[path]
    full_path = Path(path)
    if not full_path.exists():
        full_path = Path(__file__).parents[4] / path
    with open(full_path, "r") as f:
        data = yaml.safe_load(f)
    _CONCESSION_CACHE[path] = data
    return data


def _build_hs_index(items: List[Dict]) -> Dict[str, List[str]]:
    index: Dict[str, List[str]] = {}
    for item in items:
        code = re.sub(r"[.\s]", "", str(item.get("hs_code", ""))).strip()
        desc = str(item.get("description", "")).strip().upper()
        index.setdefault(code, []).append(desc)
    return index


def _normalize_hs(code: str) -> str:
    return re.sub(r"[.\s]", "", str(code)).strip()


@ValidatorRegistry.register("concession_eligibility_validator")
class ConcessionEligibilityValidator(IValidator):
    """
    Validates BOE line items against the GRA Master Concession approval list.

    Triggered only when CPC code is 40U01 or 40W01 (duty-exempted imports).
    Checks concession reference number, expiry date, and per-item HS code eligibility.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.validator_type = ValidatorType.RULE_BASED
        self.validator_name = "concession_eligibility_validator"

        self.data_path = config.get("concession_data_path", "config/data/master_concession.yaml")
        self.applicable_cpc_codes = config.get("applicable_cpc_codes", ["40U01", "40W01"])
        self.customs_code_field = config.get("customs_code_field", "bill_of_entry.customs_code")
        self.concession_ref_field = config.get("concession_ref_field", "bill_of_entry.etls_approval_number")
        self.shipment_date_field = config.get("shipment_date_field", "bill_of_entry.declaration_date")
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
        context: ValidationContext
    ) -> List[ValidationResult]:
        results: List[ValidationResult] = []

        # Load concession reference data
        try:
            concession = _load_concession_data(self.data_path)
        except Exception as exc:
            results.append(self._create_result(
                field_name="master_concession_data",
                passed=False,
                message=f"Could not load concession data from {self.data_path}: {exc}",
                severity=Severity.CRITICAL,
                source_value=None,
                target_value=None,
            ))
            return results

        meta = concession.get("metadata", {})
        approved_ref = meta.get("application_reference", "")
        expiry_str = meta.get("expiry_date", "")
        expiry_date: Optional[date] = None
        if expiry_str:
            try:
                expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        hs_index = _build_hs_index(concession.get("items", []))

        # Check CPC code — skip entire validator if not applicable
        cpc_code = self._get_field_from_documents(self.customs_code_field, context)
        if cpc_code not in self.applicable_cpc_codes:
            return results

        # ── 1. Concession reference number ────────────────────────────────
        if self.validations.get("check_concession_reference", True):
            declared_ref = self._get_field_from_documents(self.concession_ref_field, context)
            if not declared_ref:
                results.append(self._create_result(
                    field_name="etls_approval_number",
                    passed=False,
                    message=f"Master Concession reference number missing on BOE. Expected: {approved_ref}",
                    severity=self._sev("reference_number_missing", Severity.MAJOR),
                    source_value=None,
                    target_value=approved_ref,
                ))
            elif str(declared_ref).strip() != approved_ref:
                results.append(self._create_result(
                    field_name="etls_approval_number",
                    passed=False,
                    message=f"Concession reference mismatch. Declared: '{declared_ref}', Expected: '{approved_ref}'",
                    severity=self._sev("wrong_reference_number", Severity.CRITICAL),
                    source_value=declared_ref,
                    target_value=approved_ref,
                ))
            else:
                results.append(self._create_result(
                    field_name="etls_approval_number",
                    passed=True,
                    message=f"Concession reference number matches: {approved_ref}",
                    severity=Severity.INFO,
                    source_value=declared_ref,
                    target_value=approved_ref,
                ))

        # ── 2. Expiry date ────────────────────────────────────────────────
        if self.validations.get("check_expiry_date", True) and expiry_date:
            decl_date = self._parse_date(
                self._get_field_from_documents(self.shipment_date_field, context)
            )
            if decl_date and decl_date > expiry_date:
                results.append(self._create_result(
                    field_name="declaration_date",
                    passed=False,
                    message=(
                        f"Master Concession expired on {expiry_date}. "
                        f"BOE declaration date {decl_date} is after expiry. "
                        f"CPC code {cpc_code} cannot be used."
                    ),
                    severity=self._sev("concession_expired", Severity.CRITICAL),
                    source_value=str(decl_date),
                    target_value=str(expiry_date),
                ))

        # ── 3. Per-item HS code eligibility ──────────────────────────────
        if self.validations.get("check_item_eligibility", True):
            items = self._get_field_from_documents(self.line_items_field, context) or []
            for idx, item in enumerate(items):
                raw_hs = item.get(self.item_hs_field) if isinstance(item, dict) else None
                if not raw_hs:
                    continue
                normalized = _normalize_hs(str(raw_hs))
                if normalized not in hs_index:
                    desc = item.get(self.item_desc_field, "") if isinstance(item, dict) else ""
                    results.append(self._create_result(
                        field_name=f"items[{idx}].hs_code",
                        passed=False,
                        message=(
                            f"HS code '{raw_hs}' ({desc}) is not in the Master Concession "
                            f"approved list. Zero duty under CPC {cpc_code} cannot be applied."
                        ),
                        severity=self._sev("item_not_on_concession", Severity.MAJOR),
                        source_value=raw_hs,
                        target_value="approved HS code from Master Concession",
                    ))

        return results

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _sev(self, key: str, default: str) -> str:
        raw = self.failure_severities.get(key)
        if raw and hasattr(Severity, raw.upper()):
            return getattr(Severity, raw.upper())
        return default

    @staticmethod
    def _parse_date(value: Any) -> Optional[date]:
        if value is None:
            return None
        if isinstance(value, date):
            return value
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(str(value), fmt).date()
            except ValueError:
                continue
        return None

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
