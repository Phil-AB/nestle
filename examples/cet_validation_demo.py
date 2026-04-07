"""
CET (Common External Tariff) Validation Demo

Demonstrates HS code validation against the CET file:
1. Load CET file
2. Validate HS codes exist
3. Verify descriptions match
4. Check duty rates

Based on Ghana Customs CET file.
"""

import asyncio
from uuid import uuid4
from decimal import Decimal
from modules.validation_engine import get_validation_engine
from modules.validation_engine.core.base import ValidationContext
from modules.validation_engine.services.cet_file_service import get_cet_service
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


async def test_cet_service():
    """Test CET file service"""
    logger.info("=" * 80)
    logger.info("TEST 1: CET File Service")
    logger.info("=" * 80)

    cet_service = get_cet_service()

    # Load CET file
    logger.info("\n--- Loading CET file ---")
    success = cet_service.load_cet_file()

    if success:
        logger.info("✅ CET file loaded successfully")

        # Get statistics
        stats = cet_service.get_cet_statistics()
        logger.info(f"\n📊 CET Statistics:")
        logger.info(f"  Total entries: {stats['total_entries']}")
        logger.info(f"  Indexed HS codes: {stats['indexed_hs_codes']}")
        logger.info(f"  File path: {stats['file_path']}")
        logger.info(f"  Last loaded: {stats['last_loaded']}")
    else:
        logger.error("❌ Failed to load CET file")
        return

    # Test HS code lookup
    logger.info("\n--- Testing HS code lookup ---")

    test_codes = [
        ("8419.50", "Heat exchange machinery"),
        ("0101.21", "Live horses"),
        ("8703.00", "Motor cars"),
        ("1234.99", "Invalid code (should not exist)"),
    ]

    for hs_code, expected_desc in test_codes:
        logger.info(f"\nLooking up HS code: {hs_code}")

        info = cet_service.get_hs_code_info(hs_code)

        if info:
            logger.info(f"✅ Found in CET:")
            logger.info(f"  Description: {info['description']}")
            logger.info(f"  Duty Rate: {info['duty_rate_percent']}%")
        else:
            logger.info(f"❌ NOT found in CET")


async def test_hs_code_validation_correct():
    """Test HS code validation - correct data"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: HS Code Validation - CORRECT Data")
    logger.info("=" * 80)

    logger.info("\nScenario: Heat exchange machinery (8419.50)")
    logger.info("Expected: HS code exists, description matches, duty rate 10%")

    boe_data = {
        "hs_code": "8419.50",
        "description": "Heat exchange units machinery",
        "duty_rate": Decimal("10.0"),
    }

    context = ValidationContext(
        session_id=uuid4(),
        use_case="boe_validation",
        documents={"bill_of_entry": boe_data}
    )

    engine = get_validation_engine()
    validator = engine._get_validator_instance("cet_hs_code_validator", {
        "validations": [{
            "hs_code_field": "bill_of_entry.hs_code",
            "description_field": "bill_of_entry.description",
            "duty_rate_field": "bill_of_entry.duty_rate",
            "document": "bill_of_entry"
        }],
        "verify_hs_code_exists": True,
        "verify_description": True,
        "verify_duty_rate": True,
        "description_similarity_threshold": 0.6,
        "duty_rate_tolerance_percent": 0.1
    })

    results = await validator.validate(boe_data, None, context)

    logger.info("\n📋 Validation Results:")
    for i, result in enumerate(results, 1):
        status = "✅ PASS" if result.passed else "❌ FAIL"
        logger.info(f"{i}. {status} [{result.field_name}]: {result.message}")
        if result.metadata:
            logger.info(f"   Confidence: {result.confidence:.2%}")


async def test_hs_code_not_found():
    """Test HS code validation - code not in CET"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: HS Code Validation - CODE NOT IN CET")
    logger.info("=" * 80)

    logger.info("\nScenario: Invalid HS code (9999.99)")
    logger.info("Expected: HS code NOT found in CET")

    boe_data = {
        "hs_code": "9999.99",
        "description": "Some product",
        "duty_rate": Decimal("10.0"),
    }

    context = ValidationContext(
        session_id=uuid4(),
        use_case="boe_validation",
        documents={"bill_of_entry": boe_data}
    )

    engine = get_validation_engine()
    validator = engine._get_validator_instance("cet_hs_code_validator", {
        "validations": [{
            "hs_code_field": "bill_of_entry.hs_code",
            "description_field": "bill_of_entry.description",
            "duty_rate_field": "bill_of_entry.duty_rate",
            "document": "bill_of_entry"
        }]
    })

    results = await validator.validate(boe_data, None, context)

    for result in results:
        status = "✅ PASS" if result.passed else "❌ FAIL"
        logger.info(f"{status} [{result.field_name}]: {result.message}")


