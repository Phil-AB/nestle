# Validation Workflows

## Overview

The system implements two validation workflows that together cover the Nestlé Ghana import compliance process:

- **Step 2 — Vendor Document Pre-Validation:** Checks invoice, packing list, and freight document against each other *before* transmitting to the clearing agent.
- **Step 6 — BOE Cross-Verification:** Checks the draft Bill of Entry against the stored vendor documents *after* the clearing agent prepares it.

Both workflows use the same LangGraph engine — only the YAML config differs.

---

## Full Pipeline Flow

```
IMPEX Team                    System                         Clearing Agent / GRA
─────────────────────────────────────────────────────────────────────────────────

[Step 1] Receive vendor docs from supplier
(manual)

[Step 2] Upload: Invoice + Packing List + B/L
         ──────────────────────────────────►
                                  EXTRACT (Reducto)
                                  NORMALIZE (synonyms, units, formats)
                                  VALIDATE (7 checks)
                                  ◄── discrepancies? ──► HITL review
                                  REPORT: pass / requires_attention
         ◄──────────────────────────────────
         Review discrepancies
         Request corrections from supplier if needed
         (manual)

[Step 3–5] Transmit documents to clearing agent
(manual, outside system)

         Clearing agent prepares draft BOE
         GRA receives BOE

[Step 6] Upload: BOE only (vendor docs retrieved from DB by shipment_id)
         ──────────────────────────────────►
                                  EXTRACT BOE (Reducto + BOE section extractor)
                                  RETRIEVE vendor docs from DB (no re-upload)
                                  NORMALIZE all documents
                                  VALIDATE (12 checks, including duty calc + CET)
                                  ◄── discrepancies? ──► HITL review
                                  REPORT: pass / requires_attention
         ◄──────────────────────────────────
         Confirm or flag discrepancies
         If passed → BOE goes to Finance / GRA
```

---

## Step 2: Vendor Document Pre-Validation

**Config:** `config/validation/use_cases/vendor_document_validation.yaml`

### Input Documents

| Document | Required | Notes |
|----------|----------|-------|
| Invoice | Yes | Primary document |
| Packing List | Yes | Supporting |
| Bill of Lading / Airway Bill / Freight Manifest | No | One alternative accepted |
| Certificate of Origin | No | Optional |

### API

```
POST /api/v2/validation/shipments/{shipment_id}/validate-vendor-docs
Content-Type: multipart/form-data

invoice_file:            <PDF>
packing_list_file:       <PDF>
freight_manifest_file:   <PDF>  (optional)
certificate_of_origin_file: <PDF>  (optional)
```

### Validation Steps

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 2 Validation — 7 checks (config-driven, fully YAML)               │
├────┬───────────────────────────┬────────────────┬────────────────────────┤
│ #  │ Check                     │ Validator       │ Severity               │
├────┼───────────────────────────┼────────────────┼────────────────────────┤
│  1 │ Required fields present   │ required_fields │ Major                  │
│    │ invoice: invoice_number,  │                 │                        │
│    │   total_invoice_value,    │                 │                        │
│    │   net_weight, gross_weight│                 │                        │
│    │ packing_list: net_weight, │                 │                        │
│    │   gross_weight, quantity  │                 │                        │
├────┼───────────────────────────┼────────────────┼────────────────────────┤
│  2 │ Consignee matches across  │ shipper_        │ Major                  │
│    │ invoice ↔ packing_list    │ consignee       │ Fuzzy threshold: 0.75  │
│    │ ↔ bill_of_lading          │ _validator      │ (accent-stripped)      │
├────┼───────────────────────────┼────────────────┼────────────────────────┤
│  3 │ HS code consistent across │ n_way_matcher   │ Critical               │
│    │ invoice ↔ packing_list    │ (line_items)    │ Exact match            │
│    │ (per line item)           │                 │                        │
├────┼───────────────────────────┼────────────────┼────────────────────────┤
│  4 │ Net weight matches        │ tolerance_      │ Critical               │
│    │ invoice ↔ packing_list    │ _validator      │ Tolerance: ±1%         │
├────┼───────────────────────────┼────────────────┼────────────────────────┤
│  5 │ Gross weight matches      │ tolerance_      │ Critical               │
│    │ invoice ↔ packing_list    │ _validator      │ Tolerance: ±1%         │
├────┼───────────────────────────┼────────────────┼────────────────────────┤
│  6 │ Quantity matches          │ tolerance_      │ Major                  │
│    │ invoice ↔ packing_list    │ _validator      │ Tolerance: ±0.5%       │
├────┼───────────────────────────┼────────────────┼────────────────────────┤
│  7 │ Incoterm consistency      │ incoterm_       │ Major                  │
│    │ (freight/insurance vs     │ _validator      │ FOB→no freight,        │
│    │ delivery term)            │                 │ CIF→both present       │
└────┴───────────────────────────┴────────────────┴────────────────────────┘
```

### Data Flow

```
1. Upload vendor docs (multipart/form-data)
       │
       ▼
