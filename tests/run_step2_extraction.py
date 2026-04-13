"""
Step 2 Extraction Test — Run vendor documents through the extraction pipeline
and compare results against ground truth.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Load .env file
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api.services.document_processing_service import DocumentProcessingService

TEST_PDFS = Path(project_root) / "test-pdfs"

DOC_MAP = {
    "invoice": "Invoice_ (1).pdf",
    "packing_list": "Packing list_.pdf",
    "bill_of_lading": "Bill oF Lading.pdf",
}


async def extract_all():
    svc = DocumentProcessingService(use_database=False, use_ai_enhancement=True)
    results = {}
    for doc_type, filename in DOC_MAP.items():
        path = TEST_PDFS / filename
        print(f"\n{'='*60}")
        print(f"  Extracting: {doc_type} — {filename}")
        print(f"{'='*60}")
        result = await svc.process_document(file_path=path, document_type=doc_type)
        results[doc_type] = result
        print(f"  Status  : {result.get('status')}")
        print(f"  Fields  : {len(result.get('fields', {}))}")
        print(f"  Items   : {len(result.get('items', []))}")
    return results


def print_fields(doc_type: str, result: dict):
    """Pretty-print extracted fields for a document."""
    fields = result.get("fields", {})
    items = result.get("items", [])
    print(f"\n{'─'*60}")
    print(f"  {doc_type.upper()} — EXTRACTED FIELDS")
    print(f"{'─'*60}")
    for k, v in sorted(fields.items()):
        if v is not None:
            print(f"  {k:40s}: {v}")
    if items:
        print(f"\n  LINE ITEMS ({len(items)}):")
        for i, item in enumerate(items[:5], 1):
            print(f"    Item {i}: {json.dumps(item, default=str)[:200]}")


def compare_invoice(fields: dict):
    """Compare invoice fields against ground truth."""
    print(f"\n{'='*60}")
    print("  INVOICE — GROUND TRUTH COMPARISON")
    print(f"{'='*60}")

    expected = {
        "shipper_name": "Vreugdenhil Dairy Foods",
        "shipper_address": "Arkerpoort 5, P.O. Box 64, 3860 AB Nijkerk, The Netherlands",
        "consignee_name": "Nestlé Ghana Limited",
        "consignee_address": "Private Mail Bag, Kotoka International Airport, Accra, Ghana",
        "invoice_number": "9400080882",
        "invoice_date": "2026-01-21",   # or Jan 21, 2026
        "po_number": "4562599410",       # Your Order Number
        "order_number": "64896",         # Our Order Number
        "contract_number": "40017796",
        "incoterm": "FCA",
        "port_of_loading": "Rotterdam Port",
        "total_fob_value": "467775.00",
        "currency": "EUR",
        "net_weight": "189000",
        "gross_weight": "192780",
        "quantity": "7560",
        "product_description": "FFP 28% MQAV004F-1 25kg bag",
    }

    gaps = []
    for field, gt_val in expected.items():
        extracted = fields.get(field)
        if extracted is None:
            status = "MISSING"
            gaps.append(f"MISSING: {field} (expected: {gt_val!r})")
        else:
            extracted_str = str(extracted).strip()
            gt_str = str(gt_val).strip()
            if gt_str.lower() in extracted_str.lower() or extracted_str.lower() in gt_str.lower():
                status = "OK"
            else:
                status = "MISMATCH"
                gaps.append(f"MISMATCH: {field} — extracted={extracted_str!r}, expected={gt_val!r}")
        print(f"  [{status:8s}] {field:30s}: {str(extracted or '—')[:60]}")

    return gaps


def compare_packing_list(fields: dict, items: list):
    """Compare packing list fields against ground truth."""
    print(f"\n{'='*60}")
    print("  PACKING LIST — GROUND TRUTH COMPARISON")
    print(f"{'='*60}")

    expected_header = {
        "document_date": "2026-01-08",   # 08-01-2026
        "order_number": "64896",
        "contract_number": "40017796",
        "consignee_name": "Nestlé Ghana Limited",
        "incoterm": "FCA",
        "total_quantity": "7560",
        "total_net_weight": "189000",
        "total_gross_weight": "192780",
        "product_description": "Instant Fat Filled Powder 28%",
        "article_number": "E36001065",
    }

    # Expected containers
    expected_containers = [
        "CAAU8000243", "GCNU4792418", "GCNU4808303",
        "GCNU4866249", "GCNU4822554", "GCNU4803430", "GCNU4823653",
    ]

    gaps = []
    for field, gt_val in expected_header.items():
        extracted = fields.get(field)
        if extracted is None:
            status = "MISSING"
            gaps.append(f"MISSING: {field} (expected: {gt_val!r})")
        else:
            extracted_str = str(extracted).strip()
            gt_str = str(gt_val).strip()
            if gt_str.lower() in extracted_str.lower() or extracted_str.lower() in gt_str.lower():
                status = "OK"
            else:
                status = "MISMATCH"
                gaps.append(f"MISMATCH: {field} — extracted={extracted_str!r}, expected={gt_val!r}")
        print(f"  [{status:8s}] {field:30s}: {str(extracted or '—')[:60]}")

    # Check container numbers in items
    all_text = json.dumps(items, default=str)
    print(f"\n  CONTAINER NUMBER CHECK (expected 7 containers):")
    for cn in expected_containers:
        found = cn in all_text or cn in json.dumps(fields, default=str)
        status = "OK" if found else "MISSING"
        if not found:
            gaps.append(f"MISSING container: {cn}")
        print(f"  [{status:8s}] {cn}")

    return gaps


def compare_bol(fields: dict, items: list):
    """Compare bill of lading fields against ground truth."""
    print(f"\n{'='*60}")
    print("  BILL OF LADING — GROUND TRUTH COMPARISON")
    print(f"{'='*60}")

    expected = {
        "carrier_name": "Grimaldi",
        "bl_number": "S328717359",
        "booking_number": "S328717359",
        "shipper_name": "Vreugdenhil Dairy Foods",
        "consignee_name": "Nestle Ghana",
        "port_of_loading": "ANTWERP",
        "port_of_discharge": "TEMA",
        "vessel_name": "GREAT TEMA",
        "net_weight": "189000",
        "gross_weight": "192780",
        "total_quantity": "7560",
        "order_number": "64896",
        "contract_number": "40017796",
        "number_of_containers": "7",
    }

    gaps = []
    for field, gt_val in expected.items():
        extracted = fields.get(field)
        if extracted is None:
            status = "MISSING"
            gaps.append(f"MISSING: {field} (expected: {gt_val!r})")
        else:
            extracted_str = str(extracted).strip()
            gt_str = str(gt_val).strip()
            if gt_str.lower() in extracted_str.lower() or extracted_str.lower() in gt_str.lower():
                status = "OK"
            else:
                status = "MISMATCH"
                gaps.append(f"MISMATCH: {field} — extracted={extracted_str!r}, expected={gt_val!r}")
        print(f"  [{status:8s}] {field:30s}: {str(extracted or '—')[:60]}")

    return gaps


async def main():
    print("\n" + "="*60)
    print("  STEP 2 — VENDOR DOCUMENT EXTRACTION TEST")
    print("="*60)

    results = await extract_all()

    # Print all extracted fields
    for doc_type, result in results.items():
        print_fields(doc_type, result)

    # Ground truth comparison
    all_gaps = {}

    inv_fields = results["invoice"].get("fields", {})
    all_gaps["invoice"] = compare_invoice(inv_fields)

    pl_fields = results["packing_list"].get("fields", {})
    pl_items = results["packing_list"].get("items", [])
    all_gaps["packing_list"] = compare_packing_list(pl_fields, pl_items)

    bol_fields = results["bill_of_lading"].get("fields", {})
    bol_items = results["bill_of_lading"].get("items", [])
    all_gaps["bill_of_lading"] = compare_bol(bol_fields, bol_items)

    # Summary
    print(f"\n{'='*60}")
    print("  SUMMARY OF GAPS / ERRORS")
    print(f"{'='*60}")
    total_gaps = 0
    for doc_type, gaps in all_gaps.items():
        if gaps:
            print(f"\n  {doc_type.upper()} ({len(gaps)} issues):")
            for g in gaps:
                print(f"    ⚠  {g}")
            total_gaps += len(gaps)
        else:
            print(f"\n  {doc_type.upper()}: ✓ All fields match")

    print(f"\n  Total issues: {total_gaps}")

    # Save raw output for inspection
    output_path = TEST_PDFS / "extraction_results.json"
    with open(output_path, "w") as f:
        json.dump(
            {k: {"fields": v.get("fields", {}), "items": v.get("items", []), "status": v.get("status")}
             for k, v in results.items()},
            f, indent=2, default=str
        )
    print(f"\n  Raw results saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
