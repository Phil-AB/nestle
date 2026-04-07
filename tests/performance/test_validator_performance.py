"""Performance benchmarks for validators"""

import pytest
import time
from decimal import Decimal
from modules.validation_engine.validators.rule_based.incoterm_validator import IncotermValidator
from modules.validation_engine.validators.rule_based.customs_code_validator import CustomsCodeValidator
from modules.validation_engine.validators.rule_based.mode_of_shipment_validator import ModeOfShipmentValidator


@pytest.mark.asyncio
class TestValidatorPerformance:
    """Performance benchmarks - validators should execute < 10ms"""

    @pytest.fixture
    def incoterm_validator(self):
        config = {
            "validations": [{
                "incoterm_field": "invoice.incoterm",
                "freight_field": "invoice.freight_value",
                "insurance_field": "invoice.insurance_value",
                "document": "invoice"
            }]
        }
        return IncotermValidator(config)

    @pytest.fixture
    def customs_validator(self):
        config = {
            "validations": [{
                "customs_code_field": "bill_of_entry.customs_code",
                "customs_value_field": "bill_of_entry.customs_value",
                "amount_payable_field": "bill_of_entry.amount_payable",
                "document": "bill_of_entry"
            }]
        }
        return CustomsCodeValidator(config)

    async def test_incoterm_validator_speed(self, incoterm_validator, validation_context):
        """Incoterm validator should complete < 10ms"""
        validation_context.normalized_data["invoice"]["incoterm"] = "CIF"
        validation_context.normalized_data["invoice"]["freight_value"] = 5000.0
        validation_context.normalized_data["invoice"]["insurance_value"] = 2000.0

        start = time.perf_counter()
        await incoterm_validator.validate({}, {}, validation_context)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 10.0, f"Incoterm validator took {elapsed_ms:.2f}ms (target < 10ms)"
        print(f"✓ Incoterm validator: {elapsed_ms:.2f}ms")

    async def test_customs_code_validator_speed(self, customs_validator, validation_context):
        """Customs code validator should complete < 10ms"""
        validation_context.normalized_data["bill_of_entry"]["customs_code"] = "40E68"
        validation_context.normalized_data["bill_of_entry"]["customs_value"] = 100000.0
        validation_context.normalized_data["bill_of_entry"]["amount_payable"] = 5000.0

        start = time.perf_counter()
        await customs_validator.validate({}, {}, validation_context)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 10.0, f"Customs validator took {elapsed_ms:.2f}ms (target < 10ms)"
        print(f"✓ Customs code validator: {elapsed_ms:.2f}ms")

    async def test_cet_lookup_speed(self):
        """CET file lookup should be < 1ms (cached)"""
        from modules.validation_engine.services.cet_file_service import CETFileService

        service = CETFileService()
        
        # First lookup (loads file)
        start = time.perf_counter()
        result = service.get_hs_code_info("180632")
        first_lookup_ms = (time.perf_counter() - start) * 1000
        
        # Second lookup (cached)
        start = time.perf_counter()
        result = service.get_hs_code_info("180632")
        cached_lookup_ms = (time.perf_counter() - start) * 1000

        assert cached_lookup_ms < 1.0, f"CET cached lookup took {cached_lookup_ms:.3f}ms (target < 1ms)"
        print(f"✓ CET first lookup: {first_lookup_ms:.2f}ms")
        print(f"✓ CET cached lookup: {cached_lookup_ms:.3f}ms")
