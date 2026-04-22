# Step 2 & Step 6 — Detailed System Workflow

> **Scope:** Every operation, data transformation, comparison, and decision made by
> the pipeline from API entry to final response.  Written from the actual source code —
> `src/api/v2/endpoints/validation_pipeline.py`, `config/validation/use_cases/`,
> and every validator implementation under `modules/validation_engine/validators/`.

---

## Table of Contents

1. [Pre-condition — Shipment Creation](#pre-condition--shipment-creation)
2. [Step 2 — Vendor Document Pre-Validation](#step-2--vendor-document-pre-validation)
   - [A. API Entry](#a-api-entry)
   - [B. Parallel Extraction](#b-parallel-extraction)
   - [C. Normalization](#c-normalization-per-document)
   - [D. Database Persistence](#d-database-persistence)
   - [E. BL Number Assignment](#e-bl-number--shipment-number-assignment)
   - [F. Validation Session](#f-validation-session-creation)
   - [G. Workflow Execution](#g-workflow-execution)
   - [H. The 14 Checks](#h-the-14-validation-checks--exact-internal-logic)
   - [I. Result Aggregation](#i-result-aggregation--response)
3. [Step 6 — BOE Cross-Verification](#step-6--boe-cross-verification)
   - [A. API Entry](#a-api-entry-1)
   - [B. Load Step 2 Documents](#b-load-step-2-documents-from-db)
   - [C. BOE Extraction](#c-boe-extraction)
   - [D. BOE Normalization](#d-boe-normalization)
   - [E. BOE Database Persistence](#e-boe-database-persistence)
   - [F. Declaration Number Assignment](#f-declaration-number-assignment-overwrite-mode)
   - [G. Document Assembly](#g-document-assembly)
   - [H. Validation Session](#h-validation-session-creation)
   - [I. The 22 Checks](#i-the-22-validation-checks--exact-internal-logic)
   - [J. Result Aggregation](#j-result-aggregation--response)
4. [Discrepancy Structure](#k-how-a-discrepancy-is-structured)

---

## Pre-condition — Shipment Creation

**Endpoint:** `POST /api/v2/validation/shipments`

Before either step can run a **Shipment record** must exist in the database.

| Action | Detail |
|--------|--------|
| Input | Optional `shipment_number`, `supplier_name`, `consignee_name`, `incoterm`, `transport_mode` |
| Deduplication | If `shipment_number` already exists → return existing record, no duplicate created |
| Placeholder | If no `shipment_number` supplied → generates `PENDING-<uuid>` |
| Output | `shipment_id` (UUID) — used as the anchor key for all subsequent steps |
| DB state | `status = "pending"` |

---

# STEP 2 — Vendor Document Pre-Validation

---

## A. API Entry

**Endpoint:** `POST /api/v2/validation/shipments/{shipment_id}/validate-vendor-docs`

**Files accepted:**

| Parameter | Required | Type |
|-----------|----------|------|
| `invoice_file` | Yes | PDF |
| `packing_list_file` | Yes | PDF |
| `bill_of_lading_file` | No | PDF |
| `freight_manifest_file` | No | PDF |
| `certificate_of_origin_file` | No | PDF |

A `file_map` dict is built from non-None uploads: `{"invoice": file, "packing_list": file, ...}`.

---

## B. Parallel Extraction

All files are extracted **simultaneously** via `asyncio.gather()` — not sequentially.

For each file an `_extract_one(doc_type, upload)` coroutine:

1. Reads file bytes from the upload object
2. Writes to `tempfile.NamedTemporaryFile` preserving the original extension (`.pdf`)
3. Calls `DocumentProcessingService.process_document(file_path, document_type)`

**Inside `process_document()`:**

| Step | Detail |
|------|--------|
| Schema build | `SchemaGenerator` reads `config/checklist.yaml` for the doc type — produces header fields + item fields |
| Extraction mode | `focused` — Claude is told exactly which fields to extract, their meanings, and where they appear |
| LLM call | `ClaudeProvider` sends PDF + schema to AWS Bedrock (`global.anthropic.claude-sonnet-4-6`) |
| Response normalisation | `ClaudeProvider._normalise_response()` unwraps envelopes, converts `{"value": X, "confidence": Y}` dicts to the canonical internal format |
| Return | `{"status": "complete", "fields": {...}, "items": [...], "blocks": [...], "token_usage": {...}}` |

4. Temp file deleted after extraction
5. **Guard:** if `status != "complete"` → `HTTP 422`, entire pipeline stops immediately

Token usage is collected from each extraction result for later aggregation.

---

## C. Normalization (Per Document)

After `asyncio.gather()` returns, each document is processed in a loop:

```
raw_fields = result["fields"]          # Claude's raw output keys
normalized_fields = SynonymMapper.map_document_fields(raw_fields, doc_type)
```

**Inside `SynonymMapper.map_document_fields()`:**

1. Iterates every key in `raw_fields`
2. Checks each key against the synonym table in the use-case YAML config  
   Examples: `"Shipping Condition"` → `incoterm`, `"Customer ref."` → `po_number`, `"Total Gross Weight"` → `gross_weight`
3. **Priority rule:** if the canonical name already exists in `raw_fields` as a direct key it is **never overwritten** — Claude's direct assignment takes priority over synonym mapping
4. Returns `normalized_fields` dict with canonical field names

Final doc dict: `extracted_docs[doc_type] = {**normalized_fields, "items": items}`

---

## D. Database Persistence

Single DB session, all documents committed in one batch.

For each document:

| Field | Value |
|-------|-------|
| `document_id` | New UUID |
| `document_type` | e.g. `"invoice"` |
| `shipment_id` | UUID from URL |
| `fields` | `normalized_fields` |
| `items` | items list from extraction |
| `blocks` | blocks list from extraction |
| `extraction_status` | `"complete"` |
| `doc_metadata` | includes extraction token usage |

---

## E. BL Number → Shipment Number Assignment

Runs only if `"bill_of_lading"` is in `extracted_docs`.

1. `bl_number = bol_fields.get("bl_number") or bol_fields.get("bill_of_lading_number")`
2. If value is a confidence envelope dict, unwrap: `bl_number = bl_number.get("value")`
3. If `bl_number` is non-empty:
   - Load shipment from DB
   - Only update if `shipment.boe_number` is not yet set (BOE not yet processed)
   - Set `shipment.shipment_number = str(bl_number)`, commit
   - **On `IntegrityError`** (BL number already claimed):
     - Rollback
     - Find the other shipment holding that `bl_number`
     - Set their `shipment_number = "REASSIGNED-{prev.id}"`
     - Commit, then claim the number for the current shipment

---

## F. Validation Session Creation

```python
context = session_manager.create_session(
    use_case="vendor_document_validation",
    documents=extracted_docs,
    primary_document="invoice",
    supporting_documents=[all other doc types],
    shipment_id=shipment_id,
)
```

Loads `config/validation/use_cases/vendor_document_validation.yaml`.

Creates a `ValidationContext` holding:

| Field | Value |
|-------|-------|
| `session_id` | New UUID |
| `use_case` | `"vendor_document_validation"` |
| `documents` | all normalized docs |
| `primary_document` | `"invoice"` |
| `config` | full YAML config |
| `validation_results` | `[]` (grows as checks run) |
| `discrepancies` | `[]` (grows as failures are found) |

---

## G. Workflow Execution

The engine reads `workflow.steps` from the config and iterates sequentially.

For each step:

1. `session_manager.update_step(session_id, step_name)` — marks current step
2. For each validator name in the step, instantiates the validator class with the step's `config` block
3. **Cross-doc detection:** if config contains `calculations`, `documents`, or `parties` keys, or if any `validations[].source/target` has a dot → `source_data = context.documents`; else `source_data = context.documents["invoice"]`
4. `await validator.validate(source_data, target_data, context)`
5. Failed results → converted to `Discrepancy` objects
6. Both results and discrepancies appended to session

---

## H. The 14 Validation Checks — Exact Internal Logic

All checks use `on_failure: "flag_and_continue"` — no check aborts the pipeline.

---

### Check 1 — Invoice Completeness

**Validator:** `RequiredFieldsValidator`  
**Source:** `context.documents["invoice"]`

For each of the 16 required fields:

1. `_get_field_value(doc_data, field_name)` — direct key lookup
2. If value is a `{"value": X, "confidence": Y}` envelope → unwraps to `X`
3. If `value["redacted"] == True` → returns the dict itself (preserves redacted marker, counts as present)
4. Falls back to dot-path traversal if field name contains `.`

**Decision tree per field:**

```
value is None           → passed=False  "Required field '{name}' is missing from invoice"
value is empty str/list → passed=False  "Required field '{name}' in invoice is empty"
otherwise               → passed=True
```

**Fields checked:** `invoice_number`, `invoice_date`, `shipper_name`, `shipper_address`,
`consignee_name`, `consignee_address`, `incoterm`, `currency`, `total_invoice_value`,
`net_weight`, `gross_weight`, `quantity`, `product_description`, `order_number`,
`contract_number`, `po_number`

**Output:** 16 individual `ValidationResult` objects.

---

### Check 2 — Packing List Completeness

**Validator:** `RequiredFieldsValidator`  
**Same logic as Check 1**, doc = `packing_list`

**Fields checked:** `consignee_name`, `consignee_address`, `incoterm`, `net_weight`,
`gross_weight`, `quantity`, `product_description`, `order_number`, `contract_number`,
`po_number`, `container_count`, `container_numbers`

> Note: No `invoice_number` — PL links to invoice via order/contract/PO references only.

---

### Check 3 — Bill of Lading Completeness

**Validator:** `RequiredFieldsValidator`  
**`optional_documents = ["bill_of_lading"]`**

- If `context.documents.get("bill_of_lading")` is `None` → `logger.debug(...)`, `continue` — **zero results emitted, silent skip**
- If present: checks `bl_number`, `shipper_name`, `shipper_address`, `consignee_name`,
  `container_count`, `container_numbers`, `net_weight`, `gross_weight`, `quantity`,
  `order_number`, `contract_number`, `po_number`

> Shipper fields are expected to contain a "REDACTED" marker — presence is required, the value is not validated further.

---

### Check 4 — Consignee Identity (Cross-Document)

**Validator:** `ShipperConsigneeValidator`  
**Documents:** `invoice`, `packing_list`, `bill_of_lading`  
**Threshold:** `0.75`

**For each document:**

1. Reads `consignee_name` via `_get_field_from_documents("{doc_type}.consignee_name", context)`  
   — tries `context.normalized_data[doc_type]` first, then falls back to `context.documents[doc_type]`
2. If value is a dict with `"redacted": True` → **skips that document entirely**, no failure
3. Calls `_normalize_name(str(value))`:
   - Takes only line 1 if multiline (company name, not the address below)
   - Strips Unicode accents via `unicodedata.normalize("NFD")` → removes combining marks → "Nestlé" → "Nestle"
   - Removes postal address tokens (`"private mail bag"`, `"pmb"`, `"p.o. box"`, etc.) if they appear after position 0
   - Removes punctuation `.,;:!?()[]{}\"'`
   - Lowercases
   - Removes company suffixes (`Ltd`, `Limited`, `Inc`, `Corp`, `LLC`, `NV`, `BV`, `Pty`, etc.) from end

4. If fewer than 2 docs have the field → `passed=True`, INFO, skip

**Comparison — `_validate_party_match()`:**

- `ref_doc` = first document in the values dict
- For each other doc: `_calculate_similarity(ref_normalized, compare_normalized)`:
  - Splits both into word sets
  - **Jaccard similarity:** `len(intersection) / len(union)`
  - Example: `{"nestle", "ghana"}` ∩ `{"nestle", "ghana"}` = `{"nestle", "ghana"}` → Jaccard = 1.0
- `match = similarity >= 0.75`
- `min_similarity` tracked across all pairs → reported as confidence
- All match → `passed=True`; any mismatch → `passed=False`, CRITICAL if >1 mismatch else MAJOR

---

### Check 5a — Order Number Consistency

**Validator:** `NWayMatcher`  
**Config:** `field_name="order_number"`, docs=`[invoice, packing_list, bill_of_lading]`, `match_type="exact"`, `require_all=False`

**Field resolution — `_resolve_field(doc_data, "order_number")`:**

1. `doc_data.get("order_number")` — direct header lookup
2. If `None` → tries `doc_data.get("items", [])[0].get("order_number")` — first line item as fallback

**Cross-validation — `_compare_values(field_values)`:**

- `_normalize_value(val, "exact")` → returns value unchanged (no transformation)
- `unique = set(values)` — if size == 1 → all match
- If size > 1 → `_identify_mismatches()`: groups documents by their value, reports which docs disagree and their values
- `passed=False`, `confidence=0.9`

> Since `require_all=False`: documents where the field is absent are ignored. If fewer than 2 docs have the field → `passed=True`, INFO, skip.

---

### Check 5b — Contract Number Consistency

**Same logic as 5a**, `field_name="contract_number"`

---

### Check 5c — PO Number Consistency

**Same logic as 5a**, `field_name="po_number"`

> **Key distinction enforced by synonym mapping:** `"Customer ref."` → `po_number` (buyer's reference); `"Order no."` → `order_number` (seller's reference). These are separate canonical fields and are never cross-compared with each other.

---

### Check 6 — Product Description Consistency

**Validator:** `NWayMatcher`  
**Config:** `field_name="product_description"`, docs=`[invoice, packing_list, bill_of_lading]`, `match_type="fuzzy"`, `fuzzy_threshold=0.5`, `require_all=False`

**Fuzzy comparison — `_compare_fuzzy(field_values)`:**

For every pair of documents `(doc_a, doc_b)`:

1. `val_a = str(field_values[doc_a]).strip().lower()`
2. `val_b = str(field_values[doc_b]).strip().lower()`
3. `score = rapidfuzz.fuzz.token_set_ratio(val_a, val_b) / 100.0`  
   (falls back to `difflib.SequenceMatcher` if rapidfuzz not installed)
4. `token_set_ratio` tokenises both strings, sorts the token sets, compares sorted-set vs the intersection — handles abbreviated codes vs full product names
5. `passed_pair = score >= 0.5`

`all_passed = True` only if every pair passes.  
`min_score` = minimum pairwise score → reported as confidence.  
Failing pairs listed individually in the discrepancy.

> Threshold is 0.5 (not the default 0.7) because invoice uses abbreviated SAP codes
> ("FFP 28% MQAV004F-1 25kg bag") while PL/BOL use the full trade name
> ("Instant Fat Filled Powder 28% veg. fat, vit & min enriched, MQAV004F-1, 25 kg bag").

---

### Check 7 — Incoterm Consistency

**Validator:** `NWayMatcher`  
**Config:** `field_name="incoterm"`, docs=`[invoice, packing_list]`, `match_type="fuzzy"`, `require_all=True`

Both documents are required — if either is missing the field it is a failure.  
Fuzzy comparison. "FCA ROTTERDAM PORT" vs "FCA ROTTERDAM PORT" → score = 1.0 → pass.

---

### Check 8 — Incoterm Freight/Insurance Rules

**Validator:** `IncotermValidator`  
**Source fields:** `invoice.incoterm`, `invoice.freight_value`, `invoice.insurance_value`, `invoice.total_fob_value`

1. Reads `incoterm` from `invoice` via dot-path resolver
2. `incoterm_upper = str(incoterm).upper().strip().split()[0]` → extracts 3-letter code only
3. `is_boe_source`: checks if freight/insurance fields start with `"bill_of_entry."` → here they don't → `False`
4. Branches:

| Incoterm group | Rule applied |
|----------------|-------------|
| `CFR`, `CIF`, `CPT`, `CIP`, `DAP`, `DPU`, `DDP` | Freight must be present and > 0 |
| `CIF`, `CIP` | Insurance must be present and > 0 |
| `EXW`, `FCA`, `FAS`, `FOB` | Freight AND insurance must NOT be on invoice (both must be 0 or absent) |
| `CIF` only | CIF = FOB + Freight + Insurance verified with ±0.01 tolerance |

**For FCA (the Vreugdenhil case):**
- `_validate_no_freight("FCA", freight_value, insurance_value)`:
  - `freight_decimal = _to_decimal(freight_value)` → 0 if None
  - `insurance_decimal = _to_decimal(insurance_value)` → 0 if None
  - If either `> 0` → `passed=False`, MINOR, "FCA should not have freight/insurance on invoice"
  - If both 0 → `passed=True`, INFO, "FCA: No freight/insurance on invoice (correct)"

---

### Check 9 — Net Weight Consistency

**Validator:** `ToleranceValidator`  
**Tolerance:** 1.0%

**Two comparisons:**

| Source | Target | Optional |
|--------|--------|----------|
| `invoice.net_weight` | `packing_list.net_weight` | No |
| `invoice.net_weight` | `bill_of_lading.net_weight` | Yes (`optional_target: true`) |

**`_to_numeric(value)` — full parsing logic:**

| Input format | Detection | Action |
|-------------|-----------|--------|
| `int`, `float`, `Decimal` | `isinstance` check | `Decimal(str(value))` directly |
| `{"value": "...", ...}` dict | dict with `"value"` key | Takes `value["value"]` |
| `"189,000.000"` (US format) | both `,` and `.` present; last dot > last comma | strips `,` |
| `"189.000,00"` (European) | both `,` and `.` present; last comma > last dot | strips `.`, replaces `,` with `.` |
| `"7,560"` (thousands comma) | single `,`, 3 digits after | strips `,` |
| `"9,5"` (decimal comma) | single `,`, 1-2 digits after | replaces `,` with `.` |
| `"189.000"` (Euro thousands) | single `.`, exactly 3 digits after | strips `.` |
| `"189,000.00 kg"` | trailing unit suffix | `re.sub(r'[^0-9.,\-]+$', '', raw)` strips it |

**`_validate_tolerance(source, target, tolerance=1.0, type="percentage", operator="equals")`:**

```
difference     = source - target
tolerance_val  = abs(target) × 0.01        (1% of target)
passed         = abs(difference) ≤ tolerance_val
```

**`_calculate_confidence(difference, tolerance_val, passed)`:**

| State | Calculation |
|-------|-------------|
| Passed | `ratio = abs(diff) / tol_val`; `confidence = max(0.7, 1.0 - ratio × 0.3)` |
| Failed, ratio < 1.2 | `confidence = 0.6` (just outside tolerance) |
| Failed, ratio < 1.5 | `confidence = 0.4` |
| Failed, ratio ≥ 1.5 | `confidence = 0.2` |

**If `optional_target=True` and BOL is absent:** emits `passed=True`, INFO, "target not available — skipping optional cross-check".

---

### Check 10 — Gross Weight Consistency

**Same logic as Check 9**, field = `gross_weight`

---

### Check 11 — Quantity Consistency

**Same logic as Check 9**, field = `quantity`, `tolerance = 0.5%`

---

### Check 12 — Container Count Consistency

**Validator:** `NWayMatcher`  
**Config:** `field_name="container_count"`, docs=`[packing_list, bill_of_lading]`, `match_type="exact"`, `require_all=False`

If BOL not uploaded → only 1 value available → `len(field_values) < 2` → `passed=True`, INFO, skipped silently.

---

### Check 13 — Container Numbers Consistency

**Validator:** `NWayMatcher`  
**Config:** `field_name="container_numbers"`, `match_type="normalized"`, `require_all=False`

**`_normalize_value(value, "normalized")`:**

- If value contains `,` → splits on `,`, strips each token, uppercases each, **sorts alphabetically**, rejoins with `,`
- `"BEAU4500001,BEAU4500000"` and `"BEAU4500000,BEAU4500001"` → both normalize to `"BEAU4500000,BEAU4500001"` → match

Order differences between PL and BOL are handled. Set comparison, not positional.

---

### Check 14 — Country of Origin

**Validator:** `RequiredFieldsValidator`  
**`optional_documents = ["certificate_of_origin"]`**

- If `context.documents.get("certificate_of_origin")` is `None` → doc type is in `optional_documents` → `logger.debug(...)`, `continue` — **zero results emitted, silent skip**
- If present: checks `country_of_origin` and `consignee_name`

---

## I. Result Aggregation & Response

**Status determination:**

| Condition | `final_status` |
|-----------|----------------|
| `all_validations_passed == True` | `"passed"` |
| Any critical discrepancy | `"failed"` |
| Major/minor discrepancies only | `"requires_attention"` |
| Workflow paused for HITL | `"awaiting_user"` |

**Token usage aggregated:**  
`aggregate_token_usages([*extraction_usages, validation_tracker.get_summary()])` — sums input tokens, output tokens, cost, and call count across all LLM calls.

Persisted to `shipment_token_usage` table with `validation_type="vendor_validation"`.  
Also written to `invoice.APIDocument.doc_metadata["shipment_token_usage"]`.

**Email alert:** `asyncio.create_task(_send_validation_alert(...))` — fire-and-forget, never blocks the HTTP response.

**Response payload:**

```json
{
  "session_id": "...",
  "shipment_id": "...",
  "workflow_status": "completed | awaiting_user",
  "final_status": "passed | failed | requires_attention",
  "summary": {
    "total_checks": N,
    "passed_checks": N,
    "failed_checks": N,
    "total_discrepancies": N,
    "critical": N,
    "major": N,
    "minor": N,
    "documents_processed": ["invoice", "packing_list", ...]
  },
  "discrepancies": [...],
  "validation_results": [...],
  "extracted_documents": {...},
  "token_usage": {...}
}
```

---
---

# STEP 6 — BOE Cross-Verification

---

## A. API Entry

**Endpoint:** `POST /api/v2/validation/shipments/{shipment_id}/validate-boe`

**Input:** single `boe_file` (`UploadFile`, PDF)

**Pre-conditions enforced:**
- Step 2 must have already run
- Invoice and packing list must exist in DB for this `shipment_id`

---

## B. Load Step 2 Documents from DB

No re-upload required — vendor docs were stored during Step 2.

```python
vendor_docs_raw, _ = await repo.list_documents(
    shipment_id=shipment_id,
    extraction_status="complete",
    limit=20,
)
```

Queries `api_documents` table filtered by `shipment_id` and `extraction_status="complete"`.  
Filters to doc types: `invoice`, `packing_list`, `bill_of_lading`, `freight_manifest`, `certificate_of_origin`.

Reconstructs dict:
```python
vendor_docs = {
    d.document_type: {**d.fields, "items": d.items or []}
    for d in vendor_docs_raw
}
```

`d.fields` is the `normalized_fields` stored during Step 2 — already synonym-mapped.

**Hard guards:**
- `"invoice"` not in `vendor_docs` → `HTTP 422 "Run Step 2 first"`
- `"packing_list"` not in `vendor_docs` → `HTTP 422 "Run Step 2 first"`

---

## C. BOE Extraction

1. File bytes read, written to temp file
2. `processing_service.process_document(file_path, "bill_of_entry")` called
3. Inside: `SchemaGenerator` builds BOE schema from `checklist.yaml` (36 header fields + 3 item fields)
4. Claude extraction in `focused` mode
5. **BOE-specific post-processing — `boe_section_extractor`:**
   - Detects and restructures BOE layout sections:
     - `s16`: value/origin section (Field 16 — Country of Origin)
     - `s21`: entry/exit office code (Field 21)
     - `s25`: line items — goods description, HS codes, quantities
     - `s31`: package details
     - `s40`: tax computation table (duty, VAT, NHIL, GET Fund rows)
   - Flattens into a uniform `fields` + `items` structure
6. Guard: `status != "complete"` → `HTTP 422`

**Key BOE fields extracted:**

| Field | BOE Location | Description |
|-------|-------------|-------------|
| `declaration_number` | Header | GRA declaration reference |
| `customs_code` | Field 1 | CPC code (40E68, 40V02, 40U01, 40W01) |
| `hs_code` | Section 25 | 10-digit Ghana tariff code |
| `customs_value` | Field 23 | CIF value in GHS |
| `fob_ncy` | Field 19 | FOB in GHS (national currency) |
| `total_fob_value` | Field 15/33 | FOB in foreign currency |
| `freight_value` | Field 20 | Freight in GHS |
| `insurance_value` | Field 23 sub | Insurance in GHS |
| `duty_rate` | Section 47 | Import duty rate (e.g. 0.05) |
| `duty_amount` | Section 47 | Import duty in GHS |
| `vat_amount` | Tax 02 | VAT Amount Payable in GHS |
| `nhil_amount` | Tax 47 | NHIL Amount Payable in GHS |
| `get_fund_levy` | Tax 88 | GET Fund Levy in GHS |
| `amount_payable` | Summary | Total taxes payable |
| `amount_exempted` | Summary | Total taxes deferred/suspended |
| `etls_approval_number` | Header | ECOWAS Trade Liberalisation Scheme ref |
| `shipper_name` | Field 2 | Exporter name |
| `consignee_name` | Field 8 | Importer name |
| `declarant_name` | Field 9 | Clearing agent name |
| `declarant_reg_number` | Field 9 | Clearing agent CH license number |
| `entry_exit_code` | Field 14/21 | Port code ("KIA", "TMA") or GRA numeric ("10", "40") |
| `invoice_number` | Field 40 | Invoice referenced on BOE |
| `incoterm` | Field 20 | Incoterm |
| `currency` | Field 22 | Foreign currency code |
| `gross_weight` | Field 35 | Gross weight in KG |
| `container_count` | Field 19 sub | Number of containers |
| `origin` | Field 16 | Country of origin |

---

## D. BOE Normalization

```python
boe_normalized_fields = SynonymMapper.map_document_fields(
    boe_raw_fields, document_type="bill_of_entry"
)
```

BOE-specific synonym mappings applied:

| Raw key | Canonical |
|---------|-----------|
| `"declarant_representative"` | `declarant_name` |
| `"declarant_no"` | `declarant_reg_number` |
| `"curr_code"` | `currency` |
| `"cpc_code"` or `"CPC"` | `customs_code` |
| `"total_fob_fcy"` | `total_fob_value` |
| `"country_of_origin"` | `origin` |

---

## E. BOE Database Persistence

- New UUID as `boe_doc_id`
- `APIDocument` created: `document_type="bill_of_entry"`, linked to `shipment_id`
- Fields, items, blocks, token usage stored
- Committed

---

## F. Declaration Number Assignment (Overwrite Mode)

```python
decl_number = boe_normalized_fields.get("declaration_number")
if isinstance(decl_number, dict):
    decl_number = decl_number.get("value")
```

If `decl_number` is not None, a single DB session runs the following sequence:

**Step 1 — Release `boe_number` conflicts:**
```sql
SELECT * FROM shipments WHERE boe_number = '{decl_number}' AND id != '{shipment_id}'
```
For each conflicting shipment found:
- If `prev.shipment_number == decl_number`: set `prev.shipment_number = "REASSIGNED-{prev.id}"`
- Set `prev.boe_number = NULL`

**Step 2 — Release `shipment_number` conflicts:**
```sql
SELECT * FROM shipments WHERE shipment_number = '{decl_number}' AND id != '{shipment_id}'
```
For each: `prev.shipment_number = "REASSIGNED-{prev.id}"`

**Step 3 — Assign to current shipment:**
- `shipment.boe_number = decl_number` — always set
- `shipment.shipment_number = decl_number` — only if currently `None` or starts with `"PENDING-"` (do not overwrite a real BL number)
- `db.commit()`

> **Overwrite mode** is active because the system is in testing phase. In production this would
> become an error (`409 Conflict`) for duplicate BOE numbers.

---

## G. Document Assembly

```python
documents = {
    **vendor_docs,           # invoice, packing_list, bill_of_lading (from DB, Step 2)
    "bill_of_entry": {
        **boe_normalized_fields,
        "items": boe_result["items"],
    },
}
```

This single unified dict is passed to every validator as `context.documents`.

---

## H. Validation Session Creation

```python
context = session_manager.create_session(
    use_case="boe_validation",
    documents=documents,
    primary_document="bill_of_entry",
    supporting_documents=["invoice", "packing_list", ...],
    shipment_id=shipment_id,
)
```

Loads `config/validation/use_cases/boe_validation.yaml`.  
Same `ValidationContext` structure as Step 2 but with BOE validation config and `primary_document = "bill_of_entry"`.

---

## I. The 22 Validation Checks — Exact Internal Logic

---

### Check 1 — Shipper/Consignee Cross-Document Identity

**Validator:** `ShipperConsigneeValidator`  
**Two parties processed sequentially:**

**Shipper party:**
- Documents: `bill_of_entry`, `invoice`, `bill_of_lading`
- Field: `shipper_name` on each
- Threshold: `0.65`
- If BOL `shipper_name` is `{"redacted": True}` → **silently skipped**, not counted as a failure
- Normalization: identical pipeline to Step 2 Check 4 (accents → punctuation → lowercase → suffixes)
- Similarity: **Jaccard word overlap** `len(intersection) / len(union)`

**Consignee party:**
- Documents: `bill_of_entry`, `invoice`
- Field: `consignee_name`
- Threshold: `0.80`

Same comparison logic: if `min_similarity < threshold` across any pair → `passed=False`, MAJOR (1 mismatch) or CRITICAL (>1).

---

### Check 2 — Required Fields on BOE

**Validator:** `RequiredFieldsValidator`

| Document | Required fields |
|----------|----------------|
| `bill_of_entry` | `hs_code`, `gross_weight`, `quantity`, `duty_rate` |
| `invoice` | `net_weight`, `quantity` |
| `packing_list` | `net_weight`, `gross_weight` |

Same `_get_field_value()` logic — exact key lookup, envelope unwrap, redacted preservation.

---

### Check 3 — HS Code 3-Way Match

**Validator:** `NWayMatcher`  
**Config:** `field_name="hs_code"`, docs=`[bill_of_entry, invoice, packing_list]`, `match_type="exact"`, `require_all=False`

Field resolved from header first, then `items[0]` fallback.

- If only BOE has the HS code (invoice/PL don't carry it): `len(field_values) = 1 < 2` → `passed=True`, INFO, skipped
- If 2+ docs have it: `set(values)` must have size == 1 for pass

---

### Check 4 — Weight Matching

**Validator:** `ToleranceValidator`  
**Five comparisons, all `tolerance=1.0%`, `operator="equals"`:**

| # | Source | Target |
|---|--------|--------|
| a | `invoice.net_weight` | `packing_list.net_weight` |
| b | `invoice.gross_weight` | `packing_list.gross_weight` |
| c | `packing_list.gross_weight` | `bill_of_entry.gross_weight` |
| d | `bill_of_lading.gross_weight` | `invoice.gross_weight` |
| e | `bill_of_lading.net_weight` | `invoice.net_weight` |

For d and e: if BOL is absent, `target_value` resolves to `None` and the check fails (no `optional_target: true` in Step 6 config).

`_to_numeric()`, `_validate_tolerance()`, and `_calculate_confidence()` work identically to Step 2 Check 9 — see that section for full parsing detail.

> Note: BOE only carries gross weight (Field 35) — BOE net weight vs vendor doc is not compared.

---

### Check 5 — Quantity Matching

**Validator:** `ToleranceValidator`  
One comparison: `invoice.quantity` vs `packing_list.quantity`, `tolerance=0.5%`

BOE quantity is in different units (pallets/containers) — not compared against vendor doc bags.

---

### Check 6 — Duty Amount Calculation

**Validator:** `CalculationValidator`  
**Formula:** `"customs_value * duty_rate"`

1. Resolves `bill_of_entry.customs_value` and `bill_of_entry.duty_rate` from `context.documents`
2. Calls `_to_numeric()` on each value
3. If either is missing → `passed=False`, "missing fields"
4. **`_evaluate_formula(formula, field_values)`:**
   - `ast.parse("customs_value * duty_rate", mode="eval")`
   - Walks AST: `BinOp(Mult, Name("customs_value"), Name("duty_rate"))`
   - Substitutes Decimal values, computes result
   - Only allows: `Add`, `Sub`, `Mult`, `Div`, `Pow`, `Name`, `Constant`, `UnaryOp`
   - Any attribute access, function call, or subscript → `ValueError`
5. Fetches `bill_of_entry.duty_amount` as target
6. If target absent → `passed=True`, INFO, "target not present — cannot verify"
7. `difference = abs(calculated - target)`; `tolerance_val = abs(target × 0.005)`; `passed = difference ≤ tolerance_val`
8. `pct_diff = float(difference / target × 100)`

---

### Check 7 — CIF Customs Value Verification

**Validator:** `CalculationValidator`  
**Formula:** `"fob_ncy + freight_value + insurance_value"`

- `fob_ncy` → `bill_of_entry.fob_ncy` (GHS FOB, Field 19)
- `freight_value` → `bill_of_entry.freight_value`
- `insurance_value` → `bill_of_entry.insurance_value`
- `target` → `bill_of_entry.customs_value`
- Tolerance: 1.0%

> Uses BOE's own GHS fields (not invoice) so FCA/FOB shipments never produce
> false "missing fields" failures — the invoice doesn't carry freight/insurance
> for those incoterms, but the BOE always does for customs valuation purposes.

---

### Check 8 — Duty Rate Range

**Validator:** `RangeValidator`  
**Config:** `field="duty_rate"`, `min=0`, `max=1.0`, `inclusive=True`

Reads `bill_of_entry.duty_rate` from primary doc dict. Converts to `Decimal`. Checks `0 ≤ value ≤ 1.0`.

---

### Check 9 — HS Code Format

**Validator:** `RegexValidator`  
**Pattern:** `^\d{4}\.\d{2}(\.\d{2}(\.\d{2})?)?|\d{6,10}$`

`re.match(pattern, str(hs_code))`

| Input | Match |
|-------|-------|
| `"1901.90"` | `\d{4}\.\d{2}` ✓ |
| `"1901.90.20.00"` | full dotted form ✓ |
| `"1901902000"` | `\d{6,10}` ✓ |
| `"190190"` | `\d{6,10}` ✓ |
| `"ABC1234"` | ✗ |

---

### Check 10 — Customs Code Rules (CPC-specific)

**Validator:** `CustomsCodeValidator`

**Initialisation merges defaults with config:**
- Config overrides `vat_rate` per code (notably `40V02 → 0.15`, not the default `0.05`)
- All `vat_rate` values cast to `Decimal`
- `etls_only = False` here

**Execution per validation config:**

1. Reads all fields from `context.documents["bill_of_entry"]`:
   - `customs_code`, `customs_value`, `amount_payable`, `amount_exempted`, `duty_amount`, `vat_amount`
2. If `customs_code` is `None` → CRITICAL "Customs code not found in BOE"
3. If `customs_code` not in `self.customs_codes` → MAJOR "Unrecognized customs code"
4. Gets `code_config = self.customs_codes[customs_code]`

---

#### Branch: `customs_code == "40E68"` — Full VAT Payment

`_validate_40E68(customs_value, actual_amount_payable, code_config)`:

```
expected = (customs_value × 0.05).quantize("0.01", ROUND_HALF_UP)
difference = abs(expected - actual)
passed = difference ≤ 0.01
```

| Outcome | Severity |
|---------|----------|
| `passed` | INFO |
| `difference > expected × 0.05` | CRITICAL |
| otherwise | MAJOR |

---

#### Branch: `customs_code == "40V02"` — VAT Deferment

`_validate_40V02(customs_value, actual_vat_amount, actual_amount_exempted, actual_duty_amount, code_config)`:

**Sub-check A — VAT Amount Payable must be 0:**
```
actual_vat = _to_decimal(actual_vat_amount)    # Tax 02 Amount Payable column
expected   = Decimal("0.00")
passed     = abs(actual_vat - 0) ≤ 0.01
```
- Pass: INFO "Import VAT Amount Payable is 0.00 — VAT deferment correctly applied"
- Fail: CRITICAL "Import VAT must be 0.00 for VAT deferment — got {actual_vat}"

**Sub-check B — Amount Exempted holds the deferred VAT:**
```
vat_base          = customs_value + duty_amount
expected_exempted = (vat_base × 0.15).quantize("0.01", ROUND_HALF_UP)
```
- If `actual_amount_exempted` is `None` → `passed=True`, INFO, reports expected value for reference
- If present: `difference = abs(expected_exempted - actual_exempted)`; `passed = difference ≤ 0.01`
- Pass: INFO; Fail: MAJOR

> The 15% rate: Ghana's standard VAT rate.
> The base is `customs_value + duty_amount` because both attract VAT — not just the customs value.

---

#### Branch: `customs_code == "40U01"` — ECOWAS Zero Duty

`_validate_40U01(actual_duty_amount, code_config)`:
```
expected_duty = Decimal("0.00")
passed = abs(actual_duty - 0) ≤ 0.01
```
- Fail: CRITICAL "Duty Amount must be 0.00 for duty exemption"
- If `require_etls_approval=True` → also calls `_validate_etls_approval()`

---

#### Branch: `customs_code == "40W01"` — ECOWAS Zero Duty, Taxes Payable

`_validate_40W01(actual_duty_amount, actual_vat_amount, code_config)`:

1. Duty = 0 check (same as 40U01)
2. VAT > 0 check — VAT must still be payable
   - `vat_payable = actual_vat_amount > 0`
   - Fail: MINOR "Warning — VAT should be payable for this customs code"
3. If `require_etls_approval=True` → calls `_validate_etls_approval()`

---

### Check 11 — Mode of Shipment

**Validator:** `ModeOfShipmentValidator`

1. `entry_exit_code = context.documents["bill_of_entry"].get("entry_exit_code")`
2. If `None` → `passed=True`, INFO, "shipment mode validation skipped"
3. `entry_code_upper = str(entry_exit_code).upper().strip()`
4. Iterates `mode_mappings` (substring check: `if code_pattern in entry_code_upper`):

| Pattern | Mode | Notes |
|---------|------|-------|
| `"KIA"` | air | Kotoka International Airport |
| `"KOTOKA"` | air | |
| `"AIRPORT"` | air | |
| `"40"` | air | GRA ICUMS Field 14 numeric code |
| `"TMA"` | sea | Tema Port |
| `"TEMA"` | sea | |
| `"PORT"` | sea | |
| `"HARBOR"` / `"HARBOUR"` | sea | |
| `"10"` | sea | GRA ICUMS numeric code |
| `"20"` | sea | Rail — treated as sea for document purposes |
| `"BORDER"` | road | |
| `"LAND"` | road | |
| `"30"` | road | GRA ICUMS numeric code |

5. If no pattern matches → MINOR "Unknown Entry/Exit code"
6. `expected_doc_types = document_mappings[expected_mode]`:
   - `air` → `["airway_bill", "awb", "air_waybill"]`
   - `sea` → `["bill_of_lading", "bl", "bol"]`
   - `road` → `["delivery_note", "dn", "cmr"]`
7. `available_docs = list(context.documents.keys())`
8. `correct_doc_found = any(any(exp in doc.lower() for exp in expected_doc_types) for doc in available_docs)` — substring check
9. Pass: INFO with port code and mode; Fail: MAJOR with available vs expected doc types

---

### Check 12 — Incoterm Freight/Insurance Rules (BOE context)

**Validator:** `IncotermValidator`  
**Fields:** `invoice.incoterm`, `invoice.freight_value`, `invoice.insurance_value`, `invoice.total_fob_value`, `bill_of_entry.customs_value`

Same branching logic as Step 2 Check 8. `is_boe_source = False` since freight/insurance fields point to invoice. FCA → no freight/insurance on invoice verified.

---

### Check 13 — Declarant Presence

**Validator:** `RequiredFieldsValidator`  
**`required_fields = {"bill_of_entry": ["declarant_name", "declarant_reg_number"]}`**

Checks clearing agent name and CH license number are present and non-empty on the BOE.

---

### Check 14 — FOB Value: BOE vs Invoice

**Validator:** `ToleranceValidator`  
**Comparison:** `bill_of_entry.total_fob_value` vs `invoice.total_fob_value`, `tolerance=0.5%`

BOE carries FOB in foreign currency (Field 15/33). Invoice is also in foreign currency. Comparison is valid only when both are in the same currency.

What it catches: clearing agent declared a different FOB than the commercial invoice — potential undervaluation or data entry error.

---

### Check 15 — Invoice Number Cross-Check

**Validator:** `NWayMatcher`  
**Config:** `field_name="invoice_number"`, docs=`[bill_of_entry, invoice]`, `match_type="exact"`, `require_all=True`

- `require_all=True` → if either doc is missing the field → CRITICAL "missing from required documents"
- If both present: exact string comparison

---

### Check 16 — Incoterm: BOE vs Invoice

**Validator:** `NWayMatcher`  
**Config:** `match_type="incoterm"`, `require_all=False`

`_normalize_value(value, "incoterm")`:
```python
m = re.match(r'([A-Z]{3})', value.strip().upper())
return m.group(1) if m else value.upper().strip()
```
Extracts only the 3-letter code: `"FCA ROTTERDAM PORT"` → `"FCA"`.  
Comparison is on the code only — port name differences are ignored.

---

### Check 17 — Currency Consistency

**Validator:** `NWayMatcher`  
**Config:** `field_name="currency"`, `match_type="exact"`, `require_all=False`

Direct string equality. Both should be `"EUR"` (or whatever the invoice currency is).

---

### Check 18 — Country of Origin

**Validator:** `RequiredFieldsValidator`  
**`required_fields = {"bill_of_entry": ["origin"]}`**

> Field is `"origin"`, not `"country_of_origin"` — the synonym mapper converts during normalization.

---

### Check 19 — Container Count: BOE vs BOL

**Validator:** `NWayMatcher`  
**Config:** `field_name="container_count"`, docs=`[bill_of_entry, bill_of_lading]`, `require_all=False`

If BOL was not uploaded in Step 2 → only 1 value → skip.

---

### Check 20 — ETLS Approval Number

**Validator:** `CustomsCodeValidator` (`etls_only=True`)

**`etls_only=True` changes the execution path:**

```python
if self.etls_only:
    if code_config.get("require_etls_approval"):
        results.append(self._validate_etls_approval(customs_code, etls_approval_number))
    continue  # skips all amount calculations
```

Only applies to `40U01` and `40W01` — `require_etls_approval=True` on both.  
Skips all amount checks to avoid duplicating discrepancies already raised in Check 10.

**`_validate_etls_approval(customs_code, etls_approval_number)`:**
```
has_approval = bool(etls_approval_number and str(etls_approval_number).strip())
```
- Pass: INFO "{code}: ETLS Approval Number present ({number})"
- Fail: MAJOR "{code}: Import duty is zero/exempted but no ETLS Approval Number found on BOE"

---

### Check 21 — Master Concession Eligibility

**Validator:** `ConcessionEligibilityValidator`  
**Applies to:** `40U01`, `40W01`  
**Reference data:** `config/data/master_concession.yaml`

1. If `customs_code` not in `["40U01", "40W01"]` → return INFO, skipped
2. **Concession reference check:**
   - Reads `bill_of_entry.etls_approval_number`
   - Must contain `"MD202601CUSTCU030000003304"`
   - Fail: CRITICAL "Wrong or missing concession reference number"
3. **Expiry date check:**
   - Reads `bill_of_entry.declaration_date`, parses to date
   - Compares against `2026-12-31`
   - Fail: CRITICAL "Concession expired"
4. **Item eligibility:**
   - Reads `context.documents["bill_of_entry"]["items"]`
   - For each item: reads `item.get("hs_code")`
   - Normalizes (strips dots, removes non-digits)
   - Checks against approved HS code set from YAML
   - Secondary confirmation: fuzzy-matches `product_description` (threshold `0.60`)
   - Per-item result: Pass INFO / Fail MAJOR "item not listed on Master Concession"

---

### Check 22 — VAT, NHIL, GET Fund Levy Amounts

**Validator:** `CalculationValidator`  
**Three separate calculations — same base formula, different rates and targets:**

| Tax | Formula | Target field | GRA Tax Code | Rate |
|-----|---------|-------------|-------------|------|
| VAT | `(customs_value + duty_amount) * 0.15` | `bill_of_entry.vat_amount` | Tax 02 | 15% |
| NHIL | `(customs_value + duty_amount) * 0.025` | `bill_of_entry.nhil_amount` | Tax 47 | 2.5% |
| GET Fund | `(customs_value + duty_amount) * 0.025` | `bill_of_entry.get_fund_levy` | Tax 88 | 2.5% |

**Tolerance:** 0.5% for all three.

**AST evaluation of `"(customs_value + duty_amount) * 0.15"`:**
- Parses to: `BinOp(Mult, BinOp(Add, Name("customs_value"), Name("duty_amount")), Constant(0.15))`
- Evaluates inner `Add` first (correct precedence due to parentheses), then `Mult`
- All arithmetic in `Decimal` — no float imprecision

Three `ValidationResult` objects emitted individually.

---

### Check 23 — VAT Deferment Eligibility

**Validator:** `VatDefermentValidator`  
**Applies to:** `40V02` only  
**Reference data:** `config/data/vat_deferment_list.yaml` (82 approved HS codes, URV 0014)

1. If `customs_code != "40V02"` → return INFO, skipped
2. Loads and normalizes all approved HS codes: `re.sub(r'\D', '', hs_code)` (remove non-digits)
3. For each item in `context.documents["bill_of_entry"]["items"]`:
   - Reads `item.get("hs_code")`
   - Normalizes: removes non-digits → `"1901902000"`
   - Checks against approved set
   - Pass: INFO per item; Fail: MAJOR "HS code {code} not on VAT deferment list (URV 0014)"

> Example: HS `1901902000` (Filled Milk Powder FFP 28% MQAV004F-1) is item 23 on URV 0014 → pass.

---

### Check 24 — Insurance Rate Verification

**Validator:** `IncotermValidator`  
**Config:** `check_insurance_rate=True` activated

1. `incoterm` read from `invoice.incoterm` → `"FCA"`
2. `"FCA"` is in `INSURANCE_RATE_APPLICABLE` → rate check applies
3. `fob_value`, `freight_value`, `insurance_value` read from `bill_of_entry.*`
4. `transport_mode` read from `bill_of_entry.entry_exit_code`
5. `is_air = str(transport_mode).upper().startswith(("KIA",))`

| Mode | Rate | Source |
|------|------|--------|
| Air (`KIA*`) | 1.000% | `INSURANCE_RATE_AIR = Decimal("0.01")` |
| Sea / Road (all others) | 0.875% | `INSURANCE_RATE_SEA_ROAD = Decimal("0.00875")` |

```
candf              = fob + freight
expected_insurance = (candf × rate).quantize("0.01", ROUND_HALF_UP)
tolerance          = max(expected_insurance × 0.005, Decimal("0.01"))
passed             = abs(expected_insurance - actual_insurance) ≤ tolerance
```

Pass: INFO; Fail: MAJOR

---

## J. Result Aggregation & Response

Same status determination as Step 2.

Token usage: `aggregate_token_usages([boe_extraction_token_usage, boe_validation_tracker.get_summary()])` — covers BOE extraction LLM call + any AI validators.

Persisted to `shipment_token_usage` with `validation_type="boe_validation"`.

Email alert fired asynchronously.

---

## K. How a Discrepancy Is Structured

Every failed `ValidationResult` is converted to a `Discrepancy` by the engine:

```python
Discrepancy(
    field_name       = result.field_name,       # e.g. "vat_amount"
    source_document  = result.source_document,  # e.g. "bill_of_entry"
    target_document  = result.target_document,
    source_value     = result.source_value,     # actual value found
    target_value     = result.target_value,     # expected value
    difference       = result.discrepancy,      # dict: formula, diff%, tolerance, field_values
    severity         = result.severity,         # "critical" | "major" | "minor" | "info"
    confidence       = result.confidence,       # 0.0 – 1.0
    auto_fixed       = result.auto_fixed,       # bool
    metadata         = result.metadata          # customs_code, doc lists, pair details, etc.
)
```

**Severity definitions:**

| Severity | Examples | Effect |
|----------|---------|--------|
| `critical` | HS code mismatch, duty calculation error, VAT deferment violation | `final_status = "failed"` |
| `major` | Weight difference, missing declarant, wrong incoterm | `final_status = "requires_attention"` |
| `minor` | Rounding differences, weight ≤ 1% | Flagged but lower priority |
| `info` | Skipped optional checks, passed checks | Not a discrepancy |

---

## L. Full Data Flow Diagram

```
POST /create-shipment
  └─ Shipment row created (status=pending, shipment_number=PENDING-<uuid>)
       │
       ▼
POST /validate-vendor-docs
  ├─ Extract invoice + PL + BOL in parallel (Claude, focused mode)
  ├─ Normalize each doc (SynonymMapper)
  ├─ Store APIDocument rows in DB (linked to shipment_id)
  ├─ Update shipment_number = BL number (if BOL uploaded)
  ├─ Create ValidationSession (use_case=vendor_document_validation)
  ├─ Run 14 checks sequentially:
  │    1.  Invoice completeness         (RequiredFieldsValidator)
  │    2.  Packing list completeness    (RequiredFieldsValidator)
  │    3.  BOL completeness             (RequiredFieldsValidator, optional)
  │    4.  Consignee identity           (ShipperConsigneeValidator, fuzzy 0.75)
  │    5a. Order number consistency     (NWayMatcher, exact)
  │    5b. Contract number consistency  (NWayMatcher, exact)
  │    5c. PO number consistency        (NWayMatcher, exact)
  │    6.  Product description          (NWayMatcher, fuzzy 0.5)
  │    7.  Incoterm consistency         (NWayMatcher, fuzzy)
  │    8.  Incoterm freight/insurance   (IncotermValidator)
  │    9.  Net weight                   (ToleranceValidator, ±1%)
  │    10. Gross weight                 (ToleranceValidator, ±1%)
  │    11. Quantity                     (ToleranceValidator, ±0.5%)
  │    12. Container count              (NWayMatcher, exact)
  │    13. Container numbers            (NWayMatcher, normalized/sorted)
  │    14. Country of origin            (RequiredFieldsValidator, optional)
  ├─ Aggregate token usage, persist to shipment_token_usage
  ├─ Fire email alert (async, non-blocking)
  └─ Return: session_id, final_status, discrepancies, validation_results, extracted_documents

       │
    (HITL review if discrepancies — user confirms or overrides via resume endpoint)
       │
       ▼
POST /validate-boe
  ├─ Load vendor docs from DB (no re-upload — Step 2 data reused)
  ├─ Extract BOE (Claude, focused mode + boe_section_extractor)
  ├─ Normalize BOE (SynonymMapper)
  ├─ Store BOE APIDocument in DB
  ├─ Assign declaration_number → shipment.boe_number (overwrite mode)
  ├─ Merge: vendor_docs + bill_of_entry → unified context.documents
  ├─ Create ValidationSession (use_case=boe_validation)
  ├─ Run 22 checks sequentially:
  │    1.  Shipper/consignee identity   (ShipperConsigneeValidator, fuzzy 0.65/0.80)
  │    2.  Required BOE fields          (RequiredFieldsValidator)
  │    3.  HS code 3-way match          (NWayMatcher, exact)
  │    4.  Weight matching              (ToleranceValidator, ±1%, 5 comparisons)
  │    5.  Quantity matching            (ToleranceValidator, ±0.5%)
  │    6.  Duty amount calculation      (CalculationValidator: cv × duty_rate)
  │    7.  CIF customs value            (CalculationValidator: fob_ncy+freight+insurance)
  │    8.  Duty rate range              (RangeValidator: 0–1.0)
  │    9.  HS code format               (RegexValidator: 6-10 digit)
  │    10. Customs code rules           (CustomsCodeValidator: 40E68/40V02/40U01/40W01)
  │    11. Mode of shipment             (ModeOfShipmentValidator: KIA/TMA/border)
  │    12. Incoterm freight/insurance   (IncotermValidator)
  │    13. Declarant presence           (RequiredFieldsValidator)
  │    14. FOB value crosscheck         (ToleranceValidator: BOE vs invoice ±0.5%)
  │    15. Invoice number crosscheck    (NWayMatcher, exact)
  │    16. Incoterm consistency         (NWayMatcher, incoterm 3-letter code)
  │    17. Currency consistency         (NWayMatcher, exact)
  │    18. Country of origin            (RequiredFieldsValidator)
  │    19. Container count              (NWayMatcher, exact)
  │    20. ETLS approval number         (CustomsCodeValidator, etls_only=True)
  │    21. Master concession eligibility(ConcessionEligibilityValidator)
  │    22. VAT/NHIL/GET Fund amounts    (CalculationValidator: 3 formulas)
  │    23. VAT deferment eligibility    (VatDefermentValidator: URV 0014)
  │    24. Insurance rate               (IncotermValidator: 0.875%/1.0% of C&F)
  ├─ Aggregate token usage, persist to shipment_token_usage
  ├─ Fire email alert (async, non-blocking)
  └─ Return: session_id, final_status, discrepancies, validation_results, extracted_documents

       │
    (HITL review — user confirms discrepancies, corrections sent to clearing agent)
       │
       ▼
Shipment marked validated / corrections requested to customs agent
```

---

*Generated from source code — last updated 2026-04-22.*  
*See also: [WORKFLOWS.md](WORKFLOWS.md), [pipeline-map.md](pipeline-map.md)*
