"""
Test script for Universal Validation & Storage System.

This script demonstrates how to test both validation and storage engines.
Run this after setting up the database and configuration.

Usage:
    python tests/test_validation_storage.py
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from typing import Dict, Any
from modules.extraction.validation import ValidationEngine
from modules.extraction.storage import StorageEngine
from shared.utils.logger import setup_logger

logger = setup_logger(__name__)


# Test data samples
SAMPLE_DOCUMENTS = {
    "valid_document": {
        "document_id": "DOC-2024-001",
        "reference_code": "ABC-1234",
        "amount": 5000,
        "status": "approved",
        "description": "This is a valid test document with all required fields",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "items": [
            {"name": "Item 1", "amount": 2000},
            {"name": "Item 2", "amount": 3000}
        ],
        "_metadata": {
            "confidence_scores": {
                "document_id": 0.95,
                "amount": 0.92,
                "reference_code": 0.88
            }
        }
    },
    "invalid_document": {
        # Missing required field: document_id
        "reference_code": "INVALID",  # Wrong pattern
        "amount": -100,  # Negative amount
        "status": "unknown",  # Invalid enum value
        "description": "Bad",  # Too short
        "_metadata": {
            "confidence_scores": {
                "amount": 0.45  # Low confidence
            }
        }
    }
}


async def test_validation_engine():
    """Test the ValidationEngine with sample data."""
    print("\n" + "="*60)
    print("TEST 1: VALIDATION ENGINE")
    print("="*60)
    
    engine = ValidationEngine()
    
    print(f"\n📊 Available validators: {len(engine.get_available_validators())}")
    print(f"Validators: {', '.join(engine.get_available_validators())}\n")
    
    # Test 1: Valid document
    print("🔍 Test 1.1: Validating VALID document...")
    result = await engine.validate("my_document", SAMPLE_DOCUMENTS["valid_document"])
    
    print(f"  ✅ Passed: {result.passed}")
    print(f"  📈 Score: {result.score:.2f}")
    print(f"  📊 Checks: {result.summary.passed_checks}/{result.summary.total_checks}")
    
    if not result.passed:
        print(f"  ❌ Errors found:")
        for r in result.results:
            if not r['passed']:
                print(f"    - {r['message']}")
    
    # Test 2: Invalid document
    print("\n🔍 Test 1.2: Validating INVALID document...")
    result = await engine.validate("my_document", SAMPLE_DOCUMENTS["invalid_document"])
    
    print(f"  ✅ Passed: {result.passed}")
    print(f"  📈 Score: {result.score:.2f}")
    print(f"  📊 Checks: {result.summary.passed_checks}/{result.summary.total_checks}")
    print(f"  ⚠️  Errors: {result.summary.error_checks}")
    print(f"  🔔 Warnings: {result.summary.warning_checks}")
    
    if not result.passed:
        print(f"\n  ❌ Validation errors:")
        for r in result.results:
            if not r['passed']:
                severity = r['severity'].upper()
                print(f"    [{severity}] {r['message']}")
    
    print("\n✅ Validation Engine test complete!")
    return result


async def test_storage_engine():
    """Test the StorageEngine with sample data."""
    print("\n" + "="*60)
    print("TEST 2: STORAGE ENGINE")
    print("="*60)
    
    engine = StorageEngine()
    
    print(f"\n📊 Available backends: {engine.get_available_backends()}")
    
    # Test 1: Store document
    print("\n💾 Test 2.1: Storing document...")
    test_doc = {
        "invoice_number": "TEST-INV-001",
        "customer": "Test Corp",
        "amount": 10000,
        "date": "2024-11-24"
    }
    
    try:
        result = await engine.store(
            "test_invoice",
            test_doc.copy(),
            options={"unique_field": "invoice_number"}
        )
        
        if result.success:
            print(f"  ✅ Stored successfully!")
            print(f"  🆔 Document ID: {result.document_id}")
            doc_id = result.document_id
            
            # Test 2: Retrieve document
            print("\n🔍 Test 2.2: Retrieving document...")
            retrieved = await engine.retrieve("test_invoice", doc_id)
            print(f"  ✅ Retrieved: {retrieved['data']['invoice_number']}")
            print(f"  📄 Data: {retrieved['data']}")
            
            # Test 3: Update document
            print("\n✏️  Test 2.3: Updating document...")
            test_doc["amount"] = 15000
            test_doc["status"] = "updated"
            update_result = await engine.update("test_invoice", doc_id, test_doc.copy())
            
            if update_result.success:
                print(f"  ✅ Updated successfully!")
                
                # Verify update
                updated = await engine.retrieve("test_invoice", doc_id)
                print(f"  💰 New amount: {updated['data']['amount']}")
            
            # Test 4: Query documents
            print("\n🔎 Test 2.4: Querying documents...")
            results = await engine.query(
                "test_invoice",
                filters={"customer": "Test Corp"},
                limit=10
            )
            print(f"  ✅ Found {len(results)} documents")
            
            # Test 5: Delete document (cleanup)
            print("\n🗑️  Test 2.5: Deleting document (cleanup)...")
            deleted = await engine.delete("test_invoice", doc_id)
            print(f"  ✅ Deleted: {deleted}")
            
        else:
            print(f"  ❌ Storage failed: {result.backends_results}")
    
    except Exception as e:
        print(f"  ❌ Error: {e}")
        print(f"  ℹ️  Note: Make sure PostgreSQL is running and migrations are applied!")
    
    print("\n✅ Storage Engine test complete!")


async def test_combined_workflow():
    """Test validation + storage workflow."""
    print("\n" + "="*60)
    print("TEST 3: COMBINED VALIDATION + STORAGE")
    print("="*60)
    
    validation_engine = ValidationEngine()
    storage_engine = StorageEngine()
    
    doc = {
        "document_id": "COMBINED-001",
        "reference_code": "REF-9999",
        "amount": 25000,
        "status": "approved",
        "description": "Testing combined validation and storage workflow",
        "customer": "Integration Test Corp",
        "_metadata": {
            "confidence_scores": {
                "document_id": 0.98,
                "amount": 0.95
            }
        }
    }
    
    # Step 1: Validate
    print("\n🔍 Step 1: Validating document...")
    validation_result = await validation_engine.validate("my_document", doc.copy())
    
    print(f"  Validation: {'✅ PASSED' if validation_result.passed else '❌ FAILED'}")
    print(f"  Score: {validation_result.score:.2%}")
    
    if not validation_result.passed:
        print(f"  Errors:")
        for r in validation_result.results:
            if not r['passed']:
                print(f"    - {r['message']}")
        print("\n  ⛔ Document will NOT be stored due to validation failure")
        return
    
    # Step 2: Store if validation passed
    print("\n💾 Step 2: Storing validated document...")
    try:
        storage_result = await storage_engine.store(
            "validated_documents",
            doc.copy(),
            options={"unique_field": "document_id"}
        )
        
        if storage_result.success:
            print(f"  ✅ Stored with ID: {storage_result.document_id}")
            
            # Cleanup
            await storage_engine.delete("validated_documents", storage_result.document_id)
            print(f"  🗑️  Cleaned up test document")
        else:
            print(f"  ❌ Storage failed")
    except Exception as e:
        print(f"  ⚠️  Storage error: {e}")
    
    print("\n✅ Combined workflow test complete!")


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("🧪 UNIVERSAL VALIDATION & STORAGE SYSTEM - TEST SUITE")
    print("="*60)
    
    try:
        # Run validation tests
        await test_validation_engine()
        
        # Run storage tests (may fail if DB not set up)
        await test_storage_engine()
        
        # Run combined workflow
        await test_combined_workflow()
        
        print("\n" + "="*60)
        print("🎉 ALL TESTS COMPLETE!")
        print("="*60)
        print("\nNext steps:")
        print("1. Run database migration: alembic upgrade head")
        print("2. Create custom validation rules in config/validation/rules.yaml")
        print("3. Test with your own document types!")
        print()
        
    except Exception as e:
        logger.error(f"Test suite failed: {e}", exc_info=True)
        print(f"\n❌ Test suite failed: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure PostgreSQL is running")
        print("2. Run migrations: alembic upgrade head")
        print("3. Check your database connection settings")


if __name__ == "__main__":
    asyncio.run(main())
