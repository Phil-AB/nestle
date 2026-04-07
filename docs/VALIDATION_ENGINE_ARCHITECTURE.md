# Universal Validation Engine - Architecture Design

## Executive Summary

This document defines the architecture for a **standalone, universal validation engine** that provides config-driven, multi-step, version-controlled validation for any document processing use case. The engine is built with LangChain/LangGraph for agentic workflows and follows the same design principles as the extraction module: 100% dynamic, fully configurable, and production-grade.

---

## Design Principles

### 1. Universal & Use-Case Agnostic
- Works for **any validation scenario** (BOE matching, invoice validation, contract compliance, etc.)
- No hardcoded document types or validation logic
- New use cases added via configuration only

### 2. Config-Driven Architecture
- Validation rules defined in YAML
- Validator chains configured, not coded
- Tolerance, thresholds, and workflows configurable
- Zero code changes for new use cases

### 3. Hybrid Validation Approach
- **Rule-based**: Exact match, range checks, regex patterns
- **AI-based**: Semantic similarity, LLM reasoning, intelligent matching
- **Statistical**: Tolerance-based, outlier detection, trend analysis
- Combine multiple strategies for robust validation

### 4. Multi-Step Orchestration
- LangGraph state machine for complex workflows
- Sequential and parallel validation stages
- Human-in-the-loop decision points
- Conditional routing based on results

### 5. Version Control
- Track all validation runs
- Compare versions (V1 vs V2)
- Delta analysis and change detection
- Full audit trail

### 6. Pluggable & Extensible
- Validator registry with auto-registration
- Easy to add new validator types
- Provider-agnostic (works with any data source)
- Modular architecture

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Validation Engine API                         │
│                  (FastAPI REST + WebSocket)                      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Validation Orchestrator                         │
│              (LangGraph Workflow Engine)                         │
│                                                                   │
│  States: INIT → NORMALIZE → VALIDATE → ANALYZE → REPORT         │
└─────────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │ Normalization│  │  Validation  │  │  Discrepancy │
    │    Layer     │  │    Engine    │  │   Handler    │
    └──────────────┘  └──────────────┘  └──────────────┘
            │                 │                 │
            ▼                 ▼                 ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │   Synonym    │  │  Validator   │  │  Classifier  │
    │   Mapper     │  │   Registry   │  │   & Fixer    │
    └──────────────┘  └──────────────┘  └──────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │ Rule-Based   │  │  AI-Based    │  │ Statistical  │
    │ Validators   │  │  Validators  │  │ Validators   │
    └──────────────┘  └──────────────┘  └──────────────┘
