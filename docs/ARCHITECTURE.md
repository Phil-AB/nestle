# System Architecture

## Overview

This is a **document intelligence and trade compliance validation system** for Nestlé Ghana's import/customs workflow. It automates the validation of vendor documents and Bills of Entry (BOE) against each other and against regulatory requirements (Ghana Revenue Authority / CET tariff schedule).

**Core stack:** FastAPI · LangGraph · Reducto · PostgreSQL · Next.js 16

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLIENT LAYER                               │
│          Next.js 16 / React 19  (src/ui/)                           │
│   Step 2 UI · Step 6 UI · Document Explorer · Shipment Manager      │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP / REST
┌────────────────────────────▼────────────────────────────────────────┐
│                          API LAYER  (FastAPI)                        │
│                         src/api/v2/endpoints/                        │
│  validation.py · generation.py · population.py · insights.py        │
└──────┬──────────────────────┬──────────────────┬────────────────────┘
       │                      │                  │
┌──────▼──────┐   ┌───────────▼──────┐  ┌───────▼────────────────────┐
│  EXTRACTION │   │   VALIDATION     │  │   GENERATION / POPULATION  │
│   LAYER     │   │   ENGINE         │  │   modules/generation/       │
│             │   │   (LangGraph)    │  │   modules/population/       │
│ Reducto API │   │                  │  └────────────────────────────┘
│ Google DocAI│   │ Normalize →      │
│ BOE Extractor│  │ Validate →       │
│             │   │ Discrepancy →    │
└──────┬──────┘   │ HITL → Report    │
       │          └──────────┬───────┘
       │                     │
┌──────▼─────────────────────▼───────────────────────────────────────┐
│                       DATABASE LAYER                                 │
│           PostgreSQL (async SQLAlchemy)  src/database/              │
│   Shipment · Invoice · BOE · PackingList · ValidationSession        │
│   APIDocument · AuditLog · ValidationResult · Discrepancy           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Layer-by-Layer Breakdown

### 1. API Layer — `src/api/v2/`

FastAPI application with async PostgreSQL. All endpoints are versioned under `/api/v2/`.

**Key endpoints (validation pipeline):**

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v2/validation/shipments` | Create shipment (spine for all documents) |
| `POST` | `/api/v2/validation/shipments/{id}/validate-vendor-docs` | Step 2: upload + validate vendor docs |
| `POST` | `/api/v2/validation/shipments/{id}/validate-boe` | Step 6: upload BOE, retrieve stored vendor docs |
| `POST` | `/api/v2/validation/sessions/{id}/resume` | Resume after HITL confirmation |
| `GET`  | `/api/v2/validation/sessions/{id}` | Get session status + results |

**Design:** Services are injected via dependency injection. Document extraction and validation are fully async. Vendor doc fields are stored in `api_documents` (PostgreSQL) keyed by `shipment_id` so Step 6 can retrieve them without re-upload.

---

### 2. Extraction Layer — `modules/extraction/`

Converts raw uploaded files (PDF, JPEG, TIFF) into structured field dictionaries.

**Provider Factory pattern** — providers self-register, active provider configured via env:

```
UploadedFile (bytes)
    │
    ▼
ProviderFactory.get_provider()
    │
    ├── ReductoProvider      → Reducto REST API → {field: {value, bbox, confidence}}
    ├── GoogleProvider       → Google Document AI
    └── (future providers)
    │
    ▼
ai_semantic_enhancer.py      → LLM field name normalization (fallback for low-confidence fields)
    │
    ▼
boe_section_extractor.py     → GRA BOE-specific key-name scanning (values encoded in key names)
    │
    ▼
Flat field dict → stored in APIDocument.fields (JSONB)
```

**GRA BOE quirk:** Ghana Revenue Authority BOE forms cause Reducto to embed numeric values inside field *key names* (e.g. `3_gross_mass_kg_1927800000_bill_of_date` encodes `gross_weight = 192780.0`). The `BOESectionExtractor` handles this via regex pattern scanning.

---

### 3. Normalization Engine — `modules/validation_engine/normalization/`

Transforms extracted fields from multiple documents into a canonical, comparable format before validation.

```
Raw extracted fields (per document)
    │
    ▼
SynonymMapper            → "Numéro de Facture" / "Invoice No." / "invoice_number" → invoice_number
    │                       (config-first YAML lookup → fuzzy 85% → LLM batch fallback)
    ▼
UnitConverter            → 1000 LBS → 453.59 KG, EUR 100 → USD 110
    │
    ▼
FormatNormalizer         → "04/07/2026" → "2026-04-07", "1.234,56" → 1234.56
    │
    ▼
