# Universal IMPEX Extraction & Validation System

## What this system is
A universal, company-agnostic import/export document extraction and validation platform.
It is NOT specific to any one company, country, or document format.
Any company, any customs regime, any document set can be onboarded purely through config.

---

## Domain principles — non-negotiable

### No hardcoding. Ever.
- No company names, country names, CPC codes, HS codes, duty rates, field names, thresholds, or document types in code.
- Every rule, rate, threshold, field, and behaviour lives in config files or the database.
- If you find yourself writing a literal value that belongs to a business domain, stop and put it in config.

### Config is the single source of truth (SSOT)
- `checklist.yaml` — what fields to extract and validate per use case.
- `cpc_codes.yaml`, `master_concession.yaml`, `vat_deferment_list.yaml` — reference data.
- `config/validation/use_cases/` — all extraction schemas, validation workflows, normalization rules, and tolerance settings.
- Validators read from these files at runtime. Never duplicate their contents in code.
- Adding a code, rate, or rule requires only a config change, never a code change.
- Config files are validated at startup, not on the first request. Fail loudly if a required config is missing or malformed.

### 100% use-case driven
- The engine discovers and executes use cases dynamically — no use-case-specific logic in the engine core.
- All validator composition, ordering, and routing is declared in the use case YAML, not in Python.

### Universal document handling
- Accepts any document type: PDF, image (JPG, PNG, TIFF), structured (CSV, XLSX).
- Extraction is schema-driven from `checklist.yaml` extraction hints — not hardcoded per supplier or format.
- Field names are normalized through synonym mappings defined in the use case YAML, not in code.
- The system must work for **any shipment, any supplier, any carrier, any country**. A document from a Ghanaian importer, a Mexican exporter, a French shipper, or a Dutch dairy company must all process correctly through the same pipeline.
- Heuristics written in Python code (e.g. address detection, name normalization) must use **language-agnostic, universally applicable** signals. Do not embed locale-specific terms (administrative divisions, postal code formats, country-specific form labels) in code — put them in config if they are needed at all.
- When testing against a specific shipment document, fixes must be verified to be general: ask "would this break for a document from a different country or carrier?" before committing.

---

## Software engineering principles

### Investigate before changing
- Read and understand the relevant code, config, and SSOT files before making any change.
- Verify what the system currently does before deciding what to fix.
- `git blame` and `git log` are authoritative for why something was written the way it was.

### Explicit over implicit
- Config keys, validator names, and document types must be explicit strings, not inferred or computed at runtime from conventions.
- If a validator step is conditional, declare the condition in the use case YAML; do not bury it in Python logic.

### Fail fast at system boundaries
- Validate all external inputs at the API layer (file type, request schema, session existence) using Pydantic models.
- Validate all config at startup. A misconfigured validator or missing use case must raise immediately on boot, not silently fail on first use.
- Never propagate invalid state deeper into the pipeline. Reject early and surface a clear error.

### Idempotency
- Every node in the validation workflow must be safe to replay. LangGraph may re-enter a node after a checkpoint restore — nodes must not produce duplicate discrepancies, double-count results, or re-send notifications.
- Every database write that can be retried must be idempotent (upsert, not insert).

### Immutable audit trail
- Validation results, discrepancies, and session records are append-only. Never mutate a recorded discrepancy; create a new version instead.
- The `completed_steps` and `discrepancies` fields in `ValidationWorkflowState` are `Annotated[List, add]` — respect this: return deltas, not replacements.

### Separation of concerns
- **Extractors** convert raw documents into structured data. They do not validate.
- **Normalizers** canonicalize fields (synonyms, units, formats). They do not validate.
- **Validators** assert rules against normalized data. They do not extract or normalize.
- **Nodes** compose these layers in sequence. They do not contain business logic.
- **Config** declares what validators run and in what order. It does not contain code.