2. Extract concurrently (Reducto API per file)
   → raw {field: {value, bbox, confidence}} per document
       │
       ▼
3. Normalize (NormalizationEngine)
   → SynonymMapper: "Numéro de Facture" → invoice_number
   → UnitConverter: LBS → KG, EUR → USD
   → FormatNormalizer: "07/04/2026" → "2026-04-07"
       │
       ▼
4. Store in DB (APIDocument, linked to shipment_id)
   → vendor doc fields persist for Step 6 retrieval
       │
       ▼
5. Run 7 validators
       │
       ▼
6. Classify discrepancies
   → Critical/Major → HITL pause
   → Minor/Info → auto-approve
       │
   ┌───┴────────────────────────────────┐
   │ No critical/major discrepancies    │ Critical/major discrepancies
   ▼                                   ▼
7a. Generate report              7b. Pause workflow
    final_status: passed              workflow_status: awaiting_user
                                      Return: {session_id, discrepancies}
                                           │
                                           ▼
                                      User reviews in UI
                                           │
                                           ▼
                                      POST /sessions/{id}/resume
                                      {confirmations: [{id, confirmed, comment}]}
                                           │
                                           ▼
                                      Generate report
                                      final_status: passed / requires_attention
```

### Example Response

```json
{
  "session_id": "92784e35-...",
  "shipment_id": "5d6ccd7c-...",
  "workflow_status": "completed",
  "final_status": "requires_attention",
  "summary": {
    "total_checks": 13,
    "passed_checks": 12,
    "failed_checks": 1
  },
  "discrepancies": [
    {
      "field_name": "hs_code",
      "severity": "minor",
      "source_value": null,
      "message": "Field 'hs_code' only present in 1 document — skipping cross-validation"
    }
  ]
}
```

---

## Step 6: BOE Cross-Verification

**Config:** `config/validation/use_cases/boe_validation.yaml`

### Input Documents

| Document | Source | Notes |
|----------|--------|-------|
| Bill of Entry | Uploaded (Step 6) | GRA Ghana BOE form (PDF) |
| Invoice | Retrieved from DB | Stored at Step 2, linked via `shipment_id` |
| Packing List | Retrieved from DB | Stored at Step 2, linked via `shipment_id` |
| Freight Manifest / B/L | Retrieved from DB | If uploaded at Step 2 |

**No re-upload of vendor documents.** Step 6 retrieves them from the database via `shipment_id`.

### API

```
POST /api/v2/validation/shipments/{shipment_id}/validate-boe
Content-Type: multipart/form-data