```

---

## Module Structure

```
/modules/validation_engine/              # Standalone validation module
│
├── core/                                # Core engine components
│   ├── __init__.py
│   ├── base.py                         # Base interfaces and contracts
│   ├── engine.py                       # Main validation engine
│   ├── context.py                      # Validation context manager
│   ├── session_manager.py              # Session lifecycle management
│   ├── result_aggregator.py            # Aggregate validation results
│   └── config_loader.py                # Load validation configs
│
├── orchestration/                       # LangGraph workflow orchestration
│   ├── __init__.py
│   ├── workflow_engine.py              # LangGraph state machine
│   ├── state_definitions.py            # Workflow states and schemas
│   ├── graph_builder.py                # Build validation graphs
│   └── executors/                      # Step executors
│       ├── normalization_executor.py
│       ├── validation_executor.py
│       ├── analysis_executor.py
│       └── reporting_executor.py
│
├── validators/                          # Pluggable validators
│   ├── __init__.py
│   ├── base_validator.py               # Base validator interface
│   ├── validator_registry.py           # Auto-registration system
│   │
│   ├── rule_based/                     # Rule-based validators
│   │   ├── exact_match_validator.py    # Exact field matching
│   │   ├── range_validator.py          # Numeric range checks
│   │   ├── regex_validator.py          # Pattern matching
│   │   ├── required_fields_validator.py
│   │   └── cross_field_validator.py    # Field interdependencies
│   │
│   ├── ai_based/                       # AI-powered validators
│   │   ├── semantic_validator.py       # Semantic similarity
│   │   ├── llm_reasoning_validator.py  # LLM-based validation
│   │   ├── fuzzy_match_validator.py    # Fuzzy string matching
│   │   └── context_aware_validator.py  # Context-based validation
│   │
│   ├── statistical/                    # Statistical validators
│   │   ├── tolerance_validator.py      # Tolerance-based matching
│   │   ├── outlier_validator.py        # Outlier detection
│   │   ├── distribution_validator.py   # Statistical distribution
│   │   └── trend_validator.py          # Trend analysis
│   │
│   └── cross_document/                 # Multi-document validators
│       ├── n_way_matcher.py            # N-way document matching
│       ├── field_consistency_validator.py
│       ├── calculation_validator.py    # Computed field verification
│       └── relationship_validator.py   # Document relationships
│
├── normalization/                       # Data normalization layer
│   ├── __init__.py
│   ├── normalizer_engine.py            # Main normalization engine
│   ├── synonym_mapper.py               # Field name mapping
│   ├── unit_converter.py               # Unit conversions
│   ├── format_normalizer.py            # Format standardization
│   ├── type_normalizer.py              # Data type conversion
│   ├── language_detector.py            # Language detection
│   └── cache/                          # Normalization caching
│       ├── mapping_cache.py
│       └── conversion_cache.py
│
├── discrepancy/                         # Discrepancy handling
│   ├── __init__.py
│   ├── detector.py                     # Discrepancy detection
│   ├── classifier.py                   # Severity & category classification
│   ├── root_cause_analyzer.py          # Root cause analysis
│   ├── auto_fixer.py                   # Auto-fix common issues
│   ├── confidence_scorer.py            # Confidence scoring
│   └── user_confirmation.py            # Human confirmation workflow
│
├── versioning/                          # Version control system
│   ├── __init__.py
│   ├── version_manager.py              # Version tracking
│   ├── delta_analyzer.py               # Change detection
│   ├── comparator.py                   # Version comparison
│   ├── revalidation_engine.py          # Re-run validation on new versions
│   └── audit_logger.py                 # Audit trail
│
├── reporting/                           # Reporting and analytics
│   ├── __init__.py
│   ├── report_generator.py             # Generate validation reports
│   ├── result_formatter.py             # Format results
│   ├── visualizer.py                   # Create visualizations
│   ├── export_service.py               # Export to PDF, JSON, CSV
│   └── templates/                      # Report templates
│       ├── summary_template.jinja2
│       ├── detailed_template.jinja2
│       └── comparison_template.jinja2
│
├── storage/                             # Persistence layer
│   ├── __init__.py
│   ├── session_repository.py           # Validation sessions
│   ├── result_repository.py            # Validation results
│   ├── discrepancy_repository.py       # Discrepancies
│   ├── version_repository.py           # Version history
│   └── models/                         # Database models
│       ├── validation_session.py
│       ├── validation_result.py
│       ├── discrepancy.py
│       └── validation_version.py
│
├── agents/                              # LangChain agents
│   ├── __init__.py
│   ├── validation_agent.py             # Main validation agent
│   ├── normalization_agent.py          # Normalization agent
│   ├── analysis_agent.py               # Analysis agent
│   └── tools/                          # Agent tools
│       ├── validator_tool.py
│       ├── normalizer_tool.py
│       └── analyzer_tool.py
│
├── integration/                         # Integration adapters
│   ├── __init__.py
│   ├── extraction_adapter.py           # Interface with extraction module
│   ├── automation_adapter.py           # Interface with automation module
│   └── notification_adapter.py         # Notification integration
│
├── utils/                               # Utilities
│   ├── __init__.py
│   ├── helpers.py                      # Helper functions
│   ├── exceptions.py                   # Custom exceptions
│   └── constants.py                    # Constants
│
└── config/                              # Module configuration
    ├── __init__.py
    └── defaults.py                     # Default settings
```

---

## Configuration Structure

### 1. Validation Use Case Configuration

**Location**: `/config/validation/use_cases/{use_case_name}.yaml`

```yaml
# Example: /config/validation/use_cases/boe_validation.yaml

