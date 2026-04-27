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
   - [C. Normalization — Two Passes](#c-normalization--two-passes)
   - [D. Database Persistence](#d-database-persistence)
   - [E. BL Number Assignment](#e-bl-number--shipment-number-assignment)
   - [F. Validation Session](#f-validation-session-creation)
   - [G. LangGraph Workflow Execution](#g-langgraph-workflow-execution)
   - [H. The 17 Validation Workflow Steps](#h-the-17-validation-workflow-steps--exact-internal-logic)
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
   - [I. The 24 Validation Workflow Steps](#i-the-24-validation-workflow-steps--exact-internal-logic)
   - [J. Result Aggregation](#j-result-aggregation--response)
4. [Severity Model](#severity-model)
5. [Discrepancy Structure](#k-how-a-discrepancy-is-structured)

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

## C. Normalization — Two Passes

Normalization happens in **two sequential passes** before any validator runs.

### Pass 1 — SynonymMapper (pipeline, pre-session)

Runs immediately after `asyncio.gather()` returns, before session creation:

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

### Pass 2 — LangGraph normalize_node (inside workflow)

Inside the LangGraph workflow, `normalize_node` runs as the second graph node:

1. Calls `NormalizationEngine.normalize_documents()` on the full documents dict (handles global format/unit normalization across all documents)
2. Then applies use-case-specific synonym mappings from the YAML `normalization.synonyms` block via `_apply_use_case_synonyms()`:
   - Builds reverse lookup: `alias.lower() → canonical_name`
   - For each doc, for each field, checks if the key is an alias of a **different** canonical name
   - If so, adds the canonical name as an **additional** key (preserves original — never overwrites)
3. **Fallback:** if global normalization fails, use-case synonyms are still applied to the raw documents so validators can resolve field names

**Result:** `state["normalized_documents"]` — used by all validators instead of raw docs.

---

## D. Database Persistence

Single DB session, all documents committed in one batch.

For each document:

| Field | Value |
|-------|-------|
| `document_id` | New UUID |
| `document_type` | e.g. `"invoice"` |
| `shipment_id` | UUID from URL |
| `fields` | `normalized_fields` (Pass 1 output) |
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
| `documents` | all normalized docs (Pass 1) |
| `primary_document` | `"invoice"` |
| `config` | full YAML config |
| `validation_results` | `[]` (grows as checks run) |
| `discrepancies` | `[]` (grows as failures are found) |

---

## G. LangGraph Workflow Execution

The pipeline calls `ValidationWorkflow.run()` — a LangGraph state graph with 6 nodes.

**Workflow graph:**

```
START → INITIALIZE → NORMALIZE → VALIDATE → ANALYZE_DISCREPANCIES
                                                     │
                              ┌──────────────────────┤
                              │                       │
                    no discrepancies           discrepancies found
                              │                       │
                              ▼                       ▼
                       GENERATE_REPORT    REQUIRE_USER_CONFIRMATION
                                                  (interrupt here)
                                                      │
                                              (resume() called)
                                                      │
                                                      ▼
                                             GENERATE_REPORT → END
```

**Node responsibilities:**

| Node | Action |
|------|--------|
| `initialize_node` | Sets initial state, marks step `"initialize"` |
| `normalize_node` | Runs NormalizationEngine + use-case synonyms (Pass 2). Uses raw docs as fallback if global norm fails |
| `validate_node` | Iterates YAML `workflow.steps`, instantiates each validator, runs `validate()`, converts failures to Discrepancy objects, runs each through `DiscrepancyClassifier.classify()` |
| `analyze_discrepancies_node` | Checks if any discrepancies exist; if yes, sets `requires_user_confirmation=True` |
| `require_user_confirmation_node` | Sets `workflow_status=AWAITING_USER`, `awaiting_user=True` — LangGraph **interrupts before this node** and returns current state to caller |
| `generate_report_node` | Computes `final_status` (see Section I), sets `workflow_status=COMPLETED` |

**Cross-doc vs single-doc routing inside validate_node:**

```python
is_cross_doc = (
    any(key in validator_config for key in ("calculations", "documents", "parties"))
    or any("." in str(val.get("source","")) or "." in str(val.get("target",""))
           for val in validator_config.get("validations", []))
)

if is_cross_doc:
    source_data = documents_to_validate        # full docs dict
else:
    source_data = documents_to_validate[primary_document]  # primary doc flat fields
```

**Discrepancy classification** (post-validation, inside validate_node):

Each failed `ValidationResult` is converted to a `Discrepancy` and then classified by `DiscrepancyClassifier.classify()`:
1. `_classify_type()` — sets `discrepancy_type`: `value_mismatch`, `missing_field`, `calculation_error`, `format_difference`, `type_mismatch`
2. `_classify_severity()` — **always sets `severity = Severity.ERROR`** (flat model, see [Severity Model](#severity-model))
3. `_classify_category()` — sets `category`: `hs_code`, `weight`, `duty`, `currency`, `quantity`, `date`, `calculation`, `other`
4. `_determine_likely_cause()` — sets `likely_cause`: `OCR error`, `rounding difference`, `missing data`, etc.

**Checkpointing:**

LangGraph uses `AsyncPostgresSaver` (when `DATABASE_URL` is set) or `MemorySaver` (local dev) to persist the workflow state at each node. HITL resume works by `aupdate_state()` (injecting user confirmations) then re-invoking `ainvoke(None, ...)` from the checkpoint.

---

## H. The 17 Validation Workflow Steps — Exact Internal Logic

The YAML defines 17 sequential steps. All use `on_failure: "flag_and_continue"` — no check aborts the pipeline. The step names below are the exact YAML `name:` values.

> **Severity note:** all validators use `Severity.CRITICAL`, `Severity.MAJOR`, `Severity.MINOR`, `Severity.INFO` in code. `CRITICAL/MAJOR/MINOR` are all aliased to `"error"` in `constants.py`. The `DiscrepancyClassifier` further overwrites severity to `Severity.ERROR` for every failed result. In JSON output, failed results have `severity="error"`, passed/skipped results have `severity="info"`.

---

### Step 1 — invoice_completeness

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

### Step 2 — packing_list_completeness

**Validator:** `RequiredFieldsValidator`  
**Same logic as Step 1**, doc = `packing_list`

**Fields checked:** `consignee_name`, `consignee_address`, `incoterm`, `net_weight`,
`gross_weight`, `quantity`, `product_description`, `order_number`, `contract_number`,
`po_number`, `container_count`, `container_numbers`

> Note: No `invoice_number` — PL links to invoice via order/contract/PO references only.

---

### Step 3 — bol_completeness

**Validator:** `RequiredFieldsValidator`  
**`optional_documents = ["bill_of_lading"]`**

- If `context.documents.get("bill_of_lading")` is `None` → `logger.debug(...)`, `continue` — **zero results emitted, silent skip**
- If present: checks `bl_number`, `shipper_name`, `shipper_address`, `consignee_name`,
  `container_count`, `container_numbers`, `net_weight`, `gross_weight`, `quantity`,
  `order_number`, `contract_number`, `po_number`

> Shipper fields are expected to contain a "REDACTED" marker — presence is required, the value is not validated further.

---

### Step 4 — shipper_identity

**Validator:** `ShipperConsigneeValidator`  
**Documents:** `invoice`, `packing_list`, `bill_of_lading`  
**Threshold:** `0.65`

Cross-validates `shipper_name` **and** `shipper_address` across all three documents.

**Name check — `_validate_party_match()`:**

1. Reads `shipper_name` from each document via `_get_field_from_documents()`
2. If value is `{"redacted": True}` → **silently skipped** — shipper blocks are physically redacted on PL and BOL for Nestlé suppliers; if only the invoice carries a real value, fewer than 2 docs are available and the check emits INFO "insufficient data, skipping"
3. Calls `_normalize_name()`:
   - Takes line 1 only (strips address lines below)
   - Strips Unicode accents (`"Nestlé"` → `"Nestle"`)
   - Removes postal tokens (`"private mail bag"`, `"p.o. box"`, etc.)
   - Removes punctuation, lowercases, removes company suffixes
4. **Alias extraction:** `re.findall(r'\(([^)]+)\)', original_value)` — extracts parenthesized trading names. Both the primary normalized value and all aliases are tried against the comparison side; the best similarity wins. Example: `"Industrie- en Handelsonderneming Vreugdenhil B.V. (Vreugdenhil Dairy Foods)"` → alias `"vreugdenhil dairy foods"` matches BOE `"VREUGDENHIL DAIRY FOODS"` at 1.0
5. Jaccard similarity on word sets; `match = similarity >= 0.65`

**Address check — `_validate_address_match()`:**

- Reads `shipper_address` via `address_mappings`
- Applies redacted guard: dict with `"redacted": True` → skipped; dict with `"value": None` → skipped
- Normalizes address: strips accents, lowercases, removes postal noise tokens (`"motorway extens"`, `"p.o. box"`, etc.), removes punctuation, collapses whitespace
- `address_threshold = max(0.65 × 0.6, 0.4) = 0.40` — softer than name threshold
- Jaccard similarity; any pair below threshold → `passed=False`

---

### Step 5 — consignee_identity

**Validator:** `ShipperConsigneeValidator`  
**Documents:** `invoice`, `packing_list`, `bill_of_lading`  
**Threshold:** `0.75`

**Name check:**

1. Reads `consignee_name` via `_get_field_from_documents("{doc_type}.consignee_name", context)`  
   — tries `context.normalized_data[doc_type]` first, then `context.documents[doc_type]`
2. Redacted dict → silently skipped
3. Same `_normalize_name()` pipeline as Step 4
4. Alias extraction same as Step 4
5. If fewer than 2 docs have the field → `passed=True`, INFO, skip
6. Jaccard similarity; `match = similarity >= 0.75`

**Address check:**

- Reads `consignee_address` from `invoice`, `packing_list`, `bill_of_lading`
- Same `_validate_address_match()` logic as Step 4
- `address_threshold = max(0.75 × 0.6, 0.4) = 0.45`
- Vendor documents (invoice postal address, PL postal address, BOL address) are compared against each other — they share the same KIA/postal address and pass at high similarity

---

### Step 6a — order_number_consistency

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

### Step 6b — contract_number_consistency

**Same logic as Step 6a**, `field_name="contract_number"`

---

### Step 6c — po_number_consistency

**Same logic as Step 6a**, `field_name="po_number"`

> **Key distinction enforced by synonym mapping:** `"Customer ref."` → `po_number` (buyer's reference); `"Order no."` → `order_number` (seller's reference). These are separate canonical fields and are never cross-compared with each other.

---

### Step 7 — product_description_consistency

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

### Step 8 — incoterm_consistency

**Validator:** `NWayMatcher`  
**Config:** `field_name="incoterm"`, docs=`[invoice, packing_list]`, `match_type="fuzzy"`, `require_all=True`

Both documents are required — if either is missing the field it is a failure.  
Fuzzy comparison. "FCA ROTTERDAM PORT" vs "FCA ROTTERDAM PORT" → score = 1.0 → pass.

---

### Step 9 — incoterm_rules

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
  - If either `> 0` → `passed=False`, "FCA should not have freight/insurance on invoice"
  - If both 0 → `passed=True`, INFO, "FCA: No freight/insurance on invoice (correct)"

---

### Step 10 — net_weight_consistency

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

### Step 11 — gross_weight_consistency

**Same logic as Step 10**, field = `gross_weight`

**Two comparisons:**

| Source | Target | Optional |
|--------|--------|----------|
| `invoice.gross_weight` | `packing_list.gross_weight` | No |
| `invoice.gross_weight` | `bill_of_lading.gross_weight` | Yes (`optional_target: true`) |

---

### Step 12 — quantity_consistency

**Same logic as Step 10**, field = `quantity`, `tolerance = 0.5%`

**Two comparisons:**

| Source | Target | Optional |
|--------|--------|----------|
| `invoice.quantity` | `packing_list.quantity` | No |
| `invoice.quantity` | `bill_of_lading.quantity` | Yes (`optional_target: true`) |

---

### Step 13 — container_count_consistency

**Validator:** `NWayMatcher`  
**Config:** `field_name="container_count"`, docs=`[packing_list, bill_of_lading]`, `match_type="exact"`, `require_all=False`

If BOL not uploaded → only 1 value available → `len(field_values) < 2` → `passed=True`, INFO, skipped silently.

---

### Step 14 — container_numbers_consistency

**Validator:** `NWayMatcher`  
**Config:** `field_name="container_numbers"`, `match_type="normalized"`, `require_all=False`

**`_normalize_value(value, "normalized")`:**

- If value contains `,` → splits on `,`, strips each token, uppercases each, **sorts alphabetically**, rejoins with `,`
- `"BEAU4500001,BEAU4500000"` and `"BEAU4500000,BEAU4500001"` → both normalize to `"BEAU4500000,BEAU4500001"` → match

Order differences between PL and BOL are handled. Set comparison, not positional.

---

### Step 15 — country_of_origin (Optional)

**Validator:** `RequiredFieldsValidator`  
**`optional_documents = ["certificate_of_origin"]`**

- If `context.documents.get("certificate_of_origin")` is `None` → doc type is in `optional_documents` → `logger.debug(...)`, `continue` — **zero results emitted, silent skip**
- If present: checks `country_of_origin` and `consignee_name`

---

## I. Result Aggregation & Response

**Status determination (inside `generate_report_node`):**

```python
user_confirmations = state.get("user_confirmations", {})
confirmed_ids = {id for id, conf in user_confirmations.items() if conf.get("confirmed") is True}
unresolved = [d for d in all_discrepancies if str(d.get("id", "")) not in confirmed_ids]

if state.get("all_validations_passed") and not all_discrepancies:
    final_status = "passed"
elif unresolved:
    final_status = "failed"
else:
    # All discrepancies reviewed and confirmed by user
    final_status = "requires_attention"
```

> Status is **not** driven by severity tiers — it is driven by whether any discrepancies
> exist and whether the user has confirmed them. All failures carry equal weight.

**Token usage aggregated:**  
`aggregate_token_usages([*extraction_usages, validation_tracker.get_summary()])` — sums input tokens, output tokens, cost, and call count across all LLM calls.

Persisted to `shipment_token_usage` table with `validation_type="vendor_validation"`.  
Also written to `invoice.APIDocument.doc_metadata["shipment_token_usage"]`.

**Email alert:** `asyncio.create_task(_send_validation_alert(...))` — fire-and-forget, never blocks the HTTP response.

**HITL interrupt:** when discrepancies are found, LangGraph interrupts BEFORE `REQUIRE_USER_CONFIRMATION` node. The pipeline detects `workflow_status == AWAITING_USER` and returns the partial state to the caller for human review.

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
    "documents_processed": ["invoice", "packing_list", ...],
    "messages": [...]
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

`d.fields` is the `normalized_fields` stored during Step 2 — already synonym-mapped (Pass 1).

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

BOE-specific synonym mappings applied from `boe_validation.yaml`:

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

**Step 3 — Flush conflicts** via `db.flush()` so unique constraints are satisfied before the new assignment.

**Step 4 — Assign to current shipment:**
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

The LangGraph workflow then runs the same 6-node graph (INITIALIZE → NORMALIZE → VALIDATE → ANALYZE → [confirm | report]).  
Pass 2 normalization applies `boe_validation.yaml` synonyms to all documents.

---

## I. The 24 Validation Workflow Steps — Exact Internal Logic

The BOE YAML defines 24 sequential steps. All use `on_failure: "flag_and_continue"`.

> **Severity note:** same flat model as Step 2 — all failures serialize to `severity="error"`.

---

### Step 1 — shipper_consignee_validation

**Validator:** `ShipperConsigneeValidator`  
**Two parties processed sequentially:**

**Shipper party:**
- Documents: `bill_of_entry`, `invoice`, `bill_of_lading`
- Fields: `shipper_name` (name check) + `shipper_address` (address check, `check_address: true`)
- Threshold: `0.65`; address threshold: `0.40`
- If BOL `shipper_name`/`shipper_address` is `{"redacted": True}` → **silently skipped**
- Alias extraction: parenthesized trading names extracted via `re.findall(r'\(([^)]+)\)', original)` — best similarity across all alias combinations used. Example: `"Industrie- en Handelsonderneming Vreugdenhil B.V. (Vreugdenhil Dairy Foods)"` alias `"vreugdenhil dairy foods"` matches BOE `"VREUGDENHIL DAIRY FOODS"` at 1.0
- Normalization: accents → address tokens → punctuation → lowercase → suffixes (see Step 2 Step 4)
- Similarity: **Jaccard word overlap**

**Consignee party:**
- Documents: `bill_of_entry`, `invoice`, `packing_list`, `bill_of_lading`
- Name field: `consignee_name` on all four
- Address field: `consignee_address` on **invoice, packing_list, bill_of_lading only** — BOE excluded from address check because the BOE carries the registered physical office address which legitimately differs from the postal/mailing address on commercial documents
- Name threshold: `0.80`; address threshold: `0.45`
- Alias extraction applies to name comparison on both sides
- If fewer than 2 docs have the name field → `passed=True`, INFO, skip

---

### Step 2 — field_extraction_check

**Validator:** `RequiredFieldsValidator`

| Document | Required fields |
|----------|----------------|
| `bill_of_entry` | `hs_code`, `gross_weight`, `quantity`, `duty_rate` |
| `invoice` | `net_weight`, `quantity` |
| `packing_list` | `net_weight`, `gross_weight` |

Same `_get_field_value()` logic — exact key lookup, envelope unwrap, redacted preservation.

---

### Step 3 — hs_code_3way_matching

**Validator:** `NWayMatcher`  
**Config:** `field_name="hs_code"`, docs=`[bill_of_entry, invoice, packing_list, bill_of_lading]`, `match_type="exact"`, `require_all=False`

Field resolved from header first, then `items[0]` fallback.

- If only BOE has the HS code (other docs don't carry it): `len(field_values) = 1 < 2` → `passed=True`, INFO, skipped
- If 2+ docs have it: `set(values)` must have size == 1 for pass
- BOL included per `checklist.yaml` SSOT — `require_all: false` handles cases where BOL doesn't declare an HS code

---

### Step 4 — weight_matching

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

`_to_numeric()`, `_validate_tolerance()`, and `_calculate_confidence()` work identically to Step 2 Step 9 — see that section for full parsing detail.

> Note: BOE only carries gross weight (Field 35) — BOE net weight vs vendor doc is not compared.

---

### Step 5 — quantity_matching

**Validator:** `ToleranceValidator`  
One comparison: `invoice.quantity` vs `packing_list.quantity`, `tolerance=0.5%`

BOE quantity is in different units (pallets/containers) — not compared against vendor doc bags.

---

### Step 6 — duty_calculation

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

### Step 7 — cif_calculation_check

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

### Step 8 — duty_rate_validation

**Validator:** `RangeValidator`  
**Config:** `field="duty_rate"`, `min=0`, `max=1.0`, `inclusive=True`

Reads `bill_of_entry.duty_rate` from primary doc dict. Converts to `Decimal`. Checks `0 ≤ value ≤ 1.0`.

---

### Step 9 — hs_code_format

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

### Step 10 — customs_code_validation

**Validator:** `CustomsCodeValidator`

**Initialisation — config loaded from SSOT:**
- `_load_cpc_codes_yaml()` reads `config/data/cpc_codes.yaml` at init — **no hardcoded defaults**, raises `RuntimeError` if file unavailable
- Derives per-code config: `duty_rate`, `vat_rate` (0.15 for VAT-deferred codes, 0.05 for all others), `duty_exempted`, `vat_exempted`, `require_etls_approval`, `check_against`
- Step-level YAML overrides (e.g. `vat_rate: 0.15` for `40V02`) merged on top
- All numeric rates cast to `Decimal`
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

After completing the branch, the validator emits an explicit `passed=True, INFO` result for `etls_approval_number` field with message `"N/A — ETLS/concession reference not required for CPC 40E68"`. This prevents the UI from showing the field as "Missing" for codes that don't require ETLS approval.

---

#### Branch: `customs_code == "40V02"` — VAT Deferment

`_validate_40V02(customs_value, actual_vat_amount, actual_amount_exempted, actual_duty_amount, code_config)`:

**Sub-check A — VAT Amount Payable must be 0:**
```
actual_vat = _to_decimal(actual_vat_amount)    # Tax 02 Amount Payable column
expected   = Decimal("0.00")
passed     = abs(actual_vat - 0) ≤ 0.01
```
- If `actual_vat_amount is None` → `passed=False`, ERROR "vat_amount not extracted — cannot verify VAT deferment"
- Pass: INFO "Import VAT Amount Payable is 0.00 — VAT deferment correctly applied"
- Fail: ERROR "Import VAT must be 0.00 for VAT deferment — got {actual_vat}"

**Sub-check B — Amount Exempted holds the deferred VAT:**
```
vat_base          = customs_value + duty_amount
expected_exempted = (vat_base × 0.15).quantize("0.01", ROUND_HALF_UP)
```
- If `actual_amount_exempted` is `None` → `passed=True`, INFO, reports expected value for reference
- If present: `difference = abs(expected_exempted - actual_exempted)`; `passed = difference ≤ 0.01`
- Pass: INFO; Fail: MAJOR

Also emits N/A result for `etls_approval_number` (same as 40E68 — VAT deferment does not require ETLS).

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
- If `require_etls_approval=True` (not set in step 10 config — only in step 20) → calls `_validate_etls_approval()`

---

#### Branch: `customs_code == "40W01"` — ECOWAS Zero Duty, Taxes Payable

`_validate_40W01(actual_duty_amount, actual_vat_amount, code_config)`:

1. Duty = 0 check (same as 40U01)
2. VAT > 0 check — VAT must still be payable
   - `vat_payable = actual_vat_amount > 0`
   - Fail: MINOR "Warning — VAT should be payable for this customs code"
3. If `require_etls_approval=True` → calls `_validate_etls_approval()`

---

#### Branch: `customs_code == "40C01"` — 2% Import Duty

`_validate_40C01(customs_value, actual_duty_amount, code_config)`:

```
duty_rate        = code_config["duty_rate"]   # Decimal("0.02") from cpc_codes.yaml
expected_duty    = (customs_value × 0.02).quantize("0.01", ROUND_HALF_UP)
difference       = abs(expected_duty - actual_duty)
passed           = difference ≤ 0.01
```

- Pass: INFO "40C01: Duty Amount correct"
- Fail: CRITICAL "40C01: Duty Amount incorrect. Expected: {expected}, Actual: {actual}"

No ETLS check — `40C01` does not require ETLS approval (`require_etls_approval=False` in `cpc_codes.yaml`).

---

#### Branch: `customs_code == "40D01"` — N/A

`_validate_40D01()`:

Emits a single `passed=True`, INFO result: `"40D01: N/A — no specific duty validation required for this CPC code"`. This prevents the UI from showing the field as "Missing" or "Error" for this code.

---

### Step 11 — mode_of_shipment_validation

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

### Step 12 — incoterm_validation

**Validator:** `IncotermValidator`  
**Fields:** `invoice.incoterm`, `invoice.freight_value`, `invoice.insurance_value`, `invoice.total_fob_value`, `bill_of_entry.customs_value`

Same branching logic as Step 2 Step 8. `is_boe_source = False` since freight/insurance fields point to invoice. FCA → no freight/insurance on invoice verified.

---

### Step 13 — declarant_check

**Validator:** `RequiredFieldsValidator`  
**`required_fields = {"bill_of_entry": ["declarant_name", "declarant_address", "declarant_reg_number"]}`**

Checks clearing agent name, address, and CH license number are all present and non-empty on the BOE. All three fields are required per `checklist.yaml` SSOT.

---

### Step 14 — fob_value_crosscheck

**Validator:** `ToleranceValidator`  
**Comparison:** `bill_of_entry.total_fob_value` vs `invoice.total_fob_value`, `tolerance=0.5%`

BOE carries FOB in foreign currency (Field 15/33). Invoice is also in foreign currency. Comparison is valid only when both are in the same currency.

What it catches: clearing agent declared a different FOB than the commercial invoice — potential undervaluation or data entry error.

---

### Step 15 — invoice_number_crosscheck

**Validator:** `NWayMatcher`  
**Config:** `field_name="invoice_number"`, docs=`[bill_of_entry, invoice]`, `match_type="exact"`, `require_all=True`

- `require_all=True` → if either doc is missing the field → CRITICAL "missing from required documents"
- If both present: exact string comparison

---

### Step 16 — incoterm_cross_doc

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

### Step 17 — currency_consistency

**Validator:** `NWayMatcher`  
**Config:** `field_name="currency"`, `match_type="exact"`, `require_all=False`

Direct string equality. Both should be `"EUR"` (or whatever the invoice currency is).

---

### Step 18 — country_of_origin_check

**Validator:** `RequiredFieldsValidator`  
**`required_fields = {"bill_of_entry": ["origin"]}`**

> Field is `"origin"`, not `"country_of_origin"` — the synonym mapper converts during normalization.

---

### Step 19 — origin_cross_check

**Validator:** `NWayMatcher`  
**Config:** `field_name="country_of_origin"`, docs=`[bill_of_entry, bill_of_lading]`, `match_type="fuzzy"`, `fuzzy_threshold=0.8`, `require_all=False`

Cross-validates `country_of_origin` between BOE (Field 16) and BOL. Per `checklist.yaml`: "Ensure section 17 on BOE matches port of loading on BL."

- Both documents normalize `country_of_origin` via synonym mappings in `boe_validation.yaml`
- `require_all: false` — silently skipped if BOL not uploaded
- Fuzzy match handles minor format differences (e.g. `"Netherlands"` vs `"THE NETHERLANDS"`)

---

### Step 20 — container_count_consistency

**Validator:** `NWayMatcher`  
**Config:** `field_name="container_count"`, docs=`[bill_of_entry, bill_of_lading]`, `require_all=False`

If BOL was not uploaded in Step 2 → only 1 value → skip.

---

### Step 21 — etls_approval_check

**Validator:** `CustomsCodeValidator` (`etls_only=True`)

**`etls_only=True` changes the execution path:**

```python
if self.etls_only:
    if code_config.get("require_etls_approval"):
        results.append(self._validate_etls_approval(customs_code, etls_approval_number))
    continue  # skips all amount calculations
```

Only applies to `40U01` and `40W01` — `require_etls_approval=True` on both.  
Skips all amount checks to avoid duplicating discrepancies already raised in Step 10.

**`_validate_etls_approval(customs_code, etls_approval_number)`:**
```
has_approval = bool(etls_approval_number and str(etls_approval_number).strip())
```
- Pass: INFO "{code}: ETLS Approval Number present ({number})"
- Fail: MAJOR "{code}: Import duty is zero/exempted but no ETLS Approval Number found on BOE"

---

### Step 22 — master_concession_eligibility_check

**Validator:** `ConcessionEligibilityValidator`  
**Applies to:** `40U01`, `40W01`  
**Reference data:** `config/data/master_concession.yaml`

1. If `customs_code` not in `["40U01", "40W01"]` → validator returns empty list (skipped entirely)
2. **Concession reference check:**
   - Reads `bill_of_entry.etls_approval_number`
   - Compares against `metadata.application_reference` from YAML (e.g. `"MD202601CUSTCU030000003304"`)
   - If missing: ERROR "Master Concession reference number missing on BOE"
   - If mismatch: ERROR "Concession reference mismatch"
   - If match: INFO "Concession reference number matches"
3. **Expiry date check:**
   - Reads `bill_of_entry.declaration_date`, parses to date
   - Compares against `metadata.expiry_date` from YAML (e.g. `2026-12-31`)
   - If `decl_date > expiry_date`: ERROR "Master Concession expired"
4. **Item eligibility (per BOE line item):**
   - Reads `context.documents["bill_of_entry"]["items"]`
   - For each item: reads `item.get("hs_code")`
   - Normalizes: `re.sub(r"[.\s]", "", str(hs_code))` — removes dots and whitespace
   - Checks against approved HS code index built from YAML items
   - **HS code is the sole eligibility criterion** — description is only included in the error message, no fuzzy matching
   - Pass: not emitted (eligible items produce no result)
   - Fail: ERROR "HS code '{raw_hs}' ({desc}) is not in the Master Concession approved list"

---

### Step 23 — vat_deferment_eligibility_check

**Validator:** `VATDefermentValidator`  
**Applies to:** `40V02` only  
**Reference data:** `config/data/vat_deferment_list.yaml` (URV 0014)

1. If `customs_code != "40V02"` → returns empty list (skipped entirely)
2. Loads approved HS codes via `_build_hs_index(items)`: `{re.sub(r"[.\s]", "", code): description}`
3. For each item in `context.documents["bill_of_entry"]["items"]`:
   - Reads `item.get("hs_code")`
   - Normalizes: `re.sub(r"[.\s]", "", str(hs_code))` — removes dots and whitespace
   - Checks against index
   - Pass: INFO "HS code '{code}' is on the VAT deferment list (URV 0014)"
   - Fail: ERROR "HS code '{code}' is NOT on the VAT deferment list (URV 0014)"

> HS normalization uses `re.sub(r"[.\s]", "")` — removes dots and spaces.
> `1901.90.20.00` → `19019020 00` → `1901902000`.

---

### Step 24 — insurance_rate_check

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

**Status determination** — same logic as Step 2 Section I:

```python
if all_validations_passed and not all_discrepancies:
    final_status = "passed"
elif unresolved:          # discrepancies not confirmed by user
    final_status = "failed"
else:                     # all discrepancies confirmed
    final_status = "requires_attention"
```

Token usage: `aggregate_token_usages([boe_extraction_token_usage, boe_validation_tracker.get_summary()])` — covers BOE extraction LLM call + any AI validators.

Persisted to `shipment_token_usage` with `validation_type="boe_validation"`.

Email alert fired asynchronously.

**Response payload** (note: Step 6 uses `extracted_boe`, not `extracted_documents`):

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
    "documents_processed": ["invoice", "packing_list", "bill_of_entry", ...],
    "messages": [...]
  },
  "discrepancies": [...],
  "validation_results": [...],
  "extracted_boe": {
    "document_id": "...",
    "fields": {...},
    "items": [...],
    "blocks": [...]
  },
  "token_usage": {...}
}
```

---

## Severity Model

The codebase uses a **flat binary severity model** — all failures are treated equally.

```python
# constants.py
class Severity:
    ERROR    = "error"
    CRITICAL = "error"   # alias — maps to "error" in JSON
    MAJOR    = "error"   # alias — maps to "error" in JSON
    MINOR    = "error"   # alias — maps to "error" in JSON
    INFO     = "info"
```

The `DiscrepancyClassifier._classify_severity()` always sets `discrepancy.severity = Severity.ERROR` for any failed result, regardless of the original validator's severity assignment.

**In JSON output:** every failure has `"severity": "error"`, every pass/skip has `"severity": "info"`.

**Status is not driven by severity** — it is driven by whether any discrepancies remain unconfirmed by the user. All discrepancies require human review before the shipment can proceed.

---

## K. How a Discrepancy Is Structured

Every failed `ValidationResult` is converted to a `Discrepancy` in `validate_node`, then classified by `DiscrepancyClassifier`:

```python
Discrepancy(
    field_name       = result.field_name,       # e.g. "vat_amount"
    source_document  = result.source_document,  # e.g. "bill_of_entry"
    target_document  = result.target_document,
    source_value     = result.source_value,     # actual value found
    target_value     = result.target_value,     # expected value
    difference       = result.discrepancy,      # dict: formula, diff%, tolerance, field_values
    severity         = "error",                 # always "error" after classification
    confidence       = result.confidence,       # 0.0 – 1.0
    auto_fixed       = result.auto_fixed,       # bool
    metadata         = result.metadata          # customs_code, doc lists, pair details, etc.
)
```

**Post-classification fields added by `DiscrepancyClassifier`:**

| Field | Values | Set by |
|-------|--------|--------|
| `discrepancy_type` | `value_mismatch`, `missing_field`, `calculation_error`, `format_difference`, `type_mismatch` | `_classify_type()` |
| `category` | `hs_code`, `weight`, `duty`, `currency`, `quantity`, `date`, `calculation`, `other` | `_classify_category()` |
| `likely_cause` | `OCR error`, `rounding difference`, `missing data`, `format difference`, `unit difference`, `unknown` | `_determine_likely_cause()` |

---

## L. Full Data Flow Diagram

```
POST /create-shipment
  └─ Shipment row created (status=pending, shipment_number=PENDING-<uuid>)
       │
       ▼
POST /validate-vendor-docs
  ├─ Extract invoice + PL + BOL in parallel (Claude, focused mode)
  ├─ Normalize Pass 1 (SynonymMapper — pre-session)
  ├─ Store APIDocument rows in DB (linked to shipment_id)
  ├─ Update shipment_number = BL number (if BOL uploaded)
  ├─ Create ValidationContext (use_case=vendor_document_validation)
  ├─ Run LangGraph workflow (6 nodes):
  │    INITIALIZE → NORMALIZE (Pass 2: NormalizationEngine + use-case synonyms)
  │      → VALIDATE (17 steps sequentially):
  │           1.  invoice_completeness          (RequiredFieldsValidator, 16 fields)
  │           2.  packing_list_completeness     (RequiredFieldsValidator, 12 fields)
  │           3.  bol_completeness              (RequiredFieldsValidator, optional)
  │           4.  shipper_identity              (ShipperConsigneeValidator, name+address, fuzzy 0.65)
  │           5.  consignee_identity            (ShipperConsigneeValidator, name+address, fuzzy 0.75)
  │           6a. order_number_consistency      (NWayMatcher, exact)
  │           6b. contract_number_consistency   (NWayMatcher, exact)
  │           6c. po_number_consistency         (NWayMatcher, exact)
  │           7.  product_description_consistency (NWayMatcher, fuzzy 0.5)
  │           8.  incoterm_consistency          (NWayMatcher, fuzzy)
  │           9.  incoterm_rules                (IncotermValidator)
  │           10. net_weight_consistency        (ToleranceValidator, ±1%, 2 comparisons)
  │           11. gross_weight_consistency      (ToleranceValidator, ±1%, 2 comparisons)
  │           12. quantity_consistency          (ToleranceValidator, ±0.5%, 2 comparisons)
  │           13. container_count_consistency   (NWayMatcher, exact)
  │           14. container_numbers_consistency (NWayMatcher, normalized/sorted)
  │           15. country_of_origin            (RequiredFieldsValidator, optional)
  │      → ANALYZE_DISCREPANCIES
  │      → [interrupt if discrepancies → REQUIRE_USER_CONFIRMATION (pause)]
  │      → GENERATE_REPORT
  ├─ Each failed result classified by DiscrepancyClassifier (type, category, cause)
  ├─ Aggregate token usage, persist to shipment_token_usage
  ├─ Fire email alert (async, non-blocking)
  └─ Return: session_id, final_status, discrepancies, validation_results, extracted_documents

       │
    (HITL: POST /sessions/{id}/resume — user confirms or overrides discrepancies)
    (Shipment.status → "validated" or "errors" after resume)
       │
       ▼
POST /validate-boe
  ├─ Load vendor docs from DB (no re-upload — Step 2 data reused)
  ├─ Extract BOE (Claude, focused mode + boe_section_extractor)
  ├─ Normalize Pass 1 (SynonymMapper)
  ├─ Store BOE APIDocument in DB
  ├─ Assign declaration_number → shipment.boe_number (overwrite mode, flush before assign)
  ├─ Merge: vendor_docs + bill_of_entry → unified context.documents
  ├─ Create ValidationContext (use_case=boe_validation)
  ├─ Run LangGraph workflow (6 nodes, same graph):
  │    INITIALIZE → NORMALIZE (Pass 2: boe_validation.yaml synonyms)
  │      → VALIDATE (24 steps sequentially):
  │           1.  shipper_consignee_validation      (ShipperConsigneeValidator, name+address, 0.65/0.80)
  │           2.  field_extraction_check            (RequiredFieldsValidator, 3 docs)
  │           3.  hs_code_3way_matching             (NWayMatcher, exact, 4 docs incl. BOL)
  │           4.  weight_matching                   (ToleranceValidator, ±1%, 5 comparisons)
  │           5.  quantity_matching                 (ToleranceValidator, ±0.5%)
  │           6.  duty_calculation                  (CalculationValidator: cv × duty_rate)
  │           7.  cif_calculation_check             (CalculationValidator: fob_ncy+freight+insurance)
  │           8.  duty_rate_validation              (RangeValidator: 0–1.0)
  │           9.  hs_code_format                    (RegexValidator: dotted or 6-10 digit)
  │           10. customs_code_validation           (CustomsCodeValidator: loaded from cpc_codes.yaml)
  │           11. mode_of_shipment_validation       (ModeOfShipmentValidator: KIA/TMA/border)
  │           12. incoterm_validation               (IncotermValidator)
  │           13. declarant_check                   (RequiredFieldsValidator: name+address+reg_number)
  │           14. fob_value_crosscheck              (ToleranceValidator: BOE vs invoice ±0.5%)
  │           15. invoice_number_crosscheck         (NWayMatcher, exact)
  │           16. incoterm_cross_doc                (NWayMatcher, incoterm 3-letter code)
  │           17. currency_consistency              (NWayMatcher, exact)
  │           18. country_of_origin_check          (RequiredFieldsValidator)
  │           19. origin_cross_check               (NWayMatcher: BOE vs BOL country_of_origin, fuzzy 0.8)
  │           20. container_count_consistency       (NWayMatcher, exact)
  │           21. etls_approval_check              (CustomsCodeValidator, etls_only=True)
  │           22. master_concession_eligibility_check (ConcessionEligibilityValidator)
  │           23. vat_deferment_eligibility_check   (VATDefermentValidator: URV 0014)
  │           24. insurance_rate_check              (IncotermValidator: 0.875%/1.0% of C&F)
  │      → ANALYZE_DISCREPANCIES
  │      → [interrupt if discrepancies → REQUIRE_USER_CONFIRMATION (pause)]
  │      → GENERATE_REPORT
  ├─ Each failed result classified by DiscrepancyClassifier
  ├─ Aggregate token usage, persist to shipment_token_usage
  ├─ Fire email alert (async, non-blocking)
  └─ Return: session_id, final_status, discrepancies, validation_results, extracted_boe

       │
    (HITL: POST /sessions/{id}/resume — user confirms discrepancies)
    (Shipment.status → "validated" or "errors" after resume)
       │
       ▼
Shipment marked validated / corrections requested to customs agent
```

---

*Generated from source code — last updated 2026-04-23. Reflects all changes through this session: shipper/consignee address validation, alias name matching, 4-way HS code check, 40C01/40D01 CPC codes, declarant_address, origin_cross_check, cpc_codes.yaml-driven validator.*  
*See also: [WORKFLOWS.md](WORKFLOWS.md), [pipeline-map.md](pipeline-map.md)*
