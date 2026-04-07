"""
LangGraph Workflow Example
Demonstrates end-to-end BOE validation with LangGraph orchestration
"""

import asyncio
from uuid import uuid4
from modules.validation_engine.orchestration import get_validation_workflow
from modules.validation_engine.core.config_loader import get_config_loader


async def main():
    """Run LangGraph workflow example"""

    print("=" * 80)
    print("LangGraph Validation Workflow Example")
    print("=" * 80)

    # Sample documents
    documents = {
        "bill_of_entry": {
            "hs_code": "1234.56",
            "net_weight": 1000.0,
            "gross_weight": 1100.0,
            "quantity": 50,
            "duty_rate": 0.05,
            "duty_amount": 250.0
        },
        "invoice": {
            "hs_code": "1234.56",
            "net_weight": 1005.0,  # 0.5% difference
            "unit_price": 100.0,
            "quantity": 50
        },
        "packing_list": {
            "hs_code": "1234.56",
            "net_weight": 1003.0,
            "gross_weight": 1105.0,
            "quantity": 50
        }
    }

    # Load BOE validation configuration
    config_loader = get_config_loader()
    config = config_loader.load_use_case("boe_validation")

    # Get workflow
    workflow = get_validation_workflow()

    # Generate session ID
    session_id = uuid4()

    print(f"\n📋 Session ID: {session_id}")
    print(f"📄 Use Case: boe_validation")
    print(f"📦 Documents: {len(documents)}")

    # Run workflow
    print("\n🚀 Starting LangGraph workflow...")
    print("\nWorkflow Steps:")
    print("  1. INITIALIZE → Set up session")
    print("  2. NORMALIZE → French/English, units, formats")
    print("  3. VALIDATE → Run all validators")
    print("  4. ANALYZE → Check discrepancies")
    print("  5. [CONDITIONAL] → Route based on results")
    print("  6. GENERATE_REPORT → Final report")

    final_state = await workflow.run(
        session_id=session_id,
        documents=documents,
        config=config,
        primary_document="bill_of_entry",
        supporting_documents=["invoice", "packing_list"]
    )

    # Display results
    print("\n" + "=" * 80)
    print("Workflow Results")
    print("=" * 80)

    print(f"\n📊 Workflow Status: {final_state['workflow_status']}")
    print(f"✅ Final Status: {final_state['final_status']}")

    print(f"\n📝 Completed Steps:")
    for step in final_state.get("completed_steps", []):
        print(f"   ✓ {step}")

    if final_state.get("failed_steps"):
        print(f"\n❌ Failed Steps:")
        for step in final_state["failed_steps"]:
            print(f"   ✗ {step}")

    # Normalization results
    if final_state.get("normalized"):
        print(f"\n🔄 Normalization: SUCCESS")
        print(f"   Normalized {len(final_state['normalized_documents'])} documents")
    else:
        print(f"\n🔄 Normalization: SKIPPED or FAILED")

    # Validation results
    validation_results = final_state.get("validation_results", [])
    if validation_results:
        passed = sum(1 for r in validation_results if r["passed"])
        print(f"\n✅ Validation Results:")
        print(f"   Total: {len(validation_results)}")
        print(f"   Passed: {passed}")
        print(f"   Failed: {len(validation_results) - passed}")
        print(f"   Pass Rate: {passed/len(validation_results)*100:.1f}%")

    # Discrepancies
    discrepancies = final_state.get("discrepancies", [])
    if discrepancies:
        print(f"\n🔍 Discrepancies Found: {len(discrepancies)}")

        # Count by severity
        from modules.validation_engine.utils.constants import Severity
        critical = sum(1 for d in discrepancies if d["severity"] == Severity.CRITICAL)
        major = sum(1 for d in discrepancies if d["severity"] == Severity.MAJOR)
        minor = sum(1 for d in discrepancies if d["severity"] == Severity.MINOR)

        print(f"   🚨 Critical: {critical}")
        print(f"   ⚠️  Major: {major}")
        print(f"   ℹ️  Minor: {minor}")

        # Show top 3
        print(f"\n   Top Discrepancies:")
        for i, disc in enumerate(discrepancies[:3], 1):
            print(f"   {i}. {disc['field_name']} ({disc['severity']})")
    else:
        print(f"\n✅ No discrepancies found!")

    # User interaction required?
    if final_state.get("requires_user_confirmation"):
        print(f"\n⏸️  Workflow Status: AWAITING USER CONFIRMATION")
        print(f"   User must review and confirm discrepancies")
    else:
        print(f"\n✅ Workflow Status: COMPLETED")

    # Messages
    messages = final_state.get("messages", [])
    if messages:
        print(f"\n📋 Workflow Messages:")
        for msg in messages:
            print(f"   • {msg}")

    print("\n" + "=" * 80)
    print("LangGraph workflow completed!")
    print("=" * 80)

    return final_state


if __name__ == "__main__":
    asyncio.run(main())