use_case:
  name: "boe_validation"
  display_name: "BOE 3-Way Validation"
  description: "Validate BOE against Invoice, Packing List, and BOL/AWB"
  version: "1.0"

  # Documents involved in validation
  documents:
    primary:
      type: "bill_of_entry"
      role: "draft"
      required: true

    supporting:
      - type: "invoice"
        role: "source"
        required: true

      - type: "packing_list"
        role: "source"
        required: true

      - type: "bill_of_lading"
        role: "source"
        required: false
        alternatives:
          - "airway_bill"

  # Normalization rules
  normalization:
    enabled: true

    # Field synonym mapping
    synonyms:
      net_weight:
        - "Net Weight"
        - "Poids Net"
        - "Net Wt"
        - "weight_net"
        - "poids_net"

      gross_weight:
        - "Gross Weight"
        - "Poids Brut"
        - "Gross Wt"
        - "weight_gross"

      hs_code:
        - "HS Code"
        - "HSN Code"
        - "Code SH"
        - "Tariff Code"
        - "Harmonized Code"

    # Unit conversions
    units:
      weight:
        target: "KG"
        conversions:
          LBS: 0.453592
          MT: 1000
          G: 0.001
          TON: 1000

      currency:
        target: "USD"
        source: "exchange_rate_api"  # Dynamic conversion

    # Format standardization
    formats:
      date:
        target: "YYYY-MM-DD"
        sources:
          - "DD/MM/YYYY"
          - "MM/DD/YYYY"
          - "DD-MMM-YYYY"

      decimal:
        precision: 2
        separator: "."

  # Validation workflow
  workflow:
    type: "sequential"  # or "parallel"

    steps:
      - name: "field_extraction_check"
        validators:
          - "required_fields_validator"
        config:
          required_fields:
            bill_of_entry: ["hs_code", "net_weight", "gross_weight", "duty_amount"]
            invoice: ["hs_code", "net_weight", "unit_price"]
            packing_list: ["hs_code", "net_weight", "gross_weight", "quantity"]
        on_failure: "flag_and_continue"

      - name: "normalization"
        validators:
          - "synonym_mapper"
          - "unit_converter"
          - "format_normalizer"
        on_failure: "retry_with_llm"

      - name: "hs_code_matching"
        validators:
          - "exact_match_validator"
          - "semantic_validator"  # Fallback for variations
        config:
          mode: "strict"
          fields:
            - source: "invoice.hs_code"
              target: "bill_of_entry.hs_code"
              match_type: "exact"

            - source: "packing_list.hs_code"
              target: "bill_of_entry.hs_code"
              match_type: "exact"
        severity: "critical"

      - name: "weight_matching"
        validators:
          - "tolerance_validator"
        config:
          tolerance_type: "percentage"
          default_tolerance: 1.0  # 1% default
          per_session_override: true

          validations:
            - name: "net_weight_check"
              source: "invoice.net_weight"
              target: "bill_of_entry.net_weight"
              tolerance_percent: 1.0

            - name: "gross_weight_check"
              source: "packing_list.gross_weight"
              target: "bill_of_entry.gross_weight"
              tolerance_percent: 1.0

            - name: "net_gross_consistency"
              source: "bill_of_entry.net_weight"
              target: "bill_of_entry.gross_weight"
              operator: "less_than"
              severity: "major"
        severity: "critical"

      - name: "duty_calculation"
        validators:
          - "calculation_validator"
          - "llm_reasoning_validator"  # Verify complex calculations
        config:
          calculations:
            - name: "duty_amount"
              formula: "unit_price * quantity * duty_rate"
              fields:
                unit_price: "invoice.unit_price"
                quantity: "packing_list.quantity"
                duty_rate: "bill_of_entry.duty_rate"
              tolerance_percent: 0.5
        severity: "critical"

      - name: "cross_document_consistency"
        validators:
          - "n_way_matcher"
        config:
          line_items: true
          match_strategy: "fuzzy"
          confidence_threshold: 0.85
        severity: "major"

  # Discrepancy handling
  discrepancy_handling:
    classification:
      enabled: true

      severity_rules:
        critical:
          - "hs_code mismatch"
          - "duty calculation error > 5%"
          - "weight difference > 5%"

        major:
          - "weight difference > 1% and <= 5%"
          - "quantity mismatch"
          - "missing required field"

        minor:
          - "weight difference <= 1%"
          - "rounding differences"
          - "format variations"

        info:
          - "unit differences (resolved)"
          - "date format differences"
          - "synonym variations"

    auto_fix:
      enabled: true

      rules:
        - type: "format_normalization"
          issues: ["date_format", "currency_format", "number_format"]

        - type: "unit_conversion"
          issues: ["weight_unit", "currency_unit"]

        - type: "synonym_resolution"
          issues: ["field_name_variation"]

    user_confirmation:
      required_for:
        - "critical"
        - "major"

      optional_for:
        - "minor"

      auto_approve:
        - "info"

  # Version control
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

        - check: "unchanged_correct_fields"
          expected: "all_unchanged"

  # Reporting
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
      - "discrepancies"
      - "auto_fixes"
      - "user_confirmations"
      - "version_history"
      - "audit_trail"
      - "performance_metrics"

  # Automation triggers
  automation:
    on_discrepancy_detected:
      - action: "send_correction_email"
        condition: "user_confirmed_discrepancy"
        template: "boe_correction_request"

    on_validation_complete:
      - action: "update_status"
        target: "validation_session"

    on_revalidation_pass:
      - action: "mark_as_validated"
      - action: "notify_user"
