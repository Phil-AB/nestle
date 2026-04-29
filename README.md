# Universal IMPEX Extraction & Validation System

A company-agnostic, config-driven platform for automated extraction and validation of import/export customs documents. Built to process any document type (PDF, image, XLSX) for any company or customs regime — entirely through configuration, with zero hardcoded business logic.

---

## Table of Contents

1. [What This System Does](#1-what-this-system-does)
2. [Architecture Overview](#2-architecture-overview)
3. [Tech Stack](#3-tech-stack)
4. [Project Structure](#4-project-structure)
5. [Core Modules](#5-core-modules)
6. [Configuration (Single Source of Truth)](#6-configuration-single-source-of-truth)
7. [Database Schema](#7-database-schema)
8. [API Reference](#8-api-reference)
9. [UI Application](#9-ui-application)
10. [Setup & Installation](#10-setup--installation)
11. [Running the System](#11-running-the-system)
12. [Environment Variables](#12-environment-variables)
13. [Testing](#13-testing)
14. [Adding New Validators](#14-adding-new-validators)
15. [Adding New Use Cases](#15-adding-new-use-cases)
16. [System Design Principles](#16-system-design-principles)

---

## 1. What This System Does

This platform automates the end-to-end processing of trade documents submitted with customs declarations. Given a shipment's supporting documents, the system:

1. **Extracts** structured data from unstructured documents (PDFs, scanned images, Excel files) using a combination of OCR (Reducto API) and LLM-powered field extraction (Claude via AWS Bedrock).
2. **Normalizes** extracted fields across synonym variations, date formats, currency symbols, and unit conventions.
3. **Validates** documents against each other and against customs rules — detecting mismatches, missing fields, calculation errors, and out-of-tolerance values.
4. **Classifies discrepancies** by severity (critical / major / minor / info) and attempts automated fixes for correctable issues.
5. **Presents discrepancies** to a human reviewer (HITL) for confirmation or correction, recording every decision immutably.
6. **Versions** every validation run, enabling diff analysis between V1, V2, and V3 runs as documents are corrected and re-submitted.
7. **Generates reports** in JSON, PDF, and CSV formats with per-field confidence scores.
8. **Tracks LLM token usage and cost** per validation run for operational visibility.

**Supported document types:** Commercial Invoice, Bill of Entry (BOE), Packing List, Certificate of Origin (COO), Freight Document, Bill of Lading.

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Next.js Frontend                          │
│  Upload → View Extractions → HITL Review → Reports & History    │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP (REST)
┌───────────────────────────▼─────────────────────────────────────┐
│                    FastAPI Backend (v1 / v2)                      │
│  Auth → Rate Limiting → Pydantic validation → Route handlers     │
└──────┬────────────────────┬────────────────────────┬────────────┘
       │                    │                        │
┌──────▼──────┐  ┌──────────▼──────────┐  ┌────────▼────────────┐
│  Extraction │  │  Validation Engine  │  │   Reporting /        │
│  Module     │  │  (LangGraph)        │  │   Version Control    │
│             │  │                     │  │                      │
│ Reducto API │  │ normalize → validate│  │ JSON / PDF / CSV     │
│ LLM agents  │  │ → classify → HITL  │  │ Delta analysis       │
└──────┬──────┘  └──────────┬──────────┘  └────────┬────────────┘
       │                    │                        │
┌──────▼────────────────────▼────────────────────────▼───────────┐
│                      PostgreSQL (asyncpg)                        │
│  Shipments, Documents, Validation Sessions, Audit Log, BOE      │
│  History, Token Usage — all with async SQLAlchemy ORM           │
└─────────────────────────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────┐
│  YAML Config (Single Source of Truth) │
│  checklist.yaml · document_config   │
│  llm.yaml · use_cases/*.yaml        │
└─────────────────────────────────────┘
```

### Data Flow

```
User Upload (PDF / image / XLSX)
        │
        ▼
Reducto API  ──→  structured JSON
        │
        ▼
UniversalDocumentService  ──→  maps fields to ORM models
        │
        ▼
PostgreSQL  ──→  invoice, BOE, packing list, etc.
        │
        ▼
Validation Engine (LangGraph workflow)
  ├─ initialize_node      sets session context & version
  ├─ normalize_node       synonym mapping, format conversion
  ├─ validate_node        all declared validators (parallel)
  ├─ classify_node        severity scoring, auto-fix attempts
  ├─ hitl_node            interrupt, surface to user
  └─ finalize_node        write results, generate report
        │
        ▼
Immutable Audit Trail  +  Version History  +  Token Usage Log
```

---

## 3. Tech Stack

| Layer | Technology |
|---|---|
| **API** | Python 3.11+, FastAPI, Uvicorn, Pydantic v2 |
| **Workflow** | LangGraph (async, PostgreSQL checkpointing) |
| **Database** | PostgreSQL 15+, SQLAlchemy 2 (async), asyncpg, Alembic |
| **Document OCR** | Reducto API (PDF, image, XLSX) |
| **LLM** | Anthropic Claude (AWS Bedrock), Google Gemini, OpenAI GPT-4o |
| **Frontend** | Next.js 16, React 19, TypeScript 5, Tailwind CSS 4 |
| **UI Components** | Radix UI primitives, Lucide icons, Recharts, pdfjs-dist |
| **State / Data** | TanStack Query v5, React Hook Form, Zod |
| **Task Queue** | Celery + Redis (background tasks) |
| **Auth** | API key validation, JWT (python-jose), optional |
| **Email** | SendGrid or SMTP |
| **Runtime** | conda env `ocr`, Node 18+ |

---

## 4. Project Structure

```
.
├── alembic.ini                        # Alembic migration config
├── requirements.txt                   # Python dependencies
├── start_api.sh                       # API process manager (start/stop/restart/logs)
├── start_ui.sh                        # UI dev server starter
├── src/
│   ├── api/
│   │   ├── main.py                    # FastAPI app factory, startup validation
│   │   ├── config.py                  # APISettings (Pydantic, env-driven)
│   │   ├── dependencies/
│   │   │   ├── auth.py                # API key guard
│   │   │   └── rate_limit.py          # Redis rate limiter
│   │   ├── services/
│   │   │   └── document_processing_service.py
│   │   ├── v1/
│   │   │   ├── router.py
│   │   │   └── endpoints/
│   │   │       └── documents.py       # Upload, extract, HITL field update
│   │   └── v2/
│   │       ├── router.py
│   │       └── endpoints/
│   │           ├── validation.py
│   │           ├── validation_pipeline.py
│   │           ├── validation_reporting.py
│   │           ├── validation_versions.py
│   │           ├── validation_models.py
│   │           ├── automation.py
│   │           ├── insights.py
│   │           ├── analytics.py
│   │           ├── integration.py
│   │           ├── population.py
│   │           ├── profiles.py
│   │           └── notifications.py
│   ├── config/                        # YAML — Single Source of Truth
│   │   ├── checklist.yaml             # GRA extraction checklist (17 items)
│   │   ├── document_config.yaml       # Per-document required/optional fields
│   │   ├── llm.yaml                   # LLM provider routing & cost config
│   │   ├── providers.yaml             # Provider-specific settings
│   │   ├── api_config.yaml            # API settings overlay
│   │   ├── llm_pricing.yaml           # Token cost rates per model
│   │   └── validation/
│   │       └── use_cases/             # One YAML per use case
│   │           ├── boe_validation.yaml
│   │           └── vendor_validation.yaml
│   ├── database/
│   │   ├── connection.py              # Async engine, session factory
│   │   └── schema.py                  # SQLAlchemy ORM models (all tables)
│   ├── migrations/
│   │   ├── env.py                     # Alembic environment
│   │   └── versions/                  # Migration scripts (YYYYMMDD_HHMM_*)
│   ├── modules/
│   │   ├── validation_engine/         # LangGraph-based validation orchestrator
│   │   │   ├── core/                  # Engine, session manager, config loader
│   │   │   ├── discrepancy/           # Classifier, auto-fixer
│   │   │   ├── normalization/         # Format, synonym, unit normalizers
│   │   │   ├── orchestration/         # LangGraph state, nodes, workflow
│   │   │   ├── validators/            # IValidator, registry, all validators
│   │   │   ├── reporting/             # Report models & generator
│   │   │   └── version_control/       # Version manager, delta analyzer
│   │   ├── extraction/
│   │   │   ├── parser/                # Reducto provider, BOE section extractor
│   │   │   ├── agents/                # LLM extraction agents
│   │   │   └── storage/               # UniversalDocumentService (ORM mapping)
│   │   ├── automation/                # Automated approval workflows
│   │   └── notification/              # Email service (SendGrid / SMTP)
│   ├── shared/
│   │   ├── contracts/                 # Pydantic schemas (documents, BOE, Reducto)
│   │   ├── providers/                 # LLM provider abstraction (Anthropic, Gemini, OpenAI)
│   │   ├── database/                  # Universal repository, schema manager
│   │   └── utils/                     # Config loader, document type detector, helpers
│   ├── scripts/                       # Test and utility scripts
│   ├── sample-documents/              # Ground truth test documents
│   └── ui/                            # Next.js frontend (see §9)
└── uploads/                           # Uploaded documents (gitignored)
```

---

## 5. Core Modules

### 5.1 Extraction Module (`src/modules/extraction/`)

Converts raw uploaded documents into structured field data.

- **Reducto Provider** (`parser/reducto_provider.py`): Sends documents to the Reducto OCR API. Returns structured JSON with page-level blocks, tables, and form fields.
- **BOE Section Extractor** (`parser/boe_section_extractor.py`): Specialized parser for Bill of Entry sections.
- **LLM Agents** (`agents/`): Claude-powered agents that handle complex field extraction when OCR output is ambiguous or fields span multiple pages.
- **UniversalDocumentService** (`storage/universal_document_service.py`): Maps extracted JSON to SQLAlchemy ORM models using field rules from `document_config.yaml`. Handles synonym resolution, type coercion, and upserts.

### 5.2 Validation Engine (`src/modules/validation_engine/`)

A LangGraph-based asynchronous workflow engine. All orchestration is declared in YAML — the engine has no use-case-specific logic.

**Workflow nodes (executed in order):**

| Node | Responsibility |
|---|---|
| `initialize_node` | Create session, resolve use-case config, set version |
| `normalize_node` | Synonym mapping, date/currency/unit normalization |
| `validate_node` | Run all validators declared in use-case YAML (parallel) |
| `classify_node` | Score discrepancy severity, attempt auto-fixes |
| `hitl_node` | Interrupt workflow, surface discrepancies to user |
| `finalize_node` | Write results, generate report, update audit log |

**State:** All data passes between nodes via `ValidationWorkflowState` (TypedDict). Append-only fields use `Annotated[List, add]` — nodes return deltas, never replace full lists.

**Checkpointing:** Uses `AsyncPostgresSaver` in production and `MemorySaver` in dev/test. Every node is safe to re-run from a checkpoint.

**Validator registry:** Validators self-register with `@ValidatorRegistry.register("name")`. The engine looks up validators by name from the use-case YAML. No factory changes are needed to add a validator.

### 5.3 Normalization (`src/modules/validation_engine/normalization/`)

- **FormatNormalizer**: Parses 6 date formats, normalizes currency symbols (USD / $ / US Dollar → USD), converts measurement units.
- **SynonymMapper**: Maps variant field names (e.g., "shipper", "exporter", "seller") to canonical names using `synonym_mappings` declared in the use-case YAML.
- **UnitConverter**: Handles weight (KG, LB, MT, G) and volume unit conversions between documents.

### 5.4 Discrepancy System (`src/modules/validation_engine/discrepancy/`)

- **DiscrepancyClassifier**: Assigns severity (critical / major / minor / info) based on rules in the use-case YAML.
- **AutoFixer**: Corrects common issues (format differences, unit mismatches, synonym variants) without requiring human intervention. Only fields marked `auto_fixable: true` in config are touched.

### 5.5 Version Control (`src/modules/validation_engine/version_control/`)

- **VersionManager**: Records each validation run as an immutable version (V1, V2, V3…).
- **DeltaAnalyzer**: Computes field-level diffs between two versions — what was corrected, what new discrepancies appeared, what was resolved.
- **RevalidationEngine**: Re-runs the workflow when a document is updated, producing a new version while preserving prior versions.

### 5.6 Shared Providers (`src/shared/providers/`)

A unified LLM abstraction supporting Anthropic Claude (direct or via AWS Bedrock), Google Gemini, and OpenAI GPT-4o. Provider routing, model selection, token counting, retry logic, and fallback ordering are all declared in `llm.yaml` — no code changes required to switch providers or models.

---

## 6. Configuration (Single Source of Truth)

All business logic lives in YAML. **Never hardcode company names, codes, rates, thresholds, or field names in Python.**

### `src/config/checklist.yaml`

17-item GRA (Ghana Revenue Authority) extraction checklist. Defines what fields to extract per document type, with extraction hints that guide the LLM agents. Items include: shipper/consignee addresses, HS codes, product descriptions, quantities, values, weights, container details, incoterm, transport mode, and exchange rate.

### `src/config/document_config.yaml`

Per-document-type field catalogue:
- Which fields are **required** vs. **optional** for each document type (Invoice, BOE, Packing List, COO, Freight, Bill of Lading)
- Date format parse priority (6 formats)
- Decimal and integer field lists for automatic type coercion
- Currency normalization mapping
- Field defaults (e.g., `currency: USD`, `weight_unit: KG`)
- Storage behaviour (`update_on_duplicate`, `cascade_delete_items`)

### `src/config/llm.yaml`

Complete LLM configuration:
- **Active provider** (currently `anthropic` via AWS Bedrock)
- Per-provider model variants: `default`, `fast`, `pro`
- Module-to-provider routing (e.g., `population_agent → anthropic/pro`, `automation_agent → anthropic/fast`)
- Rate limits, retry policy (3 retries, exponential backoff 1–10 s), request timeout (120 s)
- Fallback chain: anthropic → google → openai
- Response caching (1 h TTL), request batching (up to 10 requests)

### `src/config/validation/use_cases/*.yaml`

One file per use case. Each file declares:

```yaml
use_case: boe_validation
version: "1.0"
required_documents:
  - invoice
  - bill_of_entry
  - packing_list
validators:
  - name: value_reconciliation
    tolerance_pct: 0.5
    severity: critical
    on_failure: flag_and_continue
  - name: hs_code_validator
    severity: major
synonym_mappings:
  shipper: [exporter, seller, consignor]
  consignee: [importer, buyer, receiver]
```

Adding a new use case requires only a new YAML file in this directory — no Python changes.

---

## 7. Database Schema

All tables use SQLAlchemy 2 `Mapped` types with async PostgreSQL via `asyncpg`.

```
shipments  (central entity)
├── invoices
│   └── invoice_items          (product_description, hs_code, qty, unit_price, total)
├── bill_of_entries
│   └── boe_items              (declaration line items, duty/VAT/CIF values)
├── packing_lists
│   └── packing_list_items     (package count, gross/net weight)
├── certificates_of_origin
│   └── coo_items              (product, hs_code, country_of_origin, qty)
├── freight_documents          (contract_number, base_freight, BAF, total)
├── validation_results
│   └── validation_errors      (field_name, error_type, severity)
├── audit_logs                 (action, entity_type, user_id, details JSONB)
├── shipment_token_usages      (model, input/output tokens, cost_usd per step)
└── shipment_boe_history       (boe_number, version, validated_at, fields JSONB)

validation_sessions            (LangGraph checkpoint registry, FK to shipments)
```

### Key Schema Notes

- **`shipments`**: Central join point. Has `boe_number`, `boe_version`, supplier/consignee names, incoterm, transport_mode, status.
- **`validation_sessions`**: Stores full `ValidationContext` as JSONB for session recovery after interrupts. `workflow_status` ∈ {created, running, awaiting_user, completed, failed}.
- **`shipment_boe_history`**: Immutable append-only history of every BOE validation run. `extracted_fields` is JSONB.
- **`shipment_token_usages`**: Per-step LLM cost tracking. `validation_type` ∈ {vendor_validation, boe_validation}.
- All write operations that can be retried use upsert — never plain insert.

---

## 8. API Reference

The API is versioned. V1 handles raw document management; V2 exposes the validation engine.

**Base URL:** `http://localhost:8000`

### V1 Endpoints (`/api/v1/`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check with DB connectivity |
| `GET` | `/` | API info |
| `POST` | `/api/v1/documents/upload` | Upload document; triggers Reducto extraction |
| `GET` | `/api/v1/documents` | List all documents |
| `GET` | `/api/v1/documents/{id}` | Document details + extracted fields |
| `PATCH` | `/api/v1/documents/{id}/fields` | HITL field correction |
| `GET` | `/api/v1/documents/{id}/metadata` | Document metadata |

### V2 Endpoints (`/api/v2/`)

**Validation:**

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v2/validation/sessions` | Create validation session for a shipment |
| `GET` | `/api/v2/validation/sessions/{id}` | Get session status & current state |
| `POST` | `/api/v2/validation/sessions/{id}/validate` | Run or resume validation workflow |
| `POST` | `/api/v2/validation/sessions/{id}/confirm-discrepancies` | Submit HITL decisions |
| `GET` | `/api/v2/validation/sessions/{id}/report` | Get final validation report |
| `GET` | `/api/v2/validation/sessions/{id}/versions` | List all versions |
| `POST` | `/api/v2/validation/sessions/{id}/compare-versions` | Diff two versions |

**Other V2:**

| Prefix | Description |
|---|---|
| `/api/v2/profiles/` | User and company profiles |
| `/api/v2/integration/` | External system webhooks and integration hooks |
| `/api/v2/automation/` | Automated approval workflow management |
| `/api/v2/insights/` | Banking customer risk assessment |
| `/api/v2/analytics/` | Validation metrics and trend analysis |
| `/api/v2/population/` | PDF form auto-population |
| `/api/v2/notifications/` | Email and webhook notifications |

### Authentication

Authentication is configurable via `API_ENABLE_AUTH`. When enabled, all requests must include an `X-API-Key` header. JWT support is also available via `python-jose`.

### Rate Limiting

Redis-based per-endpoint rate limiting. Configured via `API_RATE_LIMIT_REQUESTS` and `API_RATE_LIMIT_WINDOW_SECONDS`.

---

## 9. UI Application

**Location:** `src/ui/`  
**Framework:** Next.js 16 + React 19 + TypeScript 5  
**Start command:** `./start_ui.sh` (runs `npm run dev` on port 3000)

### Pages

| Route | Description |
|---|---|
| `/` | Home dashboard |
| `/upload` | Document upload with drag-and-drop |
| `/shipments` | Shipment list and management |
| `/shipments/[id]` | Shipment detail: all documents, validation status, history |
| `/documents` | Document explorer |
| `/documents/[id]` | Document detail with inline PDF viewer and field editor |
| `/validation` | Validation dashboard |
| `/validation/vendor-docs` | Vendor document validation (Step 2) |
| `/validation/boe` | Bill of Entry validation (Step 6) |
| `/generation` | Form and document generation |
| `/ground-truth` | Master data management |
| `/insights` | Banking insights dashboard |

### Key UI Features

- **Confidence scores** displayed on every extracted field (0–100%)
- **Inline field editing** (HITL) with original value preserved
- **PDF viewer** embedded on document detail pages (pdfjs-dist)
- **Discrepancy list** with severity badges and auto-fix indicators
- **Version comparison** panel with field-level diff highlighting
- **Token usage** tracking visible per validation session
- **Shipment selector** for BOE validation sessions

### State Management

TanStack Query v5 handles all server state. React Hook Form + Zod manage form state and validation on the client.

---

## 10. Setup & Installation

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Redis (for rate limiting and Celery)
- conda (environment management)
- AWS credentials (for Bedrock / Claude)
- Reducto API key (document OCR)

### Backend Setup

```bash
# 1. Create and activate conda environment
conda create -n ocr python=3.11 -y
conda activate ocr

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Copy and populate environment config
cp .env.example .env
# Edit .env with your credentials (see §12)

# 4. Create database
createdb nestle_impex

# 5. Run all migrations
alembic upgrade head

# 6. Verify config loads cleanly (fail-fast check)
python -c "from src.api.main import app; print('Config OK')"
```

### Frontend Setup

```bash
cd src/ui
npm install
```

---

## 11. Running the System

### Backend API

```bash
# Start (background, logs to logs/api.log)
./start_api.sh start

# Stop
./start_api.sh stop

# Restart
./start_api.sh restart

# Check status
./start_api.sh status

# Tail logs
./start_api.sh logs
```

The API server runs on **port 8000** by default.  
Health check: `GET http://localhost:8000/health`

### Frontend

```bash
./start_ui.sh
# or directly:
cd src/ui && npm run dev
```

The UI runs on **port 3000** by default.

### Running Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "describe_your_change"

# Check current state
alembic current
```

---

## 12. Environment Variables

Create a `.env` file at the project root. All variables are read at startup via `pydantic-settings`.

```dotenv
# ── Database ──────────────────────────────────────────────────
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=yourpassword
DB_NAME=nestle_impex

# ── LLM / AWS Bedrock ─────────────────────────────────────────
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...           # Direct Anthropic (if not using Bedrock)
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_SESSION_TOKEN=...                  # If using temporary credentials
AWS_REGION=us-east-1

# ── Document OCR ──────────────────────────────────────────────
REDUCTO_API_KEY=...
REDUCTO_BASE_URL=https://v1.reducto.ai

# ── Application ───────────────────────────────────────────────
APP_NAME=IMPEX Validation System
APP_VERSION=2.0.0
DEBUG=false
LOG_LEVEL=INFO

# ── File Upload ───────────────────────────────────────────────
MAX_UPLOAD_SIZE_MB=50
ALLOWED_EXTENSIONS=pdf,xlsx,xls,png,jpg,jpeg,tiff

# ── Auth (optional) ───────────────────────────────────────────
API_ENABLE_AUTH=false
API_KEY=your-api-key-here              # Required if AUTH enabled

# ── Redis (rate limiting & Celery) ────────────────────────────
REDIS_URL=redis://localhost:6379/0

# ── Email Notifications ───────────────────────────────────────
SENDGRID_API_KEY=SG....                # Or use SMTP settings below
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=notifications@yourdomain.com
SMTP_PASSWORD=...
```

---

## 13. Testing

### Test Philosophy

- **No mocking of config files.** Integration tests read the real YAML. Config changes break tests immediately.
- **Derive expected outputs first.** Read the source document or config, calculate the expected result manually, then run the test.
- **No live LLM calls in tests.** Use pre-recorded fixture responses (deterministic JSON).
- **Each validator gets its own unit test** with a known document dict. Assert all `ValidationResult` fields: `passed`, `confidence`, `message`, and discrepancy content.

### Running Tests

```bash
# Validator unit tests
python -m pytest src/modules/validation_engine/validators/tests/

# Integration coverage check
python src/scripts/test_validation_coverage.py

# End-to-end insights flow
python src/scripts/test_insights_flow.py

# Manual insights API test
python src/scripts/manual_insights_test.py
```

### Sample Documents

Ground truth test documents live in `src/sample-documents/`. Use these as fixture inputs for integration tests. Expected extraction outputs should be derived from these documents before running any extraction.

---

## 14. Adding New Validators

1. **Create the validator class** in `src/modules/validation_engine/validators/`:

```python
from modules.validation_engine.core.base import IValidator, ValidationResult
from modules.validation_engine.validators.validator_registry import ValidatorRegistry

@ValidatorRegistry.register("my_new_validator")
class MyNewValidator(IValidator):
    async def validate(self, context: ValidationContext) -> ValidationResult:
        # read only from context.normalized_documents and self.config
        ...
        return ValidationResult(passed=True, confidence=0.95, message="OK")
```

2. **Declare it in the use-case YAML** (`src/config/validation/use_cases/your_use_case.yaml`):

```yaml
validators:
  - name: my_new_validator
    severity: major
    on_failure: flag_and_continue
    config:
      some_threshold: 0.05
```

That's all. No factory changes, no router changes, no other Python edits required.

---

## 15. Adding New Use Cases

1. **Create a use-case YAML file** at `src/config/validation/use_cases/my_use_case.yaml` with the required structure (see §6).
2. **Restart the API.** The config loader reads all YAML files in that directory at startup and registers each use case automatically.
3. **Create a validation session** via `POST /api/v2/validation/sessions` with `{ "use_case": "my_use_case", "shipment_id": "..." }`.

No Python changes are required unless a completely new validator type is needed (see §14).

---

## 16. System Design Principles

These are non-negotiable constraints maintained throughout the codebase. Any change that violates them must be rejected.

### No Hardcoding
Company names, HS codes, CPC codes, duty rates, field names, thresholds — none of these appear as literals in Python. They live in YAML config or the database. If a value belongs to a business domain, it does not belong in code.

### Config is the Single Source of Truth
`checklist.yaml`, `document_config.yaml`, `llm.yaml`, and `use_cases/*.yaml` are the authoritative definitions. Validators read from these files at runtime. Adding a code, rate, or rule requires only a config change.

### Fail Fast at System Boundaries
- External inputs (file uploads, API requests) are validated at the API layer using Pydantic models.
- All YAML configs are validated at **startup**, not on first request. A misconfigured validator or missing use case raises `RuntimeError` on boot.
- Invalid state is rejected early with a clear error — never propagated deeper into the pipeline.

### Idempotency
Every LangGraph node is safe to replay from a checkpoint. LLM calls use `temperature=0`. Discrepancies are never mutated — a correction creates a new version. Database writes use upserts.

### Immutable Audit Trail
Validation results, discrepancies, and session records are append-only. `ValidationWorkflowState` uses `Annotated[List, add]` for all append-only fields — nodes return deltas, never replace full lists.

### Separation of Concerns
**Extractors** extract. **Normalizers** normalize. **Validators** validate. **Nodes** compose these in sequence. **Config** declares orchestration. None of these layers cross into another's responsibility.

### Async Throughout
The API and entire pipeline are fully async. No `time.sleep`, no synchronous file I/O, no synchronous database calls in any request path. Background tasks (email) use fire-and-forget wrappers.

### Structured Outputs
Every validator returns a `ValidationResult` (Pydantic). Every discrepancy is a `Discrepancy` with a stable UUID. Every extracted field carries a `confidence` float (0.0–1.0). No bare dicts or strings at module boundaries.

---

## Glossary

| Term | Meaning |
|---|---|
| **BOE** | Bill of Entry — customs declaration document submitted at import |
| **COO** | Certificate of Origin |
| **CPC** | Customs Procedure Code |
| **GRA** | Ghana Revenue Authority — the customs authority for this deployment |
| **HITL** | Human-in-the-Loop — user review and confirmation step in the workflow |
| **HS Code** | Harmonized System commodity classification code |
| **Reducto** | Third-party OCR/document parsing API |
| **Session** | A single validation run for a shipment (persisted LangGraph state) |
| **Use Case** | A named validation workflow configuration (e.g., `boe_validation`) |
| **SSOT** | Single Source of Truth — YAML config files are the authoritative source |
