"""
Step 6 BOE Validation Test — Extract the Bill of Entry, compare against ground
truth, then run the full 3-way validation workflow (BOE vs Invoice, Packing List,
BOL) and report results.

Usage:
    python tests/run_step6_boe_validation.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# ── Load .env ────────────────────────────────────────────────────────────────
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

# ── Project root on sys.path ─────────────────────────────────────────────────
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api.services.document_processing_service import DocumentProcessingService  # noqa: E402

TEST_PDFS = project_root / "test-pdfs"

# ── Ground truth (from test-pdfs/ground-truth/boe.txt) ───────────────────────
# Key fields the BOE extractor must produce for the validation workflow to work.
BOE_GROUND_TRUTH = {
    # Identity / reference
    "boe_number":      "40126075519",
    "bl_number":       "S328717359",
    "invoice_number":  "9400080882",
    # Parties
    "shipper_name":    "Vreugdenhil Dairy Foods",
    "consignee_name":  "Nestle Ghana Limited",
    # Goods
    "hs_code":         "1901.90",        # field 27 — 1901902000 → 1901.90
    "gross_weight":    "192780",
    "net_weight":      "189000",
    "quantity":        "7560",
    "product_description": "FFP 28%",
    "country_of_origin": "BE",
    # Financial
    "customs_value":   "6178472.22",
    "total_fob_value": "467775.00",
    "currency":        "EUR",
    "incoterm":        "FCA",
    # Tax / duty  (field 01 — Import Duty @ 5%)
    "duty_rate":       "0.05",           # stored as decimal fraction
    "duty_amount":     "308923.61",
}


def _unwrap(v):
    """Unwrap {value:..., source:...} envelope or return as-is."""
    if isinstance(v, dict) and "value" in v:
        return v["value"]
    return v


def _str(v) -> str:
    return str(_unwrap(v)).strip() if v is not None else ""


def section(title: str):
    bar = "=" * 62
    print(f"\n{bar}\n  {title}\n{bar}")


def divider(title: str = ""):
    print(f"\n{'─'*62}")
    if title:
        print(f"  {title}")
        print(f"{'─'*62}")


# ── 1. Extraction ─────────────────────────────────────────────────────────────

async def extract_boe() -> dict:
    svc = DocumentProcessingService(use_database=False, use_ai_enhancement=True)
    path = TEST_PDFS / "Bill Of Entry.pdf"
    section(f"EXTRACTING BOE — {path.name}")
    result = await svc.process_document(file_path=path, document_type="bill_of_entry")
    print(f"  Status : {result.get('status')}")
    print(f"  Fields : {len(result.get('fields', {}))}")
    print(f"  Items  : {len(result.get('items', []))}")
    return result


async def extract_vendor_docs() -> dict:
    """Re-extract the three vendor docs (same as Step 2)."""
    svc = DocumentProcessingService(use_database=False, use_ai_enhancement=True)
    doc_map = {
        "invoice":       "Invoice_ (1).pdf",
        "packing_list":  "Packing list_.pdf",
        "bill_of_lading": "Bill oF Lading.pdf",
    }
    section("EXTRACTING VENDOR DOCUMENTS (Step 2 inputs)")
    results = {}
    for doc_type, filename in doc_map.items():
        path = TEST_PDFS / filename
        print(f"\n  [{doc_type}] {filename}")
        r = await svc.process_document(file_path=path, document_type=doc_type)
        print(f"    Status={r.get('status')}  Fields={len(r.get('fields', {}))}  Items={len(r.get('items', []))}")
        results[doc_type] = r
    return results


# ── 2. Ground truth comparison ────────────────────────────────────────────────

def compare_boe(fields: dict) -> list:
    section("BOE — GROUND TRUTH COMPARISON")
    gaps = []

    for field, gt_val in BOE_GROUND_TRUTH.items():
        raw = fields.get(field)
        extracted_str = _str(raw)
        gt_str = str(gt_val).strip()

        if raw is None:
            status = "MISSING"
            gaps.append(f"MISSING: {field}  (expected: {gt_val!r})")
        elif gt_str.lower() in extracted_str.lower() or extracted_str.lower() in gt_str.lower():
            status = "OK     "
        else:
            status = "MISMATCH"
            gaps.append(
                f"MISMATCH: {field}  extracted={extracted_str!r}  expected={gt_val!r}"
            )
        print(f"  [{status}] {field:30s}: {extracted_str[:60]}")

    return gaps


def print_all_fields(label: str, fields: dict):
    divider(f"{label} — ALL EXTRACTED FIELDS")
    for k, v in sorted(fields.items()):
        if v is not None:
            print(f"  {k:40s}: {_str(v)[:80]}")


# ── 3. Run validation workflow ────────────────────────────────────────────────

async def run_validation_workflow(boe_result: dict, vendor_results: dict) -> dict:
    """Run the boe_validation workflow and return final_state."""
    from modules.validation_engine.core.session_manager import get_session_manager
    from modules.validation_engine.orchestration import get_validation_workflow

    documents = {
        "bill_of_entry": {
            **boe_result.get("fields", {}),
            "items": boe_result.get("items", []),
        },
    }
    for doc_type, r in vendor_results.items():
        documents[doc_type] = {
            **r.get("fields", {}),
            "items": r.get("items", []),
        }

    session_manager = get_session_manager()
    workflow = get_validation_workflow()

    context = await session_manager.create_session(
        use_case="boe_validation",
        documents=documents,
        primary_document="bill_of_entry",
        supporting_documents=[dt for dt in documents if dt != "bill_of_entry"],
        shipment_id="TEST-STEP6",
    )

    final_state = await workflow.run(
        session_id=context.session_id,
        documents=documents,
        config=context.config,
        primary_document="bill_of_entry",
        supporting_documents=context.supporting_documents,
    )

    return final_state


def print_validation_results(final_state: dict):
    section("VALIDATION WORKFLOW RESULTS")

    workflow_status = final_state.get("workflow_status", "unknown")
    final_status    = final_state.get("final_status", "unknown")
    all_passed      = final_state.get("all_validations_passed", False)
    discrepancies   = final_state.get("discrepancies", []) or []
    critical        = final_state.get("critical_discrepancies", []) or []
    val_results     = final_state.get("validation_results", []) or []

    print(f"  Workflow status : {workflow_status}")
    print(f"  Final status    : {final_status}")
    print(f"  All passed      : {all_passed}")
    print(f"  Total checks    : {len(val_results)}")
    print(f"  Passed          : {sum(1 for r in val_results if r.get('passed'))}")
    print(f"  Failed          : {sum(1 for r in val_results if not r.get('passed'))}")
    print(f"  Discrepancies   : {len(discrepancies)}")
    print(f"  Critical        : {len(critical)}")

    if val_results:
        divider("INDIVIDUAL CHECK RESULTS")
        for r in val_results:
            icon = "✓" if r.get("passed") else "✗"
            severity = r.get("severity", "")
            name     = r.get("check_name") or r.get("validator_name") or r.get("field_name") or "—"
            msg      = r.get("message") or r.get("description") or ""
            sv_tag   = f"[{severity.upper():8s}]" if severity else "          "
            print(f"  {icon} {sv_tag} {name}")
            if msg and not r.get("passed"):
                print(f"           → {msg[:120]}")
            if not r.get("passed"):
                sv = _str(r.get("source_value"))
                tv = _str(r.get("target_value"))
                if sv or tv:
                    print(f"           src={sv[:50]!r}  tgt={tv[:50]!r}")

    if discrepancies:
        divider("DISCREPANCIES")
        for d in discrepancies:
            sev  = (d.get("severity") or "").upper()
            name = d.get("field_name") or d.get("field") or "—"
            msg  = d.get("message") or d.get("description") or ""
            print(f"  ⚠  [{sev:8s}] {name}")
            if msg:
                print(f"             {msg[:120]}")
            sv = _str(d.get("source_value"))
            tv = _str(d.get("target_value"))
            if sv or tv:
                print(f"             src={sv[:50]!r}  tgt={tv[:50]!r}")


# ── Main ─────────────────────────────────────────────────────────────────────

async def main():
    section("STEP 6 — BOE VALIDATION TEST")

    # Step A — extract BOE
    boe_result = await extract_boe()

    # Step B — print all BOE fields
    print_all_fields("BILL OF ENTRY", boe_result.get("fields", {}))

    # Step C — compare against ground truth
    gaps = compare_boe(boe_result.get("fields", {}))

    # Step D — extract vendor docs (Step 2 inputs)
    vendor_results = await extract_vendor_docs()

    # Step E — run validation workflow
    section("RUNNING VALIDATION WORKFLOW (BOE vs Vendor Docs)")
    try:
        final_state = await run_validation_workflow(boe_result, vendor_results)
        print_validation_results(final_state)
    except Exception as e:
        print(f"\n  ERROR running validation workflow: {e}")
        import traceback
        traceback.print_exc()

    # Step F — summary of extraction gaps
    section("EXTRACTION GAP SUMMARY")
    if gaps:
        print(f"  {len(gaps)} issue(s) in BOE extraction vs ground truth:\n")
        for g in gaps:
            print(f"    ⚠  {g}")
    else:
        print("  ✓ All BOE ground truth fields match extracted values")

    # Save raw extraction output
    output = {
        "boe": {
            "fields": boe_result.get("fields", {}),
            "items":  boe_result.get("items", []),
            "status": boe_result.get("status"),
        },
        **{
            dt: {
                "fields": r.get("fields", {}),
                "items":  r.get("items", []),
                "status": r.get("status"),
            }
            for dt, r in vendor_results.items()
        },
    }
    out_path = TEST_PDFS / "step6_extraction_results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n  Raw results saved → {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
