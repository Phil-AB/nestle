"""
BOE Validation Example
Demonstrates how to use the BOE validation configuration
"""

import asyncio
from modules.validation_engine import get_validation_engine


async def main():
    """Run BOE validation example"""

    # Sample documents (in production, these come from extraction module)
    documents = {
        "bill_of_entry": {
            "hs_code": "1234.56",
            "net_weight": 1000.0,
            "gross_weight": 1100.0,
            "quantity": 50,
            "duty_rate": 0.05,
            "duty_amount": 250.0,
            "description": "Electronic Components",
            "origin": "China"
        },
        "invoice": {
            "hs_code": "1234.56",
            "net_weight": 1005.0,  # 0.5% difference - within tolerance
            "unit_price": 100.0,
            "quantity": 50,
            "description": "Electronic Components",
            "origin": "China",
            "invoice_number": "INV-2026-001",
            "invoice_date": "2026-02-09"
        },
        "packing_list": {
            "hs_code": "1234.56",
            "net_weight": 1003.0,  # 0.3% difference - within tolerance
            "gross_weight": 1105.0,  # 0.45% difference - within tolerance
            "quantity": 50,
            "description": "Electronic Components"
        }
    }

    # Get validation engine
    engine = get_validation_engine()

    print("=" * 80)
    print("BOE Validation Example")
    print("=" * 80)

    # Step 1: Create validation session
    print("\n1. Creating validation session...")
    context = await engine.create_validation_session(
        use_case="boe_validation",
        documents=documents,
        tolerance_overrides={
            "net_weight_invoice_to_boe_tolerance": 1.0,  # Session-specific override
        }
    )
    print(f"   ✅ Session created: {context.session_id}")
    print(f"   📄 Documents: {context.primary_document} + {len(context.supporting_documents)} supporting")

    # Step 2: Run validation workflow
    print("\n2. Running validation workflow...")
    summary = await engine.run_validation_workflow(context.session_id)

    print(f"\n   📊 Validation Results:")
    print(f"   - Total validations: {summary.total_validations}")
    print(f"   - Passed: {summary.passed_validations} ✅")
    print(f"   - Failed: {summary.failed_validations} ❌")
    print(f"   - Average confidence: {summary.average_confidence:.2%}")

    print(f"\n   🔍 Discrepancies:")
    print(f"   - Critical: {summary.critical_discrepancies} 🚨")
    print(f"   - Major: {summary.major_discrepancies} ⚠️")
    print(f"   - Minor: {summary.minor_discrepancies} ℹ️")
    print(f"   - Auto-fixed: {summary.auto_fixed_count} 🔧")

    # Step 3: Get detailed report
    print("\n3. Generating validation report...")
    report = await engine.get_validation_report(context.session_id, format="json")

    print(f"   📋 Final Status: {report['final_status']}")

    # Show top discrepancies
    if report.get('top_discrepancies'):
        print(f"\n   🔍 Top Discrepancies:")
        for i, disc in enumerate(report['top_discrepancies'][:3], 1):
            print(f"      {i}. {disc['field_name']}: {disc['severity']}")
            print(f"         {disc.get('likely_cause', 'Unknown cause')}")

    # Step 4: Get session status
    print("\n4. Session Status:")
    status = engine.get_session_status(context.session_id)
    print(f"   - Use case: {status['use_case']}")
    print(f"   - Version: {status['version']}")
    print(f"   - Current step: {status['current_step']}")
    print(f"   - Final status: {status['final_status']}")

    print("\n" + "=" * 80)
    print("Example completed!")
    print("=" * 80)

    return context, summary, report


if __name__ == "__main__":
    asyncio.run(main())
