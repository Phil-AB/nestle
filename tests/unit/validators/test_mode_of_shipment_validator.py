"""Unit tests for ModeOfShipmentValidator"""

import pytest
from modules.validation_engine.validators.rule_based.mode_of_shipment_validator import ModeOfShipmentValidator


@pytest.mark.asyncio
class TestModeOfShipmentValidator:
    """Test mode of shipment validation logic"""

    @pytest.fixture
    def validator(self):
        """Create validator instance"""
        config = {
            "section_21_field": "bill_of_entry.section_21.entry_exit_code"
        }
        return ModeOfShipmentValidator(config)

    async def test_kia_with_airway_bill(self, validator, validation_context):
        """Test KIA (airport) with AWB document - should pass"""
        validation_context.normalized_data["bill_of_entry"]["section_21"] = {
            "entry_exit_code": "KIA"
        }
        validation_context.documents["airway_bill"] = {"awb_number": "AWB-001"}

        results = await validator.validate({}, {}, validation_context)

        # Should pass - KIA expects AWB
        passed_results = [r for r in results if r.passed]
        assert len(passed_results) > 0
        assert any("KIA" in r.message or "air" in r.message.lower() for r in passed_results)

    async def test_kia_with_bill_of_lading(self, validator, validation_context):
        """Test KIA (airport) with BL document - should fail"""
        validation_context.normalized_data["bill_of_entry"]["section_21"] = {
            "entry_exit_code": "KIA"
        }
        validation_context.documents["bill_of_lading"] = {"bl_number": "BL-001"}
        # Remove AWB if it exists
        if "airway_bill" in validation_context.documents:
            del validation_context.documents["airway_bill"]

        results = await validator.validate({}, {}, validation_context)

        # Should fail - KIA needs AWB, not BL
        failed_results = [r for r in results if not r.passed]
        assert len(failed_results) > 0
        assert any("air" in r.message.lower() and "awb" in r.message.lower() for r in failed_results)

    async def test_tma_with_bill_of_lading(self, validator, validation_context):
        """Test TMA (port) with BL document - should pass"""
        validation_context.normalized_data["bill_of_entry"]["section_21"] = {
            "entry_exit_code": "TMA"
        }
        validation_context.documents["bill_of_lading"] = {"bl_number": "BL-001"}

        results = await validator.validate({}, {}, validation_context)

        # Should pass - TMA expects BL
        passed_results = [r for r in results if r.passed]
        assert len(passed_results) > 0
        assert any("TMA" in r.message or "sea" in r.message.lower() for r in passed_results)

    async def test_tma_with_airway_bill(self, validator, validation_context):
        """Test TMA (port) with AWB document - should fail"""
        validation_context.normalized_data["bill_of_entry"]["section_21"] = {
            "entry_exit_code": "TMA"
        }
        validation_context.documents["airway_bill"] = {"awb_number": "AWB-001"}
        # Remove BL if it exists
        if "bill_of_lading" in validation_context.documents:
            del validation_context.documents["bill_of_lading"]

        results = await validator.validate({}, {}, validation_context)

        # Should fail - TMA needs BL, not AWB
        failed_results = [r for r in results if not r.passed]
        assert len(failed_results) > 0

    async def test_missing_section_21(self, validator, validation_context):
        """Test missing Section 21 - should fail"""
        validation_context.normalized_data["bill_of_entry"].pop("section_21", None)

        results = await validator.validate({}, {}, validation_context)

        # Should fail - Section 21 required
        failed_results = [r for r in results if not r.passed]
        assert len(failed_results) > 0
        assert any("section 21" in r.message.lower() for r in failed_results)

    async def test_unknown_entry_code(self, validator, validation_context):
        """Test unknown entry/exit code"""
        validation_context.normalized_data["bill_of_entry"]["section_21"] = {
            "entry_exit_code": "UNKNOWN123"
        }

        results = await validator.validate({}, {}, validation_context)

        # Should have warning/failure for unknown code
        issues = [r for r in results if not r.passed or r.severity != "INFO"]
        assert len(issues) > 0
        assert any("unknown" in r.message.lower() for r in issues)

    async def test_kotoka_alias(self, validator, validation_context):
        """Test KOTOKA (alias for KIA) with AWB"""
        validation_context.normalized_data["bill_of_entry"]["section_21"] = {
            "entry_exit_code": "KOTOKA INTERNATIONAL AIRPORT"
        }
        validation_context.documents["airway_bill"] = {"awb_number": "AWB-001"}

        results = await validator.validate({}, {}, validation_context)

        # Should pass - KOTOKA maps to air mode
        passed_results = [r for r in results if r.passed]
        assert len(passed_results) > 0

    async def test_tema_alias(self, validator, validation_context):
        """Test TEMA (alias for TMA) with BL"""
        validation_context.normalized_data["bill_of_entry"]["section_21"] = {
            "entry_exit_code": "TEMA PORT"
        }
        validation_context.documents["bill_of_lading"] = {"bl_number": "BL-001"}

        results = await validator.validate({}, {}, validation_context)

        # Should pass - TEMA maps to sea mode
        passed_results = [r for r in results if r.passed]
        assert len(passed_results) > 0
