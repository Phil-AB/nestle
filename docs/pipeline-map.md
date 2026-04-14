BOE Validation — Full Pipeline Map
Entry Point

HTTP POST /shipments/{shipment_id}/validate-boe
File: src/api/v2/endpoints/validation.py

Receives: Shipment ID + BOE file upload
Does:
Writes file to tempfile on disk
Retrieves vendor documents (invoice, packing_list) already in DB for this shipment
Calls DocumentProcessingService.process_document() on BOE file
Persists extracted BOE as APIDocument record in DB
Calls SessionManager.create_session() with all documents
Calls ValidationWorkflow.run()
Aggregates token usage
Derives final status
Outputs: {session_id, workflow_status, final_status, summary, discrepancies, validation_results, extracted_boe, token_usage}
Calls: DocumentProcessingService → SessionManager → ValidationWorkflow
Layer 1 — Document Extraction
File: src/api/services/document_processing_service.py

Receives: File path + document type ("bill_of_entry")
Does:
Reads file bytes
Gets schema from SchemaGenerator.generate_schema(doc_type, "open")
Calls parser.extract_fields(file_bytes, schema, doc_type)
For BOE specifically: calls BOESectionExtractor.extract_flat_fields() and .extract_sections() to pull GRA BOE sections 16, 21, 25, 31, 40
Derives party names if missing via _derive_party_names()
Sanitizes Decimal values to floats
Outputs: {fields: {...}, items: [...], blocks: [...], metadata: {...}, token_usage: {...}}
Calls: parser.extract_fields() → BOESectionExtractor
File: modules/extraction/parser/extractors/boe_extractor.py

Receives: File bytes + Pydantic schema + document type
Does: Calls LLM provider (Reducto or Claude) with file + schema to extract all BOE fields as structured output
Outputs: Raw structured extraction with field values and confidence scores
Calls: LLMProvider.extract()
File: modules/extraction/parser/boe_section_extractor.py

Receives: Raw extracted fields
Does: Post-processes GRA BOE form — extracts Section 16 (HS code/customs value), Section 21 (mode of transport), Section 25 (country of origin), Section 31 (quantity/description), Section 40 (customs code). Performs CET duty rate lookup if HS code present.
Outputs: Flat fields dict + sectioned fields dict
Calls: CETFileService for duty rate lookup
File: shared/providers/llm_provider.py

Receives: File bytes + schema + provider config from config/llm.yaml + config/providers.yaml
Does: Routes to correct provider (Reducto/Gemini/Claude) based on config, calls API, returns structured response
Outputs: Structured field extraction result
Calls: GeminiProvider or ClaudeProvider or Reducto HTTP client
Layer 2 — Session Initialization
File: modules/validation_engine/core/session_manager.py

Receives: use_case="boe_validation", documents dict, primary_document, supporting_documents
Does:
Calls ConfigLoader.load_use_case("boe_validation") to get full YAML config
Creates ValidationContext Pydantic model with UUID session_id
Stores in LRU cache (max 100 entries, OrderedDict)
Writes to PostgreSQL (write-through, if DB enabled)
Outputs: ValidationContext object
Calls: ConfigLoader → DB repository
File: modules/validation_engine/core/config_loader.py

Receives: Use case name string
Does: Loads /config/validation/use_cases/boe_validation.yaml, validates structure, caches with @lru_cache(maxsize=32)
Outputs: Full config dict (documents, workflow steps, normalization rules, discrepancy rules, versioning, reporting)
Calls: Nothing — reads YAML from disk
Config File: config/validation/use_cases/boe_validation.yaml

Contains: 21 validation steps, normalization synonyms (French/English), unit conversion rules, severity classification rules, Ghana customs code logic, ETLS rules, VAT/NHIL rates, tolerance values, auto-fix rules, report templates
Layer 3 — LangGraph Workflow
File: modules/validation_engine/orchestration/workflows/validation_workflow.py

Receives: session_id, documents, config
Does: Builds LangGraph state machine with 6 nodes, sets checkpointer (AsyncPostgresSaver or MemorySaver), configures interrupt_before=[REQUIRE_USER_CONFIRMATION], invokes graph
Graph structure:

INITIALIZE → NORMALIZE → VALIDATE → ANALYZE_DISCREPANCIES
    → [conditional routing]
        → NO_DISCREPANCIES → GENERATE_REPORT → END
        → REQUIRES_USER   → REQUIRE_USER_CONFIRMATION ⏸ → GENERATE_REPORT → END
        → VALIDATION_PASSED → GENERATE_REPORT → END
