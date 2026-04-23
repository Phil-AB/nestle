#!/usr/bin/env python3
"""
Validation Coverage Test

Runs every configured step in vendor_document_validation.yaml and
boe_validation.yaml against ground-truth document data derived from
the actual PDFs in test-pdfs/ground-truth/.

Purpose:
  - Prove every check actually executes (no silent field-name mismatches)
  - Confirm expected pass/fail outcome for each check
  - Catch regressions when config or validators change

Ground truth derived from:
  test-pdfs/ground-truth/invoice.md
  test-pdfs/ground-truth/packing-list.md
  test-pdfs/ground-truth/bill-of-lading.md
  test-pdfs/ground-truth/bill-of-entry.md

Usage:
  python scripts/test_validation_coverage.py
  python scripts/test_validation_coverage.py --step2
  python scripts/test_validation_coverage.py --step6
  python scripts/test_validation_coverage.py --verbose
"""

import asyncio
import sys
import argparse
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

# Force validator self-registration by importing the package
import modules.validation_engine.validators  # noqa: F401

import yaml
from modules.validation_engine.core.base import ValidationContext
from modules.validation_engine.validators.validator_registry import ValidatorRegistry

# ─── Ground truth document data ──────────────────────────────────────────────
# Values taken directly from test-pdfs/ground-truth/*.md

INVOICE = {
    "invoice_number":     "9400080882",
    "invoice_date":       "Jan 21, 2026",
    "shipper_name":       "Industrie- en Handelsonderneming Vreugdenhil B.V. (Vreugdenhil Dairy Foods)",
    "shipper_address":    "Arkerpoort 5, P.O. Box 64, 3860 AB Nijkerk, The Netherlands",
    "consignee_name":     "Nestle Ghana Limited",
    "consignee_address":  "Private Mail Bag, Kotoka International Airport, Accra, Ghana",
    "incoterm":           "FCA ROTTERDAM PORT",
    "currency":           "EUR",
    "total_invoice_value": 467775.00,
    "total_fob_value":    467775.00,
    "net_weight":         189000.0,
    "gross_weight":       192780.0,
    "quantity":           7560.0,
    "product_description": "FFP 28% MQAV004F-1 25kg bag",
    "order_number":       "64896",
    "contract_number":    "40017796",
    "po_number":          "4562599410",
    "freight_value":      None,    # FCA — freight not on invoice
    "insurance_value":    None,    # FCA — insurance not on invoice
    "hs_code":            None,    # Not on invoice for this supplier
    "items": [
        {
            "product_description": "FFP 28% MQAV004F-1 25kg bag",
            "quantity": 7560.0,
            "hs_code": None,
        }
    ],
}

PACKING_LIST = {
    "consignee_name":       "Nestle Ghana Limited",
    "consignee_address":    "Sanyo Road Heavy Ind. Area, Tema, Ghana",
    "incoterm":             "FCA ROTTERDAM PORT",
    "net_weight":           189000.0,
    "gross_weight":         192780.0,
    "quantity":             7560.0,
    "product_description":  "Instant Fat Filled Powder 28% veg. fat, vit & min enriched, MQAV004F-1,25 kg bag",
    "order_number":         "64896",
    "contract_number":      "40017796",
    "po_number":            "4562599410",
    "container_count":      7,
    "container_numbers":    "CAAU8000243,GCNU4792418,GCNU4808303,GCNU4866249,GCNU4822554,GCNU4803430,GCNU4823653",
    "shipper_name":         None,  # Not on packing list
    "shipper_address":      None,
    "hs_code":              None,
    "items": [
        {
            "product_description": "Instant Fat Filled Powder 28% veg. fat, vit & min enriched, MQAV004F-1,25 kg bag",
            "quantity": 7560.0,
            "hs_code": None,
        }
    ],
}

