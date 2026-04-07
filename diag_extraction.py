"""
Diagnostic script: trace extraction → synonym mapping → validation
for the Nestle invoice + packing list test PDFs.
Run from project root: python diag_extraction.py
"""
import asyncio
import sys
import os

# Set up Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("PYTHONPATH", os.path.dirname(os.path.abspath(__file__)))

# Suppress noisy logs
import logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

async def main():
    from pathlib import Path
    from src.api.services.document_processing_service import DocumentProcessingService

    invoice_path = Path("test-pdfs/Invoice_ (1).pdf")
    packing_list_path = Path("test-pdfs/Packing list_.pdf")

    svc = DocumentProcessingService(use_database=False, use_ai_enhancement=False)

    print("\n=== EXTRACTING INVOICE ===")
    with open(invoice_path, "rb") as f:
        invoice_bytes = f.read()

    # Monkey-patch process_document to accept bytes directly
    # Actually just call the parser directly
    from modules.extraction.parser.provider_factory import get_active_provider
    from modules.extraction.parser.schema_generator import SchemaGenerator

    parser = get_active_provider()
    schema_gen = SchemaGenerator()

    # Invoice
    schema = schema_gen.generate_schema("invoice", "open")
    result_invoice = await parser.extract_fields(
        file_bytes=invoice_bytes,
        schema=schema,
        document_type="invoice",
        file_name="Invoice_ (1).pdf"
    )

    invoice_fields = result_invoice.get("fields", {})
    print(f"Invoice extracted {len(invoice_fields)} fields:")
    for k, v in sorted(invoice_fields.items()):
        val = v.get("value", v) if isinstance(v, dict) else v
        print(f"  {k!r:40s} = {str(val)[:60]!r}")

    # Packing list
    with open(packing_list_path, "rb") as f:
        pl_bytes = f.read()
    schema_pl = schema_gen.generate_schema("packing_list", "open")
    result_pl = await parser.extract_fields(
        file_bytes=pl_bytes,
        schema=schema_pl,
        document_type="packing_list",
        file_name="Packing list_.pdf"
    )
    pl_fields = result_pl.get("fields", {})
    print(f"\nPacking List extracted {len(pl_fields)} fields:")
    for k, v in sorted(pl_fields.items()):
        val = v.get("value", v) if isinstance(v, dict) else v
        print(f"  {k!r:40s} = {str(val)[:60]!r}")

    print("\nPacking List raw blocks:")
    for i, blk in enumerate(result_pl.get("blocks", [])):
        btype = blk.get("type", "?")
        content = blk.get("content", "")[:120].replace("\n", "\\n")
        print(f"  [{i}] {btype}: {content!r}")

    print(f"\nPacking list items (last 10 of {len(result_pl.get('items', []))}):")
    items = result_pl.get("items", [])
    for item in items[-10:]:
        print(f"  {item}")

    # Now run through synonym mapper
    print("\n=== SYNONYM MAPPING ===")
    from modules.validation_engine.normalization.normalizers.synonym_mapper import SynonymMapper
    mapper = SynonymMapper()

    invoice_doc = {**invoice_fields, "items": result_invoice.get("items", [])}
    pl_doc = {**pl_fields, "items": result_pl.get("items", [])}

    norm_invoice = mapper.map_document_fields(invoice_doc, "invoice")
    norm_pl = mapper.map_document_fields(pl_doc, "packing_list")

    print(f"\nNormalized invoice keys ({len(norm_invoice)}):")
    for k in sorted(norm_invoice.keys()):
        v = norm_invoice[k]
        val = v.get("value", v) if isinstance(v, dict) else v
        print(f"  {k!r:40s} = {str(val)[:60]!r}")

    print(f"\nNormalized packing_list keys ({len(norm_pl)}):")
    for k in sorted(norm_pl.keys()):
        v = norm_pl[k]
        val = v.get("value", v) if isinstance(v, dict) else v
        print(f"  {k!r:40s} = {str(val)[:60]!r}")

    # Check required fields
    print("\n=== REQUIRED FIELD CHECK ===")
    required = {
        "invoice": ["invoice_number", "total_invoice_value", "net_weight", "gross_weight"],
        "packing_list": ["net_weight", "gross_weight", "quantity"]
    }
    for doc_type, doc_data in [("invoice", norm_invoice), ("packing_list", norm_pl)]:
        for field in required[doc_type]:
            val = doc_data.get(field)
            if val is None:
                print(f"  MISSING: {doc_type}.{field}")
            else:
                actual = val.get("value", val) if isinstance(val, dict) else val
                print(f"  OK:      {doc_type}.{field} = {str(actual)[:50]!r}")

asyncio.run(main())
