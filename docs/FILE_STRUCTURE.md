# File Structure

Annotated production directory tree. Development artifacts, test outputs, and personal notes are excluded.

```
nestle/
├── config/                          # All runtime configuration (YAML-driven, no hardcoding)
│   ├── validation/
│   │   ├── normalization.yaml       # Field synonyms (EN/FR), unit conversions, date/decimal formats
│   │   ├── cet_integration.yaml     # Common External Tariff (CET) file integration settings
│   │   ├── use_cases/
│   │   │   ├── vendor_document_validation.yaml  # Step 2 workflow rules
│   │   │   └── boe_validation.yaml              # Step 6 workflow rules
│   │   └── validators/              # Per-validator config overrides
│   │       ├── calculation_validator.yaml
│   │       ├── customs_code_validator.yaml
│   │       └── tolerance_validator.yaml
│   ├── generation/                  # Document generation templates and field mappings
│   ├── population/                  # Form population field mappings
│   ├── storage/                     # Storage backend configuration
│   └── data/                        # Reference data (CET tariff file, country codes)
│
├── docs/                            # Architecture and implementation documentation
│   ├── ARCHITECTURE.md              # System architecture (this codebase)
│   ├── FILE_STRUCTURE.md            # This file
│   ├── WORKFLOWS.md                 # Step 2, Step 6, HITL workflow diagrams
│   ├── VALIDATION_ENGINE_ARCHITECTURE.md
│   ├── VALIDATION_ENGINE_IMPLEMENTATION_STATUS.md
│   ├── REPORTING_IMPLEMENTATION.md
│   └── VERSION_CONTROL_IMPLEMENTATION.md
│
├── examples/                        # Runnable usage examples for each module
│   ├── boe_validation_example.py
│   ├── cet_validation_demo.py
│   ├── customs_code_validation_demo.py
│   ├── langgraph_workflow_example.py
│   ├── normalization_example.py
│   ├── reporting_demo.py
│   └── version_control_demo.py
│
├── migrations/                      # Alembic database migrations
│   └── versions/
│       └── 20260406_0001_add_validation_sessions.py
│
├── modules/                         # Core business logic (extraction, validation, generation)
│   ├── extraction/                  # Document parsing and field extraction
│   │   ├── agents/                  # LangChain agents for extraction orchestration
│   │   ├── ground_truth/            # Ground truth management for extraction QA
│   │   ├── parser/
│   │   │   ├── provider_factory.py  # Plug-and-play provider factory (self-registering)
│   │   │   ├── reducto_provider.py  # Reducto API integration (PDF, TIFF, JPEG)
│   │   │   ├── google_provider.py   # Google Document AI provider
│   │   │   ├── base.py              # IParserProvider interface
│   │   │   ├── schema_generator.py  # Dynamic schema generation per document type
│   │   │   ├── spatial_extractor.py # BBox-aware field extraction for table data
│   │   │   ├── ai_semantic_enhancer.py  # LLM field name normalization fallback
│   │   │   └── boe_section_extractor.py # GRA Ghana BOE form section-specific extractor
│   │   ├── storage/
│   │   │   ├── universal_document_service.py  # Unified document storage interface
│   │   │   └── backends/postgresql_backend.py
│   │   └── validation/              # Extraction quality scoring
│   │
│   ├── validation_engine/           # Core validation system (LangGraph orchestrated)
│   │   ├── core/
│   │   │   ├── base.py              # ValidationContext, ValidationResult, Discrepancy types
│   │   │   ├── engine.py            # ValidationEngine: session creation, validator dispatch
│   │   │   ├── session_manager.py   # LRU cache + PostgreSQL write-through session persistence
│   │   │   ├── config_loader.py     # YAML use case config loader
│   │   │   └── result_aggregator.py # Aggregate results across validators
│   │   ├── discrepancy/
│   │   │   ├── classifiers/discrepancy_classifier.py  # Severity classification (critical/major/minor/info)
│   │   │   └── fixers/auto_fixer.py                   # Auto-fix format, units, synonyms
│   │   ├── normalization/
│   │   │   ├── core/normalization_engine.py            # Orchestrates all normalization steps
│   │   │   └── normalizers/
│   │   │       ├── synonym_mapper.py   # Field name synonym resolution (EN/FR), LLM batch fallback
│   │   │       ├── unit_converter.py   # Weight/currency unit conversion
│   │   │       └── format_normalizer.py # Date, decimal, boolean, whitespace normalization
│   │   ├── orchestration/
│   │   │   ├── state_definitions.py                    # ValidationWorkflowState TypedDict (30+ fields)
│   │   │   ├── workflows/validation_workflow.py        # LangGraph graph definition and runner
│   │   │   └── nodes/validation_nodes.py               # LangGraph node implementations
│   │   ├── reporting/
│   │   │   ├── report_manager.py       # Generates JSON, PDF, CSV reports
│   │   │   ├── report_models.py        # Report data structures
│   │   │   ├── generators/             # Format-specific report generators
│   │   │   └── analytics/analytics_engine.py  # Accuracy, precision, discrepancy metrics
│   │   ├── services/
│   │   │   └── cet_file_service.py     # CET tariff file loader and HS code lookup
│   │   ├── validators/
│   │   │   ├── validator_registry.py   # Self-registering validator registry
│   │   │   ├── rule_based/
│   │   │   │   ├── required_fields_validator.py     # Field presence checks
│   │   │   │   ├── regex_validator.py               # Format validation (HS code: XXXX.XX)
│   │   │   │   ├── range_validator.py               # Numeric range checks (duty_rate 0–1)
│   │   │   │   ├── exact_match_validator.py         # Strict equality matching
│   │   │   │   ├── incoterm_validator.py            # Freight/insurance vs Incoterm rules
│   │   │   │   ├── mode_of_shipment_validator.py    # BOE Section 21 vs transport doc
│   │   │   │   └── customs_code_validator.py        # CPC code-specific rules (40V02, 40E68, etc.)
│   │   │   ├── cross_document/
│   │   │   │   ├── n_way_matcher.py                 # N-way exact/fuzzy field matching
│   │   │   │   ├── shipper_consignee_validator.py   # Fuzzy party name cross-doc matching
│   │   │   │   └── calculation_validator.py         # Duty/VAT formula verification
│   │   │   ├── statistical/
│   │   │   │   └── tolerance_validator.py           # Percentage-tolerance numeric matching
│   │   │   └── ai_based/
│   │   │       └── cet_hs_code_validator.py         # LLM semantic HS code vs CET validation
│   │   ├── utils/
│   │   │   ├── constants.py    # ValidatorType, Severity, DiscrepancyCategory enums
│   │   │   └── exceptions.py   # ValidationException, NormalizationException, etc.
│   │   └── version_control/    # Revalidation and BOE version delta tracking
│   │
│   ├── generation/              # Document generation (BOE, Invoice, Packing List templates)
│   ├── population/              # PDF form field population from extracted data
│   ├── insights/                # Banking/financial insights analysis
│   ├── analytics/               # System-level analytics and metrics
│   └── automation/              # Post-validation automation (notifications, corrections)
│
├── scripts/                     # Deployment and setup scripts
│   ├── start_api.sh             # FastAPI server start/stop/restart
│   ├── start_ui.sh              # Next.js UI start/stop/restart
│   ├── setup_database.sh        # PostgreSQL schema initialization
│   ├── setup_db_simple.sh       # Simplified DB setup
│   ├── create_api_documents_table.sql  # api_documents table DDL
│   └── setup_insights_storage.py      # Insights storage initialization
│
├── shared/                      # Cross-module shared libraries
│   ├── contracts/
│   │   └── boe_section_schemas.py   # BOE structured data types (Pydantic)
│   ├── providers/
│   │   ├── llm_provider.py      # LangChain LLM factory (OpenAI, Anthropic, Gemini, Bedrock)
│   │   └── base_provider.py     # Base provider interface
│   └── utils/
│       ├── logger.py            # Structured logging
│       ├── config.py            # Environment configuration
│       └── llm_config.py        # Per-module LLM config resolution
│
├── src/                         # Application layer (FastAPI + Next.js)
│   ├── api/
│   │   ├── main.py              # FastAPI app factory, CORS, middleware, router mount
│   │   ├── config.py            # API settings (env vars, DB URL, CORS origins)
│   │   ├── services/
│   │   │   └── document_processing_service.py  # Extraction orchestration + BOE section extractor integration
│   │   ├── v1/                  # Legacy API v1 endpoints
│   │   └── v2/
│   │       ├── router.py        # v2 route aggregator
│   │       └── endpoints/
│   │           ├── validation.py    # Validation pipeline endpoints (Step 2, Step 6, HITL resume)
│   │           ├── generation.py    # Document generation endpoints
│   │           ├── population.py    # Form population endpoints
│   │           ├── insights.py      # Banking insights endpoints
│   │           ├── profiles.py      # Document profile management
│   │           ├── analytics.py     # Analytics endpoints
│   │           ├── integration.py   # Pre-loan integration
│   │           └── automation.py    # Automation triggers
│   ├── database/
│   │   ├── connection.py        # Async PostgreSQL session management (AsyncSession)
│   │   ├── schema.py            # SQLAlchemy ORM models (all tables)
│   │   ├── models/
│   │   │   └── api_document.py  # APIDocument model (uploaded file metadata + extracted fields)
│   │   └── repositories/
│   │       └── validation_session_repository.py  # CRUD for validation_sessions table
│   └── ui/                      # Next.js 16 / React 19 frontend
│       ├── app/                 # App Router pages
│       │   ├── validation/      # BOE validation UI (Step 6)
│       │   │   └── vendor-docs/ # Vendor doc pre-validation UI (Step 2)
│       │   ├── shipments/       # Shipment management
│       │   ├── documents/       # Document explorer
│       │   ├── upload/          # Document upload
│       │   ├── generation/      # Document generation
│       │   └── insights/        # Banking insights
│       ├── components/          # Shared React components
│       │   ├── vendor-validation-form.tsx  # Step 2 upload + result form
│       │   ├── upload-form.tsx
│       │   └── sidebar.tsx
│       └── lib/
│           ├── api-client.ts    # Typed API client (fetch wrappers)
│           └── api.ts           # API endpoint constants
│
├── tests/                       # Test suite
│   ├── conftest.py              # Shared fixtures
│   ├── integration/
│   │   └── test_boe_validation_workflow.py
│   ├── unit/validators/         # Per-validator unit tests
│   ├── performance/             # Performance benchmarks
│   └── version_control/        # Version control module tests
│
├── CLAUDE.md                    # Developer guidelines and project conventions
├── alembic.ini                  # Alembic migration configuration
└── requirements.txt             # Python dependencies
```