async def test_description_mismatch():
    """Test HS code validation - description mismatch"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: HS Code Validation - DESCRIPTION MISMATCH")
    logger.info("=" * 80)

    logger.info("\nScenario: HS code 8419.50 with wrong description")
    logger.info("CET Description: Heat exchange units")
    logger.info("Provided Description: Plastic toys")

    boe_data = {
        "hs_code": "8419.50",
        "description": "Plastic toys for children",  # WRONG description
        "duty_rate": Decimal("10.0"),
    }

    context = ValidationContext(
        session_id=uuid4(),
        use_case="boe_validation",
        documents={"bill_of_entry": boe_data}
    )

    engine = get_validation_engine()
    validator = engine._get_validator_instance("cet_hs_code_validator", {
        "validations": [{
            "hs_code_field": "bill_of_entry.hs_code",
            "description_field": "bill_of_entry.description",
            "duty_rate_field": "bill_of_entry.duty_rate",
            "document": "bill_of_entry"
        }],
        "verify_description": True,
        "description_similarity_threshold": 0.6
    })

    results = await validator.validate(boe_data, None, context)

    for result in results:
        status = "✅ PASS" if result.passed else "❌ FAIL"
        logger.info(f"{status} [{result.field_name}]: {result.message}")
        if result.field_name == "description" and result.metadata:
            logger.info(f"   Similarity Score: {result.metadata.get('similarity_score', 0):.2%}")


async def test_duty_rate_mismatch():
    """Test HS code validation - duty rate mismatch"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 5: HS Code Validation - DUTY RATE MISMATCH")
    logger.info("=" * 80)

    logger.info("\nScenario: HS code 8419.50 with wrong duty rate")
    logger.info("CET Duty Rate: 10%")
    logger.info("Provided Duty Rate: 5%")

    boe_data = {
        "hs_code": "8419.50",
        "description": "Heat exchange machinery",
        "duty_rate": Decimal("5.0"),  # WRONG: Should be 10%
    }

    context = ValidationContext(
        session_id=uuid4(),
        use_case="boe_validation",
        documents={"bill_of_entry": boe_data}
    )

    engine = get_validation_engine()
    validator = engine._get_validator_instance("cet_hs_code_validator", {
        "validations": [{
            "hs_code_field": "bill_of_entry.hs_code",
            "description_field": "bill_of_entry.description",
            "duty_rate_field": "bill_of_entry.duty_rate",
            "document": "bill_of_entry"
        }],
        "verify_duty_rate": True,
        "duty_rate_tolerance_percent": 0.1
    })

    results = await validator.validate(boe_data, None, context)

    for result in results:
        status = "✅ PASS" if result.passed else "❌ FAIL"
        logger.info(f"{status} [{result.field_name}]: {result.message}")


async def test_search_by_description():
    """Test searching HS codes by description"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 6: Search HS Codes by Description")
    logger.info("=" * 80)

    cet_service = get_cet_service()

    search_queries = [
        "heat exchange",
        "motor cars",
        "live animals",
    ]

    for query in search_queries:
        logger.info(f"\nSearching for: '{query}'")
        results = cet_service.search_by_description(query, top_n=3)

        if results:
            logger.info(f"Found {len(results)} matches:")
            for i, result in enumerate(results, 1):
                logger.info(f"  {i}. HS Code: {result['hs_code']}")
                logger.info(f"     Description: {result['description']}")
                logger.info(f"     Duty Rate: {result['duty_rate_percent']}%")
                logger.info(f"     Similarity: {result['similarity_score']:.2%}")
        else:
            logger.info("No matches found")


async def main():
    """Run all tests"""
    logger.info("🚀 CET (Common External Tariff) Validation Demo")
    logger.info("Testing HS code validation against Ghana Customs CET file\n")

    try:
        await test_cet_service()
        await test_hs_code_validation_correct()
        await test_hs_code_not_found()
        await test_description_mismatch()
        await test_duty_rate_mismatch()
        await test_search_by_description()

        logger.info("\n" + "=" * 80)
        logger.info("✅ All CET validation tests completed!")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Error running tests: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
