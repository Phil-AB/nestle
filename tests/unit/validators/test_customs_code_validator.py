"""Unit tests for CustomsCodeValidator (Sprint 1)"""

import pytest
from decimal import Decimal
from modules.validation_engine.validators.rule_based.customs_code_validator import CustomsCodeValidator


@pytest.mark.asyncio
class TestCustomsCodeValidator:
    """Test Ghana customs code validation logic"""

    @pytest.fixture
    def validator(self):
        """Create validator instance"""
        config = {
            "validations": [{
                "customs_code_field": "bill_of_entry.customs_code",
                "customs_value_field": "bill_of_entry.customs_value",
                "amount_payable_field": "bill_of_entry.amount_payable",
                "amount_exempted_field": "bill_of_entry.amount_exempted",
                "vat_amount_field": "bill_of_entry.vat_amount",
                "duty_amount_field": "bill_of_entry.duty_amount",
                "document": "bill_of_entry"
            }]
        }
        return CustomsCodeValidator(config)

    async def test_40E68_full_vat_payment(self, validator, validation_context):
        """Test 40E68: Full VAT payment (5% of customs value)"""
        validation_context.normalized_data["bill_of_entry"]["customs_code"] = "40E68"
        validation_context.normalized_data["bill_of_entry"]["customs_value"] = Decimal("100000.00")
        validation_context.normalized_data["bill_of_entry"]["amount_payable"] = Decimal("5000.00")
        validation_context.normalized_data["bill_of_entry"]["vat_amount"] = Decimal("5000.00")

        results = await validator.validate({}, {}, validation_context)

        # Should pass - 5% VAT calculated correctly
        passed_results = [r for r in results if r.passed]
        assert len(passed_results) > 0

    async def test_40V02_vat_exempted(self, validator, validation_context):
        """Test 40V02: VAT exempt"""
        validation_context.normalized_data["bill_of_entry"]["customs_code"] = "40V02"
        validation_context.normalized_data["bill_of_entry"]["customs_value"] = Decimal("100000.00")
        validation_context.normalized_data["bill_of_entry"]["amount_payable"] = Decimal("0.00")
        validation_context.normalized_data["bill_of_entry"]["amount_exempted"] = Decimal("5000.00")

        results = await validator.validate({}, {}, validation_context)

        # Should pass - VAT exemption
        passed_results = [r for r in results if r.passed]
        assert len(passed_results) > 0

    async def test_40U01_duty_exempted(self, validator, validation_context):
        """Test 40U01: Duty exempt"""
        validation_context.normalized_data["bill_of_entry"]["customs_code"] = "40U01"
        validation_context.normalized_data["bill_of_entry"]["duty_amount"] = Decimal("0.00")

        results = await validator.validate({}, {}, validation_context)

        # Should pass
        passed_results = [r for r in results if r.passed]
        assert len(passed_results) > 0