boe_file: <PDF>   (only file needed — vendor docs auto-retrieved from DB)
```

### Validation Steps

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Step 6 Validation — 12 checks                                          │
├────┬────────────────────────────────┬─────────────────┬─────────────────┤
│ #  │ Check                          │ Validator        │ Severity        │
├────┼────────────────────────────────┼─────────────────┼─────────────────┤
│  1 │ Consignee matches              │ shipper_         │ Major           │
│    │ BOE ↔ Invoice ↔ B/L            │ consignee        │ Fuzzy: 0.8      │
│    │ Shipper matches                │ _validator       │                 │
│    │ BOE ↔ Invoice ↔ B/L            │                  │                 │
├────┼────────────────────────────────┼─────────────────┼─────────────────┤
│  2 │ Required fields present        │ required_fields  │ Major           │
│    │ BOE: hs_code, gross_weight,    │                  │                 │
│    │   quantity, duty_rate          │                  │                 │
│    │ Invoice: net_weight, quantity  │                  │                 │
│    │ PL: net_weight, gross_weight   │                  │                 │
├────┼────────────────────────────────┼─────────────────┼─────────────────┤
│  3 │ HS code 3-way match            │ n_way_matcher    │ Critical        │
│    │ BOE ↔ Invoice ↔ Packing List   │                  │ require_all:    │
│    │                                │                  │ false (skip if  │
│    │                                │                  │ only in 1 doc)  │
├────┼────────────────────────────────┼─────────────────┼─────────────────┤
│  4 │ Net weight                     │ tolerance_       │ Critical        │
│    │ Invoice ↔ Packing List         │ _validator       │ Tolerance: ±1%  │
├────┼────────────────────────────────┼─────────────────┼─────────────────┤
│  5 │ Gross weight                   │ tolerance_       │ Critical        │
│    │ Invoice ↔ Packing List         │ _validator       │ Tolerance: ±1%  │
│    │ Packing List ↔ BOE             │                  │                 │
├────┼────────────────────────────────┼─────────────────┼─────────────────┤
│  6 │ Quantity                       │ tolerance_       │ Major           │
│    │ Invoice ↔ Packing List         │ _validator       │ Tolerance: ±0.5%│
│    │ (BOE qty in pallets — skip)    │                  │                 │
├────┼────────────────────────────────┼─────────────────┼─────────────────┤
│  7 │ Duty calculation               │ calculation_     │ Critical        │
│    │ duty_amount = customs_value    │ _validator       │ Tolerance: ±0.5%│
│    │              × duty_rate       │                  │                 │
├────┼────────────────────────────────┼─────────────────┼─────────────────┤
│  8 │ Duty rate in valid range       │ range_validator  │ Major           │
│    │ 0.0 ≤ duty_rate ≤ 1.0          │                  │ (catches OCR    │
│    │                                │                  │  "10" vs "0.10")│
├────┼────────────────────────────────┼─────────────────┼─────────────────┤
│  9 │ HS code format                 │ regex_validator  │ Major           │
│    │ Pattern: ^\d{4}\.\d{2}$        │                  │ e.g. "1901.90" │
├────┼────────────────────────────────┼─────────────────┼─────────────────┤
│ 10 │ Customs code rules             │ customs_code_    │ Critical        │
│    │ 40V02: VAT=5%, payable=0       │ _validator       │                 │
│    │ 40E68: standard duty+VAT       │                  │                 │
│    │ 40W01: duty exemption, pay=0   │                  │                 │
│    │ 40U01: temporary import        │                  │                 │
├────┼────────────────────────────────┼─────────────────┼─────────────────┤
│ 11 │ Mode of shipment               │ mode_of_         │ Major           │
│    │ BOE Sec.21 (KIA→AWB, TMA→BL)  │ shipment_        │                 │
│    │                                │ _validator       │                 │
├────┼────────────────────────────────┼─────────────────┼─────────────────┤
│ 12 │ Incoterm consistency           │ incoterm_        │ Major           │
│    │ (freight/insurance vs term)    │ _validator       │                 │
│    │ + CET HS code validation       │ cet_hs_code_     │ Critical        │
│    │   (LLM semantic match)         │ _validator       │                 │
└────┴────────────────────────────────┴─────────────────┴─────────────────┘
```

### Data Flow

```
1. Upload BOE PDF
       │
       ▼
2. Extract BOE (Reducto + BOESectionExtractor)
   → BOESectionExtractor scans GRA key names:
     "3_gross_mass_kg_1927800000_..." → gross_weight = 192780.0
     "7_importer_&_address_...liect_nestle_ghana_limited_..." → consignee_name
     "12_delivery_terms_&_place_fca_..." → incoterm = "FCA"
     "15_total_fob_fcy_imp_ncy_exp_46777500" → total_fob_value = 467775.00
       │
       ▼
3. Retrieve vendor docs from DB
   SELECT * FROM api_documents
   WHERE shipment_id = ? AND document_type IN ('invoice', 'packing_list', ...)
   AND extraction_status = 'complete'
       │
       ▼
4. Normalize all 4 documents (NormalizationEngine)
       │
       ▼
5. Run 12 validators
       │
       ▼
6. Classify discrepancies
   → Critical/Major → HITL pause
   → Minor/Info → auto-approve
       │
   ┌───┴────────────────────────────────┐
   │ No critical/major discrepancies    │ Critical/major discrepancies
   ▼                                   ▼
7a. final_status: passed          7b. workflow_status: awaiting_user
    → BOE cleared for Finance          → HITL review
                                       → User confirms/rejects
                                       → Resume → generate report
```