Canonical field dict     → {invoice_number: "9400080882", net_weight: 189000.0, ...}
```

**Priority rule:** A field whose source name IS the canonical name (direct match) always beats a synonym-mapped field. Prevents low-confidence Reducto keys from overwriting correctly-named fields.

---

### 4. Validation Engine — `modules/validation_engine/`

Pluggable, config-driven validation system. All rules are defined in YAML — no hardcoded logic.

**Registry pattern:** Validators self-register via `@ValidatorRegistry.register("name")` decorator.

**Validator types:**

| Type | Examples | Detection |
|------|----------|-----------|
| Rule-based | `required_fields_validator`, `regex_validator`, `range_validator`, `incoterm_validator`, `customs_code_validator` | Single-doc field paths |
| Cross-document | `n_way_matcher`, `shipper_consignee_validator`, `calculation_validator` | Dot-notation paths (e.g. `invoice.net_weight`) |
| Statistical | `tolerance_validator` | Source/target with tolerance |
| AI-based | `cet_hs_code_validator` | LLM semantic matching |

**Dispatch rule:** The engine detects cross-document validators by checking if validation config contains dot-notation field paths. Cross-doc validators receive the full `documents` dict; single-doc validators receive only their primary document's fields.

---

### 5. LangGraph Workflow — `modules/validation_engine/orchestration/`

The validation pipeline is a stateful LangGraph graph. State persists through HITL pauses.

```
START
  │
  ▼
INITIALIZE         Load config, validate document presence
  │
  ▼
NORMALIZE          Run NormalizationEngine on all documents
  │
  ▼
VALIDATE           Execute validators per use-case config steps
  │
  ▼
ANALYZE            Classify discrepancies, run auto-fixes
  │
  ├── no critical/major ──────────────────────────┐
  │                                               │
  ▼                                               │
REQUIRE_USER_CONFIRMATION   ◄── HITL pause        │
  │  (checkpoint saved, workflow suspended)       │
  │  User submits confirmations via API           │
  │  Workflow resumes from this node              │
  │                                               │
  ▼                                               │
GENERATE_REPORT  ◄─────────────────────────────────┘
  │
  ▼
END
```

**HITL persistence:** LangGraph checkpointer (PostgreSQL in production, MemorySaver in dev) saves the full workflow state before pausing. Server restarts don't lose in-progress sessions.

**Session Manager:** LRU cache (max 100 sessions) + write-through to `validation_sessions` table. On cache miss, falls back to DB.

---

### 6. Discrepancy Handling — `modules/validation_engine/discrepancy/`

**Classification:**

| Severity | Triggers | Action |
|----------|----------|--------|
| **Critical** | HS code mismatch, duty calc >5%, CET fail, missing required field | HITL required |
| **Major** | Weight 1–5%, party name differ, format invalid, duty rate OOB | HITL required |
| **Minor** | Weight ≤1%, rounding | Auto-approved |
| **Info** | Unit differences, synonym variations | Auto-approved |

**Auto-fixer** resolves format/unit/synonym issues before HITL escalation, minimizing manual review burden.

---

### 7. Database Layer — `src/database/`

Async PostgreSQL via SQLAlchemy `AsyncSession`.

**Core models:**

| Table | Purpose |
|-------|---------|
| `shipments` | Central entity — all documents linked via `shipment_id` |
| `api_documents` | Uploaded file metadata + extracted fields (JSONB) |
| `validation_sessions` | LangGraph workflow state, HITL status, context (JSONB) |
| `invoices` | Structured invoice data |
| `bill_of_entries` | Structured BOE data |
| `packing_lists` | Structured packing list data |
| `freight_documents` | B/L, AWB data |
| `validation_results` | Per-check pass/fail records |
| `audit_log` | Immutable change trail |

**Repository pattern:** `validation_session_repository.py` provides typed CRUD; raw SQL is never used outside repositories.

---

### 8. Frontend — `src/ui/`

Next.js 16 (App Router) + React 19.

**Stack:** TailwindCSS 4 · Radix UI · React Query · React Hook Form + Zod · PDFjs · Recharts

**Key pages:**

| Route | Purpose |
|-------|---------|
| `/validation/vendor-docs` | Step 2 — upload invoice, packing list, B/L; view results |
| `/validation` | Step 6 — upload BOE; view cross-verification results; HITL confirm |
| `/shipments` | Shipment list and management |
| `/documents` | Document explorer with PDF preview |
| `/generation` | Document generation (BOE, invoice templates) |

---

### 9. External Services

| Service | Usage | Config |
|---------|-------|--------|
| **Reducto API** | PDF/image document parsing | `REDUCTO_API_KEY`, `REDUCTO_BASE_URL` |
| **OpenAI / Anthropic / Gemini / Bedrock** | Field normalization, semantic validation | `ACTIVE_LLM_PROVIDER`, provider API keys |
| **Exchange Rate API** | Currency conversion with live rates | Fallback hardcoded rates in `unit_converter.py` |
| **CET File** | Ghana HS code tariff schedule | `config/data/CET_Ghana.csv` |

---

## Key Design Principles

| Principle | Implementation |
|-----------|---------------|
| **Config-driven** | All validation rules, synonyms, tolerances in YAML — no hardcoded business logic |
| **Provider factory** | Swap extraction providers (Reducto → Google) with one env var change |
| **Registry pattern** | Add new validators without touching engine code — just register and configure |
| **Canonical priority** | Direct field name match always beats synonym mapping — prevents bad Reducto keys overwriting good values |
| **Graceful degradation** | Missing CET file, missing entry/exit code, insufficient docs → INFO/PASS (skip) not FAIL |
| **HITL first** | Critical discrepancies always surface to user — system never silently overrides compliance data |
| **Shipment as spine** | `shipment_id` links all documents across Step 2 and Step 6 — no re-upload of vendor docs for BOE check |
