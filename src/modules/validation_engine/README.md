# Universal Validation Engine

A standalone, config-driven validation engine for document validation workflows.

## Features

- **100% Config-Driven**: All validation logic defined in YAML configuration files
- **Universal**: Works for any validation use case (BOE, invoice, contract, customs, etc.)
- **Hybrid Validation**: Combines rule-based, AI-based, and statistical validators
- **Multi-Step Orchestration**: LangGraph-based workflow engine with conditional routing
- **Version Control**: Track validation runs, compare versions, detect changes
- **Pluggable Architecture**: Validators self-register, no factory code changes needed
- **Production-Grade**: Async operations, error handling, logging, monitoring

## Architecture

```
validation_engine/
├── core/                    # Core engine components
│   ├── base.py             # Base interfaces (IValidator, IDiscrepancyClassifier, etc.)
│   ├── engine.py           # Main ValidationEngine
│   ├── session_manager.py  # Session lifecycle management
│   ├── config_loader.py    # Configuration loading
│   └── result_aggregator.py # Result analysis and reporting
│
├── validators/              # Pluggable validators
│   ├── validator_registry.py  # Auto-registration system
│   ├── rule_based/         # Rule-based validators
│   ├── ai_based/           # AI-powered validators
│   ├── statistical/        # Statistical validators
│   └── cross_document/     # Multi-document validators
│
├── orchestration/          # LangGraph workflow orchestration
├── normalization/          # Data normalization layer
├── discrepancy/           # Discrepancy detection and classification
├── versioning/            # Version control and comparison
├── reporting/             # Report generation
├── storage/               # Persistence layer
└── utils/                 # Utilities, constants, exceptions
```

## Quick Start

### 1. Create a Validation Session

```python
from modules.validation_engine import get_validation_engine

engine = get_validation_engine()

# Create validation session
context = await engine.create_validation_session(
    use_case="boe_validation",  # Configured in /config/validation/use_cases/
    documents={
        "bill_of_entry": {"hs_code": "1234.56", "net_weight": 1000, ...},
        "invoice": {"hs_code": "1234.56", "net_weight": 1000, ...},
        "packing_list": {"hs_code": "1234.56", "net_weight": 1000, ...}
    },
    tolerance_overrides={"weight_tolerance_percent": 1.5}
)

print(f"Session ID: {context.session_id}")
```

### 2. Run Validation Workflow

```python
# Execute validation
summary = await engine.run_validation_workflow(context.session_id)

print(f"Total validations: {summary.total_validations}")
print(f"Passed: {summary.passed_validations}")
print(f"Discrepancies: {summary.total_discrepancies}")
print(f"Critical: {summary.critical_discrepancies}")
```

### 3. Get Validation Report

```python
# Generate report
report = await engine.get_validation_report(
    session_id=context.session_id,
    format="json"  # or "pdf", "csv"
)

print(f"Final Status: {report['final_status']}")
print(f"Top Discrepancies: {report['top_discrepancies']}")
```

### 4. Handle User Confirmations

```python
# User confirms discrepancy
await engine.add_user_confirmation(
    session_id=context.session_id,
    discrepancy_id="<discrepancy-uuid>",
    confirmed=True,
    comment="HS Code mismatch confirmed - supplier error"
)

# User provides missing data
await engine.add_user_data(
    session_id=context.session_id,
    field_name="freight_value",
    value=5000.00
)
```

## Configuration

### Use Case Configuration

Define validation use cases in `/config/validation/use_cases/{use_case_name}.yaml`:

```yaml
use_case:
  name: "boe_validation"
  display_name: "BOE 3-Way Validation"

  documents:
    primary:
      type: "bill_of_entry"
      required: true
    supporting:
      - type: "invoice"
        required: true
      - type: "packing_list"
        required: true

  workflow:
    steps:
      - name: "hs_code_matching"
        validators:
          - "exact_match_validator"
        config:
          fields:
            - source: "invoice.hs_code"
              target: "bill_of_entry.hs_code"
        severity: "critical"

      - name: "weight_matching"
        validators:
          - "tolerance_validator"
        config:
          tolerance_percent: 1.0
        severity: "critical"
```