BILL_OF_LADING = {
    "bl_number":          "S328717359",
    "shipper_name":       None,     # REDACTED on this BOL — completeness check will flag correctly
    "shipper_address":    None,     # REDACTED on this BOL
    "consignee_name":     "Nestle Ghana Ltd",
    "consignee_address":  "Kotoka International Airport, Accra, Ghana",
    "port_of_loading":    "ANTWERP",
    "port_of_discharge":  "TEMA",
    "net_weight":         189000.0,
    "gross_weight":       192780.0,
    "quantity":           7560.0,
    "container_count":    7,
    "container_numbers":  "CAAU8000243,GCNU4792418,GCNU4808303,GCNU4866249,GCNU4822554,GCNU4803430,GCNU4823653",
    "order_number":       "64896",
    "contract_number":    "40017796",
    "po_number":          "4562599410",  # CUSTOMER REF from BOL totals block
    "country_of_origin":  None,    # Not stated on BOL
    "hs_code":            None,
    "product_description": "Instant Fat Filled Powder 28% veg. fat, vit & min enriched, MQAV004F-1",
}

BILL_OF_ENTRY = {
    "boe_number":           "40126075519",
    "invoice_number":       "9400080882",
    "shipper_name":         "VREUGDENHIL DAIRY FOODS",
    "shipper_address":      "ARKERPOORT 5, 3861 PS, P.O. BOX 64 3860 AB",
    "consignee_name":       "NESTLE GHANA LIMITED",
    "consignee_address":    "NO.33 SOUTH LEGON COMMERCIAL AREA, MOTORWAY EXTENS DZORWULU",
    "declarant_name":       "CARGO CENTER GHANA LIMITED",
    "declarant_address":    "UNN OFFICE NEAR TEMA HARBOUR, TEMA HARBOUR STREET, TEMA",
    "declarant_reg_number": "CH000258",
    "hs_code":              "1901.90",
    "hs_code_full":         "1901902000",
    "customs_code":         "40V02",
    "incoterm":             "FCA TEMA",
    "currency":             "EUR",
    "entry_exit_code":      "10",       # Sea
    "port_of_loading":      "BEANR Antwerpen",
    "country_of_origin":    "BE",
    "origin":               "BE",
    "gross_weight":         192780.0,
    "net_weight":           189000.0,
    "quantity":             7560.0,
    "total_fob_value":      467775.0,   # EUR
    "fob_ncy":              5991028.31, # GHS
    "freight_value":        133851.18,  # GHS
    "insurance_value":      53592.73,   # GHS
    "customs_value":        6178472.22, # GHS (CIF)
    "duty_rate":            0.05,
    "duty_amount":          308923.61,
    "vat_rate":             0.15,
    "vat_amount":           973109.37,
    "container_count":      7,
    "container_numbers":    "CAAU8000243,GCNU4792418,GCNU4808303,GCNU4866249,GCNU4822554,GCNU4803430,GCNU4823653",
    "product_description":  "FFP 28% MQAV004F-1 25KG BAG",
    "items": [
        {
            "hs_code":              "1901.90",
            "product_description":  "FFP 28% MQAV004F-1 25KG BAG",
            "quantity":             7560.0,
            "country_of_origin":    "BE",
        }
    ],
}

STEP2_DOCS = {
    "invoice":       INVOICE,
    "packing_list":  PACKING_LIST,
    "bill_of_lading": BILL_OF_LADING,
}

STEP6_DOCS = {
    "invoice":       INVOICE,
    "packing_list":  PACKING_LIST,
    "bill_of_lading": BILL_OF_LADING,
    "bill_of_entry": BILL_OF_ENTRY,
}

# ─── Expected outcomes ────────────────────────────────────────────────────────
# "pass"  = all results should have passed=True
# "fail"  = at least one result should have passed=False
# "skip"  = expected to produce INFO/skip result (require_all=false, field absent)
# "any"   = may pass or skip depending on extraction; just must not raise

STEP2_EXPECTED = {
    "invoice_completeness":           "pass",
    "packing_list_completeness":      "pass",
    "bol_completeness":               "fail",  # shipper block REDACTED on this BOL
    "shipper_identity":               "skip",  # BOL shipper REDACTED — only 1 doc has name
    "consignee_identity":             "fail",  # invoice=bill-to(KIA Accra) vs PL=ship-to(Sanyo Tema): sim=0.09 < 0.1
    "order_number_consistency":       "pass",
    "contract_number_consistency":    "pass",
    "po_number_consistency":          "pass",
    "product_description_consistency": "any",  # fuzzy match — depends on threshold
    "incoterm_consistency":           "pass",
    "incoterm_rules":                 "pass",  # FCA — no freight/insurance on invoice: correct
    "net_weight_consistency":         "pass",
    "gross_weight_consistency":       "pass",
    "quantity_consistency":           "pass",
    "container_count_consistency":    "pass",
    "container_numbers_consistency":  "pass",
    "country_of_origin":              "skip",  # certificate_of_origin not uploaded — INFO N/A
}

