flowchart TD

    %% PRE-CONDITION
    A([START]) --> B["POST /api/v2/validation/shipments Create Shipment Record"]
    B --> B1{shipment_number provided?}
    B1 -- Yes --> B2{Already exists?}
    B2 -- Yes --> B3[Return existing record]
    B2 -- No --> B4["Create new shipment status = pending"]
    B1 -- No --> B5["Generate PENDING-uuid status = pending"]
    B3 & B4 & B5 --> C([shipment_id UUID])

    %% STEP 2 — API ENTRY
    C --> D["POST /validate-vendor-docs shipment_id"]
    D --> D1["Build file_map invoice + packing_list required BOL / freight / COO optional"]

    %% PARALLEL EXTRACTION
    D1 --> E["asyncio.gather — Parallel Extraction All files extracted simultaneously"]
    E --> E1["_extract_one per doc 1. Read bytes 2. Write to NamedTemporaryFile 3. DocumentProcessingService.process_document()"]
    E1 --> E2["Inside process_document() SchemaGenerator reads checklist.yaml SSOT Extraction mode: focused LLM: Claude Sonnet via AWS Bedrock ClaudeProvider._normalise_response()"]
    E2 --> E3{status complete?}
    E3 -- No --> E4([HTTP 422 — Pipeline aborted])
    E3 -- Yes --> E5["Collect token usage Delete temp file"]

    %% NORMALIZATION PASS 1
    E5 --> F["Normalization Pass 1 — SynonymMapper.map_document_fields() per document"]
    F --> F1["Synonym resolution from use-case YAML Shipping Condition -> incoterm Customer ref. -> po_number Canonical key takes priority over alias"]
    F1 --> F2["extracted_docs doc_type = normalized_fields + items"]

    %% DB PERSISTENCE
    F2 --> G["DB Persistence — Batch Commit APIDocument rows per doc document_id, shipment_id, fields, items, blocks"]

    %% BL NUMBER ASSIGNMENT
    G --> H{bill_of_lading present?}
    H -- No --> I
    H -- Yes --> H1["Extract bl_number Unwrap confidence envelope if needed"]
    H1 --> H2{IntegrityError? BL already claimed?}
    H2 -- No --> H3["shipment.shipment_number = bl_number Commit"]
    H2 -- Yes --> H4["Rollback Set prev shipment to REASSIGNED-id Claim number for current shipment"]
    H3 & H4 --> I

    %% VALIDATION SESSION
    I["session_manager.create_session() use_case: vendor_document_validation primary_doc: invoice"] --> J["ValidationContext created session_id, documents, config validation_results=[] discrepancies=[]"]

    %% LANGGRAPH WORKFLOW
    J --> K["LangGraph Workflow — 6 Nodes INITIALIZE → NORMALIZE Pass 2 → VALIDATE → ANALYZE → REQUIRE_USER_CONFIRMATION interrupt → GENERATE_REPORT"]

    %% 17 CHECKS — STEP 2
    K --> L["STEP 2 — 17 VALIDATION CHECKS All steps: on_failure flag_and_continue"]
    L --> L1["Check 1 — Invoice Completeness RequiredFieldsValidator 16 required fields invoice_number, shipper_name, shipper_address consignee_name, consignee_address incoterm, currency, total_invoice_value net_weight, gross_weight, quantity product_description, order_number contract_number, po_number, invoice_date"]
    L1 --> L2["Check 2 — Packing List Completeness RequiredFieldsValidator 12 fields consignee_name, consignee_address incoterm, net_weight, gross_weight quantity, product_description order_number, contract_number, po_number container_count, container_numbers"]
    L2 --> L3["Check 3 — BOL Completeness RequiredFieldsValidator optional_documents: bill_of_lading Silent skip if BOL not uploaded"]
    L3 --> L3b["Check 4 — Shipper Identity ShipperConsigneeValidator name cross-check: invoice + PL + BOL fuzzy threshold 0.65 address cross-check: same 3 docs address threshold 0.40 Alias extraction: parenthesized trading names e.g. Company B.V. Vreugdenhil Dairy Foods Redacted docs silently skipped"]
    L3b --> L4["Check 5 — Consignee Identity ShipperConsigneeValidator name cross-check: invoice + PL + BOL fuzzy threshold 0.75 address cross-check: invoice + PL + BOL address threshold 0.45 Alias extraction same as shipper check Fewer than 2 docs: INFO skip"]
    L4 --> L5["Check 6a/b/c — Reference Numbers order_number / contract_number / po_number NWayMatcher — exact match require_all: false Skip gracefully if field absent"]
    L5 --> L6["Check 7 — Product Description NWayMatcher — fuzzy rapidFuzz token_set_ratio >= 0.5 Low threshold: abbreviated SAP codes vs full trade names"]
    L6 --> L7["Check 8 — Incoterm Consistency NWayMatcher — fuzzy Invoice + PL require_all: true"]
    L7 --> L8["Check 9 — Incoterm Freight and Insurance Rules IncotermValidator FCA/FOB: freight and insurance must be 0 on invoice CIF: FOB + Freight + Insurance verified +-0.01 tolerance"]
    L8 --> L9["Check 10/11 — Net and Gross Weight ToleranceValidator 1% _to_numeric: parses US/EU/unit formats Invoice vs PL required Invoice vs BOL optional_target: true"]
    L9 --> L10["Check 12 — Quantity Consistency ToleranceValidator 0.5% Invoice vs PL required Invoice vs BOL optional"]
    L10 --> L11["Check 13 — Container Count NWayMatcher exact PL + BOL require_all: false"]
    L11 --> L12["Check 14 — Container Numbers NWayMatcher normalized Split on comma, uppercase, sort: order-insensitive"]
    L12 --> L13["Check 15 — Country of Origin RequiredFieldsValidator optional_documents: certificate_of_origin Silent skip if COO not uploaded"]

    %% RESULT AGGREGATION STEP 2
    L13 --> M["DiscrepancyClassifier — per failed result classify type, category, likely_cause severity always = error flat binary model"]
    M --> M0["generate_report_node final_status determination"]
    M0 --> M2{unresolved discrepancies?}
    M2 -- none --> M3([passed])
    M2 -- unresolved --> M4([failed — awaiting HITL])
    M2 -- all user-confirmed --> M5([requires_attention])
    M3 & M4 & M5 --> MA["aggregate_token_usages Persist to shipment_token_usage"]
    MA --> MB["Email alert fired async non-blocking"]
    MB --> N["Return: session_id, final_status discrepancies, validation_results extracted_documents token_usage"]

    %% HITL
    N --> O{"HITL Review POST /sessions/id/resume User confirms or overrides each discrepancy Shipment.status updated to validated or errors"}
    O --> P

    %% STEP 6 — BOE CROSS-VERIFICATION
    P["POST /validate-boe shipment_id"] --> Q["Load Step 2 Docs from DB No re-upload — vendor docs reused Filter: invoice, packing_list, bill_of_lading"]
    Q --> QG{invoice and packing_list present?}
    QG -- No --> QG1([HTTP 422 — Run Step 2 first])
    QG -- Yes --> R["BOE Extraction DocumentProcessingService focused mode + boe_section_extractor LLM: Claude Sonnet via AWS Bedrock s16 origin s21 entry/exit s25 items/HS s40 tax table"]
    R --> R1{status complete?}
    R1 -- No --> R2([HTTP 422 — Pipeline aborted])
    R1 -- Yes --> S["BOE Normalization Pass 1 SynonymMapper — BOE field synonyms cpc_code -> customs_code declarant_representative -> declarant_name country_of_origin -> origin"]
    S --> T["BOE DB Persistence APIDocument for bill_of_entry Linked to shipment_id"]
    T --> U["Declaration Number Assignment db.flush before assign declaration_number -> shipment.boe_number overwrite mode Release conflicts first"]
    U --> V["Document Assembly Merge: vendor_docs + bill_of_entry Unified context.documents for all validators"]
    V --> W["session_manager.create_session() use_case: boe_validation primary_doc: bill_of_entry LangGraph 6-node workflow NORMALIZE Pass 2: boe_validation.yaml synonyms"]

    %% 24 CHECKS — STEP 6
    W --> X["STEP 6 — 24 VALIDATION CHECKS All steps: on_failure flag_and_continue"]
    X --> X1["Check 1 — Shipper/Consignee Identity ShipperConsigneeValidator SHIPPER: BOE + Invoice + BOL name fuzzy 0.65 + address fuzzy 0.40 Alias extraction: parenthesized trading names Redacted docs silently skipped CONSIGNEE: BOE + Invoice + PL + BOL name fuzzy 0.80 Invoice + PL + BOL address fuzzy 0.45 BOE excluded from consignee address check — registered vs postal address"]
    X1 --> X2["Check 2 — Required BOE Fields RequiredFieldsValidator hs_code, gross_weight, quantity, duty_rate on BOE net_weight, quantity on Invoice net_weight, gross_weight on PL"]
    X2 --> X3["Check 3 — HS Code 4-Way Match NWayMatcher exact BOE + Invoice + PL + BOL require_all: false SSOT: checklist.yaml hs_code extracted from all 4 docs"]
    X3 --> X4["Check 4 — Weight Matching ToleranceValidator 1% 5 comparisons invoice-PL net gross packing-BOE gross BOL-invoice gross net"]
    X4 --> X5["Check 5 — Quantity Matching ToleranceValidator 0.5% invoice vs packing_list"]
    X5 --> X6["Check 6 — Duty Amount Calculation CalculationValidator formula: customs_value x duty_rate AST-safe evaluation Decimal arithmetic"]
    X6 --> X7["Check 7 — CIF Customs Value CalculationValidator formula: fob_ncy + freight_value + insurance_value All from BOE in GHS Tolerance 1%"]
    X7 --> X8["Check 8 — Duty Rate Range RangeValidator 0.0 to 1.0 inclusive"]
    X8 --> X9["Check 9 — HS Code Format RegexValidator XXXX.XX or 6-10 digit numeric"]
    X9 --> X10["Check 10 — Customs Code Rules CustomsCodeValidator Loaded from cpc_codes.yaml SSOT 40E68: duty = 5% x customs_value 40V02: vat_amount = 0, exempted = 15% x CIF+duty 40U01: duty_amount = 0 40W01: duty_amount = 0, VAT payable 40C01: duty = 2% x customs_value 40D01: N/A — INFO result only"]
    X10 --> X11["Check 11 — Mode of Shipment ModeOfShipmentValidator KIA/AIRPORT/40 = air TMA/TEMA/10 = sea BORDER/LAND/30 = road"]
    X11 --> X12["Check 12 — Incoterm Freight and Insurance IncotermValidator Same rules as Check 9 above FCA/FOB: no freight/insurance on invoice"]
    X12 --> X13["Check 13 — Declarant Check RequiredFieldsValidator declarant_name declarant_address declarant_reg_number All 3 required on BOE"]
    X13 --> X14["Check 14 — FOB Value Crosscheck ToleranceValidator 0.5% BOE total_fob_value vs invoice total_fob_value"]
    X14 --> X15["Check 15 — Invoice Number Crosscheck NWayMatcher exact require_all: true"]
    X15 --> X16["Check 16 — Incoterm Cross-Doc NWayMatcher match_type: incoterm 3-letter code only e.g. FCA ROTTERDAM PORT -> FCA"]
    X16 --> X17["Check 17 — Currency Consistency NWayMatcher exact BOE vs Invoice"]
    X17 --> X18["Check 18 — Country of Origin on BOE RequiredFieldsValidator field: origin normalized from country_of_origin"]
    X18 --> X18b["Check 19 — Origin Cross-Check NWayMatcher fuzzy 0.8 BOE vs BOL country_of_origin require_all: false SSOT: BOE section 17 must match BOL port of loading"]
    X18b --> X19["Check 20 — Container Count NWayMatcher exact BOE vs BOL require_all: false"]
    X19 --> X20["Check 21 — ETLS Approval Number CustomsCodeValidator etls_only: true 40U01 and 40W01 only require_etls_approval: true etls_approval_number must be present on BOE"]
    X20 --> X21["Check 22 — Master Concession Eligibility ConcessionEligibilityValidator 40U01 and 40W01 only Reads config/data/master_concession.yaml Checks: concession reference, expiry date each BOE item HS code vs approved list"]
    X21 --> X22["Check 23 — VAT Deferment Eligibility VATDefermentValidator 40V02 only Reads config/data/vat_deferment_list.yaml URV 0014 Each BOE item HS code vs approved list"]
    X22 --> X23["Check 24 — Insurance Rate Verification IncotermValidator check_insurance_rate: true Air KIA: 1.0% of C+F Sea/Road: 0.875% of C+F All values from BOE in GHS Tolerance: 0.5% of expected or 0.01 min"]

    %% RESULT AGGREGATION STEP 6
    X23 --> Y["DiscrepancyClassifier — per failed result classify type, category, likely_cause severity always = error flat binary model"]
    Y --> Y0["generate_report_node final_status determination"]
    Y0 --> Y2{unresolved discrepancies?}
    Y2 -- none --> Y3([passed])
    Y2 -- unresolved --> Y4([failed — awaiting HITL])
    Y2 -- all user-confirmed --> Y5([requires_attention])
    Y3 & Y4 & Y5 --> YA["aggregate_token_usages BOE extraction + validation Persist to shipment_token_usage"]
    YA --> YB["Email alert fired async non-blocking"]
    YB --> Z["Return: session_id, final_status discrepancies, validation_results extracted_boe token_usage"]

    %% FINAL HITL
    Z --> Z1{"HITL Review POST /sessions/id/resume User confirms discrepancies Shipment.status -> validated or errors"}
    Z1 --> Z2([Shipment validated or corrections requested to clearing agent])

    %% SEVERITY MODEL SUBGRAPH
    subgraph SM["Severity Model — Flat Binary"]
        direction LR
        SM1["error All failures regardless of type status = failed if unresolved"]
        SM2["info Passed checks skipped optional docs N/A results"]
        SM3["Status is driven by unresolved discrepancies not by severity tier Every failure requires user confirmation"]
    end

    %% STYLING
    classDef apiNode fill:#1e40af,color:#fff,stroke:#1e3a8a
    classDef processNode fill:#065f46,color:#fff,stroke:#064e3b
    classDef decisionNode fill:#78350f,color:#fff,stroke:#713f12
    classDef checkNode fill:#1e293b,color:#e2e8f0,stroke:#334155
    classDef terminalOk fill:#14532d,color:#fff,stroke:#166534
    classDef terminalFail fill:#7f1d1d,color:#fff,stroke:#991b1b
    classDef terminalWarn fill:#92400e,color:#fff,stroke:#78350f
    classDef hitlNode fill:#4a044e,color:#fff,stroke:#6b21a8

    class D,P apiNode
    class B,D1,E,E1,E2,E5,F,F1,F2,G,H1,H3,H4,I,J,K,Q,R,S,T,U,V,W processNode
    class B1,B2,E3,H,H2,M2,QG,R1,Y2 decisionNode
    class L,L1,L2,L3,L3b,L4,L5,L6,L7,L8,L9,L10,L11,L12,L13 checkNode
    class X,X1,X2,X3,X4,X5,X6,X7,X8,X9,X10,X11,X12,X13,X14,X15,X16,X17,X18,X18b,X19,X20,X21,X22,X23 checkNode
    class M3,Y3,Z2 terminalOk
    class M4,Y4,E4,R2,QG1 terminalFail
    class M5,Y5 terminalWarn
    class O,Z1 hitlNode