### Validator Configuration

Optionally configure validators in `/config/validation/validators/{validator_name}.yaml`:

```yaml
validator:
  name: "tolerance_validator"
  type: "statistical"
  settings:
    default_tolerance_percent: 1.0
```

## Creating Custom Validators

### 1. Implement IValidator Interface

```python
from modules.validation_engine import IValidator, ValidationResult, ValidationContext

class MyCustomValidator(IValidator):
    """My custom validator"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.validator_type = "rule_based"
        self.validator_name = "my_custom_validator"

    async def validate(
        self,
        source_data: dict,
        target_data: dict,
        context: ValidationContext
    ) -> list[ValidationResult]:
        # Your validation logic here
        results = []

        # Example: Check if field exists
        if "my_field" not in source_data:
            results.append(ValidationResult(
                validator_name=self.validator_name,
                validator_type=self.validator_type,
                field_name="my_field",
                passed=False,
                confidence=1.0,
                severity="major",
                message="Field 'my_field' is missing"
            ))

        return results

    def supports_field_type(self, field_type: str) -> bool:
        return field_type in ["string", "number"]
```

### 2. Register Validator

```python
from modules.validation_engine import ValidatorRegistry

@ValidatorRegistry.register("my_custom_validator")
class MyCustomValidator(IValidator):
    # ... implementation
```

That's it! The validator is now available for use in any validation workflow.

## API Integration

See `/src/api/v2/endpoints/validation.py` for REST API endpoints:

- `POST /api/v2/validation/sessions` - Create session
- `GET /api/v2/validation/sessions/{id}` - Get session status
- `POST /api/v2/validation/sessions/{id}/validate` - Run validation
- `POST /api/v2/validation/sessions/{id}/confirm-discrepancies` - User confirmation
- `GET /api/v2/validation/sessions/{id}/report` - Get report

## Core Concepts

### ValidationContext
- Contains all session data and state
- Passed through workflow steps
- Stores documents, results, discrepancies, user input

### ValidationResult
- Output of a single validator
- Includes passed/failed status, confidence, severity, message
- Can include auto-fix information

### Discrepancy
- Detected mismatch between documents
- Classified by severity (critical, major, minor, info)
- Can be auto-fixable or require user confirmation

### Workflow Steps
- Sequential execution of validators
- Configurable error handling (stop, continue, retry)
- Conditional routing based on results

### Version Control
- Track V1, V2, V3... of validation runs
- Compare versions to detect fixes/regressions
- Full audit trail

## Best Practices

1. **Use Config-Driven Approach**: Define validation logic in YAML, not code
2. **Start with Rule-Based**: Use simple validators first, add AI/statistical as needed
3. **Set Appropriate Severity**: Critical for business-critical fields, info for formatting
4. **Enable Auto-Fix**: Let system fix common issues (format, units, synonyms)
5. **Human-in-the-Loop**: Require user confirmation for critical discrepancies
6. **Version Everything**: Use version control for iterative validation

## Testing

```python
# Example test
import pytest
from modules.validation_engine import get_validation_engine

@pytest.mark.asyncio
async def test_boe_validation():
    engine = get_validation_engine()

    context = await engine.create_validation_session(
        use_case="boe_validation",
        documents={
            "bill_of_entry": {"hs_code": "1234.56"},
            "invoice": {"hs_code": "1234.56"}
        }
    )

    summary = await engine.run_validation_workflow(context.session_id)

    assert summary.all_validations_passed
    assert summary.critical_discrepancies == 0
```

## Documentation

- **Architecture**: See `/VALIDATION_ENGINE_ARCHITECTURE.md`
- **API Reference**: See `/src/api/v2/endpoints/validation.py`
- **Configuration Guide**: See `/config/validation/README.md` (to be created)

## License

Internal use only - Nestlé project