### Example Response (awaiting HITL)

```json
{
  "session_id": "bd9c7a75-...",
  "shipment_id": "37e00ad9-...",
  "workflow_status": "awaiting_user",
  "final_status": "requires_attention",
  "summary": {
    "total_checks": 23,
    "passed_checks": 22,
    "failed_checks": 1,
    "critical": 0,
    "major": 1
  },
  "discrepancies": [
    {
      "id": "4781b4cd-...",
      "field_name": "consignee",
      "severity": "major",
      "source_value": "Nestle Ghana Limited",
      "target_value": {"invoice": "Nestlé Ghana Limited"},
      "message": "Consignee MISMATCH: bill_of_entry vs invoice"
    }
  ]
}
```

### HITL Resume

```
POST /api/v2/validation/sessions/{session_id}/resume
{
  "confirmations": [
    {
      "discrepancy_id": "4781b4cd-...",
      "confirmed": true,
      "comment": "Accent difference only — same company"
    }
  ]
}

→ Response: { "workflow_status": "completed", "final_status": "passed" }
```

---

## HITL (Human-in-the-Loop) Flow

```
                 Discrepancy detected
                         │
                         ▼
              ┌──────────────────────┐
              │  Auto-fixable?       │
              │  (format, unit,      │
              │   synonym)           │
              └──────────┬───────────┘
                    Yes  │  No
                   ┌─────┴──────────────┐
                   ▼                    ▼
            Auto-fix applied    Severity check
            continue            │
                           ┌────┴────┐
                        Minor/Info   Critical/Major
                           │              │
                           ▼              ▼
                      Auto-approve   PAUSE WORKFLOW
                                     Save checkpoint
                                          │
                                          ▼
                                   Return to user:
                                   {session_id,
                                    discrepancies}
                                          │
                                    User reviews
                                    in UI
                                          │
                                          ▼
                                   POST /sessions/{id}/resume
                                   {confirmations: [...]}
                                          │
                                          ▼
                                   Restore checkpoint
                                   Apply user decisions
                                          │
                                          ▼
                                   GENERATE REPORT
                                   final_status:
                                   passed / requires_attention
```

**Checkpoint durability:**
- State saved to `validation_sessions` table (JSONB `context_data`)
- LangGraph checkpointer persists graph state
- Server restart does NOT lose HITL sessions
- User can resume hours/days later

---

## Normalization Details

Both workflows share the same normalization pipeline. Key transformations:

### Synonym Mapping (EN/FR support)

| Extracted Field | Canonical Name |
|----------------|----------------|
| "Numéro de Facture", "Invoice No.", "Inv. No" | `invoice_number` |
| "Poids Net", "Net Weight", "Net Wt" | `net_weight` |
| "Poids Brut", "Gross Weight" | `gross_weight` |
| "Quantité", "Qty", "No. of Units" | `quantity` |
| "Valeur Douanière", "Customs Value" | `customs_value` |
| "Code Douanier", "CPC", "container_nos_chassis_nos" | `customs_code` |

### Unit Conversion

| From | To | Factor |
|------|----|--------|
| LBS | KG | × 0.453592 |
| MT (metric tonne) | KG | × 1000 |
| G | KG | × 0.001 |
| EUR | USD | live rate (fallback: 1.10) |
| GBP | USD | live rate (fallback: 1.30) |

### Format Normalization

| Input | Output |
|-------|--------|
| "7.560 BG" (European thousands) | 7560.0 |
| "04/07/2026", "April 7, 2026" | "2026-04-07" |
| "$1,234.56", "USD 1234.56" | 1234.56 |
| "oui", "yes", "true", "1" | `true` |
| "Nestlé Ghana Limited" | "Nestle Ghana Limited" (accent-stripped for comparison) |

---

## Revalidation (Version Control)

When a BOE is revised and resubmitted:

```
1. Create new session with previous_version_id = old_session_id
2. Run full validation again
3. DeltaAnalyzer compares V1 vs V2:
   - Which critical discrepancies from V1 are now fixed?
   - Any new discrepancies in V2?
4. Pass criteria: all V1 criticals resolved, no new criticals
5. Report: side-by-side V1 vs V2 comparison
```
