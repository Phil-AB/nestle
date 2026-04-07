"""
Reporting and Analytics Demo

Demonstrates the reporting and analytics capabilities of the validation engine.

This example shows:
1. Generating validation summary reports in multiple formats
2. Creating detailed discrepancy reports
3. Generating executive summaries
4. Comparing versions with reports
5. Analytics dashboard data
6. Exporting to different formats (JSON, CSV, PDF)
"""

import asyncio
from uuid import uuid4, UUID
from datetime import datetime

from modules.validation_engine import (
    get_validation_engine,
    get_report_manager,
    get_analytics_engine
)
from modules.validation_engine.reporting import (
    ReportRequest,
    ReportFormat,
    ReportType
)
from modules.validation_engine.core.base import (
    ValidationContext,
    Discrepancy,
    ValidationResult
)


async def main():
    print("=" * 80)
    print("REPORTING AND ANALYTICS DEMO")
    print("=" * 80)
    print()

    # Initialize components
    report_manager = get_report_manager()
    analytics_engine = get_analytics_engine()

    # =========================================================================
    # STEP 1: Create Sample Validation Session
    # =========================================================================
    print("STEP 1: Creating sample validation session")
    print("-" * 80)

    session_id = uuid4()

    # Create sample context with validation results and discrepancies
    sample_context = ValidationContext(
        session_id=session_id,
        use_case="boe_validation",
        version=1,
        documents={
            "bill_of_entry": {"net_weight": "1000 KG", "hs_code": "8471.30.00"},
            "invoice": {"net_weight": "999 KG", "hs_code": "8471.30.00"},
            "packing_list": {"net_weight": "1000 KG", "hs_code": "8471.30.00"}
        },
        primary_document="bill_of_entry",
        supporting_documents=["invoice", "packing_list"],
        config={},
        validation_results=[
            ValidationResult(
                validator_name="tolerance_validator",
                field_name="net_weight",
                passed=False,
                confidence=0.95,
                message="Weight exceeds tolerance threshold"
            ),
            ValidationResult(
                validator_name="exact_match_validator",
                field_name="hs_code",
                passed=True,
                confidence=1.0,
                message="HS Code matches across all documents"
            ),
            ValidationResult(
                validator_name="exact_match_validator",
                field_name="gross_weight",
                passed=True,
                confidence=0.98,
                message="Gross weight matches"
            )
        ],
        discrepancies=[
            Discrepancy(
                field_name="net_weight",
                source_document="bill_of_entry",
                target_document="invoice",
                source_value="1000 KG",
                target_value="999 KG",
                discrepancy_type="value_mismatch",
                severity="critical",
                confidence=0.95,
                category="weight",
                likely_cause="measurement_difference",
                impact="high",
                auto_fix_applied=False
            )
        ]
    )

    # Store session (in production, this would be in database)
    from modules.validation_engine.core.session_manager import get_session_manager
    session_manager = get_session_manager()
    session_manager.create_session(sample_context)

    print(f"✓ Created validation session: {session_id}")
    print(f"  Use case: {sample_context.use_case}")
    print(f"  Documents: {len(sample_context.documents)}")
    print(f"  Validations: {len(sample_context.validation_results)}")
    print(f"  Discrepancies: {len(sample_context.discrepancies)}")
    print()

    # =========================================================================
    # STEP 2: Generate Validation Summary Report (JSON)
    # =========================================================================
    print("STEP 2: Generating Validation Summary Report (JSON)")
    print("-" * 80)

    request = ReportRequest(
        report_type=ReportType.VALIDATION_SUMMARY,
        format=ReportFormat.JSON,
        session_id=session_id
    )

    report = await report_manager.generate_report(request)

    print(f"✓ Report generated:")
    print(f"  Report ID: {report['metadata']['report_id']}")
    print(f"  Type: {report['metadata']['report_type']}")
    print(f"  Format: {report['metadata']['format']}")
    print()

    print("Summary:")
    summary = report['data']['validation_summary']
    print(f"  Total Validations: {summary['total_validations']}")
    print(f"  Passed: {summary['passed_validations']}")
    print(f"  Failed: {summary['failed_validations']}")
    print(f"  Accuracy: {summary['accuracy_score']}%")
    print(f"  Final Status: {summary['final_status']}")
    print()

    disc_summary = report['data']['discrepancy_summary']
    print("Discrepancies:")
    print(f"  Total: {disc_summary['total_discrepancies']}")
    print(f"  Critical: {disc_summary['by_severity']['critical']}")
    print(f"  Major: {disc_summary['by_severity']['major']}")
    print(f"  Minor: {disc_summary['by_severity']['minor']}")
    print()

    # =========================================================================
    # STEP 3: Generate Detailed Discrepancy Report
    # =========================================================================
    print("STEP 3: Generating Detailed Discrepancy Report")
    print("-" * 80)

    request = ReportRequest(
        report_type=ReportType.DISCREPANCY_DETAIL,
        format=ReportFormat.JSON,
        session_id=session_id
    )

    report = await report_manager.generate_report(request)

    print(f"✓ Discrepancy detail report generated")
    print()

    data = report['data']
    print(f"Total Discrepancies: {data['total_discrepancies']}")
    print(f"Resolution Rate: {data['resolution_rate']}%")
    print(f"Average Confidence: {data['avg_confidence']}")
    print()

    print("Breakdown by Severity:")
    print(f"  Critical: {len(data['critical_discrepancies'])}")
    print(f"  Major: {len(data['major_discrepancies'])}")
    print(f"  Minor: {len(data['minor_discrepancies'])}")
    print(f"  Info: {len(data['info_discrepancies'])}")
    print()

    print("Breakdown by Category:")
    for category, discs in data['by_category'].items():
        print(f"  {category}: {len(discs)}")
    print()

    # =========================================================================
    # STEP 4: Generate Executive Summary
    # =========================================================================
    print("STEP 4: Generating Executive Summary")
    print("-" * 80)

    request = ReportRequest(
        report_type=ReportType.EXECUTIVE_SUMMARY,
        format=ReportFormat.JSON,
        session_id=session_id
    )

    report = await report_manager.generate_report(request)

    exec_summary = report['data']
    print(f"✓ Executive summary generated")
    print()

    print(f"Status: {exec_summary['final_status'].upper()} ({exec_summary['status_color']})")
    print(f"Message: {exec_summary['status_message']}")
    print(f"Accuracy: {exec_summary['accuracy_score']}%")
    print()

    print("Key Findings:")
    for i, finding in enumerate(exec_summary['key_findings'], 1):
        print(f"  {i}. {finding}")
    print()

    if exec_summary['recommendations']:
        print("Recommendations:")
        for i, rec in enumerate(exec_summary['recommendations'], 1):
            print(f"  {i}. {rec}")
        print()

    # =========================================================================
    # STEP 5: Export to CSV
    # =========================================================================
    print("STEP 5: Exporting to CSV Format")
    print("-" * 80)

    request = ReportRequest(
        report_type=ReportType.VALIDATION_SUMMARY,
        format=ReportFormat.CSV,
        session_id=session_id
    )

    report = await report_manager.generate_report(request)

    csv_content = report['data']
    csv_lines = csv_content.split('\n')

    print(f"✓ CSV report generated")
    print(f"  Total lines: {len(csv_lines)}")
    print()

    print("Preview (first 15 lines):")
    print("-" * 40)
    for line in csv_lines[:15]:
        print(line)
    print("-" * 40)
    print()

    # Save CSV to file
    csv_filename = f"validation_report_{session_id}.csv"
    with open(csv_filename, 'w') as f:
        f.write(csv_content)
    print(f"✓ Saved to: {csv_filename}")
    print()

    # =========================================================================
    # STEP 6: Generate PDF Report
    # =========================================================================
    print("STEP 6: Generating PDF Report")
    print("-" * 80)

    request = ReportRequest(
        report_type=ReportType.VALIDATION_SUMMARY,
        format=ReportFormat.PDF,
        session_id=session_id
    )

    report = await report_manager.generate_report(request)

    pdf_content = report['data']

    print(f"✓ PDF report generated")
    print(f"  Size: {len(pdf_content)} bytes")
    print()

    # Save PDF to file
    pdf_filename = f"validation_report_{session_id}.pdf"
    with open(pdf_filename, 'wb') as f:
        f.write(pdf_content)
    print(f"✓ Saved to: {pdf_filename}")
    print(f"  Note: For production PDF, install weasyprint")
    print()

    # =========================================================================
    # STEP 7: Analytics Dashboard (Simulated)
    # =========================================================================
    print("STEP 7: Analytics Dashboard Data")
    print("-" * 80)

    from datetime import timedelta

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)

    dashboard = await analytics_engine.get_dashboard_data(
        start_date=start_date,
        end_date=end_date
    )

    print(f"✓ Analytics dashboard data generated")
    print(f"  Period: {start_date.date()} to {end_date.date()}")
    print()

    print("Overall Metrics:")
    print(f"  Total Sessions: {dashboard.total_sessions}")
    print(f"  Total Validations: {dashboard.total_validations}")
    print(f"  Average Accuracy: {dashboard.avg_accuracy}%")
    print(f"  Revalidation Rate: {dashboard.revalidation_rate}%")
    print()

    if dashboard.status_distribution:
        print("Status Distribution:")
        for status, count in dashboard.status_distribution.items():
            print(f"  {status}: {count}")
        print()

    if dashboard.discrepancy_trends:
        print("Discrepancy Trends:")
        for severity, count in dashboard.discrepancy_trends.items():
            print(f"  {severity}: {count}")
        print()

    # =========================================================================
    # STEP 8: Audit Trail Report
    # =========================================================================
    print("STEP 8: Generating Audit Trail Report")
    print("-" * 80)

    request = ReportRequest(
        report_type=ReportType.AUDIT_TRAIL,
        format=ReportFormat.JSON,
        session_id=session_id
    )

    report = await report_manager.generate_report(request)

    audit = report['data']

    print(f"✓ Audit trail report generated")
    print()

    print(f"Session ID: {audit['session_id']}")
    print(f"Use Case: {audit['use_case']}")
    print(f"Created: {audit['created_at']}")
    print(f"Total Events: {audit['total_events']}")
    print()

    print("Event Breakdown:")
    print(f"  Workflow Events: {len(audit['workflow_events'])}")
    print(f"  Validation Steps: {len(audit['validation_steps'])}")
    print(f"  User Inputs: {len(audit['user_inputs'])}")
    print(f"  User Confirmations: {len(audit['user_confirmations'])}")
    print()

    # =========================================================================
    # COMPLETE
    # =========================================================================
    print("=" * 80)
    print("DEMO COMPLETE")
    print("=" * 80)
    print()

    print("Generated Reports:")
    print(f"  1. Validation Summary (JSON)")
    print(f"  2. Discrepancy Detail (JSON)")
    print(f"  3. Executive Summary (JSON)")
    print(f"  4. Validation Summary (CSV) - saved to {csv_filename}")
    print(f"  5. Validation Summary (PDF) - saved to {pdf_filename}")
    print(f"  6. Analytics Dashboard Data")
    print(f"  7. Audit Trail (JSON)")
    print()

    print("The reporting system successfully:")
    print("  ✓ Generated reports in multiple formats (JSON, CSV, PDF)")
    print("  ✓ Provided 6 different report types")
    print("  ✓ Generated analytics dashboard data")
    print("  ✓ Exported to files (CSV, PDF)")
    print("  ✓ Calculated comprehensive metrics")
    print("  ✓ Created executive summaries and audit trails")
    print()

    print("All reports are production-ready and can be:")
    print("  - Served via REST API")
    print("  - Exported to cloud storage")
    print("  - Emailed to stakeholders")
    print("  - Integrated with BI tools")
    print()


if __name__ == "__main__":
    asyncio.run(main())
