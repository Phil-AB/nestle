# Universal IMPEX Extraction & Validation System

## What this system is
A universal, company-agnostic import/export document extraction and validation platform.
It is NOT specific to any one company, country, or document format.
Any company, any customs regime, any document set can be onboarded purely through config.

## Core principles — non-negotiable

### No hardcoding. Ever.
- No company names, country names, CPC codes, HS codes, duty rates, field names, thresholds, or document types in code.
- Every rule, rate, threshold, field, and behaviour lives in config files or the database.
- If you find yourself writing a literal value that belongs to a business domain, stop and put it in config.

### Config is the SSOT
- `checklist.yaml` is the SSOT for what fields to extract and validate per use case.
- `cpc_codes.yaml`, `master_concession.yaml`, `vat_deferment_list.yaml` are the SSOT for their respective reference data.
- Validators must read from these files at runtime — never duplicate their contents in code.
- Adding a new code, rate, or rule must require only a config change, never a code change.

### 100% use-case driven
- All extraction schemas, validation workflows, normalization rules, and tolerance settings are defined per use case in `config/validation/use_cases/`.
- The engine discovers and executes use cases dynamically — no use-case-specific logic in the engine core.

### Universal document handling
- Accepts any document type: PDF, image (JPG, PNG, TIFF), structured (CSV, XLSX), and others.
- Extraction is schema-driven from `checklist.yaml` extraction hints — not hardcoded per supplier or format.
- Field names are normalized through synonym mappings defined in the use case YAML, not in code.

## Engineering standards

### Investigate before changing
- Read and understand the relevant code, config, and SSOT files before making any change.
- Verify what the system currently does before deciding what to fix.

### Architecture
- Backend: Python, FastAPI, LangChain, LangGraph (agentic orchestration).
- Validation engine: config-driven LangGraph workflow with 6 nodes (initialize → normalize → validate → analyze → [HITL] → report).
- All validators are registry-registered and instantiated dynamically from use case config — no hardcoded validator lists.
- Scale horizontally (stateless API workers) and vertically (async throughout).

### Code quality
- Build for simplicity, strong abstraction, evolvability, reliability, and maintainability.
- Professional, structured codebase that other developers can extend without tribal knowledge.
- No comments that describe what the code does — only comments that explain non-obvious WHY.

### Testing
- Before running a test: read the source documents directly, derive expected outputs, then run — so discrepancies are immediately identifiable.

### UI
- Every extracted field must display a confidence score.
- Every field must be editable by the user before being saved to the database (human-in-the-loop review).

## What to do when you see hardcoding
Remove it. Move the value to the appropriate config file or database table. Wire the code to read it dynamically.
