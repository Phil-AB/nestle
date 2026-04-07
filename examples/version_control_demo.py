"""
Version Control Demo

Demonstrates the version control and revalidation capabilities
of the validation engine.

This example shows:
1. Creating an initial validation (V1)
2. Detecting discrepancies
3. Creating a revalidation with corrected documents (V2)
4. Comparing V1 vs V2 with delta analysis
5. Viewing version history and lineage
"""

import asyncio
from uuid import uuid4

from modules.validation_engine import (
    get_validation_engine,
    get_revalidation_engine,
    get_version_manager,
    get_delta_analyzer,
    RevalidationRequest
)


async def main():
    print("=" * 80)
    print("VERSION CONTROL AND REVALIDATION DEMO")
    print("=" * 80)
    print()

    # Initialize engines
    validation_engine = get_validation_engine()
    revalidation_engine = get_revalidation_engine()
    version_manager = get_version_manager()
    delta_analyzer = get_delta_analyzer()

    # =========================================================================
    # STEP 1: Create Initial Validation (V1)
    # =========================================================================
    print("STEP 1: Creating initial validation (V1)")
    print("-" * 80)

    # Sample BOE documents with discrepancies
    documents_v1 = {
        "bill_of_entry": {
            "boe_number": "BOE-2025-001",
            "hs_code": "8471.30.00",
            "net_weight": "1000 KG",
            "gross_weight": "1100 KG",
            "invoice_value": "50000 USD",
            "duty_rate": "10%",
            "calculated_duty": "5000 USD",
            "invoice_date": "2025-01-15"
        },
        "invoice": {
            "invoice_number": "INV-2025-001",
            "hs_code": "8471.30.00",
            "net_weight": "999 KG",  # DISCREPANCY: 1 KG difference
            "gross_weight": "1100 KG",
            "total_value": "50000 USD",
            "invoice_date": "2025-01-15"
        },
        "packing_list": {
            "packing_list_number": "PL-2025-001",
            "hs_code": "8471.30.00",
            "net_weight": "1000 KG",
            "gross_weight": "1099 KG",  # DISCREPANCY: 1 KG difference
            "invoice_date": "2025-01-15"
        }
    }

    # Create validation session
    context_v1 = await validation_engine.create_validation_session(
        use_case="boe_validation",
        documents=documents_v1
    )

    print(f"✓ Created validation session: {context_v1.session_id}")
    print(f"  Use case: {context_v1.use_case}")
    print(f"  Version: V{context_v1.version}")
    print()

    # Run validation (simulated - in real scenario, would run full workflow)
    print("Running validation workflow...")
    # In production: await workflow.run(context_v1.session_id, ...)
    print("✓ Validation completed")
    print()

    # Create version metadata
    version_meta_v1 = await version_manager.create_version_metadata(
        context_v1,
        created_by="demo_user",
        notes="Initial BOE validation - found weight discrepancies",
        tags=["boe", "initial_validation", "demo"]
    )

    print(f"✓ Version metadata created:")
    print(f"  Status: {version_meta_v1.status}")
    print(f"  Total discrepancies: {version_meta_v1.total_discrepancies}")
    print(f"  Critical: {version_meta_v1.critical_count}")
    print(f"  Major: {version_meta_v1.major_count}")
    print(f"  Final status: {version_meta_v1.final_status}")
    print()

    # =========================================================================
    # STEP 2: Analyze V1 Results
    # =========================================================================
    print("STEP 2: Analyzing V1 results")
    print("-" * 80)

    # Get revalidation suggestion
    suggestion = await revalidation_engine.suggest_revalidation(
        context_v1.session_id
    )

    print(f"Revalidation recommended: {suggestion['recommended']}")
    print(f"Confidence: {suggestion['confidence']}")
    print("Reasons:")
    for reason in suggestion['reasons']:
        print(f"  - {reason}")
    print()

    # =========================================================================
    # STEP 3: Create Revalidation (V2) with Corrected Documents
    # =========================================================================
    print("STEP 3: Creating revalidation (V2) with corrected documents")
    print("-" * 80)

    # Updated documents with corrections
    documents_v2 = {
        "bill_of_entry": {
            "boe_number": "BOE-2025-001",
            "hs_code": "8471.30.00",
            "net_weight": "999.5 KG",  # CORRECTED: closer to invoice
            "gross_weight": "1100 KG",
            "invoice_value": "50000 USD",
            "duty_rate": "10%",
            "calculated_duty": "5000 USD",
            "invoice_date": "2025-01-15"
        },
        "invoice": {
            "invoice_number": "INV-2025-001",
            "hs_code": "8471.30.00",
            "net_weight": "999 KG",
            "gross_weight": "1100 KG",
            "total_value": "50000 USD",
            "invoice_date": "2025-01-15"
        },
        "packing_list": {
            "packing_list_number": "PL-2025-001",
            "hs_code": "8471.30.00",
            "net_weight": "999.5 KG",  # CORRECTED
            "gross_weight": "1100 KG",  # CORRECTED
            "invoice_date": "2025-01-15"
        }
    }

    # Create revalidation request
    revalidation_request = RevalidationRequest(
        original_session_id=context_v1.session_id,
        revalidation_reason="Updated BOE with corrected weights from customs",
        updated_documents=documents_v2,
        tolerance_overrides={
            "net_weight": 0.5  # Allow 0.5% tolerance
        },
        notes="Corrected net weight discrepancy after customs verification",
        tags=["weight_correction", "customs_verified"]
    )

    # Execute revalidation
    print("Executing revalidation...")
    revalidation_result = await revalidation_engine.create_revalidation(
        revalidation_request
    )

    print(f"✓ Revalidation completed:")
    print(f"  New session ID: {revalidation_result.new_session_id}")
    print(f"  New version: V{revalidation_result.new_version}")
    print(f"  Status: {revalidation_result.status}")
    print(f"  Final status: {revalidation_result.final_status}")
    print()

    # =========================================================================
    # STEP 4: Analyze V1 vs V2 Comparison
    # =========================================================================
    print("STEP 4: Comparing V1 vs V2")
    print("-" * 80)

    comparison = revalidation_result.comparison

    if comparison:
        print(f"Total changes detected: {comparison.total_changes}")
        print(f"  Fixed: {comparison.fixed_count}")
        print(f"  New: {comparison.new_count}")
        print(f"  Persistent: {comparison.persistent_count}")
        print(f"  Improved: {comparison.improved_count}")
        print(f"  Worsened: {comparison.worsened_count}")
        print()

        print(f"Improvement rate: {comparison.improvement_rate}%")
        print(f"Regression rate: {comparison.regression_rate}%")
        print()

        print("Detailed changes:")
        for i, change in enumerate(comparison.changes[:5], 1):  # Show first 5
            print(f"{i}. Field: {change.field_name}")
            print(f"   Type: {change.change_type}")
            if change.v1_present:
                print(f"   V1: {change.v1_source_value} vs {change.v1_target_value} ({change.v1_severity})")
            if change.v2_present:
                print(f"   V2: {change.v2_source_value} vs {change.v2_target_value} ({change.v2_severity})")
            print()

        # Get change summary
        summary = await delta_analyzer.get_change_summary(comparison)

        print("Overall Assessment:")
        print(f"  {summary['overall_assessment']}")
        print()

        if summary.get('critical_changes'):
            print("Critical Changes:")
            for change in summary['critical_changes']:
                print(f"  - {change['message']}")
            print()

        if summary.get('recommendations'):
            print("Recommendations:")
            for rec in summary['recommendations']:
                print(f"  - {rec}")
            print()

    # =========================================================================
    # STEP 5: Version History and Lineage
    # =========================================================================
    print("STEP 5: Viewing version history and lineage")
    print("-" * 80)

    # Get version history
    history = await version_manager.get_version_history(context_v1.session_id)

    print(f"Total versions: {len(history)}")
    print()

    for version in history:
        print(f"Version {version.version}:")
        print(f"  Session ID: {version.session_id}")
        print(f"  Status: {version.status}")
        print(f"  Final Status: {version.final_status}")
        print(f"  Accuracy: {version.accuracy_score}%")
        print(f"  Discrepancies: {version.total_discrepancies}")
        print(f"  Created: {version.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Notes: {version.notes}")
        print()

    # Get lineage
    lineage = await version_manager.get_lineage(
        revalidation_result.new_session_id,
        revalidation_result.new_version
    )

    print(f"Version Lineage (depth: {len(lineage)}):")
    for i, ver in enumerate(lineage):
        arrow = " → " if i < len(lineage) - 1 else ""
        print(f"  V{ver['version']} ({ver['final_status']}){arrow}", end="")
    print()
    print()

    # =========================================================================
    # STEP 6: Get Comprehensive Version Summary
    # =========================================================================
    print("STEP 6: Comprehensive version summary")
    print("-" * 80)

    summary = await version_manager.get_version_summary(
        revalidation_result.new_session_id,
        revalidation_result.new_version
    )

    print(f"Session: {summary['session_id']}")
    print(f"Version: V{summary['version']}")
    print(f"Status: {summary['status']}")
    print(f"Final Status: {summary['final_status']}")
    print(f"Accuracy: {summary['accuracy_score']}%")
    print()

    print("Validation Summary:")
    print(f"  Total: {summary['validation_summary']['total']}")
    print(f"  Passed: {summary['validation_summary']['passed']}")
    print(f"  Failed: {summary['validation_summary']['failed']}")
    print()

    print("Discrepancy Summary:")
    print(f"  Total: {summary['discrepancy_summary']['total']}")
    print(f"  Critical: {summary['discrepancy_summary']['critical']}")
    print(f"  Major: {summary['discrepancy_summary']['major']}")
    print(f"  Minor: {summary['discrepancy_summary']['minor']}")
    print()

    print("Metadata:")
    print(f"  Created by: {summary['metadata']['created_by']}")
    print(f"  Created at: {summary['metadata']['created_at']}")
    print(f"  Tags: {', '.join(summary['metadata']['tags'])}")
    print()

    # =========================================================================
    # COMPLETE
    # =========================================================================
    print("=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)
    print()
    print("Summary:")
    print(f"  - Created V1 with {len(documents_v1)} documents")
    print(f"  - Detected {version_meta_v1.total_discrepancies} discrepancies in V1")
    print(f"  - Created V2 with corrected documents")
    print(f"  - Fixed {comparison.fixed_count if comparison else 0} discrepancies")
    print(f"  - Tracked complete version lineage")
    print()
    print("The validation engine successfully:")
    print("  ✓ Tracked versions across multiple validations")
    print("  ✓ Performed delta analysis (V1 vs V2)")
    print("  ✓ Identified fixed, new, and persistent discrepancies")
    print("  ✓ Maintained version lineage and metadata")
    print("  ✓ Provided actionable recommendations")
    print()


if __name__ == "__main__":
    asyncio.run(main())