Outputs: Final workflow state dict
Calls: All 6 nodes in modules/validation_engine/orchestration/nodes/validation_nodes.py
Layer 4 — Workflow Nodes (in order)
File: modules/validation_engine/orchestration/nodes/validation_nodes.py

Node	Receives	Does	Outputs	Calls
INITIALIZE	Current state	Marks step as initialized	current_step="initialize"	Nothing
NORMALIZE	state["documents"]	Passes all docs through normalization	state["normalized_documents"]	NormalizationEngine
VALIDATE	Normalized docs + 21 config steps	Iterates each step, calls validators, collects results, converts failures to discrepancies	state["validation_results"], state["discrepancies"]	ValidatorRegistry → each validator
ANALYZE_DISCREPANCIES	state["discrepancies"]	Counts by severity, sets requires_user_confirmation flag	state["requires_user_confirmation"]	DiscrepancyClassifier
REQUIRE_USER_CONFIRMATION	Current state	Sets awaiting_user=True, workflow pauses here	state["workflow_status"]="awaiting_user"	Nothing — LangGraph interrupt
GENERATE_REPORT	Full state + user confirmations (if any)	Recalculates final_status considering confirmed discrepancies, determines passed/failed/requires_attention	state["final_status"], state["workflow_status"]="completed"	ResultAggregator
Layer 5 — Normalization Engine
File: modules/validation_engine/normalization/core/normalization_engine.py

Receives: Raw documents dict, normalization config section from YAML
Does (in order):
SynonymMapper.map_document_fields() — renames all field variants to canonical names ("Poids Net" → "net_weight", "HSN Code" → "hs_code")
UnitConverter.convert_weight() — all weights to KG (LBS, MT, G, TON → KG)
UnitConverter.convert_currency() — all currencies to USD using exchange rate API with fallback rates
FormatNormalizer.normalize_date() — all dates to YYYY-MM-DD
FormatNormalizer.normalize_decimal() — handles European format 189.000,00 → 189000.00
Outputs: Normalized documents dict with canonical field names and standardized values
Calls: SynonymMapper, UnitConverter, FormatNormalizer
Layer 6 — Validator Registry & Dispatch
File: modules/validation_engine/validators/validator_registry.py

Receives: Validator name string + step config
Does: Looks up registered validator class by name, instantiates with step config
Outputs: Instantiated validator object
All validators self-register via: @ValidatorRegistry.register("name") decorator on their class
Layer 7 — The 21 Validation Steps (in order from config)
Each validator receives (source_data, target_data, ValidationContext) and outputs List[ValidationResult].

