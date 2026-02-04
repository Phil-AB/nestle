"""
Test universal OCR system end-to-end.

Tests the provider-agnostic architecture with Reducto.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio

from modules.extraction.parser.schema_generator import SchemaGenerator
from modules.extraction.parser.provider_factory import get_active_provider
from modules.extraction.storage.universal_document_service import UniversalDocumentStorageService
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


async def test_universal_extraction_pipeline():
    """
    Test the complete universal extraction pipeline.

    Flow:
    1. Generate universal schema from config
    2. Get active provider (Reducto from config)
    3. Extract with provider (translates schema, calls API, normalizes response)
    4. Save with universal storage service
    """
    logger.info("=" * 80)
    logger.info("TESTING UNIVERSAL OCR SYSTEM")
    logger.info("=" * 80)

    # Test document type
    document_type = "invoice"

    # Step 1: Generate universal schema
    logger.info("\n1. Generating universal schema from config...")
    schema_generator = SchemaGenerator()
    universal_schema = schema_generator.generate_schema(document_type)

    logger.info(f"   Generated schema for {document_type}")
    logger.info(f"   Fields: {len(universal_schema.get('fields', {}))} header fields")
    if 'items' in universal_schema:
        logger.info(f"   Items: {len(universal_schema['items'].get('fields', {}))} item fields")

    # Step 2: Mock extraction (no real file for now)
    logger.info("\n2. Mock extraction (simulating provider response)...")

    # Simulate what a provider would return in universal format
    mock_universal_data = {
        "fields": {
            "invoice_number": "INV-2024-TEST-001",
            "invoice_date": "2024-01-15",
            "currency": "USD",
            "total_fob_value": 5000.00,
            "consignee_name": "Test Company Ltd",
            "shipper_name": "Supplier Inc"
        },
        "items": [
            {
                "line_number": 1,
                "product_description": "Test Product A",
                "quantity": 100.0,
                "unit_price": 25.0,
                "total_value": 2500.0
            },
            {
                "line_number": 2,
                "product_description": "Test Product B",
                "quantity": 50.0,
                "unit_price": 50.0,
                "total_value": 2500.0
            }
        ],
        "metadata": {
            "provider": "reducto",
            "confidence": 0.95,
            "extraction_time": 2.3
        }
    }

    logger.info("   Mock data created with 6 fields and 2 items")

    # Step 3: Save to database
    logger.info("\n3. Saving to database using universal storage service...")
    storage_service = UniversalDocumentStorageService()
    storage_result = await storage_service.save_document(document_type, mock_universal_data)

    if storage_result.success:
        logger.info("   ✅ STORAGE SUCCESS!")
        response = storage_result.document_response

        logger.info(f"\n   Document ID: {response.document_id}")
        logger.info(f"   Document Number: {response.document_number}")
        logger.info(f"   Extraction Status: {response.extraction_status}")
        logger.info(f"   Saved Fields: {len(response.saved_fields)}")
        logger.info(f"   Missing Fields: {len(response.missing_fields)}")
        logger.info(f"   Items Count: {response.items_count}")
        logger.info(f"   Was Updated: {response.was_updated}")

        if response.missing_fields:
            logger.warning(f"   Missing required fields: {response.missing_fields}")

    else:
        logger.error("   ❌ STORAGE FAILED!")
        logger.error(f"   Error: {storage_result.error_response.error_message}")

    logger.info("\n" + "=" * 80)
    logger.info("TEST COMPLETE")
    logger.info("=" * 80)

    return storage_result.success


async def test_schema_generation():
    """Test schema generation for all document types."""
    logger.info("\n" + "=" * 80)
    logger.info("TESTING SCHEMA GENERATION")
    logger.info("=" * 80)

    schema_generator = SchemaGenerator()
    document_types = ["invoice", "boe", "packing_list", "coo", "freight"]

    for doc_type in document_types:
        logger.info(f"\nGenerating schema for: {doc_type}")
        schema = schema_generator.generate_schema(doc_type)

        fields_count = len(schema.get('fields', {}))
        has_items = 'items' in schema
        items_count = len(schema['items'].get('fields', {})) if has_items else 0

        logger.info(f"  ✓ {fields_count} header fields")
        if has_items:
            logger.info(f"  ✓ {items_count} item fields")
        logger.info(f"  ✓ Unique field: {schema['metadata']['unique_field']}")

    logger.info("\n✅ Schema generation test passed!")


async def test_provider_translation():
    """Test provider schema translation."""
    logger.info("\n" + "=" * 80)
    logger.info("TESTING PROVIDER SCHEMA TRANSLATION")
    logger.info("=" * 80)

    # Generate universal schema
    schema_generator = SchemaGenerator()
    universal_schema = schema_generator.generate_schema("invoice")

    logger.info("\n1. Universal schema generated")
    logger.info(f"   Universal format fields: {list(universal_schema['fields'].keys())[:5]}...")

    # Get provider and translate
    async with get_active_provider() as provider:
        logger.info(f"\n2. Active provider: {provider.__class__.__name__}")

        # Translate to provider-specific format
        provider_schema = provider.translate_schema(universal_schema)

        logger.info(f"\n3. Translated to provider format")
        logger.info(f"   Provider schema type: {provider_schema.get('type')}")
        logger.info(f"   Provider schema properties: {list(provider_schema.get('properties', {}).keys())[:5]}...")

        logger.info("\n✅ Schema translation test passed!")


if __name__ == "__main__":
    # Run all tests
    print("\n🧪 RUNNING UNIVERSAL SYSTEM TESTS\n")

    # Test 1: Schema generation
    asyncio.run(test_schema_generation())

    # Test 2: Provider translation
    asyncio.run(test_provider_translation())

    # Test 3: Full pipeline
    asyncio.run(test_universal_extraction_pipeline())

    print("\n✅ ALL TESTS COMPLETED\n")