### Dependency injection over hidden singletons
- Pass dependencies (session manager, config loader, validator registry) via constructor injection.
- Singleton accessors (`get_validation_workflow()`, `get_validator_registry()`) are acceptable at the composition root (API layer), but modules should not call them internally.

### No gold-plating
- Do not add features, abstractions, or error handling for scenarios that cannot happen given the current system boundaries.
- Three similar validators is better than a premature abstraction. Extract shared logic only when a third case arrives.
- No half-implemented features. A stub that silently passes is worse than no validator at all — raise `NotImplementedError` or skip explicitly.

---

## Agentic system design

### Node purity (LangGraph)
- Every workflow node (`initialize_node`, `normalize_node`, `validate_node`, etc.) must be a pure function over `ValidationWorkflowState`.
- Nodes return a state delta (only the keys they change). They must not mutate the input state object.
- Side effects (database writes, email dispatch) belong in service calls within nodes — not in edge routing functions.

### Deterministic routing
- Conditional edge functions (`_route_after_analysis`) must be deterministic, pure functions — no LLM calls, no I/O, no randomness.
- Routing decisions must be derivable solely from the current state.

### Checkpoint safety
- The workflow uses LangGraph's `AsyncPostgresSaver` in production and `MemorySaver` in dev/test.
- Every node must be safe to re-run from a checkpoint: replaying a node must not corrupt state or double-emit side effects.
- Use `interrupt_before` (not `interrupt_after`) so the interrupted node has not yet executed and is safe to resume cleanly.

### State is the contract
- The `ValidationWorkflowState` TypedDict is the complete shared memory of the workflow. Nothing passes between nodes except through state.
- Do not pass context via global variables, thread-locals, or closures across node boundaries.
- All append-only fields in state use `Annotated[List, add]` — never overwrite them with a full list replacement.

### LLM reliability
- All LLM extraction calls use temperature=0 for determinism. Do not raise temperature without a documented reason.
- Extraction prompts must request structured JSON output. Parse the response against a known schema; if parsing fails, return an empty result with a logged warning — never raise an unhandled exception.
- Validate LLM output against the expected field set before writing to state. Fields not in the schema are discarded.
- Do not call an LLM inside a conditional edge or routing function.

### Graceful degradation
- A document with missing fields produces partial extraction, not a pipeline failure. The validation engine runs checks on the fields that are present and flags which fields were absent.
- A single failing validator does not abort the pipeline. All validators use `on_failure: flag_and_continue` unless explicitly overridden in config.
- A failed normalization step marks the field as un-normalized but allows downstream validators to attempt validation on the raw value.

### Human-in-the-loop (HITL)
- The workflow interrupts *before* `REQUIRE_USER_CONFIRMATION`, not after. The node runs only once user decisions are attached.
- Surface the minimum necessary context for a user decision: the field names, extracted values, and the discrepancy description. Do not require users to understand validator internals.
- User corrections propagate through `aupdate_state` into the LangGraph checkpoint before `resume()` is called. Never re-run the full pipeline to incorporate corrections.
- Every HITL decision is recorded immutably in the session (discrepancy_id → confirmed/rejected + comment).

### Minimal agent footprint
- Extractors request only the document sections and field names declared in the use case's checklist schema.
- Validators receive only the normalized documents and the validator's own config slice — not the full use case config.
- Agents do not accumulate context between independent shipment runs. Each `session_id` is isolated.

### Structured outputs throughout
- Every validator returns a `ValidationResult` (Pydantic model). No dict-based ad hoc returns.
- Every discrepancy is a `Discrepancy` (Pydantic model) with a stable UUID, not a bare string.
- Extraction results carry a `confidence` float (0.0–1.0) on every extracted field. This is surfaced to the UI — never omit it.

---

## Registry patterns

### Validator registry
- Validators self-register with `@ValidatorRegistry.register("validator_name")`. No factory code changes required.
- Every validator must implement `IValidator`. The registry enforces this at registration time.
- To add a validator: create the class, apply the decorator, declare it in the use case YAML. No other file changes.