Step	Config Step Name	Validator File	What it checks	Severity if fail
1	shipper_consignee_validation	validators/cross_document/shipper_consignee_validator.py	Fuzzy match (80% threshold) of shipper/consignee name+address across BOE, Invoice, BL	MAJOR
2	field_extraction_check	validators/rule_based/required_fields_validator.py	Required fields exist on each doc type (BOE: hs_code, gross_weight, quantity, duty_rate; Invoice: net_weight, quantity)	CRITICAL
3	hs_code_3way_matching	validators/cross_document/n_way_matcher.py	HS code exact match across BOE, Invoice, Packing List	CRITICAL
4	weight_matching	validators/cross_document/tolerance_validator.py	Gross weight: Invoice↔Packing List, Packing List↔BOE, BOL↔Invoice (all ±1%)	MAJOR
5	quantity_matching	validators/cross_document/tolerance_validator.py	Quantity: Invoice↔Packing List (±0.5%)	MAJOR
6	duty_calculation	validators/cross_document/calculation_validator.py	duty_amount = customs_value × duty_rate (±0.5%)	CRITICAL
7	duty_rate_validation	validators/rule_based/range_validator.py	duty_rate must be 0.0–1.0	MAJOR
8	hs_code_format	validators/rule_based/regex_validator.py	HS code matches XXXX.XX or 6–10 digit pattern	MAJOR
9	customs_code_validation	validators/rule_based/customs_code_validator.py	Ghana codes 40E68/40V02/40U01/40W01 — validates amounts against code-specific rules	CRITICAL
10	mode_of_shipment_validation	validators/rule_based/mode_of_shipment_validator.py	Transport doc type matches Section 21 mode (air/sea/road/rail)	MAJOR
11	incoterm_validation	validators/rule_based/incoterm_validator.py	Freight/insurance charges consistent with declared Incoterm	MAJOR
12	cet_hs_code_validation	validators/ai_based/cet_hs_code_validator.py	HS code exists in Ghana CET file, description similarity ≥60%, duty rate within ±0.1% of CET rate	CRITICAL
13	declarant_check	validators/rule_based/required_fields_validator.py	Declarant name + registration number present on BOE	MAJOR
14	fob_value_crosscheck	validators/cross_document/tolerance_validator.py	BOE FOB value ↔ Invoice total FOB (±0.5%)	MAJOR
15	incoterm_cross_doc	validators/cross_document/n_way_matcher.py	Incoterm (3-letter code) matches BOE ↔ Invoice	MAJOR
16	currency_consistency	validators/cross_document/n_way_matcher.py	Currency code matches BOE ↔ Invoice	MAJOR
17	country_of_origin_check	validators/rule_based/required_fields_validator.py	Country of origin declared on BOE	MAJOR
18	container_count_consistency	validators/cross_document/n_way_matcher.py	Container count matches BOE ↔ BOL	MAJOR
19	etls_approval_check	validators/rule_based/customs_code_validator.py	If duty=0 (codes 40U01/40W01), ETLS approval number must be present	CRITICAL
20	vat_nhil_rate_check	validators/cross_document/calculation_validator.py	VAT=15%, NHIL=2.5%, GET Fund=2.5% of (customs_value + duty_amount) (±0.5%)	MAJOR
21	insurance_rate_check	validators/cross_document/calculation_validator.py	Insurance = 0.875% of C&F (sea/road) or 1% (air)	MINOR
CET Lookup (used by step 12):

File: modules/validation_engine/services/cet_file_service.py

Receives: HS code string
Does: Loads config/data/CET_Ghana.csv, looks up HS code entry, returns description + official duty rate
Outputs: {hs_code, description, duty_rate} or None
Layer 8 — Discrepancy Classification & Auto-Fix
File: modules/validation_engine/discrepancy/classifiers/discrepancy_classifier.py

Receives: Each failed ValidationResult
Does: Matches field_name + discrepancy_type against severity rules from config → classifies as CRITICAL/MAJOR/MINOR/INFO, sets category (HS_CODE, WEIGHT, DUTY, CURRENCY, etc.), sets likely_cause (OCR_ERROR, ROUNDING, UNIT_DIFFERENCE, etc.)
Outputs: Classified Discrepancy object
File: modules/validation_engine/discrepancy/fixers/auto_fixer.py

Receives: Discrepancy + ValidationContext
Does: Checks if auto_fixable=true in config, attempts fix (date format normalization, unit conversion, whitespace/case normalization), compares if values match after fix
Outputs: Fix metadata {fix_type, original_value, fixed_value} or None
Only applies to: Format/unit/whitespace discrepancies — never silently fixes value mismatches
Layer 9 — Result Aggregation
File: modules/validation_engine/core/result_aggregator.py

Receives: All ValidationResult objects from all 21 steps
Does: Counts total/passed/failed, counts discrepancies by severity, calculates average confidence, determines all_validations_passed, has_critical_discrepancies, requires_user_confirmation, processing time
Outputs: ValidationResultSummary Pydantic model
Layer 10 — Version Management & Reporting
File: modules/validation_engine/version_control/version_manager.py

Receives: ValidationContext + optional notes/tags
Does: Calculates accuracy_score (passed/total × 100), determines final_status, stores VersionMetadata keyed as {session_id}:v{version}, maintains lineage chain V1→V2→V3
Outputs: VersionMetadata object
File: modules/validation_engine/reporting/report_manager.py

Receives: Report request (type + format + session_id)
Does: Routes to generator — VALIDATION_SUMMARY, DISCREPANCY_DETAIL, VERSION_COMPARISON, AUDIT_TRAIL, EXECUTIVE_SUMMARY; formats as JSON/PDF/CSV
Outputs: {metadata: {...}, data: {...}}
Data Model: What flows through everything
File: modules/validation_engine/core/base.py

Three core objects flow through the entire pipeline:


ValidationContext     → the session container (all docs, config, results, state)
ValidationResult      → one check outcome (passed/failed, confidence, source/target values)
Discrepancy           → one failed check with severity, category, fix status, user confirmation
ValidationResultSummary → final rolled-up counts and status
Vendor Validation — Full Pipeline Map
Entry Point

