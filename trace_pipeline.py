"""
Pipeline File Tracer — instruments the validation pipelines to capture
every Python module actually loaded during execution.

Usage:
    python trace_pipeline.py vendor
    python trace_pipeline.py boe
    python trace_pipeline.py both
"""

import sys
import os
import json
import atexit
from pathlib import Path
from datetime import datetime

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── Tracking state ──────────────────────────────────────────────────────────
_trace_log: list[str] = []          # ordered list of modules as they load
_seen: set[str] = set()
PROJECT_PREFIX = str(PROJECT_ROOT)  # only care about project files


def _track_import(name: str):
    """Record a project module import."""
    if name in _seen:
        return
    _seen.add(name)
    # Only track project-local modules
    mod = sys.modules.get(name)
    if mod is None:
        return
    f = getattr(mod, "__file__", None)
    if f and f.startswith(PROJECT_PREFIX):
        rel = os.path.relpath(f, PROJECT_ROOT)
        _trace_log.append(rel)


def _snapshot(label: str) -> set[str]:
    """Take a snapshot of currently loaded project modules."""
    modules = set()
    for name, mod in sys.modules.items():
        f = getattr(mod, "__file__", None)
        if f and f.startswith(PROJECT_PREFIX):
            rel = os.path.relpath(f, PROJECT_ROOT)
            modules.add(rel)
    return modules


# ── Hook sys.import to catch dynamic loads ──────────────────────────────────
_original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __builtins__["__import__"]


def _tracing_import(name, *args, **kwargs):
    result = _original_import(name, *args, **kwargs)
    _track_import(name)
    return result


# ── Helper: extract field values from extraction data ───────────────────────
def _extract_fields(doc_data: dict) -> dict:
    """Extract clean field values from extraction results."""
    fields = doc_data.get("fields", {})
    clean = {}
    for k, v in fields.items():
        if isinstance(v, dict) and "value" in v:
            clean[k] = v["value"]
        else:
            clean[k] = v
    return clean


# ── Vendor Validation Pipeline (Step 2) ─────────────────────────────────────
async def run_vendor_validation():
    """Run the vendor document validation pipeline with tracing."""
    print("\n" + "=" * 70)
    print("STEP 2: VENDOR DOCUMENT VALIDATION")
    print("=" * 70)

    # Load extraction results
    with open(PROJECT_ROOT / "test-pdfs" / "extraction_results.json") as f:
        data = json.load(f)

    documents = {}
    if "invoice" in data:
        documents["invoice"] = _extract_fields(data["invoice"])
    if "packing_list" in data:
        documents["packing_list"] = _extract_fields(data["packing_list"])
    if "bill_of_lading" in data and data["bill_of_lading"].get("fields"):
        documents["bill_of_lading"] = _extract_fields(data["bill_of_lading"])

    print(f"  Documents: {list(documents.keys())}")

    # Snapshot BEFORE
    before = _snapshot("vendor_before")

    # Import and run the pipeline (same path as the API endpoint)
    from modules.validation_engine import get_validation_engine
    from modules.validation_engine.orchestration import get_validation_workflow
    from modules.validation_engine.version_control import get_version_manager

    engine = get_validation_engine()

    # Create session (same as POST /validation/sessions)
    print("  Creating validation session...")
    context = await engine.create_validation_session(
        use_case="vendor_document_validation",
        documents=documents,
    )
    session_id = context.session_id
    print(f"  Session created: {session_id}")

    # Run validation (same as POST /validation/sessions/{id}/validate)
    print("  Running validation workflow...")
    workflow = get_validation_workflow()

    from modules.validation_engine.core.session_manager import get_session_manager
    session_manager = get_session_manager()
    ctx = await session_manager.get_session(session_id)

    final_state = await workflow.run(
        session_id=session_id,
        documents=ctx.documents,
        config=ctx.config,
        primary_document=ctx.primary_document,
        supporting_documents=ctx.supporting_documents,
        tolerance_overrides=ctx.tolerance_overrides,
    )

    status = final_state.get("final_status", "unknown")
    print(f"  Validation complete: {status}")

    # Snapshot AFTER
    after = _snapshot("vendor_after")

    touched = sorted(after - before)
    print(f"  Files touched: {len(touched)}")

    return touched