```

---

### 2. Validator Configuration

**Location**: `/config/validation/validators/{validator_type}.yaml`

```yaml
# Example: /config/validation/validators/tolerance_validator.yaml

validator:
  name: "tolerance_validator"
  type: "statistical"
  description: "Validates numeric fields with configurable tolerance"

  settings:
    default_tolerance_percent: 1.0
    default_tolerance_absolute: null

    comparison_modes:
      - "percentage"
      - "absolute"
      - "relative"

    operators:
      - "equals"
      - "less_than"
      - "greater_than"
      - "within_range"

  llm_config:
    enabled: false  # This validator doesn't need LLM

  caching:
    enabled: true
    ttl_seconds: 3600
```

---

### 3. Normalization Configuration

**Location**: `/config/validation/normalization.yaml`

```yaml
normalization:
  # Synonym mapping
  synonym_mapping:
    strategy: "hybrid"  # config + llm_fallback

    llm_fallback:
      enabled: true
      provider: "google"  # From llm.yaml
      model: "default"
      confidence_threshold: 0.8
      cache_successful_mappings: true

  # Unit conversion
  unit_conversion:
    weight:
      target_unit: "KG"
      conversions:
        LBS: 0.453592
        MT: 1000
        G: 0.001
        TON: 1000
        T: 1000

    currency:
      source: "exchange_rate_api"
      cache_ttl: 86400  # 24 hours
      fallback_rates:
        EUR: 1.1
        GBP: 1.3
        JPY: 0.0091

  # Format normalization
  format_normalization:
    date:
      target_format: "YYYY-MM-DD"
      supported_formats:
        - "DD/MM/YYYY"
        - "MM/DD/YYYY"
        - "DD-MMM-YYYY"
        - "YYYY/MM/DD"

    decimal:
      decimal_separator: "."
      thousands_separator: ","
      precision: 2

    currency:
      position: "prefix"  # $1000 or 1000$
      symbol: "$"
```

---

## Core Interfaces

### 1. Base Validator Interface

```python
# /modules/validation_engine/validators/base_validator.py

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class ValidationResult(BaseModel):
    """Standard validation result format"""
    validator_name: str
    passed: bool
    confidence: float  # 0.0 - 1.0
    field_name: Optional[str] = None
    source_value: Any
    target_value: Any
    expected_value: Optional[Any] = None
    discrepancy: Optional[Dict[str, Any]] = None
    severity: str  # "critical", "major", "minor", "info"
    message: str
    auto_fixed: bool = False
    metadata: Dict[str, Any] = {}


