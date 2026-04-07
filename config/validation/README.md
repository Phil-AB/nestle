# Validation Engine Configuration Guide

This directory contains all configuration files for the Universal Validation Engine.

## Directory Structure

```
config/validation/
├── README.md                    # This file
├── normalization.yaml           # Global normalization config
│
├── use_cases/                   # Validation use case definitions
│   ├── boe_validation.yaml     # BOE 3-way validation
│   ├── invoice_validation.yaml
│   └── contract_validation.yaml
│
└── validators/                  # Validator-specific configs
    ├── tolerance_validator.yaml
    ├── calculation_validator.yaml
    ├── exact_match_validator.yaml
    └── ...
```

---

## 1. Use Case Configuration

### Location
`/config/validation/use_cases/{use_case_name}.yaml`

### Purpose
Defines a complete validation scenario including:
- Documents involved
- Normalization rules
- Validation workflow steps
- Discrepancy handling
- Automation triggers
- Reporting

### Structure

```yaml
use_case:
  name: "my_use_case"
  display_name: "My Use Case"
  description: "What this validation does"
  version: "1.0"

  # Documents
  documents:
    primary:
      type: "document_type"
      required: true
    supporting:
      - type: "other_document"
        required: true

  # Normalization (optional)
  normalization:
    enabled: true
    synonyms:
      field_name:
        - "Synonym 1"
        - "Synonym 2"

  # Validation workflow
  workflow:
    type: "sequential"
    steps:
      - name: "step_1"
        validators:
          - "validator_name"
        config:
          # Validator-specific config
        on_failure: "continue"
        severity: "critical"

  # Discrepancy handling
  discrepancy_handling:
    classification:
      enabled: true
    auto_fix:
      enabled: true
    user_confirmation:
      required_for: ["critical", "major"]

  # Versioning
  versioning:
    enabled: true

  # Reporting
  reporting:
    enabled: true
    export_formats: ["json", "pdf"]
```

### Example: BOE Validation

See `/config/validation/use_cases/boe_validation.yaml` for a complete example.

**Key Features**:
- 3-way document matching (BOE, Invoice, Packing List)
- 7 validation steps (HS Code, weights, quantities, duty calculation)
- French/English synonym handling
- Weight tolerance matching (±1%)
- Automatic correction email generation

---

## 2. Normalization Configuration

### Location
`/config/validation/normalization.yaml`

### Purpose
Global normalization rules applied before validation:
- Field name synonyms (French ↔ English)
- Unit conversions (KG, LBS, MT)
- Format standardization (dates, decimals, currencies)

### Synonym Mapping

```yaml
normalization:
  synonym_mapping:
    enabled: true
    synonyms:
      canonical_name:
        - "Synonym 1"
        - "Synonym 2"
        - "Synonym 3"
```

**Example**:
```yaml
synonyms:
  net_weight:
    - "Net Weight"
    - "Poids Net"
    - "Net Wt"
    - "weight_net"
```

### Unit Conversion

```yaml
normalization:
  unit_conversion:
    enabled: true
    weight:
      target_unit: "KG"
      conversions:
        LBS: 0.453592
        MT: 1000
```

### Format Standardization

```yaml
normalization:
  format_normalization:
    date:
      target_format: "YYYY-MM-DD"
      supported_formats:
        - "DD/MM/YYYY"
        - "MM/DD/YYYY"
```

---

## 3. Validator Configuration

### Location
`/config/validation/validators/{validator_name}.yaml`

### Purpose
Optional validator-specific configuration. Most validators work with defaults from use case config.

### When to Create Validator Config

Create a validator config file when:
1. Validator needs global defaults
2. Multiple use cases share validator settings
3. Validator behavior needs documentation

### Example: Tolerance Validator

```yaml
validator:
  name: "tolerance_validator"
  type: "statistical"

  settings:
    default_tolerance_percent: 1.0
    operators: ["equals", "less_than", "greater_than"]
```

---

## 4. Creating a New Use Case

### Step 1: Define Your Use Case

```yaml
use_case:
  name: "invoice_validation"
  display_name: "Invoice Validation"
  description: "Validate invoice totals and line items"
```

### Step 2: Specify Documents

```yaml
documents:
  primary:
    type: "invoice"
    required: true
  supporting:
    - type: "purchase_order"
      required: true
```

### Step 3: Add Normalization (if needed)

```yaml
normalization:
  enabled: true
  synonyms:
    total_amount:
      - "Total Amount"
      - "Montant Total"
      - "Grand Total"
```

### Step 4: Define Workflow Steps

```yaml
workflow:
  type: "sequential"
  steps:
    - name: "check_required_fields"
      validators: ["required_fields_validator"]
      config:
        required_fields:
          invoice: ["invoice_number", "date", "total"]
      severity: "critical"

    - name: "validate_total"
      validators: ["calculation_validator"]
      config:
        calculations:
          - name: "invoice_total"
            formula: "subtotal + tax"
            fields:
              subtotal: "invoice.subtotal"
              tax: "invoice.tax_amount"
            target: "invoice.total"
      severity: "critical"
```