STEP6_EXPECTED = {
    "shipper_consignee_validation":       "fail",  # consignee bill-to(BOE Dzorwulu) vs ship-to(PL Tema) sim < threshold
    "field_extraction_check":             "pass",
    "hs_code_3way_matching":              "skip",  # HS code only on BOE — invoice/PL/BOL don't carry it
    "weight_matching":                    "pass",
    "quantity_matching":                  "pass",
    "duty_calculation":                   "pass",
    "cif_calculation_check":              "any",   # depends on fob_ncy extraction
    "duty_rate_validation":               "pass",
    "hs_code_format":                     "pass",
    "customs_code_validation":            "fail",  # 40V02: checks VAT deferred — real finding expected
    "mode_of_shipment_validation":        "pass",
    "incoterm_validation":                "pass",  # FCA — no freight/insurance on invoice: correct
    "declarant_check":                    "pass",
    "fob_value_crosscheck":               "pass",
    "invoice_number_crosscheck":          "pass",
    "incoterm_cross_doc":                 "pass",
    "currency_consistency":               "pass",
    "country_of_origin_check":            "pass",
    "origin_cross_check":                 "skip",  # BOL port_of_loading absent → require_all=false → INFO skip
    "container_count_consistency":        "pass",
    "etls_approval_check":                "skip",  # 40V02 not an ETLS code — INFO N/A
    "master_concession_eligibility_check": "skip",  # 40V02 not a concession code — INFO N/A
    "vat_deferment_eligibility_check":    "pass",  # 1901.90 prefix-matches 1901902000 on VAT deferment list
    "insurance_rate_check":               "pass",  # Sea 0.875%: 53592.73 ≈ 0.875% × (5991028 + 133851)
}

# ─── Helpers ──────────────────────────────────────────────────────────────────

PASS  = "\033[32m✓\033[0m"
FAIL  = "\033[31m✗\033[0m"
SKIP  = "\033[33m~\033[0m"
WARN  = "\033[33m!\033[0m"
BOLD  = "\033[1m"
RESET = "\033[0m"


def _make_context(documents: dict, use_case: str, config: dict) -> ValidationContext:
    return ValidationContext(
        session_id=uuid4(),
        use_case=use_case,
        version="1.0",
        documents=documents,
        primary_document="invoice" if use_case == "vendor_document_validation" else "bill_of_entry",
        supporting_documents=[k for k in documents if k != "invoice"],
        config={"use_case": config},
        normalized_data=documents,
    )