### Extractor registry
- Extractors register via `_BUILT_IN_REGISTRY` in `registry.py` or via `extractor_class` in `document_config.yaml` (no code change required for the latter).
- If no extractor is registered for a document type, `MissingExtractorError` is raised with a clear remediation message. This is intentional — do not add a generic fallback.

---

## Code quality

### Types everywhere
- All function signatures have full type annotations (Python `typing`).
- Workflow state uses `TypedDict`. Data exchange at module boundaries uses Pydantic models.
- Do not use `Dict[str, Any]` where a more specific type is possible.

### Async discipline
- The API and pipeline are async throughout. Never block the event loop: no `time.sleep`, no synchronous file I/O in a request path, no synchronous database calls.
- Use `asyncio.gather` for parallel validator execution where validators are independent.
- Background tasks (email notifications) use fire-and-forget wrappers that swallow their own exceptions cleanly.

### Error handling
- Catch specific exceptions, not bare `except Exception`. Log with `exc_info=True` when the stack trace matters.
- Internal pipeline errors produce a structured error response (session_id, step, error message). Never leak stack traces to the API client in production.
- Config errors and missing dependencies raise at startup, not at request time.

### Logging
- Every significant action logs: session_id, use_case, step name, and outcome (passed/failed/count).
- LLM calls log: model name, token usage, latency, and extraction field count.
- Confidence scores are logged at extraction time and stored in the database.
- Use structured logger calls (`get_logger(__name__)`), not print statements.

### Comments
- Write no comments that describe *what* the code does. Well-named identifiers do that.
- Write a comment only when the *why* is non-obvious: a business constraint, a subtle invariant, a workaround for a known upstream bug.
- Do not add comments that explain the current task or caller ("added for Step 6 flow"). Those belong in commit messages.

---

## Testing

### Derive expected outputs before running
- Before running a test: read the source documents or config directly, derive the expected extraction result or validation outcome manually, then run the test. Discrepancies are immediately identifiable this way.

### Use real config in tests
- Never mock config files or the config loader in integration tests. If a test needs a specific config, create a minimal fixture config in the test directory.
- Real config must be read at test time so that config changes break tests immediately rather than silently.

### Validator unit tests
- Give each validator a known document dict with known values. Assert the exact `ValidationResult` fields: `passed`, `confidence`, `message`, and the discrepancy content.
- Test the unhappy path: missing fields, out-of-range values, mismatched documents.

### LLM tests
- Do not call live LLM APIs in unit or integration tests. Use deterministic fixture responses (pre-recorded JSON).
- Test the extraction parser against known document fixtures — not against live documents.

---

## UI

- Every extracted field displays a confidence score (0–100%).
- Every field is editable by the user before the session is saved to the database (HITL review).
- Field edits are recorded as user overrides with the original extracted value preserved.
- The UI must reflect the current workflow status (`awaiting_user`, `completed`, `failed`) without polling — use the response from the step endpoints directly.

---

## What to do when you see hardcoding
Remove it. Move the value to the appropriate config file or database table. Wire the code to read it dynamically. If the change touches a SSOT file (`cpc_codes.yaml`, `master_concession.yaml`, etc.), verify the validator that reads it also handles the new shape correctly.

---

## Protected files — never modify under any circumstances

The following files must **never** be edited by Claude — not to fix a bug, not to match a test, not to improve extraction, not for any reason:

- `src/config/checklist.yaml` — the GRA import checklist; owned by the business, not the engineering team
- `src/config/data/cpc_codes.yaml` — official customs procedure codes
- `src/config/data/master_concession.yaml` — official duty concession reference data
- `src/config/data/vat_deferment_list.yaml` — official VAT deferment reference data

These are authoritative source-of-truth documents. If a validator or extractor produces an unexpected result against one of these files, investigate and fix the code — never alter the file to make the result fit.