### Step 5: Configure Discrepancy Handling

```yaml
discrepancy_handling:
  user_confirmation:
    required_for: ["critical", "major"]
  auto_fix:
    enabled: true
```

### Step 6: Save and Test

Save to `/config/validation/use_cases/invoice_validation.yaml`

Test:
```python
from modules.validation_engine import get_validation_engine

engine = get_validation_engine()
context = await engine.create_validation_session(
    use_case="invoice_validation",
    documents={...}
)
```

---

## 5. Workflow Configuration

### Workflow Types

**Sequential** (default):
```yaml
workflow:
  type: "sequential"
  steps:
    - name: "step_1"
      # Executes first
    - name: "step_2"
      # Executes after step_1
```

**Parallel** (future):
```yaml
workflow:
  type: "parallel"
  steps:
    # All steps execute simultaneously
```

### Step Configuration

```yaml
steps:
  - name: "my_validation_step"
    description: "What this step does"

    # Validators to run
    validators:
      - "validator_1"
      - "validator_2"

    # Validator configuration
    config:
      # Passed to validators

    # Error handling
    on_failure: "continue"  # or "stop", "retry_with_llm"

    # Severity for failed validations
    severity: "critical"  # or "major", "minor", "info"
```

### Error Handling Options

- **`continue`**: Log error, continue to next step
- **`stop`**: Stop workflow immediately
- **`flag_and_continue`**: Create failed result, continue
- **`retry_with_llm`**: Use LLM fallback (future)

---

## 6. Validator Configuration in Use Case

### Exact Match Validator

```yaml
validators: ["exact_match_validator"]
config:
  fields:
    - source: "invoice.hs_code"
      target: "bill_of_entry.hs_code"
      match_type: "exact"  # or "case_insensitive", "normalized"
```

### Tolerance Validator

```yaml
validators: ["tolerance_validator"]
config:
  tolerance_type: "percentage"
  default_tolerance: 1.0
  per_session_override: true

  validations:
    - name: "weight_check"
      source: "invoice.net_weight"
      target: "boe.net_weight"
      tolerance_percent: 1.0
      operator: "equals"
```

### Calculation Validator

```yaml
validators: ["calculation_validator"]
config:
  calculations:
    - name: "duty_amount"
      formula: "unit_price * quantity * duty_rate"
      fields:
        unit_price: "invoice.unit_price"
        quantity: "packing_list.quantity"
        duty_rate: "boe.duty_rate"
      target: "boe.duty_amount"
      tolerance_percent: 0.5
```

### N-Way Matcher

```yaml
validators: ["n_way_matcher"]
config:
  field_name: "hs_code"
  documents:
    - "bill_of_entry"
    - "invoice"
    - "packing_list"
  match_type: "exact"
  require_all: true
```

### Required Fields Validator

```yaml
validators: ["required_fields_validator"]
config:
  required_fields:
    document_type_1: ["field1", "field2"]
    document_type_2: ["field3", "field4"]
  allow_empty: false
```

### Range Validator

```yaml
validators: ["range_validator"]
config:
  validations:
    - field: "duty_rate"
      min: 0
      max: 1.0
      operator: "within_range"
      inclusive: true
```

### Regex Validator

```yaml
validators: ["regex_validator"]
config:
  validations:
    - field: "hs_code"
      pattern: "^\\d{4}\\.\\d{2}$"
      description: "HS Code format (XXXX.XX)"
```

---

## 7. Severity Levels

### Critical
- Validation failure prevents compliance
- Example: HS Code mismatch, duty calculation error > 5%

### Major
- Significant discrepancy requiring attention
- Example: Weight difference > 1% and <= 5%

### Minor
- Small discrepancy, may be acceptable
- Example: Weight difference <= 1%

### Info
- Informational, no action needed
- Example: Format differences resolved by normalization

---

## 8. Discrepancy Handling

### Classification

```yaml
discrepancy_handling:
  classification:
    enabled: true
    severity_rules:
      critical:
        - "hs_code mismatch"
        - "duty calculation error > 5%"
      major:
        - "weight difference > 1%"
      minor:
        - "rounding differences"
```

### Auto-Fix

```yaml
discrepancy_handling:
  auto_fix:
    enabled: true
    rules:
      - type: "format_normalization"
        issues: ["date_format", "currency_format"]
      - type: "unit_conversion"
        issues: ["weight_unit"]
```

### User Confirmation

```yaml
discrepancy_handling:
  user_confirmation:
    required_for: ["critical", "major"]
    optional_for: ["minor"]
    auto_approve: ["info"]
```

---

## 9. Version Control

Enable version tracking for V1, V2, V3... validation runs:

