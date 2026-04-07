"""
Customs Code Validation Demo

Demonstrates the customs code validator with Ghana customs codes:
- 40E68: Full VAT payment
- 40V02: VAT exempted
- 40U01: Duty exempted
- 40W01: Duty exempted with taxes payable
"""

import asyncio
from uuid import uuid4
from decimal import Decimal
from modules.validation_engine import get_validation_engine
from modules.validation_engine.core.base import ValidationContext
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


async def test_customs_code_40E68():
    """Test 40E68: Full VAT payment (5%)"""
    logger.info("=" * 80)
    logger.info("TEST 1: Customs Code 40E68 - Full VAT Payment")
    logger.info("=" * 80)

    # Test case 1: Correct calculation
    logger.info("\n--- Test Case 1a: CORRECT calculation ---")
    boe_data_correct = {
        "customs_code": "40E68",
        "customs_value": Decimal("10000.00"),
        "amount_payable": Decimal("500.00"),  # 5% of 10,000 = 500
    }

    context = ValidationContext(
        session_id=uuid4(),
        use_case="boe_validation",
        documents={"bill_of_entry": boe_data_correct}
    )

    engine = get_validation_engine()
    validator = engine._get_validator_instance("customs_code_validator", {
        "validations": [{
            "customs_value_field": "bill_of_entry.customs_value",
            "amount_payable_field": "bill_of_entry.amount_payable",
            "customs_code_field": "bill_of_entry.customs_code"
        }]
    })

    results = await validator.validate(boe_data_correct, None, context)

    for result in results:
        status = "✅ PASS" if result.passed else "❌ FAIL"
        logger.info(f"{status}: {result.message}")
        logger.info(f"  Confidence: {result.confidence:.2f}")
        logger.info(f"  Severity: {result.severity}")

    # Test case 2: Incorrect calculation
    logger.info("\n--- Test Case 1b: INCORRECT calculation ---")
    boe_data_incorrect = {
        "customs_code": "40E68",
        "customs_value": Decimal("10000.00"),
        "amount_payable": Decimal("450.00"),  # WRONG: Should be 500
    }

    context.documents = {"bill_of_entry": boe_data_incorrect}
    results = await validator.validate(boe_data_incorrect, None, context)

    for result in results:
        status = "✅ PASS" if result.passed else "❌ FAIL"
        logger.info(f"{status}: {result.message}")
        logger.info(f"  Expected: {result.target_value}")
        logger.info(f"  Actual: {result.source_value}")
        logger.info(f"  Difference: {abs(result.target_value - result.source_value)}")


async def test_customs_code_40V02():
    """Test 40V02: VAT exempted"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: Customs Code 40V02 - VAT Exempted")
    logger.info("=" * 80)

    # Test case: Correct - Amount Payable = 0, Amount Exempted = 5%
    logger.info("\n--- Test Case 2a: CORRECT (VAT exempted) ---")
    boe_data_correct = {
        "customs_code": "40V02",
        "customs_value": Decimal("10000.00"),
        "amount_payable": Decimal("0.00"),  # Must be 0 for exemption
        "amount_exempted": Decimal("500.00"),  # 5% of 10,000 = 500
    }

    context = ValidationContext(
        session_id=uuid4(),
        use_case="boe_validation",
        documents={"bill_of_entry": boe_data_correct}
    )

    engine = get_validation_engine()
    validator = engine._get_validator_instance("customs_code_validator", {
        "validations": [{
            "customs_value_field": "bill_of_entry.customs_value",
            "amount_payable_field": "bill_of_entry.amount_payable",
            "amount_exempted_field": "bill_of_entry.amount_exempted",
            "customs_code_field": "bill_of_entry.customs_code"
        }]
    })

    results = await validator.validate(boe_data_correct, None, context)

    for result in results:
        status = "✅ PASS" if result.passed else "❌ FAIL"
        logger.info(f"{status} [{result.field_name}]: {result.message}")

    # Test case: Incorrect - Amount Payable non-zero
    logger.info("\n--- Test Case 2b: INCORRECT (Amount Payable should be 0) ---")
    boe_data_incorrect = {
        "customs_code": "40V02",
        "customs_value": Decimal("10000.00"),
        "amount_payable": Decimal("500.00"),  # WRONG: Should be 0 for exemption
        "amount_exempted": Decimal("0.00"),
    }

    context.documents = {"bill_of_entry": boe_data_incorrect}
    results = await validator.validate(boe_data_incorrect, None, context)

    for result in results:
        status = "✅ PASS" if result.passed else "❌ FAIL"
        logger.info(f"{status} [{result.field_name}]: {result.message}")


async def test_customs_code_40U01():
    """Test 40U01: Duty exempted"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: Customs Code 40U01 - Duty Exempted")
    logger.info("=" * 80)

    # Test case: Correct - Duty = 0
    logger.info("\n--- Test Case 3a: CORRECT (Duty exempted) ---")
    boe_data_correct = {
        "customs_code": "40U01",
        "duty_amount": Decimal("0.00"),  # Must be 0 for exemption
    }

    context = ValidationContext(
        session_id=uuid4(),
        use_case="boe_validation",
        documents={"bill_of_entry": boe_data_correct}
    )

    engine = get_validation_engine()
    validator = engine._get_validator_instance("customs_code_validator", {
        "validations": [{
            "duty_amount_field": "bill_of_entry.duty_amount",
            "customs_code_field": "bill_of_entry.customs_code"
        }]
    })

    results = await validator.validate(boe_data_correct, None, context)

    for result in results:
        status = "✅ PASS" if result.passed else "❌ FAIL"
        logger.info(f"{status}: {result.message}")

    # Test case: Incorrect - Duty non-zero
    logger.info("\n--- Test Case 3b: INCORRECT (Duty should be 0) ---")
    boe_data_incorrect = {
        "customs_code": "40U01",
        "duty_amount": Decimal("250.00"),  # WRONG: Should be 0
    }

    context.documents = {"bill_of_entry": boe_data_incorrect}
    results = await validator.validate(boe_data_incorrect, None, context)

    for result in results:
        status = "✅ PASS" if result.passed else "❌ FAIL"
        logger.info(f"{status}: {result.message}")


