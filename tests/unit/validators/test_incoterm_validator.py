"""Unit tests for IncotermValidator"""

import pytest
from decimal import Decimal
from modules.validation_engine.validators.rule_based.incoterm_validator import IncotermValidator


@pytest.mark.asyncio
class TestIncotermValidator:
    """Test incoterm validation logic"""

    @pytest.fixture
    def validator(self):
        """Create validator instance"""
        config = {
            "validations": [{
                "incoterm_field": "invoice.incoterm",
                "freight_field": "invoice.freight_value",
                "insurance_field": "invoice.insurance_value",
                "fob_field": "invoice.total_fob_value",
                "cif_field": "bill_of_entry.cif_value",
                "document": "invoice"
            }],
            "tolerance": 0.01
        }
        return IncotermValidator(config)

    async def test_cfr_freight_required_present(self, validator, validation_context):
        """Test CFR: Freight value present (should pass)"""
        validation_context.normalized_data["invoice"]["incoterm"] = "CFR"
        validation_context.normalized_data["invoice"]["freight_value"] = 5000.0

        results = await validator.validate({}, {}, validation_context)

        # Should pass - CFR has freight
        passed_results = [r for r in results if r.passed and "freight" in r.field_name.lower()]
        assert len(passed_results) > 0

    async def test_cfr_freight_required_missing(self, validator, validation_context):
        """Test CFR: Freight value missing (should fail)"""
        validation_context.normalized_data["invoice"]["incoterm"] = "CFR"
        validation_context.normalized_data["invoice"]["freight_value"] = None

        results = await validator.validate({}, {}, validation_context)

        # Should fail - CFR requires freight
        failed_results = [r for r in results if not r.passed and "freight" in r.message.lower()]
        assert len(failed_results) > 0
        assert any("CFR" in r.message for r in failed_results)

    async def test_cif_freight_insurance_required(self, validator, validation_context):
        """Test CIF: Both freight and insurance required"""
        validation_context.normalized_data["invoice"]["incoterm"] = "CIF"
        validation_context.normalized_data["invoice"]["freight_value"] = 5000.0
        validation_context.normalized_data["invoice"]["insurance_value"] = 2000.0

        results = await validator.validate({}, {}, validation_context)

        # Should pass - CIF has both
        passed_results = [r for r in results if r.passed]
        assert len(passed_results) >= 2  # At least freight + insurance checks

    async def test_cif_missing_insurance(self, validator, validation_context):
        """Test CIF: Insurance missing (should fail)"""
        validation_context.normalized_data["invoice"]["incoterm"] = "CIF"
        validation_context.normalized_data["invoice"]["freight_value"] = 5000.0
        validation_context.normalized_data["invoice"]["insurance_value"] = None

        results = await validator.validate({}, {}, validation_context)

        # Should fail - CIF requires insurance
        failed_results = [r for r in results if not r.passed and "insurance" in r.message.lower()]
        assert len(failed_results) > 0

    async def test_fob_no_freight(self, validator, validation_context):
        """Test FOB: No freight expected"""
        validation_context.normalized_data["invoice"]["incoterm"] = "FOB"
        validation_context.normalized_data["invoice"]["freight_value"] = 0.0
        validation_context.normalized_data["invoice"]["insurance_value"] = 0.0

        results = await validator.validate({}, {}, validation_context)

        # Should pass - FOB has no freight/insurance
        passed_results = [r for r in results if r.passed]
        assert len(passed_results) > 0

    async def test_fob_with_freight_warning(self, validator, validation_context):
        """Test FOB: Freight present (should warn)"""
        validation_context.normalized_data["invoice"]["incoterm"] = "FOB"
        validation_context.normalized_data["invoice"]["freight_value"] = 5000.0

        results = await validator.validate({}, {}, validation_context)

        # Should have warning/failure - FOB shouldn't have freight
        issues = [r for r in results if not r.passed or r.severity == "MINOR"]
        assert len(issues) > 0

    async def test_cif_calculation_correct(self, validator, validation_context):
        """Test CIF calculation: CIF = FOB + Insurance + Freight"""
        validation_context.normalized_data["invoice"]["incoterm"] = "CIF"
        validation_context.normalized_data["invoice"]["total_fob_value"] = 100000.0
        validation_context.normalized_data["invoice"]["freight_value"] = 5000.0
        validation_context.normalized_data["invoice"]["insurance_value"] = 5000.0
        validation_context.normalized_data["bill_of_entry"]["cif_value"] = 110000.0  # Correct

        results = await validator.validate({}, {}, validation_context)

        # Should pass - CIF calculation is correct
        passed_results = [r for r in results if r.passed and "cif" in r.field_name.lower()]
        assert len(passed_results) > 0

    async def test_cif_calculation_incorrect(self, validator, validation_context):
        """Test CIF calculation: Incorrect CIF value"""
        validation_context.normalized_data["invoice"]["incoterm"] = "CIF"
        validation_context.normalized_data["invoice"]["total_fob_value"] = 100000.0
        validation_context.normalized_data["invoice"]["freight_value"] = 5000.0
        validation_context.normalized_data["invoice"]["insurance_value"] = 5000.0
        validation_context.normalized_data["bill_of_entry"]["cif_value"] = 105000.0  # Wrong!

        results = await validator.validate({}, {}, validation_context)

        # Should fail - CIF should be 110,000 not 105,000
        failed_results = [r for r in results if not r.passed and "cif" in r.field_name.lower()]
        assert len(failed_results) > 0
        assert any("110000" in r.message for r in failed_results)

    async def test_incoterm_case_insensitive(self, validator, validation_context):
        """Test that incoterms are case-insensitive"""
        validation_context.normalized_data["invoice"]["incoterm"] = "cif"  # lowercase
        validation_context.normalized_data["invoice"]["freight_value"] = 5000.0
        validation_context.normalized_data["invoice"]["insurance_value"] = 2000.0

        results = await validator.validate({}, {}, validation_context)

        # Should still work with lowercase
        assert len(results) > 0