def _load_use_case(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


async def _run_step(step: dict, documents: dict, use_case: str, use_case_config: dict, verbose: bool) -> dict:
    """Run all validators for one step, return result summary."""
    step_name = step.get("name", "unknown")
    validators_cfg = step.get("validators", [])
    step_config = step.get("config", {})

    all_results = []
    errors = []

    primary = "invoice" if use_case == "vendor_document_validation" else "bill_of_entry"
    is_cross_doc = any(
        key in step_config for key in ("documents", "parties", "calculations")
    ) or any(
        "." in str(v.get("source", "")) or "." in str(v.get("target", ""))
        for v in step_config.get("validations", [])
        if isinstance(v, dict)
    )

    context = _make_context(documents, use_case, use_case_config)

    for validator_name in validators_cfg:
        try:
            validator = ValidatorRegistry.get_validator(validator_name, step_config)
            source_data = documents if is_cross_doc else documents.get(primary, {})
            target_data = documents if is_cross_doc else None
            results = await validator.validate(source_data, target_data, context)
            all_results.extend(results)
        except Exception as e:
            errors.append(f"{validator_name}: {e}")

    return {
        "step": step_name,
        "results": all_results,
        "errors": errors,
        "ran": len(all_results) > 0 or len(errors) > 0,
    }


def _assess(step_name: str, run_result: dict, expected_outcomes: dict, verbose: bool) -> tuple[bool, str]:
    """Return (ok, summary_line)."""
    errors = run_result["errors"]
    results = run_result["results"]

    if errors:
        return False, f"{FAIL} {BOLD}{step_name}{RESET}  ERROR: {'; '.join(errors)}"

    if not results:
        return False, f"{FAIL} {BOLD}{step_name}{RESET}  produced NO results — silent skip"

    expected = expected_outcomes.get(step_name, "any")
    passed_all = all(r.passed for r in results)
    failed_any = any(not r.passed for r in results)
    info_only  = all(getattr(r, "severity", "info") in ("info", "INFO") for r in results)
    skipped    = all(r.passed and "skipping" in (r.message or "").lower() for r in results)

    detail_lines = []
    if verbose:
        for r in results:
            icon = PASS if r.passed else FAIL
            detail_lines.append(
                f"    {icon} [{r.field_name}] {r.message}"
            )

    if expected == "pass":
        ok = passed_all
        icon = PASS if ok else FAIL
        status = "all passed" if ok else f"UNEXPECTED FAILURE in {[r.field_name for r in results if not r.passed]}"
    elif expected == "fail":
        ok = failed_any
        icon = PASS if ok else FAIL
        status = "failure detected (expected)" if ok else "unexpectedly passed"
    elif expected == "skip":
        ok = passed_all  # skips emit passed=True INFO results
        icon = PASS if ok else FAIL
        n_skipped = sum(1 for r in results if "skipping" in (r.message or "").lower() or "present in only" in (r.message or "").lower() or "not available" in (r.message or "").lower())
        status = f"skipped/INFO ({n_skipped}/{len(results)} results)" if ok else f"UNEXPECTED FAILURE: {[r.field_name for r in results if not r.passed]}"
    else:  # "any"
        ok = not errors
        icon = PASS if ok else FAIL
        p = sum(1 for r in results if r.passed)
        status = f"{p}/{len(results)} passed"

    line = f"  {icon} {step_name:<45} {status}"
    if detail_lines:
        line += "\n" + "\n".join(detail_lines)
    return ok, line


async def run_step2(verbose: bool) -> tuple[int, int]:
    config_path = Path(__file__).parent.parent / "config/validation/use_cases/vendor_document_validation.yaml"
    use_case_config = _load_use_case(config_path)
    steps = use_case_config.get("use_case", {}).get("workflow", {}).get("steps", [])

    print(f"\n{BOLD}STEP 2 — Vendor Document Validation  ({len(steps)} steps){RESET}")
    print("─" * 70)

    passed = failed = 0
    for step in steps:
        run_result = await _run_step(step, STEP2_DOCS, "vendor_document_validation", use_case_config, verbose)
        ok, line = _assess(step["name"], run_result, STEP2_EXPECTED, verbose)
        print(line)
        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\n  {BOLD}Step 2 result: {passed} passed, {failed} failed{RESET}")
    return passed, failed


async def run_step6(verbose: bool) -> tuple[int, int]:
    config_path = Path(__file__).parent.parent / "config/validation/use_cases/boe_validation.yaml"
    use_case_config = _load_use_case(config_path)
    steps = use_case_config.get("use_case", {}).get("workflow", {}).get("steps", [])

    print(f"\n{BOLD}STEP 6 — BOE Validation  ({len(steps)} steps){RESET}")
    print("─" * 70)

    passed = failed = 0
    for step in steps:
        run_result = await _run_step(step, STEP6_DOCS, "boe_validation", use_case_config, verbose)
        ok, line = _assess(step["name"], run_result, STEP6_EXPECTED, verbose)
        print(line)
        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\n  {BOLD}Step 6 result: {passed} passed, {failed} failed{RESET}")
    return passed, failed


async def main():
    parser = argparse.ArgumentParser(description="Validation coverage test")
    parser.add_argument("--step2", action="store_true", help="Run Step 2 only")
    parser.add_argument("--step6", action="store_true", help="Run Step 6 only")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show per-field result detail")
    args = parser.parse_args()

    run_both = not args.step2 and not args.step6

    total_passed = total_failed = 0

    if args.step2 or run_both:
        p, f = await run_step2(args.verbose)
        total_passed += p
        total_failed += f

    if args.step6 or run_both:
        p, f = await run_step6(args.verbose)
        total_passed += p
        total_failed += f

    print(f"\n{'='*70}")
    overall = PASS if total_failed == 0 else FAIL
    print(f"{overall} {BOLD}Overall: {total_passed} passed, {total_failed} failed{RESET}")

    sys.exit(0 if total_failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