```yaml
versioning:
  enabled: true
  track_changes: true

  revalidation:
    on_new_version: true
    compare_with_previous: true

    comparison_rules:
      - check: "fixed_discrepancies"
        expected: "all_fixed"
      - check: "new_discrepancies"
        expected: "none_critical"
```

---

## 10. Automation Triggers

### Email Notifications

```yaml
automation:
  on_discrepancy_detected:
    - action: "send_correction_email"
      condition: "user_confirmed_discrepancy"
      template: "correction_request"
```

### Status Updates

```yaml
automation:
  on_validation_complete:
    - action: "update_status"
      target: "validation_session"
```

---

## 11. Reporting

```yaml
reporting:
  enabled: true

  templates:
    summary: "validation_summary"
    detailed: "validation_detailed"
    comparison: "version_comparison"

  export_formats:
    - "json"
    - "pdf"
    - "csv"

  include:
    - "validation_results"
    - "discrepancies_by_severity"
    - "auto_fixes_applied"
    - "audit_trail"
```

---

## 12. Best Practices

### 1. Start Simple
Begin with required field validation, then add complexity:
```yaml
steps:
  - name: "check_fields"
    validators: ["required_fields_validator"]
  - name: "exact_match"
    validators: ["exact_match_validator"]
  - name: "tolerance_match"
    validators: ["tolerance_validator"]
```

### 2. Use Appropriate Severities
- **Critical**: Compliance issues, legal requirements
- **Major**: Business-critical, needs attention
- **Minor**: Nice to have, not blocking
- **Info**: Informational only

### 3. Enable Auto-Fix Wisely
Auto-fix for:
- ✅ Format differences
- ✅ Unit conversions
- ✅ Whitespace normalization

Don't auto-fix:
- ❌ Data mismatches
- ❌ Calculation errors
- ❌ Business logic violations

### 4. Configure Tolerance Appropriately
- **Financial**: 0.1-0.5%
- **Weights**: 0.5-1%
- **Quantities**: 0-0.5%

### 5. Test with Real Documents
Always test with real sample documents before production.

### 6. Document Business Rules
Add descriptions to workflow steps:
```yaml
- name: "duty_calculation"
  description: "Verify duty = unit_price × quantity × duty_rate per customs regulation XYZ"
```

---

## 13. Troubleshooting

### Config Not Loading
```
Error: Use case 'my_use_case' not found
```
**Solution**: Check file exists at `/config/validation/use_cases/my_use_case.yaml`

### Validator Not Found
```
Error: Validator 'my_validator' not registered
```
**Solution**: Check validator is imported in `/modules/validation_engine/validators/__init__.py`

### Field Not Found
```
Error: Field 'invoice.hs_code' not found
```
**Solution**:
1. Check field path matches document structure
2. Enable normalization if field name varies
3. Add synonym mapping

### Normalization Not Working
```
Synonym 'Poids Net' not mapped to 'net_weight'
```
**Solution**: Add to `/config/validation/normalization.yaml`:
```yaml
synonyms:
  net_weight:
    - "Poids Net"
```

---

## 14. Examples

### Complete BOE Validation
See: `/config/validation/use_cases/boe_validation.yaml`

### Simple Invoice Validation
```yaml
use_case:
  name: "simple_invoice"

  documents:
    primary: {type: "invoice"}

  workflow:
    steps:
      - name: "check_total"
        validators: ["calculation_validator"]
        config:
          calculations:
            - name: "total"
              formula: "subtotal + tax"
              fields:
                subtotal: "invoice.subtotal"
                tax: "invoice.tax"
              target: "invoice.total"
```

---

## 15. Reference

### Available Validators

| Validator | Type | Purpose |
|-----------|------|---------|
| `exact_match_validator` | Rule-based | Exact field matching |
| `tolerance_validator` | Statistical | Numeric tolerance matching |
| `calculation_validator` | Cross-document | Computed field verification |
| `n_way_matcher` | Cross-document | N-way field comparison |
| `required_fields_validator` | Rule-based | Required field checking |
| `range_validator` | Rule-based | Numeric range validation |
| `regex_validator` | Rule-based | Pattern matching |

### Workflow Step Options

- **name**: Step identifier (required)
- **description**: Human-readable description
- **validators**: List of validator names (required)
- **config**: Validator configuration
- **on_failure**: Error handling (continue, stop, flag_and_continue)
- **severity**: Result severity (critical, major, minor, info)

### Normalization Options

- **synonyms**: Field name variations
- **unit_conversion**: Unit transformation rules
- **format_normalization**: Format standardization
- **llm_fallback**: AI-powered fallback matching

---

## Questions?

For more information:
- Architecture: `/VALIDATION_ENGINE_ARCHITECTURE.md`
- Implementation Status: `/VALIDATION_ENGINE_IMPLEMENTATION_STATUS.md`
- Validator README: `/modules/validation_engine/README.md`

---

**Last Updated**: 2026-02-09