UI Form → POST /validation/shipments → POST /validation/shipments/{id}/validate-vendor-docs
File: src/ui/components/vendor-validation-form.tsx

Receives: User uploads: invoice, packing_list, bill_of_lading, freight_manifest (optional), certificate_of_origin (optional) + shipment details
Step 1: Calls apiClient.createShipment() → gets back shipment_id
Step 2: Calls apiClient.validateVendorDocs(shipment_id, files) with all uploaded files
Receives response: Stores session_id, discrepancies, validation_results, extracted_documents in state
If extracted_documents present: Transitions to step="field_review" (editable field review UI)
If awaiting_user: Transitions to step="review" (discrepancy confirmation UI)
When complete: Transitions to step="complete"
Calls: apiClient in src/ui/lib/api-client.ts
Layer 1 — API Endpoint
File: src/api/v2/endpoints/validation.py — validate_vendor_docs()

Receives: shipment_id + multipart files (invoice, packing_list, bill_of_lading, etc.)
Does:
Creates DocumentProcessingService(use_database=False, use_ai_enhancement=False)
Extracts all uploaded files concurrently via _extract_one() helper (writes to tempfile, calls process_document(), cleans up)
Persists each extracted document to DB as APIDocument record linked to shipment_id
Calls SessionManager.create_session(use_case="vendor_document_validation", documents={...})
Calls ValidationWorkflow.run(session_id)
Aggregates token usage across all documents
Derives final_status from workflow result
Builds summary counts
Outputs: {session_id, shipment_id, workflow_status, final_status, summary, discrepancies, validation_results, extracted_documents}
Calls: DocumentProcessingService (×N files concurrently) → SessionManager → ValidationWorkflow
Layer 2 — Document Extraction (per file)
File: src/api/services/document_processing_service.py

Receives: File path + document type
Does:
Reads file bytes
Gets schema: SchemaGenerator.generate_schema(doc_type, "open")
Calls parser.extract_fields(file_bytes, schema, doc_type) — routes to correct extractor
For BOL: calls _post_process_bol() to fill gaps (bl_number, container_numbers)
For all docs: calls _derive_party_names() to extract shipper/consignee from addresses if names missing
Outputs: {fields: {...}, items: [...], metadata: {...}, token_usage: {...}}
Calls: One of the extractors below based on doc_type
Document Type	Extractor File
invoice	modules/extraction/parser/extractors/invoice_extractor.py
packing_list	modules/extraction/parser/extractors/packing_list_extractor.py
bill_of_lading	modules/extraction/parser/extractors/bol_extractor.py
Each extractor:

Receives: File bytes + Pydantic schema
Does: Calls LLM provider with file + schema, returns structured fields
Calls: shared/providers/llm_provider.py → shared/providers/gemini_provider.py or Claude provider
Base class for all extractors: modules/extraction/parser/extractors/base.py

Defines common interface: extract(file_bytes, schema, doc_type) → structured result
LLM Provider routing:

File: shared/providers/llm_provider.py

Receives: File bytes + schema + config from config/llm.yaml and config/providers.yaml
Does: Selects active provider (Gemini/Claude/Reducto) from config, calls API, returns structured response
Calls: shared/providers/gemini_provider.py or claude_provider.py
Layer 3 — Session + Config (same engine as BOE)
File: modules/validation_engine/core/session_manager.py

Receives: use_case="vendor_document_validation", extracted documents dict
Calls: ConfigLoader.load_use_case("vendor_document_validation")
Outputs: ValidationContext with session_id, cached + persisted to DB
File: modules/validation_engine/core/config_loader.py

Loads: config/validation/use_cases/vendor_document_validation.yaml
Outputs: Full config dict with 14 validation steps, normalization rules, severity rules
Layer 4 — LangGraph Workflow (same engine, different config)
Same modules/validation_engine/orchestration/workflows/validation_workflow.py and modules/validation_engine/orchestration/nodes/validation_nodes.py — the workflow engine is shared. What changes is the YAML config loaded, which drives different steps and validators.

