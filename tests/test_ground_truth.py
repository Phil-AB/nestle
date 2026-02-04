"""
Quick test for the Ground Truth Validator.
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from modules.extraction.validation import ValidationEngine


async def test_ground_truth_validator():
    print("\n" + "="*60)
    print("🎯 GROUND TRUTH VALIDATOR TEST")
    print("="*60)
    
    engine = ValidationEngine()
    
    # Simulated OCR extraction (with some errors)
    extracted_data = {
        "invoice_number": "INV-12345",      # ✅ Correct
        "supplier_name": "ACME Corporation", # ⚠️ Close (truth: "ACME Corp")
        "total_amount": 15000.50,            # ⚠️ Off by 0.50 (truth: 15000.00)
        "date": "2024-01-15",                # ✅ Correct
        "po_number": "PO-9999"               # ❌ Wrong (truth: "PO-8888")
    }
    
    # Ground truth (manually verified or from database)
    ground_truth = {
        "invoice_number": "INV-12345",
        "supplier_name": "ACME Corp",
        "total_amount": 15000.00,
        "date": "2024-01-15",
        "po_number": "PO-8888"
    }
    
    # Validation config
    validation_config = {
        "validator": "ground_truth",
        "params": {
            "fields": [
                {"field": "invoice_number", "strategy": "exact"},
                {"field": "supplier_name", "strategy": "fuzzy", "threshold": 0.85},
                {"field": "total_amount", "strategy": "numeric", "tolerance": 1.00},
                {"field": "date", "strategy": "exact"},
                {"field": "po_number", "strategy": "exact"}
            ],
            "min_accuracy": 0.80  # 80% accuracy required
        },
        "severity": "error"
    }
    
    # Manually create validator (simulating config-driven approach)
    from modules.extraction.validation.validators.accuracy_validators import GroundTruthValidator
    
    validator = GroundTruthValidator(validation_config)
    result = await validator.validate(
        extracted_data,
        context={"ground_truth": ground_truth}
    )
    
    print(f"\n📊 Results:")
    print(f"  Overall Passed: {result.passed}")
    print(f"  Accuracy Score: {result.actual_value:.2%}")
    print(f"  Threshold: {result.expected_value:.2%}")
    
    print(f"\n📝 Field-by-Field Results:")
    field_results = result.metadata.get('field_results', {})
    for field, details in field_results.items():
        status = "✅" if details['match'] else "❌"
        score = details['score']
        print(f"  {status} {field}: {score:.2%}")
        print(f"     Extracted: {details.get('extracted')}")
        print(f"     Truth:     {details.get('ground_truth')}")
        if 'difference' in details:
            print(f"     Difference: {details['difference']}")
        if 'similarity' in details:
            print(f"     Similarity: {details['similarity']:.2%}")
    
    if not result.passed:
        print(f"\n⚠️  Message: {result.message}")
    else:
        print(f"\n✅ All fields meet accuracy threshold!")
    
    print("\n" + "="*60)


if __name__ == "__main__":
    asyncio.run(test_ground_truth_validator())