async def test_customs_code_40W01():
    """Test 40W01: Duty exempted but taxes payable"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: Customs Code 40W01 - Duty Exempted, Taxes Payable")
    logger.info("=" * 80)

    # Test case: Correct - Duty = 0, VAT > 0
    logger.info("\n--- Test Case 4a: CORRECT (Duty exempted, VAT payable) ---")
    boe_data_correct = {
        "customs_code": "40W01",
        "duty_amount": Decimal("0.00"),  # Must be 0 (duty exempted)
        "vat_amount": Decimal("300.00"),  # VAT still payable
    }

    context = ValidationContext(
        session_id=uuid4(),
        use_case="boe_validation",
        documents={"bill_of_entry": boe_data_correct}
    )

    engine = get_validation_engine()
    validator = engine._get_validator_instance("customs_code_validator", {
        "validations": [{
            "duty_amount_field": "bill_of_entry.duty_amount",
            "vat_amount_field": "bill_of_entry.vat_amount",
            "customs_code_field": "bill_of_entry.customs_code"
        }]
    })

    results = await validator.validate(boe_data_correct, None, context)

    for result in results:
        status = "✅ PASS" if result.passed else "❌ FAIL"
        logger.info(f"{status} [{result.field_name}]: {result.message}")


async def test_real_world_scenario():
    """Test a complete real-world BOE validation"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 5: Real-World BOE Validation")
    logger.info("=" * 80)

    logger.info("\nScenario: Import of machinery with code 40E68 (Full VAT payment)")
    logger.info("Customs Value: $50,000")
    logger.info("Expected VAT (5%): $2,500")

    boe_data = {
        "declaration_number": "BOE-2024-001234",
        "customs_code": "40E68",
        "customs_value": Decimal("50000.00"),
        "amount_payable": Decimal("2500.00"),  # Correct: 5% of 50,000
        "hs_code": "8419.50",
        "description": "Heat exchange machinery",
        "net_weight": Decimal("5000.00"),
        "duty_rate": Decimal("0.10"),  # 10%
    }

    context = ValidationContext(
        session_id=uuid4(),
        use_case="boe_validation",
        documents={"bill_of_entry": boe_data}
    )

    engine = get_validation_engine()
    validator = engine._get_validator_instance("customs_code_validator", {
        "validations": [{
            "customs_value_field": "bill_of_entry.customs_value",
            "amount_payable_field": "bill_of_entry.amount_payable",
            "customs_code_field": "bill_of_entry.customs_code"
        }]
    })

    results = await validator.validate(boe_data, None, context)

    logger.info("\n📋 Validation Results:")
    for i, result in enumerate(results, 1):
        status = "✅ PASS" if result.passed else "❌ FAIL"
        logger.info(f"{i}. {status}: {result.message}")
        if result.metadata:
            logger.info(f"   Metadata: {result.metadata}")


async def main():
    """Run all tests"""
    logger.info("🚀 Customs Code Validator Demo")
    logger.info("Testing Ghana Customs ICUMS codes: 40E68, 40V02, 40U01, 40W01\n")

    try:
        await test_customs_code_40E68()
        await test_customs_code_40V02()
        await test_customs_code_40U01()
        await test_customs_code_40W01()
        await test_real_world_scenario()

        logger.info("\n" + "=" * 80)
        logger.info("✅ All customs code validation tests completed!")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Error running tests: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