Layer 5 — The 14 Vendor Validation Steps
Step	What it checks	Validator	Severity if fail
1	Required fields present per doc type	validators/rule_based/required_fields_validator.py	CRITICAL
2	Shipper name fuzzy match across all docs (80% threshold)	validators/cross_document/shipper_consignee_validator.py	MAJOR
3	Consignee name fuzzy match across Invoice, Packing List, BOL	validators/cross_document/shipper_consignee_validator.py	MAJOR
4	Product description semantic consistency	validators/cross_document/n_way_matcher.py	MINOR
5	Invoice FOB value is positive and non-zero	validators/rule_based/range_validator.py	CRITICAL
6	Incoterm consistency: Invoice ↔ Packing List	validators/cross_document/n_way_matcher.py	MAJOR
7	Incoterm rules: FCA/FOB → no freight expected; CFR/CIF → freight required	validators/rule_based/incoterm_validator.py	MAJOR
8	Gross weight: Invoice ↔ Packing List (±1%)	validators/cross_document/tolerance_validator.py	MAJOR
9	Gross weight: Invoice ↔ BOL (±1%)	validators/cross_document/tolerance_validator.py	MAJOR
10	Quantity: Invoice ↔ Packing List ↔ BOL (±0.5%)	validators/cross_document/tolerance_validator.py	MAJOR
11	PO / order number / contract number exact match	validators/cross_document/n_way_matcher.py	MAJOR
12	Container count: Packing List ↔ BOL exact match	validators/cross_document/n_way_matcher.py	MAJOR
13	Container numbers match: Packing List ↔ BOL	validators/cross_document/n_way_matcher.py	MAJOR
14	Country of origin present on Certificate of Origin (if provided)	validators/rule_based/required_fields_validator.py	MINOR
Layer 6 — Field Review (UI)
File: src/ui/components/vendor-validation-form.tsx — step="field_review"

Receives: extracted_documents with field values + confidence scores
Shows: Editable row per field, confidence percentage per field
On save: Calls apiClient.updateDocumentFields(document_id, field_edits) → PATCH /documents/{id}/fields
After save: Moves to step="review" with updated values
Calls: src/ui/lib/api-client.ts updateDocumentFields()
Layer 7 — HITL: Discrepancy Review (UI)
File: src/ui/components/vendor-validation-form.tsx — step="review"

Shown when: workflow_status === "awaiting_user"
Receives: List of discrepancies (severity, source value, target value, field, message)
Does: Shows each discrepancy as a card with Accept/Reject buttons
On confirm: Calls apiClient.resumeValidationSession(session_id, confirmations)
Calls: src/ui/lib/api-client.ts resumeValidationSession()
File: src/api/v2/endpoints/validation.py — resume_validation_session()

Receives: {session_id, confirmations: [{discrepancy_id, confirmed: true/false}]}
Does:
Retrieves session from SessionManager
Updates each discrepancy status: confirmed → resolved, rejected → failed
Re-derives final_status:
Any critical rejected → "failed"
All critical/major confirmed or auto-fixed → "passed"
Otherwise → "requires_attention"
Resumes LangGraph workflow via workflow.resume()
Outputs: {session_id, workflow_status: "completed", final_status, summary, discrepancies}
Layer 8 — Completion & DB Persistence
File: src/ui/components/vendor-validation-form.tsx — step="complete"

Shows: Final status banner (green/red/yellow), summary counts, all validation results grouped by validator, all discrepancies, shipment ID
Button: "Proceed to Step 6 — BOE Validation" which triggers the BOE pipeline above
File: src/database/schema.py

Stores:
APIDocument — one record per extracted file (fields, items, blocks as JSONB, token_usage, linked to shipment_id)
ValidationSession — session state and results
Shipment — top-level shipment record linking all documents and sessions
Shared Infrastructure (used by both pipelines)
File	Role
modules/validation_engine/core/base.py	ValidationContext, ValidationResult, Discrepancy, ValidationResultSummary Pydantic models
modules/validation_engine/core/result_aggregator.py	Rolls up all results into summary counts and final status
modules/validation_engine/discrepancy/classifiers/discrepancy_classifier.py	Classifies each failed result → severity, category, likely_cause
modules/validation_engine/discrepancy/fixers/auto_fixer.py	Auto-fixes format/unit discrepancies where safe
modules/validation_engine/validators/validator_registry.py	Registry — maps validator name strings to classes
modules/validation_engine/normalization/core/normalization_engine.py	Normalizes all documents before any validation runs
modules/validation_engine/reporting/report_manager.py	Generates JSON/PDF/CSV reports
modules/validation_engine/version_control/version_manager.py	Tracks V1→V2→V3 revalidation lineage
shared/utils/token_tracker.py	Tracks LLM token usage across all providers