# ── BOE Validation Pipeline (Step 6) ────────────────────────────────────────
async def run_boe_validation():
    """Run the BOE validation pipeline with tracing."""
    print("\n" + "=" * 70)
    print("STEP 6: BOE VALIDATION")
    print("=" * 70)

    # Load step 6 extraction results
    with open(PROJECT_ROOT / "test-pdfs" / "step6_extraction_results.json") as f:
        data = json.load(f)

    documents = {}
    if "boe" in data:
        documents["bill_of_entry"] = _extract_fields(data["boe"])
    if "invoice" in data:
        documents["invoice"] = _extract_fields(data["invoice"])
    if "packing_list" in data:
        documents["packing_list"] = _extract_fields(data["packing_list"])
    if "bill_of_lading" in data and data["bill_of_lading"].get("fields"):
        documents["bill_of_lading"] = _extract_fields(data["bill_of_lading"])

    print(f"  Documents: {list(documents.keys())}")

    # Snapshot BEFORE
    before = _snapshot("boe_before")

    from modules.validation_engine import get_validation_engine
    from modules.validation_engine.orchestration import get_validation_workflow
    from modules.validation_engine.version_control import get_version_manager

    engine = get_validation_engine()

    # Create session
    print("  Creating validation session...")
    context = await engine.create_validation_session(
        use_case="boe_validation",
        documents=documents,
    )
    session_id = context.session_id
    print(f"  Session created: {session_id}")

    # Run validation
    print("  Running validation workflow...")
    workflow = get_validation_workflow()

    from modules.validation_engine.core.session_manager import get_session_manager
    session_manager = get_session_manager()
    ctx = await session_manager.get_session(session_id)

    final_state = await workflow.run(
        session_id=session_id,
        documents=ctx.documents,
        config=ctx.config,
        primary_document=ctx.primary_document,
        supporting_documents=ctx.supporting_documents,
        tolerance_overrides=ctx.tolerance_overrides,
    )

    status = final_state.get("final_status", "unknown")
    print(f"  Validation complete: {status}")

    # Snapshot AFTER
    after = _snapshot("boe_after")

    touched = sorted(after - before)
    print(f"  Files touched: {len(touched)}")

    return touched


# ── Main ────────────────────────────────────────────────────────────────────
async def main():
    import asyncio

    which = sys.argv[1] if len(sys.argv) > 1 else "both"

    # Capture baseline (all modules already loaded by Python stdlib + deps)
    baseline = _snapshot("baseline")

    vendor_files = []
    boe_files = []

    if which in ("vendor", "both"):
        vendor_files = await run_vendor_validation()

    if which in ("boe", "both"):
        boe_files = await run_boe_validation()

    # ── Combined results ────────────────────────────────────────────────────
    all_active = sorted(set(vendor_files + boe_files))

    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    print(f"\n--- Vendor Validation (Step 2): {len(vendor_files)} files ---")
    for f in vendor_files:
        print(f"  {f}")

    print(f"\n--- BOE Validation (Step 6): {len(boe_files)} files ---")
    for f in boe_files:
        print(f"  {f}")

    print(f"\n--- Combined Active Files: {len(all_active)} ---")
    for f in all_active:
        print(f"  {f}")

    # ── Now scan ALL .py files in the project and find dead code ────────────
    all_py_files = set()
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Skip these directories entirely
        skip_dirs = {
            "node_modules", ".git", "__pycache__", ".pytest_cache",
            ".next", "static", "logs", "screenshots", "examples",
            "test-pdfs", "uploads",
        }
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for fn in files:
            if fn.endswith(".py"):
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, PROJECT_ROOT)
                all_py_files.add(rel)

    dead_files = sorted(all_py_files - set(all_active))

    print(f"\n--- DEAD CODE: {len(dead_files)} files ---")
    for f in dead_files:
        print(f"  {f}")

    # ── Save results to JSON ────────────────────────────────────────────────
    results = {
        "timestamp": datetime.now().isoformat(),
        "vendor_files": vendor_files,
        "boe_files": boe_files,
        "all_active_files": all_active,
        "all_project_files": sorted(all_py_files),
        "dead_files": dead_files,
    }

    out_path = PROJECT_ROOT / "trace_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