class IValidator(ABC):
    """Base interface for all validators"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.validator_type: str = ""  # "rule_based", "ai_based", "statistical"
        self.validator_name: str = ""

    @abstractmethod
    async def validate(
        self,
        source_data: Dict[str, Any],
        target_data: Dict[str, Any],
        context: "ValidationContext"
    ) -> List[ValidationResult]:
        """Execute validation logic"""
        pass

    @abstractmethod
    def supports_field_type(self, field_type: str) -> bool:
        """Check if validator supports this field type"""
        pass

    def get_metadata(self) -> Dict[str, Any]:
        """Return validator metadata"""
        return {
            "name": self.validator_name,
            "type": self.validator_type,
            "config": self.config
        }
```

---

### 2. Validator Registry

```python
# /modules/validation_engine/validators/validator_registry.py

from typing import Dict, Type, List
from .base_validator import IValidator

class ValidatorRegistry:
    """Registry for auto-registration of validators"""

    _validators: Dict[str, Type[IValidator]] = {}

    @classmethod
    def register(cls, validator_name: str):
        """Decorator for auto-registering validators"""
        def decorator(validator_class: Type[IValidator]):
            cls._validators[validator_name] = validator_class
            return validator_class
        return decorator

    @classmethod
    def get_validator(cls, validator_name: str, config: Dict) -> IValidator:
        """Get validator instance by name"""
        if validator_name not in cls._validators:
            raise ValueError(f"Validator {validator_name} not registered")

        validator_class = cls._validators[validator_name]
        return validator_class(config)

    @classmethod
    def list_validators(cls) -> List[str]:
        """List all registered validators"""
        return list(cls._validators.keys())


# Usage in validator implementations:
# @ValidatorRegistry.register("exact_match_validator")
# class ExactMatchValidator(IValidator):
#     ...
```

---

### 3. Validation Context

```python
# /modules/validation_engine/core/context.py

from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

class ValidationContext(BaseModel):
    """Context passed through validation workflow"""

    # Session info
    session_id: UUID
    use_case: str
    version: int

    # Documents
    documents: Dict[str, Dict[str, Any]]  # {doc_type: extracted_data}
    primary_document: str
    supporting_documents: List[str]

    # Configuration
    config: Dict[str, Any]
    tolerance_overrides: Dict[str, float] = {}

    # State
    current_step: str
    normalized_data: Dict[str, Dict[str, Any]] = {}
    validation_results: List["ValidationResult"] = []
    discrepancies: List[Dict[str, Any]] = []

    # User interaction
    user_provided_data: Dict[str, Any] = {}
    user_confirmations: Dict[str, bool] = {}

    # Metadata
    created_at: datetime
    updated_at: datetime

    class Config:
        arbitrary_types_allowed = True
```

---

## LangGraph Workflow States

```python
# /modules/validation_engine/orchestration/state_definitions.py

from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph

class ValidationState(TypedDict):
    """State for validation workflow"""

    # Input
    session_id: str
    use_case: str
    documents: Dict[str, Any]
    config: Dict[str, Any]

    # Normalization
    normalized: bool
    normalization_errors: List[Dict[str, Any]]

    # Validation
    validation_step: str
    validation_results: List[Dict[str, Any]]
    all_validations_passed: bool

    # Discrepancy
    discrepancies: List[Dict[str, Any]]
    critical_discrepancies: List[Dict[str, Any]]
    auto_fixed_count: int

    # User interaction
    requires_user_confirmation: bool
    user_confirmed: bool
    user_input: Dict[str, Any]

    # Versioning
    is_revalidation: bool
    previous_version_id: str
    changes_detected: List[Dict[str, Any]]

    # Output
    final_status: str  # "passed", "failed", "requires_attention"
    report: Dict[str, Any]

    # Metadata
    error: str
    messages: List[str]
```

**Workflow Graph**:

```
START
  │
  ▼
INITIALIZE_SESSION
  │
  ▼
NORMALIZE_DATA ────────► NORMALIZATION_FAILED ──► RETRY_WITH_LLM
  │                                                      │
  │◄─────────────────────────────────────────────────────┘
  ▼
RUN_VALIDATIONS (parallel execution)
  │
  ▼
ANALYZE_DISCREPANCIES
  │
  ├──► NO_DISCREPANCIES ──► GENERATE_REPORT ──► END
  │
  ├──► AUTO_FIXABLE ──► APPLY_FIXES ──► RE_VALIDATE
  │                                          │
  │◄─────────────────────────────────────────┘
  │
  ▼
CLASSIFY_DISCREPANCIES
  │
  ├──► INFO_ONLY ──► GENERATE_REPORT ──► END
  │
  ▼
REQUIRE_USER_CONFIRMATION
  │
  ▼
WAIT_FOR_USER ──► USER_CONFIRMS ──► TRIGGER_AUTOMATION ──► GENERATE_REPORT ──► END
                       │
                       └──► USER_REJECTS ──► MARK_FALSE_POSITIVE ──► GENERATE_REPORT ──► END
```

---

## Database Schema

```python
# /modules/validation_engine/storage/models/validation_session.py

from sqlalchemy import Column, String, Integer, Float, Boolean, TIMESTAMP, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

class ValidationSession(Base):
    """Validation session tracking"""
    __tablename__ = "validation_sessions"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Use case
    use_case = Column(String(100), nullable=False, index=True)
    use_case_version = Column(String(20), default="1.0")

    # Session info
    session_type = Column(String(50), default="validation")  # "validation", "revalidation"
    status = Column(String(50), nullable=False, index=True)  # "created", "normalizing", "validating", "analyzing", "awaiting_user", "completed", "failed"

    # Documents
    primary_document_id = Column(UUID(as_uuid=True), ForeignKey("universal_documents.id"))
    supporting_document_ids = Column(JSONB, default=[])  # List of document IDs
    document_types = Column(JSONB, default={})  # {doc_id: doc_type}

    # Versioning
    version = Column(Integer, default=1)
    parent_session_id = Column(UUID(as_uuid=True), ForeignKey("validation_sessions.id"), nullable=True)
    is_revalidation = Column(Boolean, default=False)

    # Configuration
    config = Column(JSONB, nullable=False)
    tolerance_overrides = Column(JSONB, default={})

    # User input
    user_provided_data = Column(JSONB, default={})
    user_confirmations = Column(JSONB, default={})

    # Results summary
    total_validations = Column(Integer, default=0)
    passed_validations = Column(Integer, default=0)
    failed_validations = Column(Integer, default=0)

    total_discrepancies = Column(Integer, default=0)
    critical_discrepancies = Column(Integer, default=0)
    major_discrepancies = Column(Integer, default=0)
    minor_discrepancies = Column(Integer, default=0)
    info_discrepancies = Column(Integer, default=0)

    auto_fixed_count = Column(Integer, default=0)

    # Final outcome
    final_status = Column(String(50))  # "passed", "failed", "requires_attention", "false_positive"
    confidence_score = Column(Float)  # 0.0 - 1.0

    # Automation
    correction_email_sent = Column(Boolean, default=False)
    correction_email_id = Column(UUID(as_uuid=True), nullable=True)

    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(TIMESTAMP, nullable=True)

    # Metrics
    processing_time_seconds = Column(Float)

    # Audit
    created_by = Column(String(100))

    # Relationships
    validation_results = relationship("ValidationResult", back_populates="session")
    discrepancies = relationship("Discrepancy", back_populates="session")
    versions = relationship("ValidationVersion", back_populates="session")

    # Indexes
    __table_args__ = (
        Index("idx_validation_session_status", "status"),
        Index("idx_validation_session_use_case", "use_case"),
        Index("idx_validation_session_created_at", "created_at"),
    )


class ValidationResult(Base):
    """Individual validation result"""
    __tablename__ = "validation_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("validation_sessions.id"), nullable=False)

    # Validator info
    validator_name = Column(String(100), nullable=False)
    validator_type = Column(String(50), nullable=False)  # "rule_based", "ai_based", "statistical"

    # Validation details
    field_name = Column(String(255))
    source_document = Column(String(100))
    target_document = Column(String(100))

    source_value = Column(JSONB)
    target_value = Column(JSONB)
    expected_value = Column(JSONB, nullable=True)

    # Result
    passed = Column(Boolean, nullable=False)
    confidence = Column(Float)  # 0.0 - 1.0
    severity = Column(String(50))  # "critical", "major", "minor", "info"

    # Details
    message = Column(String(1000))
    auto_fixed = Column(Boolean, default=False)
    metadata = Column(JSONB, default={})

    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationships
    session = relationship("ValidationSession", back_populates="validation_results")


class Discrepancy(Base):
    """Detected discrepancies"""
    __tablename__ = "discrepancies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("validation_sessions.id"), nullable=False)

    # Discrepancy details
    field_name = Column(String(255), nullable=False)
    discrepancy_type = Column(String(100))  # "value_mismatch", "missing_field", "calculation_error"

    source_document = Column(String(100))
    target_document = Column(String(100))

    source_value = Column(JSONB)
    target_value = Column(JSONB)
    difference = Column(JSONB)  # Calculated difference

    # Classification
    severity = Column(String(50), nullable=False)  # "critical", "major", "minor", "info"
    category = Column(String(100))  # "hs_code", "weight", "duty", "currency"

    # Root cause
    likely_cause = Column(String(255))  # "OCR error", "calculation error", "format difference"
    confidence = Column(Float)  # 0.0 - 1.0

    # Resolution
    auto_fixable = Column(Boolean, default=False)
    auto_fixed = Column(Boolean, default=False)
    suggested_fix = Column(JSONB, nullable=True)

    user_confirmed = Column(Boolean, nullable=True)
    user_comment = Column(String(1000), nullable=True)

    resolution_status = Column(String(50))  # "open", "fixed", "false_positive", "accepted"

    # Timestamps
    detected_at = Column(TIMESTAMP, default=datetime.utcnow)
    resolved_at = Column(TIMESTAMP, nullable=True)

    # Relationships
    session = relationship("ValidationSession", back_populates="discrepancies")


class ValidationVersion(Base):
    """Version history and comparison"""
    __tablename__ = "validation_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("validation_sessions.id"), nullable=False)

    version_number = Column(Integer, nullable=False)
    previous_version_id = Column(UUID(as_uuid=True), ForeignKey("validation_versions.id"), nullable=True)

    # Changes
    changes_detected = Column(JSONB, default=[])
    fixed_discrepancies = Column(JSONB, default=[])
    remaining_discrepancies = Column(JSONB, default=[])
    new_discrepancies = Column(JSONB, default=[])

    # Comparison result
    comparison_status = Column(String(50))  # "improved", "degraded", "unchanged"
    validation_passed = Column(Boolean)

    # Timestamps
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationships
    session = relationship("ValidationSession", back_populates="versions")
```

---

## API Endpoints

```python
# /src/api/v2/endpoints/validation.py

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from typing import List
from uuid import UUID

router = APIRouter(prefix="/validation", tags=["validation"])

@router.post("/sessions")
async def create_validation_session(
    use_case: str,
    primary_document: UploadFile = File(...),
    supporting_documents: List[UploadFile] = File(...),
    tolerance_overrides: dict = None
):
    """
    Create a new validation session

    1. Upload documents
    2. Extract data using extraction module
    3. Create validation session
    4. Start workflow
    """
    pass


@router.get("/sessions/{session_id}")
async def get_session_status(session_id: UUID):
    """Get validation session status and progress"""
    pass


@router.post("/sessions/{session_id}/validate")
async def run_validation(session_id: UUID):
    """Execute validation workflow"""
    pass


@router.post("/sessions/{session_id}/user-input")
async def submit_user_input(
    session_id: UUID,
    field_name: str,
    value: any
):
    """Submit user-provided data for missing fields"""
    pass


@router.post("/sessions/{session_id}/confirm-discrepancies")
async def confirm_discrepancies(
    session_id: UUID,
    discrepancy_ids: List[UUID],
    confirmed: bool,
    comment: str = None
):
    """User confirms or rejects discrepancies"""
    pass


@router.post("/sessions/{session_id}/revalidate")
async def revalidate(
    session_id: UUID,
    new_documents: List[UploadFile] = File(...)
):
    """
    Upload new version and revalidate

    1. Extract new documents
    2. Create new session version
    3. Compare with previous version
    4. Run validation
    """
    pass


@router.get("/sessions/{session_id}/report")
async def get_validation_report(
    session_id: UUID,
    format: str = "json"  # json, pdf, csv
):
    """Generate validation report"""
    pass


@router.get("/sessions/{session_id}/discrepancies")
async def get_discrepancies(session_id: UUID):
    """Get all discrepancies for session"""
    pass


@router.get("/sessions/{session_id}/versions")
async def get_version_history(session_id: UUID):
    """Get version history and comparisons"""
    pass


@router.get("/use-cases")
async def list_use_cases():
    """List all configured validation use cases"""
    pass


@router.get("/validators")
async def list_validators():
    """List all registered validators"""
    pass
```

---

## Integration Points

### 1. With Extraction Module

```python
# /modules/validation_engine/integration/extraction_adapter.py

from modules.extraction.parser import ProviderFactory
from modules.extraction.storage import UniversalDocumentService

class ExtractionAdapter:
    """Adapter to interface with extraction module"""

    async def extract_documents(
        self,
        files: List[UploadFile],
        document_types: Dict[str, str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Extract data from documents using extraction module

        Returns: {doc_id: extracted_data}
        """
        provider = ProviderFactory.get_provider("reducto")

        extracted_docs = {}
        for file in files:
            doc_type = document_types.get(file.filename)
            result = await provider.parse_document(file, doc_type)
            extracted_docs[file.filename] = result

        return extracted_docs
```

### 2. With Automation Module

```python
# /modules/validation_engine/integration/automation_adapter.py

from modules.automation.services import EmailService

class AutomationAdapter:
    """Adapter to interface with automation module"""

    async def send_correction_email(
        self,
        session_id: UUID,
        discrepancies: List[Dict[str, Any]]
    ):
        """Trigger correction request email"""
        email_service = EmailService()
        await email_service.send_correction_request(session_id, discrepancies)
```

---

## Key Features Summary

### 1. Universal & Configurable
- ✅ Works for any validation use case
- ✅ New use cases added via YAML config
- ✅ No code changes required

### 2. Hybrid Validation
- ✅ Rule-based validators (fast, deterministic)
- ✅ AI-based validators (intelligent, semantic)
- ✅ Statistical validators (tolerance, outliers)
- ✅ Combine multiple strategies

### 3. Multi-Step Orchestration
- ✅ LangGraph state machine
- ✅ Sequential and parallel execution
- ✅ Human-in-the-loop
- ✅ Error recovery

### 4. Version Control
- ✅ Track all validation runs
- ✅ Compare versions (V1 vs V2)
- ✅ Delta analysis
- ✅ Full audit trail

### 5. Intelligent Discrepancy Handling
- ✅ Automatic classification (severity, category)
- ✅ Root cause analysis
- ✅ Auto-fix common issues
- ✅ User confirmation workflow

### 6. Production-Grade
- ✅ Async operations
- ✅ Redis caching
- ✅ Comprehensive error handling
- ✅ Observability and monitoring
- ✅ Scalable architecture

### 7. Extensible
- ✅ Pluggable validators (registry pattern)
- ✅ Easy to add new validator types
- ✅ Provider-agnostic
- ✅ Modular design

---

## Implementation Priority

### Phase 1: Core Infrastructure (Week 1)
1. Base interfaces and contracts
2. Validator registry
3. Config loader
4. Session manager
5. Storage models

### Phase 2: Validators (Week 2)
6. Rule-based validators
7. Statistical validators
8. Normalization layer
9. Cross-document validators

### Phase 3: Orchestration (Week 2-3)
10. LangGraph workflow engine
11. Discrepancy handler
12. Version control system

### Phase 4: AI & Advanced Features (Week 3)
13. AI-based validators
14. Auto-fix engine
15. Root cause analyzer

### Phase 5: API & Integration (Week 3-4)
16. REST API endpoints
17. Extraction module integration
18. Automation module integration

### Phase 6: Reporting & Polish (Week 4)
19. Report generator
20. Analytics and metrics
21. Testing and optimization

---

## Success Criteria

### Functional
- ✅ Handles any validation use case via config
- ✅ Supports N-way document matching
- ✅ Intelligent discrepancy detection
- ✅ Version control and comparison
- ✅ Human-in-the-loop workflows

### Performance
- ✅ < 30 seconds for full validation workflow
- ✅ < 2% false positive rate
- ✅ 99.5%+ accuracy
- ✅ Handles 20+ concurrent sessions

### Quality
- ✅ 100% config-driven
- ✅ Zero hardcoded logic
- ✅ Production-grade code
- ✅ Comprehensive test coverage
- ✅ Full documentation

---

## Conclusion

This **Universal Validation Engine** provides a production-grade, config-driven, extensible foundation for any document validation use case. The architecture is:

- **Universal**: Works for any validation scenario
- **Configurable**: All logic defined in YAML
- **Hybrid**: Combines rule-based, AI-based, and statistical approaches
- **Multi-step**: LangGraph orchestration for complex workflows
- **Version controlled**: Full audit trail and comparison
- **Extensible**: Easy to add new validators and features
- **Production-ready**: Scalable, secure, and maintainable

The BOE validation use case becomes just one configuration file, demonstrating the power and flexibility of this universal design.
